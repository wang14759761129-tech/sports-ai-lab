"""Bounded-memory adapter around the pinned RacketVision BallTrack model.

The upstream model and checkpoint are unchanged. Frames are decoded and inferred
as a stream so processing memory does not grow with clip duration.
"""
import argparse
import json
import sys
import time
from collections import deque
from pathlib import Path


def _write_json_atomic(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    for name in ('runtime', 'checkpoint', 'video', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--top-k', type=int, default=0)
    parser.add_argument('--minimum-response', type=float, default=.01)
    parser.add_argument('--nms-radius', type=int, default=5)
    parser.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    parser.add_argument('--diagnostic-frames', default='', help='Comma-separated frames whose real heatmaps are retained')
    parser.add_argument('--batchsize', type=int, default=2)
    parser.add_argument('--median-input', default='', help='Shared full-match median.npz, created once from a bounded sample')
    args = parser.parse_args()
    if args.batchsize < 1 or args.batchsize > 8:
        raise ValueError('batchsize must be in 1..8 to keep accelerator memory bounded')

    import cv2
    import numpy as np
    import torch
    sys.path.insert(0, str(Path(args.runtime) / 'source/BallTrack'))
    from inference import BallInferencer

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    print('STAGE Loading frozen BallTrack model', flush=True)
    if args.device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable; explicitly select CPU mode')
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    model_load_started = time.perf_counter()

    class AlignedInferencer(BallInferencer):
        def __init__(self, *values, **options):
            super().__init__(*values, **options)
            self.diagnostic_index = 0
            self.diagnostics = []
            self.peak_rows = []
            self.candidate_seconds = 0.0
            self.diagnostic_frames = {int(x) for x in args.diagnostic_frames.split(',') if x.strip()}

        def _predict_location(self, heatmap):
            import cv2
            import numpy as np
            index = self.diagnostic_index
            self.diagnostic_index += 1
            selected = super()._predict_location(heatmap)
            if args.top_k:
                from candidates import extract_peaks
                candidate_started = time.perf_counter()
                peaks = extract_peaks(heatmap, args.top_k, args.minimum_response, args.nms_radius)
                self.peak_rows.append({'frame': index, 'heatmap_shape': list(heatmap.shape), 'candidates': peaks})
                self.candidate_seconds += time.perf_counter() - candidate_started
            if self.diagnostic_frames:
                mask = (heatmap > self.thre).astype('uint8') * 255
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                candidates = []
                for contour in contours:
                    x, y, w, h = cv2.boundingRect(contour)
                    region = heatmap[y:y+h, x:x+w]
                    candidates.append({'model_center': [x+w/2, y+h/2], 'bbox': [x, y, w, h],
                                       'bbox_area': w*h, 'mean_heatmap': float(region.mean()),
                                       'peak_heatmap': float(region.max()),
                                       'selected_by_upstream': (x, y, w, h) == tuple(selected[:4])})
                y, x = np.unravel_index(np.argmax(heatmap), heatmap.shape)
                self.diagnostics.append({'frame': index, 'heatmap_shape': list(heatmap.shape),
                    'threshold': self.thre, 'global_peak': {'model_xy': [int(x), int(y)], 'value': float(heatmap[y, x])},
                    'candidates': sorted(candidates, key=lambda item: item['bbox_area'], reverse=True),
                    'semantics': 'Real model sigmoid heatmap; bbox mean is not calibrated probability. Upstream selects largest thresholded bounding box.'})
                if index in self.diagnostic_frames:
                    folder = output / 'heatmaps'
                    folder.mkdir(exist_ok=True)
                    np.savez_compressed(folder / f'frame_{index:06d}.npz', heatmap=heatmap.astype(np.float32))
            return selected

    tracker = AlignedInferencer(str(Path(args.runtime) / 'source/BallTrack/configs/tracknetv3_base.py'),
                                args.checkpoint, device=args.device, batchsize=args.batchsize)
    model_load_seconds = time.perf_counter() - model_load_started
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError('Cannot read video')
    frame_count_hint = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    success, first = cap.read()
    if not success or first is None:
        cap.release()
        raise RuntimeError('No frames decoded')
    source_height, source_width = first.shape[:2]
    if fps <= 0:
        cap.release()
        raise RuntimeError('Video FPS is unavailable')

    print('STAGE Preparing bounded background', flush=True)
    background_started = time.perf_counter()
    if args.median_input:
        median = np.load(args.median_input)['median']
        if median.shape[:2] != (tracker.height, tracker.width):
            cap.release()
            raise RuntimeError('Shared whole-match background dimensions do not match frozen model input')
        background_method = 'shared whole-match median from up to 100 deterministic evenly sampled frames'
    else:
        sample_count = min(100, max(1, frame_count_hint))
        sample_indexes = np.linspace(0, max(0, frame_count_hint - 1), sample_count, dtype=int)
        samples = []
        for index in sample_indexes:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            read_ok, frame = cap.read()
            if read_ok and frame is not None:
                samples.append(cv2.resize(frame, (tracker.width, tracker.height)))
        if not samples:
            cap.release()
            raise RuntimeError('Could not sample background frames')
        median = np.median(np.stack(samples, axis=0), axis=0).astype(np.uint8)
        del samples
        background_method = 'up to 100 evenly sampled frames from this clip'
    median_normalized = np.moveaxis(np.expand_dims(median.astype(np.float32) / 255.0, 0), -1, 1)
    np.savez_compressed(output / 'median.npz', median=median)
    background_preprocessing_seconds = time.perf_counter() - background_started

    print('STAGE Tracking ball (streaming decode)', flush=True)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    success, first = cap.read()
    if not success or first is None:
        cap.release()
        raise RuntimeError('Could not restart video decoder at frame zero')
    history = deque(maxlen=tracker.seq_len)
    batch_data = []
    batch_indexes = []
    results = []
    decoded_frames = 0
    video_decode_seconds = 0.0
    preprocess_seconds = 0.0
    model_inference_seconds = 0.0
    coordinate_postprocess_seconds = 0.0

    def infer_batch():
        nonlocal batch_data, batch_indexes, model_inference_seconds, coordinate_postprocess_seconds
        if not batch_data:
            return
        inference_started = time.perf_counter()
        data = torch.from_numpy(np.stack(batch_data, axis=0)).float().to(tracker.device)
        with torch.no_grad():
            if tracker.device.type == 'cuda':
                with torch.amp.autocast('cuda'):
                    predictions, _, _ = tracker.model.forward(frames=data)
            else:
                predictions, _, _ = tracker.model.forward(frames=data)
        predictions = predictions.detach().cpu().numpy()
        model_inference_seconds += time.perf_counter() - inference_started
        for local_index, prediction in zip(batch_indexes, predictions):
            heatmap = prediction[0]
            postprocess_started = time.perf_counter()
            x, y, w, h, confidence = tracker._predict_location(heatmap)
            cx = int((x + w / 2) * (source_width / tracker.width))
            cy = int((y + h / 2) * (source_height / tracker.height))
            visible = not (cx == 0 and cy == 0)
            results.append({'Frame': local_index, 'X': cx, 'Y': cy, 'Visibility': int(visible),
                            'Confidence': round(confidence, 4)})
            coordinate_postprocess_seconds += time.perf_counter() - postprocess_started
        batch_data, batch_indexes = [], []

    frame_loop_started = time.perf_counter()
    frame = first
    while True:
        if frame is None:
            break
        preprocess_started = time.perf_counter()
        resized = cv2.resize(frame, (tracker.width, tracker.height)).astype(np.float32) / 255.0
        history.append(resized)
        if len(history) < tracker.seq_len:
            padded = [history[0]] * (tracker.seq_len - len(history)) + list(history)
        else:
            padded = list(history)
        sequence = np.moveaxis(np.stack(padded, axis=0), -1, 1)
        model_input = np.concatenate([median_normalized, sequence], axis=0).reshape(
            -1, tracker.height, tracker.width)
        batch_data.append(model_input)
        batch_indexes.append(decoded_frames)
        decoded_frames += 1
        preprocess_seconds += time.perf_counter() - preprocess_started
        if len(batch_data) >= args.batchsize:
            infer_batch()
        decode_started = time.perf_counter()
        read_ok, frame = cap.read()
        video_decode_seconds += time.perf_counter() - decode_started
        if not read_ok:
            break
    infer_batch()
    cap.release()
    frame_loop_seconds = time.perf_counter() - frame_loop_started
    if not results:
        raise RuntimeError('No frames decoded')
    if torch.cuda.is_available() and tracker.device.type == 'cuda':
        torch.cuda.synchronize()
    serialization_started = time.perf_counter()
    _write_json_atomic(output / 'raw_prediction.json', results)
    if tracker.diagnostics:
        _write_json_atomic(output / 'candidate_diagnostics.json', tracker.diagnostics)
    if args.top_k:
        _write_json_atomic(output / 'peak_candidates.json', tracker.peak_rows)
    prediction_serialization_seconds = time.perf_counter() - serialization_started
    runtime = dict(processing_seconds=time.perf_counter() - started, decoded_frames=decoded_frames,
                   frame_count_hint=frame_count_hint, torch=torch.__version__, cuda=torch.version.cuda,
                   python=sys.version, gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                   peak_vram_bytes=torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None,
                   peak_vram_reserved_bytes=torch.cuda.max_memory_reserved() if torch.cuda.is_available() else None,
                   alignment='inclusive history ending at output frame; initial repeated-frame padding',
                   background=background_method,
                   memory_mode='streaming; model history and inference batch only, independent of chunk length')
    runtime['profile'] = {'candidate_extraction_seconds': tracker.candidate_seconds,
                          'video_decode_seconds': video_decode_seconds,
                          'decode_preprocess_seconds': preprocess_seconds,
                          'background_preprocessing_seconds': background_preprocessing_seconds,
                          'model_load_seconds': model_load_seconds,
                          'model_inference_seconds': model_inference_seconds,
                          'coordinate_postprocess_seconds': coordinate_postprocess_seconds,
                          'frame_loop_wall_seconds': frame_loop_seconds,
                          'prediction_serialization_seconds': prediction_serialization_seconds}
    import psutil
    memory = psutil.Process().memory_info()
    runtime['peak_cpu_ram_bytes'] = getattr(memory, 'peak_wset', None)
    runtime['current_cpu_ram_bytes'] = memory.rss
    _write_json_atomic(output / 'runtime.json', runtime)


if __name__ == '__main__':
    main()
