"""Prepare candidate-centric DEV requests, with GT used only to select audit frames."""
from __future__ import annotations

import json
import os
from pathlib import Path
import statistics
import sys

PRODUCT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PRODUCT/'scripts'))
from run_full_dev_hit_v02 import resolve_full_dev_inputs  # noqa: E402


def main(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    dev = Path(os.environ['LOCALAPPDATA'])/'PTTI-Dev'
    scene_path = dev/'vision-v2/scene-bootstrap/scene_bootstrap_eval_manifest.json'
    scene = json.loads(scene_path.read_text(encoding='utf-8'))
    jobs = []
    for game in (1, 2, 3):
        source = resolve_full_dev_inputs(game, Path(os.environ['LOCALAPPDATA']))
        folder = next((dev/f'evidence/hit_event_v0_2/full_dev/game_{game}').glob('*/raw_candidates.json')).parent
        raw = json.loads((folder/'raw_candidates.json').read_text(encoding='utf-8'))
        gt = json.loads((folder/'ground_truth_strokes.json').read_text(encoding='utf-8'))
        baseline = json.loads((folder/'full_dev_hit_evaluation.json').read_text(encoding='utf-8'))
        frames = {int(c['source_frame']) for c in raw}
        for event in gt:
            for offset in (-2, 0, 2):
                frame = int(event['source_frame'])+offset
                if 0 <= frame < baseline['media']['frame_count']:
                    frames.add(frame)
        boxes = []
        for row in scene['frame_results']:
            if row['game'] != f'game_{game}':
                continue
            choices = [d['bbox'] for d in row['detections'] if 'table' in d['label']]
            if choices:
                boxes.append(max(choices, key=lambda b: (b[2]-b[0])*(b[3]-b[1])))
        table = [statistics.median(b[i] for b in boxes) for i in range(4)] if boxes else None
        ordered = sorted(frames)
        for index in range(0, len(ordered), 256):
            request = {'game': f'game_{game}', 'video_path': str(source['video']),
                       'video_sha256': source['entry']['sha256'], 'fps': 120,
                       'frames': ordered[index:index+256], 'table_bbox': table,
                       'table_status': 'STATIC_CAMERA_COARSE_BOX_PROXY_SOURCE_LINKAGE_NOT_FORMALLY_VERIFIED',
                       'table_source_path': str(scene_path), 'purpose': 'RESEARCH_DEV_CANDIDATE_CENTRIC',
                       'ground_truth_content': 'NOT_PASSED_TO_WORKER'}
            name = f'game_{game}-batch-{index//256:04d}'
            path = output/f'{name}.request.json'
            payload = json.dumps(request, indent=2)
            if path.exists() and path.read_text(encoding='utf-8') != payload:
                raise RuntimeError('IMMUTABLE_REQUEST_CHANGED')
            path.write_text(payload, encoding='utf-8')
            jobs.append({'request': str(path), 'output': str(output/f'{name}.result.json')})
        print(f'game_{game}: requests={len(ordered)}, table={table}', flush=True)
    (output/'jobs.json').write_text(json.dumps(jobs, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1])
