"""Build one deterministic, bounded-sample background image for a full match."""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--video', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    import cv2
    import numpy as np
    runtime = Path(args.runtime)
    source = runtime / 'source' / 'BallTrack'
    if not source.is_dir():
        raise RuntimeError(f'Pinned RacketVision source is missing: {source}')
    sys.path.insert(0, str(source))
    from mmengine.config import Config

    config = Config.fromfile(str(runtime / 'source/BallTrack/configs/tracknetv3_base.py'), lazy_import=False)
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError('Cannot read the authorized match video')
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if frame_count < 1:
        cap.release()
        raise RuntimeError('Video frame count is unavailable')
    indexes = np.linspace(0, frame_count - 1, min(100, frame_count), dtype=int)
    samples = []
    for index in indexes:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = cap.read()
        if ok and frame is not None:
            samples.append(cv2.resize(frame, (config.width, config.height)))
    cap.release()
    if not samples:
        raise RuntimeError('Could not sample the video background')
    median = np.median(np.stack(samples, axis=0), axis=0).astype(np.uint8)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, median=median)
    metadata = {'method': 'up to 100 deterministic evenly spaced frames over the complete video',
                'sampled_global_frames': [int(index) for index in indexes],
                'sample_count': len(samples), 'model_width': config.width,
                'model_height': config.height, 'source_frame_count': frame_count,
                'background_sha256': hashlib.sha256(median.tobytes()).hexdigest(),
                'scope': 'whole-match shared background for every chunk'}
    output.with_suffix('.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
