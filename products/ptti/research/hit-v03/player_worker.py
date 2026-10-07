"""Bounded RT-DETR worker; input is image-frame requests, never annotations."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

PRODUCT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PRODUCT))


def validate_request(request):
    if request.get('game') not in {'game_1', 'game_2', 'game_3'}:
        raise ValueError('NON_DEV_GAME_REJECTED')
    frames = request.get('frames', [])
    if not 1 <= len(frames) <= 256 or any(type(f) is not int or f < 0 for f in frames):
        raise ValueError('UNSAFE_WORKER_FRAME_REQUEST')
    if frames != sorted(set(frames)) or request.get('fps') != 120:
        raise ValueError('NONCANONICAL_FRAME_REQUEST')
    if any(key in request for key in {'annotations', 'stroke_gt', 'bounce_gt', 'net_gt', 'rally_ending_gt'}):
        raise ValueError('GT_CONTENT_FORBIDDEN_AT_INFERENCE')
    video = Path(request['video_path'])
    expected_root = Path(os.environ['LOCALAPPDATA'])/'PTTI-Dev/research-datasets/ExtendedOpenTTGames/videos/train'
    if video.resolve().parent != expected_root.resolve() or video.name != request['game']+'.mp4':
        raise ValueError('VIDEO_OUTSIDE_ALLOWED_DEV_INPUTS')
    return video, expected_root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('request')
    parser.add_argument('output')
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text(encoding='utf-8'))
    video, expected_root = validate_request(request)
    download = json.loads((expected_root.parents[1]/'DEV_VIDEO_DOWNLOAD_MANIFEST.json').read_text(encoding='utf-8'))
    source = next(e for e in download['games'] if e['game'] == request['game'])
    if source['sha256'] != request['video_sha256'] or video.stat().st_size != source['expected_bytes']:
        raise ValueError('VERIFIED_SOURCE_IDENTITY_CHANGED')
    initial_stat = video.stat()
    from resources import available_ram, process_rss
    if available_ram() < 3*1024**3:
        raise RuntimeError('RESOURCE_GUARD_INSUFFICIENT_AVAILABLE_RAM')
    # Reuse the previously verified RT-DETR launch boundary: torch from the
    # worker runtime, transformers from its isolated scene dependency overlay.
    sys.path.insert(0, str(Path(os.environ['LOCALAPPDATA'])/'PTTI-Dev/vision-v2/venv/Lib/site-packages'))
    import cv2
    import torch
    from PIL import Image
    from transformers import RTDetrForObjectDetection, RTDetrImageProcessor
    from backend.person_detector import RTDetrPredictionAdapter, TablePersonRoleResolver, verify_r18

    torch.set_num_threads(2)
    model_folder = Path(os.environ['LOCALAPPDATA'])/'PTTI-Dev/vision-v2/models/rtdetr-r18vd'
    provenance = verify_r18(model_folder)
    start = time.perf_counter()
    processor = RTDetrImageProcessor.from_pretrained(model_folder, local_files_only=True)
    model = RTDetrForObjectDetection.from_pretrained(model_folder, local_files_only=True).eval().to('cuda')
    load_seconds = time.perf_counter()-start
    torch.cuda.reset_peak_memory_stats()
    cv2.setNumThreads(1)
    capture = cv2.VideoCapture(request['video_path'], cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 2])
    if not capture.isOpened():
        raise RuntimeError('BOUNDED_VIDEO_DECODER_UNAVAILABLE')
    wanted = sorted(set(request['frames']))
    capture.set(cv2.CAP_PROP_POS_FRAMES, wanted[0])
    actual = int(round(capture.get(cv2.CAP_PROP_POS_FRAMES)))
    if actual != wanted[0]:
        raise RuntimeError('SOURCE_SEEK_FRAME_MISMATCH')
    rows = []
    timings = []
    peak_rss = 0
    minimum_available = available_ram()
    try:
        target_index = 0
        while target_index < len(wanted):
            if not capture.grab():
                raise RuntimeError('SOURCE_DECODE_FAILED')
            if actual == wanted[target_index]:
                ok, frame = capture.retrieve()
                if not ok:
                    raise RuntimeError('SOURCE_RETRIEVE_FAILED')
                image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                before = time.perf_counter()
                with torch.inference_mode():
                    inputs = processor(images=image, return_tensors='pt').to('cuda')
                    output = model(**inputs)
                    result = processor.post_process_object_detection(output,
                        target_sizes=torch.tensor([[image.height, image.width]], device='cuda'), threshold=.25)[0]
                torch.cuda.synchronize()
                timings.append(time.perf_counter()-before)
                predictions = [{'label': model.config.id2label[int(label)], 'score': float(score), 'bbox': box.tolist()}
                               for score, label, box in zip(result['scores'], result['labels'], result['boxes'])]
                people = RTDetrPredictionAdapter().adapt(predictions, image_size=image.size,
                    frame=actual, timestamp_ms=actual*1000/request['fps'])
                resolved = TablePersonRoleResolver().resolve(request.get('table_bbox'), people, image_size=image.size)
                rows.append({'source_frame': actual, 'timestamp_ms': actual*1000/request['fps'],
                             'decoded_pts_ms': capture.get(cv2.CAP_PROP_POS_MSEC),
                             'video_sha256': request['video_sha256'], 'people': resolved})
                if abs(rows[-1]['decoded_pts_ms']-rows[-1]['timestamp_ms']) > .5:
                    raise RuntimeError('DECODED_PTS_TIMELINE_MISMATCH')
                target_index += 1
                memory = available_ram()
                minimum_available = min(minimum_available, memory)
                peak_rss = max(peak_rss, process_rss())
                if memory < 1.5*1024**3 or peak_rss > 3*1024**3:
                    print(json.dumps({'status': 'RESOURCE_GUARD_STOP', 'completed_frames_in_worker': len(rows),
                                      'available_ram_bytes': memory, 'peak_rss_bytes': peak_rss}), flush=True)
                    raise RuntimeError('RESOURCE_GUARD_WORKER_MEMORY_LIMIT')
                del inputs, output, result, image, frame
                if target_index < len(wanted) and wanted[target_index]-actual > 240:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, wanted[target_index])
                    actual = int(round(capture.get(cv2.CAP_PROP_POS_FRAMES)))
                    if actual != wanted[target_index]:
                        raise RuntimeError('SOURCE_RESEEK_FRAME_MISMATCH')
                    continue
            actual += 1
    finally:
        capture.release()
    final_stat = video.stat()
    if final_stat.st_size != initial_stat.st_size or final_stat.st_mtime_ns != initial_stat.st_mtime_ns:
        raise ValueError('SOURCE_CHANGED_DURING_WORKER')
    report = {'status': 'COMPLETE', 'request_sha256': __import__('hashlib').sha256(Path(args.request).read_bytes()).hexdigest(),
              'provenance': provenance, 'frames': rows, 'runtime': {'load_seconds': load_seconds,
              'inference_seconds': sum(timings), 'total_seconds': time.perf_counter()-start,
              'frames': len(rows), 'peak_rss_bytes': peak_rss, 'minimum_available_ram_bytes': minimum_available,
              'peak_allocated_vram_bytes': torch.cuda.max_memory_allocated()}}
    target = Path(args.output)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(report), encoding='utf-8')
    temporary.replace(target)
    print(json.dumps(report['runtime']), flush=True)


if __name__ == '__main__':
    main()
