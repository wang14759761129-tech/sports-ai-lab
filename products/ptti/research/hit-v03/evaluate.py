"""A/B/C/D research ablations; runtime features cannot receive annotations."""
from __future__ import annotations

from collections import Counter
import hashlib
import html
import json
import os
from pathlib import Path
import sys

PRODUCT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PRODUCT))
from backend.evidence_fusion import evaluate_hit_events  # noqa: E402
from backend.hit_event_v02 import (  # noqa: E402
    HitEventV02Config, HitSequenceDecoder, StrokeIntervalPrior, TemporalCandidateClusterer,
)
from runtime import player_proximity, review_workload, soft_adjustment  # noqa: E402

CONFIG = {'table_center_penalty': .08, 'person_distance_penalty': .12, 'distance_scale': .12}


def main(cache, output, modes_to_run='ABCD'):
    cache, output = Path(cache), Path(output)
    jobs = json.loads((cache/'jobs.json').read_text(encoding='utf-8'))
    detections = {}
    tables = {}
    runtime = []
    for job in jobs:
        request = json.loads(Path(job['request']).read_text(encoding='utf-8'))
        tables[request['game']] = request['table_bbox']
        path = Path(job['output'])
        if not path.exists():
            if any(mode in modes_to_run for mode in 'CD'):
                raise RuntimeError('INCOMPLETE_PLAYER_CACHE_ABLATION_NOT_RUN')
            continue
        result = json.loads(path.read_text(encoding='utf-8'))
        if result['request_sha256'] != hashlib.sha256(Path(job['request']).read_bytes()).hexdigest():
            raise ValueError('PLAYER_CHECKPOINT_CHANGED')
        game = request['game']
        tables[game] = request['table_bbox']
        detections.setdefault(game, {}).update({r['source_frame']: r for r in result['frames']})
        runtime.append(result['runtime'])
    output.mkdir(parents=True, exist_ok=False)
    config_payload = json.dumps(CONFIG, sort_keys=True)
    (output/'V03_DEV_EXPERIMENT_CONFIG.json').write_text(config_payload, encoding='utf-8')
    reports = []
    dev = Path(os.environ['LOCALAPPDATA'])/'PTTI-Dev'
    for game in ('game_1', 'game_2', 'game_3'):
        folder = next((dev/f'evidence/hit_event_v0_2/full_dev/{game}').glob('*/full_dev_hit_evaluation.json')).parent
        baseline = json.loads((folder/'full_dev_hit_evaluation.json').read_text(encoding='utf-8'))
        raw = json.loads((folder/'raw_candidates.json').read_text(encoding='utf-8'))
        truth = json.loads((folder/'ground_truth_strokes.json').read_text(encoding='utf-8'))
        requested_frames = {int(c['source_frame']) for c in raw}
        balls = {}
        with (folder/'full_match_frame_evidence.jsonl').open(encoding='utf-8') as stream:
            for line in stream:
                frame = json.loads(line)
                if frame['source_frame'] in requested_frames:
                    balls[frame['source_frame']] = (frame['ball']['x'], frame['ball']['y'])
        config = HitEventV02Config.from_dict(baseline['config'])
        prior = StrokeIntervalPrior(**baseline['prior'])
        player_features = {}
        if any(mode in modes_to_run for mode in 'CD'):
            with (output/f'{game}-candidate-player-evidence.jsonl').open('w', encoding='utf-8') as stream:
                for candidate in raw:
                    frame = candidate['source_frame']
                    feature = player_proximity(balls[frame], detections[game][frame]['people'], (1920, 1080))
                    player_features[frame] = feature
                    stream.write(json.dumps({'event_id': candidate['event_id'], 'source_frame': frame,
                        'timestamp_ms': candidate['timestamp_ms'], 'video_sha256': baseline['video_sha256'],
                        'ball_point': balls[frame], 'player_evidence': feature})+'\n')
        modes = {}
        for mode in modes_to_run:
            modified = []
            for c in raw:
                point = balls[c['source_frame']]
                evidence = (player_features[c['source_frame']]
                            if mode in 'CD' else None)
                modified.append(soft_adjustment(c, ball_point=point, table=tables[game], player=evidence,
                                               mode=mode, config=CONFIG))
            clusters = TemporalCandidateClusterer(config.cluster_window_ms).cluster(modified)
            decoder = HitSequenceDecoder(config, prior).decode(clusters['kept'])
            combined_review = decoder['accepted']+decoder['review_candidates']
            automatic_metrics = evaluate_hit_events(decoder['accepted'], truth, tolerances_ms=baseline['tolerances_ms'])
            review_metrics = evaluate_hit_events(combined_review, truth, tolerances_ms=baseline['tolerances_ms'])
            duration = baseline['media']['duration']
            metric = automatic_metrics['by_tolerance']['plus_minus_2_processing_frames']
            if mode == 'A':
                frozen = baseline['stage_metrics']['decoded']['by_tolerance']['plus_minus_2_processing_frames']
                if any(metric[key] != frozen[key] for key in ['matched', 'false_positives', 'false_negatives']):
                    raise ValueError('ABLATION_A_DOES_NOT_REPRODUCE_BASELINE')
                review_frozen = baseline['stage_metrics']['review_mode']['by_tolerance']['plus_minus_2_processing_frames']
                review_actual = review_metrics['by_tolerance']['plus_minus_2_processing_frames']
                if any(review_actual[key] != review_frozen[key] for key in ['matched', 'false_positives', 'false_negatives']):
                    raise ValueError('ABLATION_A_REVIEW_DOES_NOT_REPRODUCE_BASELINE')
            modes[mode] = {'automatic_metrics': automatic_metrics, 'review_metrics': review_metrics,
                          'fp_per_minute': metric['false_positives']*60/duration,
                          'fn_per_minute': metric['false_negatives']*60/duration,
                          'review_workload': review_workload(len(combined_review), duration),
                          'raw_count': len(raw), 'cluster_count': len(clusters['kept']),
                          'decoded_count': len(decoder['accepted']), 'review_count': len(combined_review),
                          'soft_feature_counts': dict(Counter(reason for c in modified for reason in c['research_soft_penalties']))}
            (output/f'{game}-{mode}-decoded.json').write_text(json.dumps(decoder), encoding='utf-8')
        reports.append({'game': game, 'duration_s': duration, 'gt_strokes': len(truth), 'modes': modes})
    aggregate = {}
    for mode in modes_to_run:
        rows = [r['modes'][mode] for r in reports]
        metrics = [r['automatic_metrics']['by_tolerance']['plus_minus_2_processing_frames'] for r in rows]
        tp, fp, fn = (sum(r[key] for r in metrics) for key in ['matched', 'false_positives', 'false_negatives'])
        duration = sum(r['duration_s'] for r in reports)
        aggregate[mode] = {'tp': tp, 'fp': fp, 'fn': fn, 'precision': tp/(tp+fp) if tp+fp else None,
                           'recall': tp/(tp+fn) if tp+fn else None, 'f1': 2*tp/(2*tp+fp+fn) if tp+fp+fn else None,
                           'fp_per_minute': fp*60/duration, 'fn_per_minute': fn*60/duration,
                           'review_workload': review_workload(sum(r['review_count'] for r in rows), duration)}
        review_rows = [r['review_metrics']['by_tolerance']['plus_minus_2_processing_frames'] for r in rows]
        rtp, rfp, rfn = (sum(r[key] for r in review_rows) for key in ['matched', 'false_positives', 'false_negatives'])
        aggregate[mode]['review_metrics'] = {'tp': rtp, 'fp': rfp, 'fn': rfn,
            'precision': rtp/(rtp+rfp) if rtp+rfp else None, 'recall': rtp/(rtp+rfn) if rtp+rfn else None,
            'f1': 2*rtp/(2*rtp+rfp+rfn) if rtp+rfp+rfn else None}
    report = {'scope': 'FULL_DEV_EXPLORATORY_NOT_HOLDOUT', 'config': CONFIG,
              'config_sha256': hashlib.sha256(config_payload.encode()).hexdigest(),
              'games': reports, 'aggregate': aggregate, 'worker_runtime': runtime,
              'geometry_limitation': 'Coarse bbox normalization; camera dependent; not physical table plane',
              'roles': 'UNCONFIRMED_CANDIDATES_NOT_ATHLETE_IDENTITIES', 'pose': 'OFF',
              'calibration_holdout_official_test': 'NOT_ACCESSED'}
    (output/'ablation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (output/'ablation.html').write_text('<!doctype html><meta charset="utf-8"><h1>Hit v0.3 DEV ablations</h1><pre>'+
        html.escape(json.dumps({'aggregate': aggregate, 'scope': report['scope']}, indent=2))+'</pre>', encoding='utf-8')
    print(json.dumps(aggregate, indent=2), flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 'ABCD')
