"""Evaluate frozen 20 development frames, never read official test data."""
from __future__ import annotations
import json
import os
import platform
import sys
import time
from pathlib import Path

DEV = Path(os.environ['LOCALAPPDATA']) / 'PTTI-Dev' / 'vision-v2'
sys.path.insert(0, str(DEV / 'venv/Lib/site-packages'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import torch
import transformers
from PIL import Image
from transformers import RTDetrForObjectDetection, RTDetrImageProcessor
from backend.person_detector import FROZEN_MANIFEST_SHA, RTDetrPredictionAdapter, file_sha, verify_r18


def main():
    root = DEV / 'scene-bootstrap'
    path = root/'person_detector_r18_raw.json'
    if path.exists():
        raise RuntimeError('RAW_RESULT_ALREADY_EXISTS_DO_NOT_OVERWRITE')
    manifest_path = root / 'scene_bootstrap_eval_manifest.json'
    if file_sha(manifest_path) != FROZEN_MANIFEST_SHA:
        raise RuntimeError('FROZEN_MANIFEST_CHANGED')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    folder = DEV / 'models/rtdetr-r18vd'
    provenance = verify_r18(folder)
    start = time.perf_counter()
    processor = RTDetrImageProcessor.from_pretrained(folder, local_files_only=True)
    model = RTDetrForObjectDetection.from_pretrained(folder, local_files_only=True).eval().to('cuda')
    torch.cuda.synchronize()
    load_seconds = time.perf_counter()-start
    frames, timings = [], []
    torch.cuda.reset_peak_memory_stats()
    for game in manifest['games']:
        for sample in game['sampled_frames']:
            path = root / sample['image']
            if file_sha(path).upper() != sample['frame_sha256'].upper():
                raise RuntimeError('FROZEN_FRAME_CHANGED')
            image = Image.open(path).convert('RGB')
            before = time.perf_counter()
            inputs = processor(images=image, return_tensors='pt').to('cuda')
            with torch.inference_mode():
                output = model(**inputs)
            result = processor.post_process_object_detection(output,
                target_sizes=torch.tensor([[image.height, image.width]], device='cuda'), threshold=.10)[0]
            torch.cuda.synchronize()
            elapsed = (time.perf_counter()-before)*1000
            timings.append(elapsed)
            raw = [{'label': model.config.id2label[int(label)], 'score': float(score), 'bbox': box.tolist()}
                   for score, label, box in zip(result['scores'], result['labels'], result['boxes'])]
            source_frame = round(sample['timestamp_seconds'] * game['media']['fps'])
            people = RTDetrPredictionAdapter().adapt(raw, image_size=image.size, frame=source_frame,
                timestamp_ms=round(sample['timestamp_seconds']*1000), threshold=.10)
            for i, p in enumerate(people):
                p['candidate_id'] = f"rtdetr-{game['game']}-s{sample['slot']:02d}-d{i}"
            frames.append({**sample, 'frame': source_frame, 'timestamp_ms':round(sample['timestamp_seconds']*1000),
                           'raw_person_detections':people, 'inference_ms':elapsed})
            print(f"INFERRED {game['game']} {sample['slot']} persons={len(people)} ms={elapsed:.1f}", flush=True)
    try:
        import psutil
        ram = psutil.Process().memory_info().rss
    except ImportError:
        ram = None
    report = {'status':'REAL_DEV_RAW_INFERENCE_COMPLETE', 'model':provenance['model'], 'provenance':provenance,
              'manifest_sha256':FROZEN_MANIFEST_SHA, 'dataset':'Extended OpenTTGames',
              'license':'CC BY-NC-SA 4.0', 'commercial_use':False, 'split':'official training, development only',
              'runtime':{'python':platform.python_version(), 'torch':torch.__version__,
                         'transformers':transformers.__version__, 'cuda':torch.version.cuda,
                         'gpu':torch.cuda.get_device_name(0), 'model_load_seconds':load_seconds,
                         'mean_inference_ms':sum(timings)/len(timings),
                         'steady_mean_inference_ms':sum(timings[1:])/len(timings[1:]),
                         'fps':1000*len(timings)/sum(timings),
                         'peak_allocated_vram_bytes':torch.cuda.max_memory_allocated(),
                         'peak_reserved_vram_bytes':torch.cuda.max_memory_reserved(), 'end_rss_bytes':ram},
              'frames':frames}
    path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report['runtime']),flush=True)


if __name__ == '__main__':
    main()
