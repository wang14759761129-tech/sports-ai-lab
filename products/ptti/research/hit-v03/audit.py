"""TRAIN DEV diagnostics only. Never imported by production inference."""
from __future__ import annotations

import bisect
from collections import Counter
import hashlib
import html
import json
import math
import os
from pathlib import Path
import subprocess
import sys

PRODUCT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PRODUCT))
from backend.extended_openttgames import EventGroundTruthAdapter  # noqa: E402
from backend.hit_event_v02 import HitEventV02Config, HitSequenceDecoder, StrokeIntervalPrior  # noqa: E402


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    position = (len(values)-1)*q
    lo, hi = math.floor(position), math.ceil(position)
    return values[lo]+(values[hi]-values[lo])*(position-lo)


def distribution(values):
    bins = [-math.inf, -500, -250, -100, -50, -25, 0, 25, 50, 100, 250, 500, math.inf]
    return {'count': len(values), 'quantiles_ms': {
        name: percentile(values, q) for name, q in
        [('P1', .01), ('P5', .05), ('P25', .25), ('median', .5), ('P75', .75), ('P95', .95)]},
        'histogram': [{'lower_ms': a if math.isfinite(a) else None,
                       'upper_ms': b if math.isfinite(b) else None,
                       'count': sum(a <= x < b for x in values)} for a, b in zip(bins, bins[1:])]}


def nearest(events, times, timestamp):
    index = bisect.bisect_left(times, timestamp)
    candidates = [i for i in [index-1, index] if 0 <= i < len(events)]
    if not candidates:
        return None
    event = events[min(candidates, key=lambda i: abs(times[i]-timestamp))]
    return {'event_id': event['event_id'], 'timestamp_ms': event['timestamp_ms'],
            'delta_ms': timestamp-event['timestamp_ms'], 'native_label': event['native_label']}


def event_proximity(candidate, by_type, window_ms=100):
    nearby = {kind: nearest(rows, [e['timestamp_ms'] for e in rows], candidate['timestamp_ms'])
              for kind, rows in by_type.items()}
    labels = []
    for kind, label in [('STROKE', 'NEAR_STROKE_DUPLICATE'), ('BOUNCE', 'NEAR_BOUNCE'),
                        ('NET', 'NEAR_NET'), ('RALLY_ENDING', 'NEAR_RALLY_END')]:
        if nearby.get(kind) and abs(nearby[kind]['delta_ms']) <= window_ms:
            labels.append(label)
    if candidate.get('ball_quality') == 'JUMP_SUSPECT':
        labels.append('BALLTRACK_JUMP')
    if candidate.get('candidate_player', 'UNKNOWN') == 'UNKNOWN':
        labels.append('PLAYER_PROXIMITY_UNKNOWN')
    if not any(label != 'PLAYER_PROXIMITY_UNKNOWN' for label in labels):
        labels.append('UNEXPLAINED')
    return {'nearest_events': nearby, 'labels': labels,
            'interpretation': 'NONEXCLUSIVE_TEMPORAL_PROXIMITY_NOT_PROVEN_CAUSE'}


def local_kinematics(ball, times, timestamp, window=150):
    lo, hi = bisect.bisect_left(times, timestamp-window), bisect.bisect_right(times, timestamp+window)
    points = ball[lo:hi]
    velocities = []
    for a, b in zip(points, points[1:]):
        dt = (b['timestamp_ms']-a['timestamp_ms'])/1000
        if 0 < dt <= .12:
            vx, vy = (b['x']-a['x'])/dt, (b['y']-a['y'])/dt
            velocities.append({'timestamp_ms': b['timestamp_ms'], 'vx_px_s': vx, 'vy_px_s': vy,
                               'speed_px_s': math.hypot(vx, vy), 'angle_radians': math.atan2(vy, vx)})
    pre = sum(p['timestamp_ms'] < timestamp for p in points)
    post = sum(p['timestamp_ms'] > timestamp for p in points)
    acceleration = []
    for a, b in zip(velocities, velocities[1:]):
        dt = (b['timestamp_ms']-a['timestamp_ms'])/1000
        if 0 < dt <= .12:
            angle = math.atan2(math.sin(b['angle_radians']-a['angle_radians']),
                               math.cos(b['angle_radians']-a['angle_radians']))
            acceleration.append({'timestamp_ms': b['timestamp_ms'],
                'magnitude_px_s2': math.hypot(b['vx_px_s']-a['vx_px_s'], b['vy_px_s']-a['vy_px_s'])/dt,
                'curvature_proxy_radians_per_px': abs(angle)/max(1e-6, (a['speed_px_s']+b['speed_px_s'])*dt/2)})
    return {'trajectory': points, 'velocity': velocities, 'acceleration_curvature_proxy': acceleration,
            'pre_count': pre, 'post_count': post,
            'observations': len(points), 'expected_cfr_frames': 37,
            'missing_fraction_proxy': max(0, 1-len(points)/37),
            'coordinate_system': 'SOURCE_IMAGE_PIXELS', 'scope': 'CAMERA_DEPENDENT',
            'model_evidence': 'RAW_MODEL_RESPONSE_NOT_CALIBRATED_PROBABILITY'}


def diagnose_fn_center(ball, times, timestamp, tolerance_ms, config):
    centers = range(bisect.bisect_left(times, timestamp-tolerance_ms-.001),
                    bisect.bisect_right(times, timestamp+tolerance_ms+.001))
    evaluations = []
    for index in centers:
        if index < 2 or index+2 >= len(ball):
            evaluations.append({'timestamp_ms': times[index], 'reason': 'BALL_FRAGMENT'})
            continue
        points = ball[index-2:index+3]
        gaps = [b['timestamp_ms']-a['timestamp_ms'] for a, b in zip(points, points[1:])]
        if max(gaps) > config['max_ball_gap_ms']:
            evaluations.append({'timestamp_ms': times[index], 'reason': 'BALL_FRAGMENT', 'max_gap_ms': max(gaps)})
            continue
        vectors = []
        for a, b in [(points[0], points[1]), (points[3], points[4])]:
            dt = (b['timestamp_ms']-a['timestamp_ms'])/1000
            vectors.append(((b['x']-a['x'])/dt, (b['y']-a['y'])/dt))
        speeds = [math.hypot(*v) for v in vectors]
        if min(speeds) <= 1e-6:
            evaluations.append({'timestamp_ms': times[index], 'reason': 'WEAK_SPEED_CHANGE'})
            continue
        cosine = max(-1, min(1, sum(a*b for a, b in zip(*vectors))/math.prod(speeds)))
        direction = math.acos(cosine)/math.pi
        speed_change = abs(speeds[1]-speeds[0])/max(speeds)
        score = .65*direction+.35*speed_change
        evaluations.append({'timestamp_ms': times[index], 'direction_score': direction,
            'speed_change_ratio': speed_change, 'kinematic_score': score,
            'reason': 'THRESHOLD_MISS' if score < config['minimum_kinematic_score'] else 'UNKNOWN'})
    return {'center_observations_within_tolerance': len(evaluations), 'evaluations': evaluations,
            'mechanisms': sorted({r['reason'] for r in evaluations}) if evaluations else ['BALL_FRAGMENT'],
            'note': 'Context before/after does not guarantee a visible eligible center observation'}


def attrition_diagnostics(report, raw, clustered):
    """Reconstruct immutable decoder traces, then join GT only in diagnostics."""
    config = HitEventV02Config.from_dict(report['config'])
    prior = StrokeIntervalPrior(**report['prior'])
    decoded = HitSequenceDecoder(config, prior).decode(clustered)
    raw_matches = report['stage_metrics']['raw']['by_tolerance']['plus_minus_2_processing_frames']['matches']
    cluster_matches = report['stage_metrics']['cluster']['by_tolerance']['plus_minus_2_processing_frames']['matches']
    raw_match = {m['ground_truth_index']: raw[m['prediction_index']] for m in raw_matches}
    cluster_match = {m['ground_truth_index']: clustered[m['prediction_index']] for m in cluster_matches}
    suppressed = {c['event_id']: c for c in decoded['suppressed']}
    results = []
    for event in report['stage_attrition']:
        if event['loss_stage'] == 'TEMPORAL_CLUSTER_LOSS':
            matched = raw_match[event['ground_truth_index']]
            selected = next((c for c in clustered if matched['event_id'] in c['cluster_members']), None)
            results.append({'event': event, 'stage': 'CLUSTER', 'raw_matched': matched,
                            'selected_cluster_member': selected,
                            'selected_delta_ms': selected['timestamp_ms']-event['timestamp_ms'] if selected else None,
                            'mechanism': 'MAX_SCORE_MEMBER_MOVED_OUTSIDE_TOLERANCE' if selected else 'UNKNOWN'})
        elif event['stage_found']['cluster'] and not event['stage_found']['decoded']:
            matched = cluster_match[event['ground_truth_index']]
            results.append({'event': event, 'stage': 'DECODER', 'cluster_matched': matched,
                            'mechanism': 'REVIEW_ONLY' if event['stage_found']['review_mode'] else 'AUTO_REJECTED',
                            'decoder_suppression': suppressed.get(matched['event_id'])})
    return results


def fragment_proximity(timestamp, starts, ends, window_ms=150):
    labels = []
    for times, label in [(starts, 'BALLTRACK_FRAGMENT_START'), (ends, 'BALLTRACK_FRAGMENT_END')]:
        index = bisect.bisect_left(times, timestamp)
        distance = min((abs(times[i]-timestamp) for i in [index-1, index] if 0 <= i < len(times)), default=math.inf)
        if distance <= window_ms:
            labels.append(label)
    return labels


def run(local, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    dev = Path(local)/'PTTI-Dev'
    root = dev/'evidence/hit_event_v0_2/full_dev'
    baseline = {'scope': 'IMMUTABLE_DEV_ONLY', 'games': [], 'production_database': 'NOT_ACCESSED',
                'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=PRODUCT, text=True).strip(),
                'metrics_implementation_sha256': sha(PRODUCT/'backend/evidence_fusion.py'),
                'balltrack_version': 'BALLTRACK_V1_FROZEN_RAW'}
    all_games = []
    for game in (1, 2, 3):
        paths = list((root/f'game_{game}').glob('*/full_dev_hit_evaluation.json'))
        if len(paths) != 1:
            raise ValueError('BASELINE_SELECTION_AMBIGUOUS')
        path = paths[0]
        report = json.loads(path.read_text(encoding='utf-8'))
        if report['game'] != f'game_{game}' or report['split_role'] != 'DEV':
            raise ValueError('NON_DEV_BASELINE_REJECTED')
        folder = path.parent
        annotation = dev/f'research-datasets/ExtendedOpenTTGames/annotations/train/game_data/game_{game}.json'
        if sha(annotation) != report['annotation_sha256']:
            raise ValueError('ANNOTATION_CHANGED')
        artifacts = {p.name: {'path': str(p), 'sha256': sha(p)} for p in folder.iterdir() if p.is_file()}
        baseline['games'].append({'game': report['game'], 'video_sha256': report['video_sha256'],
                                 'annotation_sha256': report['annotation_sha256'],
                                 'config_sha256': report['config_sha256'], 'artifacts': artifacts})
        events = EventGroundTruthAdapter(fps=120).parse(json.loads(annotation.read_text(encoding='utf-8')))
        types = {kind: [e for e in events if e['event_type'] == kind]
                 for kind in ['STROKE', 'BOUNCE', 'NET', 'RALLY_ENDING']}
        ball = []
        with (folder/'full_match_frame_evidence.jsonl').open(encoding='utf-8') as stream:
            for line in stream:
                frame = json.loads(line)
                if frame['ball'].get('visible'):
                    ball.append({'timestamp_ms': frame['timestamp_ms'], 'source_frame': frame['source_frame'],
                                 'x': frame['ball']['x'], 'y': frame['ball']['y'],
                                 'model_response': frame['ball'].get('model_evidence')})
        times = [p['timestamp_ms'] for p in ball]
        starts = times[:1]+[b for a, b in zip(times, times[1:]) if b-a > report['config']['max_ball_gap_ms']]
        ends = [a for a, b in zip(times, times[1:]) if b-a > report['config']['max_ball_gap_ms']]+times[-1:]
        stages = {}
        raw = json.loads((folder/'raw_candidates.json').read_text(encoding='utf-8'))
        raw_times = [c['timestamp_ms'] for c in raw]
        for stage, filename in [('raw', 'raw_candidates.json'), ('cluster', 'clustered_candidates.json'),
                                ('decoded', 'decoded_candidates.json')]:
            candidates = json.loads((folder/filename).read_text(encoding='utf-8'))
            metric = report['stage_metrics'][stage]['by_tolerance']['plus_minus_2_processing_frames']
            unmatched = set(metric['unmatched_prediction_ids'])
            diagnostics = [dict(candidate_id=c['event_id'], timestamp_ms=c['timestamp_ms'],
                                source_frame=c['source_frame'], evidence_components=c['evidence_components'],
                                **event_proximity(c, types)) for c in candidates if c['event_id'] in unmatched]
            for diagnostic in diagnostics:
                diagnostic['labels'].extend(fragment_proximity(diagnostic['timestamp_ms'], starts, ends))
                stroke = diagnostic['nearest_events'].get('STROKE')
                diagnostic['review_hypotheses'] = (['SERVE_PREPARATION'] if stroke and
                    'serve' in stroke['native_label'] and -500 <= stroke['delta_ms'] < -50 else [])
            if len(diagnostics) != metric['false_positives']:
                raise ValueError('FP_DIAGNOSTIC_COUNT_MISMATCH')
            stages[stage] = {'metrics': {k: metric[k] for k in ['matched', 'false_positives', 'false_negatives',
                                                             'precision', 'recall', 'f1']},
                             'fp_labels_nonexclusive': dict(Counter(label for d in diagnostics for label in d['labels'])),
                             'fp_diagnostics': diagnostics,
                             'nearest_event_distributions': {
                                 kind: distribution([d['nearest_events'][kind]['delta_ms'] for d in diagnostics
                                                     if d['nearest_events'][kind]]) for kind in types},
                             'all_candidate_event_distributions': {
                                 kind: distribution([nearest(events, [e['timestamp_ms'] for e in events],
                                     c['timestamp_ms'])['delta_ms'] for c in candidates]) if events else distribution([])
                                 for kind, events in types.items()}}
        fn_ids = set(report['stage_metrics']['raw']['by_tolerance']['plus_minus_2_processing_frames']['unmatched_ground_truth_ids'])
        truth = json.loads((folder/'ground_truth_strokes.json').read_text(encoding='utf-8'))
        context = {e['event_id']: e for e in report['ball_context_by_ground_truth']}
        fns = []
        for event in truth:
            if event['event_id'] not in fn_ids:
                continue
            index = bisect.bisect_left(raw_times, event['timestamp_ms'])
            options = [i for i in [index-1, index] if 0 <= i < len(raw)]
            candidate = raw[min(options, key=lambda i: abs(raw_times[i]-event['timestamp_ms']))] if options else None
            delta = candidate['timestamp_ms']-event['timestamp_ms'] if candidate else None
            fns.append({'event': event, 'ball_context': context[event['event_id']],
                        'nearest_raw_candidate': candidate, 'nearest_delta_ms': delta,
                        'diagnostic': 'BALL_FRAGMENT' if not context[event['event_id']]['ball_context_available'] else
                        ('CANDIDATE_OUTSIDE_TOLERANCE' if delta is not None and abs(delta) <= 150 else 'NO_CANDIDATE'),
                        'causal_interpretation': 'PROXIMITY_DIAGNOSTIC_ONLY',
                        'ball_window': local_kinematics(ball, times, event['timestamp_ms']),
                        'center_diagnostic': diagnose_fn_center(ball, times, event['timestamp_ms'],
                            report['tolerances_ms']['plus_minus_2_processing_frames'], report['config'])})
        event_windows = [{**e, 'kinematics': local_kinematics(ball, times, e['timestamp_ms'])}
                         for e in events if e['event_type'] in types]
        result = {'game': report['game'], 'stages': stages, 'raw_fn': fns,
                  'raw_fn_context': dict(Counter('PRESENT' if f['ball_context']['ball_context_available'] else 'MISSING' for f in fns)),
                  'raw_fn_mechanism_proxy': dict(Counter(f['diagnostic'] for f in fns)),
                  'event_counts': {k: len(v) for k, v in types.items()},
                  'stage_attrition': report['stage_attrition'],
                  'event_kinematics': event_windows,
                  'loss_diagnostics': attrition_diagnostics(report, raw,
                      json.loads((folder/'clustered_candidates.json').read_text(encoding='utf-8')))}
        (output/f'game_{game}_diagnostics.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        all_games.append({k: v for k, v in result.items() if k not in ['raw_fn', 'event_kinematics', 'stage_attrition', 'stages', 'loss_diagnostics']} |
                         {'stages': {k: {n: v for n, v in s.items() if n != 'fp_diagnostics'} for k, s in stages.items()}})
        print(f'game_{game}: FP audited, FN={len(fns)}, context={result["raw_fn_context"]}', flush=True)
    (output/'V02_IMMUTABLE_BASELINE.json').write_text(json.dumps(baseline, indent=2), encoding='utf-8')
    summary = {'scope': 'DEV_DIAGNOSTICS_ONLY_NO_ALGORITHM_CHANGE', 'games': all_games,
               'limitations': ['Temporal proximity is not a proven cause', 'Player experiment NOT RUN',
                               'Table experiment NOT RUN', 'No official TEST/calibration/holdout accessed']}
    (output/'event_confusion_audit.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (output/'event_confusion_audit.html').write_text('<!doctype html><meta charset="utf-8"><title>Hit v0.3 audit</title>'
        '<h1>Hit v0.3 · DEV event confusion audit</h1><p>Temporal proximity is not causal attribution.</p><pre>'+
        html.escape(json.dumps(summary, indent=2, ensure_ascii=False))+'</pre>', encoding='utf-8')


if __name__ == '__main__':
    run(os.environ['LOCALAPPDATA'], sys.argv[1])
