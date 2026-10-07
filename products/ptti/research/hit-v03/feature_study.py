"""Event-conditioned diagnostics; GT labels never cross into inference."""
import json
import math
from pathlib import Path
import statistics
import sys

from audit import percentile
from runtime import table_coordinates


def summary(values):
    return {'count': len(values), 'p5': percentile(values, .05), 'p25': percentile(values, .25),
            'median': percentile(values, .5), 'p75': percentile(values, .75), 'p95': percentile(values, .95)}


def main(audit_folder, cache):
    audit_folder, cache = Path(audit_folder), Path(cache)
    report = {'scope': 'DEV_DIAGNOSTICS_ONLY', 'games': [],
              'warning': 'Overlapping marginal distributions do not establish a reliable classifier'}
    for game in (1, 2, 3):
        data = json.loads((audit_folder/f'game_{game}_diagnostics.json').read_text(encoding='utf-8'))
        request = json.loads((cache/f'game_{game}-batch-0000.request.json').read_text(encoding='utf-8'))
        groups = {}
        for kind in ('STROKE', 'BOUNCE', 'NET'):
            rows = [e for e in data['event_kinematics'] if e['event_type'] == kind]
            speed, missing, distance, direction, speed_change, acceleration = [], [], [], [], [], []
            for event in rows:
                evidence = event['kinematics']
                missing.append(evidence['missing_fraction_proxy'])
                if evidence['velocity']:
                    speed.append(statistics.median(v['speed_px_s'] for v in evidence['velocity']))
                if evidence['acceleration_curvature_proxy']:
                    acceleration.append(statistics.median(v['magnitude_px_s2'] for v in evidence['acceleration_curvature_proxy']))
                before = [p for p in evidence['trajectory'] if p['timestamp_ms'] < event['timestamp_ms']][-2:]
                after = [p for p in evidence['trajectory'] if p['timestamp_ms'] > event['timestamp_ms']][:2]
                if len(before) == 2 and len(after) == 2:
                    vectors = []
                    for a, b in [before, after]:
                        dt = (b['timestamp_ms']-a['timestamp_ms'])/1000
                        vectors.append(((b['x']-a['x'])/dt, (b['y']-a['y'])/dt))
                    magnitudes = [math.hypot(*v) for v in vectors]
                    if min(magnitudes) > 1e-6:
                        cosine = max(-1, min(1, sum(a*b for a, b in zip(*vectors))/math.prod(magnitudes)))
                        direction.append(math.degrees(math.acos(cosine)))
                        speed_change.append(abs(magnitudes[1]-magnitudes[0])/max(magnitudes))
                if evidence['trajectory']:
                    point = min(evidence['trajectory'], key=lambda p: abs(p['timestamp_ms']-event['timestamp_ms']))
                    if abs(point['timestamp_ms']-event['timestamp_ms']) <= 16.668:
                        geometry = table_coordinates((point['x'], point['y']), request['table_bbox'])
                        if geometry:
                            distance.append(geometry['center_distance_proxy'])
            groups[kind] = {'events': len(rows), 'median_window_speed_px_s': summary(speed),
                            'pre_post_direction_change_degrees': summary(direction),
                            'pre_post_speed_change_ratio': summary(speed_change),
                            'median_acceleration_proxy_px_s2': summary(acceleration),
                            'local_missing_fraction': summary(missing),
                            'table_center_distance_proxy_with_nearby_observation': summary(distance)}
        report['games'].append({'game': f'game_{game}', 'features': groups})
    target = audit_folder/'event_feature_distributions.json'
    target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
