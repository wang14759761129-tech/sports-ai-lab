"""Additional native-event diagnostic frames, excluding already requested frames."""
import json
import os
from pathlib import Path
import sys

PRODUCT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PRODUCT))
from backend.extended_openttgames import EventGroundTruthAdapter  # noqa: E402


def main(cache):
    cache = Path(cache)
    jobs = json.loads((cache/'jobs.json').read_text(encoding='utf-8'))
    original_jobs = list(jobs)
    for game in (1, 2, 3):
        requests = [json.loads(Path(j['request']).read_text(encoding='utf-8')) for j in original_jobs]
        requests = [r for r in requests if r['game'] == f'game_{game}']
        existing = {f for r in requests for f in r['frames']}
        path = Path(os.environ['LOCALAPPDATA'])/f'PTTI-Dev/research-datasets/ExtendedOpenTTGames/annotations/train/game_data/game_{game}.json'
        events = EventGroundTruthAdapter(fps=120).parse(json.loads(path.read_text(encoding='utf-8')))
        frames = sorted({e['frame'] for e in events if e['event_type'] in {'BOUNCE', 'NET', 'RALLY_ENDING'}}-existing)
        for index in range(0, len(frames), 256):
            name = f'game_{game}-event-batch-{index//256:04d}'
            request_path = cache/f'{name}.request.json'
            request = {**requests[0], 'frames': frames[index:index+256],
                       'purpose': 'RESEARCH_DEV_NATIVE_EVENT_NEIGHBORHOOD_DIAGNOSTICS'}
            if request_path.exists():
                raise RuntimeError('EXTRA_EVENT_PLAN_ALREADY_EXISTS')
            request_path.write_text(json.dumps(request, indent=2), encoding='utf-8')
            jobs.append({'request': str(request_path), 'output': str(cache/f'{name}.result.json')})
        print(f'game_{game} additional native-event frames: {len(frames)}', flush=True)
    (cache/'candidate_jobs_original.json').write_text(json.dumps(original_jobs, indent=2), encoding='utf-8')
    (cache/'jobs_with_event_diagnostics.json').write_text(json.dumps(jobs, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1])
