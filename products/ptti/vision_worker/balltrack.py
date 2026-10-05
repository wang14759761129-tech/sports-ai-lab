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
    parser.add_argument('--top-k', type=int, default=0)
    parser.add_argument('--minimum-response', type=float, default=.01)
    parser.add_argument('--nms-radius', type=int, default=5)
    parser.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    parser.add_argument('--diagnostic-frames',default='',help='Comma-separated frames whose real heatmaps are retained')
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
    extraction_started=time.perf_counter()
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
    frame_extraction_seconds=time.perf_counter()-extraction_started
    diagnostic_frames={int(x) for x in args.diagnostic_frames.split(',') if x.strip()}
    diagnostics=[]
    peak_rows=[]
    candidate_seconds=0.0
    # Deterministic bounded background sample; no GT is used in preprocessing.
    background_started=time.perf_counter()
    indexes = np.linspace(0, len(paths) - 1, min(100, len(paths)), dtype=int)
    def read_frame(path):
        frame = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None: raise RuntimeError('Cannot decode extracted frame')
        return frame
    median = np.median(np.array([read_frame(paths[i]) for i in indexes]), axis=0).astype(np.uint8)
    median_path = output / 'median.npz'; np.savez(median_path, median=median)
    background_preprocessing_seconds=time.perf_counter()-background_started
    print('STAGE Tracking ball', flush=True)

    class AlignedInferencer(BallInferencer):
        diagnostic_index=0

        def _predict_location(self,heatmap):
            nonlocal candidate_seconds
            index=self.diagnostic_index;self.diagnostic_index+=1
            selected=super()._predict_location(heatmap)
            if args.top_k:
                from candidates import extract_peaks
                candidate_started=time.perf_counter()
                peaks=extract_peaks(heatmap,args.top_k,args.minimum_response,args.nms_radius)
                peak_rows.append({'frame':index,'heatmap_shape':list(heatmap.shape),'candidates':peaks})
                candidate_seconds+=time.perf_counter()-candidate_started
            if diagnostic_frames:
                mask=(heatmap>self.thre).astype('uint8')*255
                contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                candidates=[]
                for contour in contours:
                    x,y,w,h=cv2.boundingRect(contour)
                    region=heatmap[y:y+h,x:x+w]
                    candidates.append({'model_center':[x+w/2,y+h/2],'bbox':[x,y,w,h],
                                       'bbox_area':w*h,'mean_heatmap':float(region.mean()),'peak_heatmap':float(region.max()),
                                       'selected_by_upstream':(x,y,w,h)==tuple(selected[:4])})
                y,x=np.unravel_index(np.argmax(heatmap),heatmap.shape)
                diagnostics.append({'frame':index,'heatmap_shape':list(heatmap.shape),'threshold':self.thre,
                                    'global_peak':{'model_xy':[int(x),int(y)],'value':float(heatmap[y,x])},
                                    'candidates':sorted(candidates,key=lambda x:x['bbox_area'],reverse=True),
                                    'semantics':'Real model sigmoid heatmap; bbox mean is not calibrated probability. Upstream selects largest thresholded bounding box, not highest peak.'})
                if index in diagnostic_frames:
                    folder=output/'heatmaps';folder.mkdir(exist_ok=True)
                    np.savez_compressed(folder/f'frame_{index:06d}.npz',heatmap=heatmap.astype(np.float32))
            return selected

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
    model_load_started=time.perf_counter()
    tracker = AlignedInferencer(str(Path(args.runtime) / 'source/BallTrack/configs/tracknetv3_base.py'),
                               args.checkpoint, device=args.device, batchsize=2)
    model_load_seconds=time.perf_counter()-model_load_started
    if args.device=='cuda': torch.cuda.synchronize()
    inference_started=time.perf_counter()
    prediction = tracker(paths, str(median_path))
    if args.device=='cuda': torch.cuda.synchronize()
    model_inference_seconds=time.perf_counter()-inference_started
    serialization_started=time.perf_counter()
    (output / 'raw_prediction.json').write_text(json.dumps(prediction), encoding='utf-8')
    if diagnostic_frames:
        (output/'candidate_diagnostics.json').write_text(json.dumps(diagnostics,indent=2),encoding='utf-8')
    if args.top_k:
        (output/'peak_candidates.json').write_text(json.dumps(peak_rows),encoding='utf-8')
    prediction_serialization_seconds=time.perf_counter()-serialization_started
    info = dict(processing_seconds=time.perf_counter() - started, decoded_frames=len(paths),
                torch=torch.__version__, cuda=torch.version.cuda, python=sys.version,
                gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                peak_vram_bytes=torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None,
                alignment='inclusive history ending at output frame; initial repeated-frame padding',
                background='up to 100 evenly sampled frames from this rally, not full-match median')
    info['profile']={'candidate_extraction_seconds':candidate_seconds,
                     'frame_extraction_seconds':frame_extraction_seconds,
                     'background_preprocessing_seconds':background_preprocessing_seconds,
                     'model_load_seconds':model_load_seconds,
                     'model_inference_seconds':model_inference_seconds,
                     'prediction_serialization_seconds':prediction_serialization_seconds}
    import psutil
    memory = psutil.Process().memory_info()
    info['peak_cpu_ram_bytes'] = getattr(memory, 'peak_wset', None)
    info['current_cpu_ram_bytes'] = memory.rss
    (output / 'runtime.json').write_text(json.dumps(info, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
