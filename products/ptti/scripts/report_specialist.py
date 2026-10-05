"""Archive the completed, fixed A/B/C pilot without rerunning or tuning it."""
import html
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vision.benchmark import read_ground_truth, percentile
from vision.specialist import sha256, validate_provenance


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    home = ROOT / 'outputs/vision/specialist_v1'
    target = ROOT / 'configs/experiments/TTI_SPECIALIST_V1.json'
    if target.exists():
        raise FileExistsError('Completed experiment record must not be overwritten')
    results = {'A': load(home / 'A_official.json')['known_evaluation']}
    provenance = {}
    for name in ['B', 'C']:
        checkpoint = ROOT / f'models/tti_tabletennis/tti_balltrack_tt_ft_v1_{name}.pth'
        p = load(checkpoint.with_suffix('.provenance.json'))
        validate_provenance(p, checkpoint)
        provenance[name] = {k: v for k, v in p.items() if k != 'model_path'}
        results[name] = load(home / f'{name}_known_evaluation.json')
    per_match = {}
    for name, result in results.items():
        groups = {}
        for clip in result['clips']:
            _, match, rally = clip['source_id'].split('/')
            group = groups.setdefault(match, dict(visible=0, detected=0, negative=0, fp=0, errors=[]))
            gt = read_ground_truth(home / f'dataset/tabletennis/all/{match}/csv/{rally}_ball.csv')
            for p in clip['raw_predictions']:
                g = gt[p['frame']]
                group['visible' if g['visible'] else 'negative'] += 1
                if p['visible']:
                    if g['visible']:
                        group['detected'] += 1
                        group['errors'].append(math.hypot(p['pixel_x'] - g['x'], p['pixel_y'] - g['y']))
                    else:
                        group['fp'] += 1
        for match, group in groups.items():
            errors = group.pop('errors')
            group.update(recall=group['detected']/group['visible'], mean=sum(errors)/len(errors), median=percentile(errors,.5), p95=percentile(errors,.95), catastrophic={str(t):sum(e>t for e in errors) for t in [20,50,100]})
        per_match[name] = groups
    # User acceptance includes declining catastrophic errors; both candidates
    # are rejected if they fail that requirement. No arbitrary percentage cutoff.
    raw = results['A']['tti_style']
    accepted = [name for name in ['B','C'] if results[name]['tti_style']['recall'] >= raw['recall'] and results[name]['tti_style']['catastrophic']['100'] < raw['catastrophic']['100'] and results[name]['tti_style']['false_positives'] <= raw['false_positives']]
    if accepted:
        raise RuntimeError('Candidate requires full human acceptance review; do not auto-promote')
    artifacts = [home / n for n in ['A_official.json','B_training.json','B_known_evaluation.json','C_training.json','C_known_evaluation.json','split.json','training_config.json','prepared_inputs.json','hard_negative_train.json','hard_negative_dev.json']]
    historical = load(ROOT / 'configs/experiments/TTI_TRACKER_V1.json')
    for item in historical['artifacts']:
        if sha256(ROOT / item['path']) != item['sha256']:
            raise ValueError('Historical evidence changed')
    record = dict(experiment='TTI_SPECIALIST_V1', scope='bounded 3-epoch pilot; rally median proxy, not full official reproduction', release_gate='HISTORICAL_DB_UNVERIFIED', vision_gate='BALLTRACK_MODEL_IMPROVEMENT_FAILED', default_pipeline='RAW_RACKETVISION', final_test='NOT_SELECTED_OR_RUN: candidates failed known evaluation', provenance=provenance, known_evaluation={n:{k:r[k] for k in ['official_style','tti_style','peak_rank','witness','seconds']} for n,r in results.items()}, per_match=per_match, hard_negatives={role:len(load(home/f'hard_negative_{role}.json')) for role in ['train','dev']}, taxonomy='All 7 remain UNKNOWN. Crops reviewed; objects visible are insufficient to prove causal categories.', artifacts=[dict(path=str(p.relative_to(ROOT)),sha256=sha256(p)) for p in artifacts])
    target.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    lines=['# Specialist v1 — completed pilot', '', 'Release Gate: HISTORICAL_DB_UNVERIFIED', 'Vision Gate: BALLTRACK_MODEL_IMPROVEMENT_FAILED', '', 'Neither candidate passes. No final untouched test was selected or run. RAW remains default; rejected Tracker V1 remains disabled. No production DB access, merge, tag, release, RacketPose or TrajPred.', '', 'These are 625 sparse annotated frames, not all video frames. Recall below is visibility coverage: wrong-position detections also count as detected and are penalized by error buckets. Official F1 includes wrong-localization failures. Error percentiles use visible GT with a decoded prediction; misses are reported separately. All frames are 1920×1080. Responses are uncalibrated sigmoid heatmap outputs.', '', '| Model | Detected / 525 | Recall | FP / 100 | Mean px | Median px | P95 px | >20 | >50 | >100 | Official F1 |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for n,r in results.items():
        m=r['tti_style']; c=m['catastrophic']
        lines.append(f"| {n} | {m['detected']} | {m['recall']:.4%} | {m['false_positives']} | {m['mean']:.4f} | {m['median']:.4f} | {m['p95']:.4f} | {c['20']} | {c['50']} | {c['100']} | {r['official_style']['f1']:.6f} |")
    lines += ['', '## Peak ranks (cumulative counts / 525)', '', '| Model | 1 | ≤4 | ≤8 | ≤16 | ≤32 | ≤64 | >64 | No nearby peak |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for n,r in results.items():
        lines.append('| '+n+' | '+' | '.join(str(r['peak_rank'][k]) for k in ['1','4','8','16','32','64','greater_than64','no_nearby_peak'])+' |')
    lines += ['', '## Clothing witness: match10/001 frame184', '', '| Model | True response | Clothing response | GT rank | Pixel error |', '|---|---:|---:|---:|---:|']
    for n,r in results.items():
        w=r['witness']; lines.append(f"| {n} | {w['true_ball_region_response']:.6f} | {w['clothing_peak_response']:.6f} | {w['gt_peak_rank']} | {w['pixel_error']} |")
    lines += ['', '## Per-match known evaluation (not untouched generalization)', '', '| Match | Model | Detected / visible | FP | Mean | Median | P95 | >20 / >50 / >100 |', '|---|---|---:|---:|---:|---:|---:|---|']
    for match in sorted(per_match['A']):
        for n in results:
            m=per_match[n][match]; c=m['catastrophic']; lines.append(f"| {match} | {n} | {m['detected']}/{m['visible']} | {m['fp']} | {m['mean']:.3f} | {m['median']:.3f} | {m['p95']:.3f} | {c['20']} / {c['50']} / {c['100']} |")
    lines += ['', '## Runtime and limits', '', 'Evaluation time includes dataset IO, CUDA inference, candidate-rank extraction and compressed heatmap evidence writing; it is not pure model FPS. Training time includes DEV evaluation. No stage profiler or real-time claim.', '', 'TRAIN: match20–27,16 clips,400 annotations. DEV: match28–31,7 clips,175 annotations. KNOWN:11 matches,25 clips,625 annotations. All three roles are match-disjoint; official parent exposure is separately tracked. Official metadata covers all50 matches, so genuinely model-unseen final games must come from a new trustworthy source.', '', 'C changes only TRAIN sampling weight1→3 for four mined peaks; DEV has three mined peaks and is never sampled for training. Both use identical parent, seed, architecture, loss, mixup, learning rate1e-5, batch2,3 epochs and400 draws/epoch. Seven reviewed crops remain UNKNOWN; no color rule or claimed referee category is inferred from a cropped object alone.', '', 'Small training coverage and GT-free rally-median proxy limit interpretation. Stop this pilot; do not tune against KNOWN results or claim all model fine-tuning is disproven. Future training needs broader TRAIN/DEV coverage and reproducible backgrounds before a separately preregistered experiment. Native GUI remains MANUAL_GUI_CHECK_REQUIRED. Original111 tests retained;124 passed,0 failed,1 existing Starlette deprecation warning.', '']
    for n,p in provenance.items():
        lines.append(f"{n}: best DEV epoch {p['best_epoch']}, training+DEV {p['training_seconds']:.2f}s, checkpoint SHA256 `{p['checkpoint_sha256']}`; known evaluation {results[n]['seconds']:.2f}s.")
    text='\n'.join(lines)+'\n'
    (ROOT/'docs/BALLTRACK-SPECIALIST-v1-RESULTS.md').write_text(text,encoding='utf-8')
    (home/'specialist_report.html').write_text('<!doctype html><meta charset="utf-8"><title>TTI Specialist pilot</title><style>body{max-width:1200px;margin:40px auto;font:16px system-ui}pre{white-space:pre-wrap}</style><h1>TTI Specialist — rejected pilot</h1><pre>'+html.escape(text)+'</pre>',encoding='utf-8')
    print(json.dumps(record['known_evaluation'],indent=2))


if __name__ == '__main__':
    main()
