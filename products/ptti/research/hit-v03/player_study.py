"""Diagnose player proximity at native events using paired, same-frame observations."""
from collections import Counter
import json
from pathlib import Path
import sys

from feature_study import summary
from runtime import player_proximity


def main(audit, cache, ablation=None):
    audit, cache = Path(audit), Path(cache)
    jobs = json.loads((cache/'jobs_with_event_diagnostics.json').read_text(encoding='utf-8'))
    frames = {}
    for job in jobs:
        path = Path(job['output'])
        if not path.exists():
            raise RuntimeError('INCOMPLETE_EVENT_DIAGNOSTIC_PLAYER_CACHE')
        request = json.loads(Path(job['request']).read_text(encoding='utf-8'))
        frames.setdefault(request['game'], {}).update({r['source_frame']: r for r in
            json.loads(path.read_text(encoding='utf-8'))['frames']})
    report = {'scope': 'TRAIN_DEV_ONLY_CONDITIONAL_ON_PAIRED_EVIDENCE', 'games': [],
              'role_mapping': 'UNCONFIRMED_NOT_STRIKING_SIDE_ACCURACY',
              'warning': 'Evidence availability differs by event type; do not interpret as unbiased accuracy'}
    for game in (1, 2, 3):
        data = json.loads((audit/f'game_{game}_diagnostics.json').read_text(encoding='utf-8'))
        groups = {}
        samples = []
        for kind in ('STROKE', 'BOUNCE', 'NET'):
            distances = []
            availability = Counter()
            events = [e for e in data['event_kinematics'] if e['event_type'] == kind]
            for event in events:
                points = [p for p in event['kinematics']['trajectory'] if
                          abs(p['timestamp_ms']-event['timestamp_ms']) <= 16.668 and
                          p['source_frame'] in frames[f'game_{game}']]
                if not points:
                    availability['NO_PAIRED_BALL_PERSON_FRAME'] += 1
                    continue
                point = min(points, key=lambda p: abs(p['timestamp_ms']-event['timestamp_ms']))
                paired = frames[f'game_{game}'][point['source_frame']]
                evidence = player_proximity((point['x'], point['y']), paired['people'], (1920, 1080))
                distance = evidence['minimum_player_candidate_distance']
                availability['PAIRED_OBSERVATION'] += 1
                if distance is None:
                    availability['ROLE_CANDIDATE_UNAVAILABLE'] += 1
                else:
                    distances.append(distance)
                samples.append({'event_id': event['event_id'], 'event_type': kind, 'gt_timestamp_ms': event['timestamp_ms'],
                    'observation_timestamp_ms': point['timestamp_ms'], 'gt_delta_ms': point['timestamp_ms']-event['timestamp_ms'],
                    'ball': point, 'player_evidence': evidence})
            groups[kind] = {'native_events': len(events), 'availability': dict(availability),
                            'distance_to_player_candidate_normalized': summary(distances)}
        if ablation:
            feature_path = Path(ablation)/f'game_{game}-candidate-player-evidence.jsonl'
            features = [json.loads(line) for line in feature_path.read_text(encoding='utf-8').splitlines()]
            for stage in ('raw', 'decoded'):
                ids = {fp['candidate_id'] for fp in data['stages'][stage]['fp_diagnostics']}
                selected = [r for r in features if r['event_id'] in ids]
                distances = [r['player_evidence']['minimum_player_candidate_distance'] for r in selected
                             if r['player_evidence']['minimum_player_candidate_distance'] is not None]
                groups[f'{stage.upper()}_FP'] = {'fp_total': len(ids), 'paired_candidate_rows': len(selected),
                    'role_evidence_unavailable': len(selected)-len(distances),
                    'distance_to_player_candidate_normalized': summary(distances),
                    'large_player_distance_proxy_count': sum(distance >= .12 for distance in distances),
                    'interpretation': 'SPATIAL_PROXY_NOT_PROVEN_CAUSE_OR_STRIKING_SIDE_TRUTH'}
        (audit/f'game_{game}_paired_event_player_evidence.json').write_text(json.dumps(samples), encoding='utf-8')
        report['games'].append({'game': f'game_{game}', 'groups': groups})
    (audit/'player_event_proximity_study.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
