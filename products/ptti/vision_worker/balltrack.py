"""Subprocess boundary: official model + explicit frame-alignment correction."""
import argparse
import json
import sys
import time
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    for name in ('runtime', 'checkpoint', 'video', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    args = parser.parse_args()
    import cv2
    import numpy as np
    import torch
    sys.path.insert(0, str(Path(args.runtime) / 'source/BallTrack'))
    from inference import BallInferencer
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    print('STAGE Preparing frames', flush=True)
    frame_dir = output / 'frames'; frame_dir.mkdir(exist_ok=True)
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened(): raise RuntimeError('Cannot read video')
    paths = []
    while True:
        success, frame = cap.read()
        if not success: break
        path = frame_dir / f'{len(paths):06d}.jpg'
        success, encoded = cv2.imencode('.jpg', frame)
        if not success: raise RuntimeError('Frame write failed')
        encoded.tofile(path)
        paths.append(str(path))
        if len(paths) > 1800: raise RuntimeError('Experimental worker frame limit exceeded')
    cap.release()
    if not paths: raise RuntimeError('No frames decoded')
    # Deterministic bounded background sample; no GT is used in preprocessing.
    indexes = np.linspace(0, len(paths) - 1, min(100, len(paths)), dtype=int)
    def read_frame(path):
        frame = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None: raise RuntimeError('Cannot decode extracted frame')
        return frame
    median = np.median(np.array([read_frame(paths[i]) for i in indexes]), axis=0).astype(np.uint8)
    median_path = output / 'median.npz'; np.savez(median_path, median=median)
    print('STAGE Tracking ball', flush=True)

    class AlignedInferencer(BallInferencer):
        def _load_frames(self, frame_paths):
            # OpenCV imread/imwrite do not reliably handle Windows Chinese paths.
            raw = [read_frame(path) for path in frame_paths]
            resized = np.array([cv2.resize(f, (self.width, self.height)) for f in raw], dtype=np.float32) / 255.0
            return raw, resized

        def _preprocess_batch(self, frames, start, end, median):
            batch = []
            for i in range(start, end):
                # Training labels are the last included frame. Upstream range(i-L,i)
                # emits frame i-1 but labels i; include i to remove that off-by-one.
                ids = [max(0, j) for j in range(i - self.seq_len + 1, i + 1)]
                sequence = np.moveaxis(frames[ids], -1, 1)
                batch.append(np.concatenate([median, sequence], 0).reshape(-1, self.height, self.width))
            return torch.from_numpy(np.array(batch)).float().to(self.device)

    if args.device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable; explicitly select CPU mode')
    if torch.cuda.is_available(): torch.cuda.reset_peak_memory_stats()
    tracker = AlignedInferencer(str(Path(args.runtime) / 'source/BallTrack/configs/tracknetv3_base.py'),
                               args.checkpoint, device=args.device, batchsize=2)
    prediction = tracker(paths, str(median_path))
    (output / 'raw_prediction.json').write_text(json.dumps(prediction), encoding='utf-8')
    info = dict(processing_seconds=time.perf_counter() - started, decoded_frames=len(paths),
                torch=torch.__version__, cuda=torch.version.cuda, python=sys.version,
                gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                peak_vram_bytes=torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None,
                alignment='inclusive history ending at output frame; initial repeated-frame padding',
                background='up to 100 evenly sampled frames from this rally, not full-match median')
    import psutil
    memory = psutil.Process().memory_info()
    info['peak_cpu_ram_bytes'] = getattr(memory, 'peak_wset', None)
    info['current_cpu_ram_bytes'] = memory.rss
    (output / 'runtime.json').write_text(json.dumps(info, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
