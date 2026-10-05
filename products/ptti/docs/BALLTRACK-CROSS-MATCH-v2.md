# TTI Ball Tracker experiment v2

Release Gate: **HISTORICAL_DB_UNVERIFIED**. Production database stays frozen. Existing forensic artifacts are retained; this experiment never imports the backend or opens a match database.

Vision Gate: **CROSS_MATCH_GENERALIZATION_REQUIRED** until the frozen evaluation is reviewed. No main merge, tag, release, TrajPred or RacketPose is authorized by this experiment.

## Split and exposure

Development: original ten rallies 000/001 in match1, match10, match11, match12 and match13. Existing five 002 rallies remain Internal Holdout; their historical files and results are unchanged.

Cross-Match Holdout: ten official validation rallies in six different matches: match14..17 (000/001), match18/000 and match19/000. Selection is ordered first available validation rallies, fixed before prediction or GT inspection. Players, venue, camera identities, lighting and referee presence are UNKNOWN unless separately reviewed. Distinct match IDs do not prove distinct venues or players.

Important limitation: the upstream config uses train for fitting and val for best-checkpoint selection. The new matches occur in upstream train/val. This is an unseen-match holdout for **TTI development**, not independent unseen-match evidence for the upstream pretrained model. The official test split contains only the five development matches. Do not claim original-model generalization or scientific validation from this experiment.

Primary sources are pinned [official dataset splits](https://huggingface.co/datasets/linfeng302/RacketVision/tree/85157ca21faa2abca96d837dd2b963738029bcc8/tabletennis/info) and [official BallTrack config](https://github.com/OrcustD/RacketVision/blob/c44af2a08524d3cb54d818f19686f4cdea4d2793/source/BallTrack/configs/tracknetv3_base.py).

## Tracker

Real model sigmoid heatmaps → local extrema → spatial NMS → candidate list. The worker keeps unmodified upstream bounding-box RAW alongside candidates. Heatmap peaks and upstream box means are real response measurements, not calibrated probabilities.

TTIBallTracker performs offline beam search with a null observation option. Additive costs use negative-log response, resolution/FPS-normalized velocity, bounded acceleration residual, and a GT-free clip-level persistent response map. Acceleration cost is capped to allow racket contact and bounce; speed is a soft cost rather than a hard exclusion. Equal motion histories are deduplicated. A SceneContext can supply soft penalties but defaults empty; no inferred table geometry or absolute ROI mask exists.

Every frame records raw_prediction, tti_prediction, decision, reason and evidence. No calibrated model probability or fabricated TTI confidence is emitted. Linear short-gap interpolation is explicit and optional; default is OFF. Interpolated observations are excluded from detection recall and included only in usable coverage.

The experiment is CLI-only and does not replace the desktop/default RAW pipeline. Optical-flow/frame-difference evidence is not enabled. This is a modest explainable association experiment, not a trained replacement model.

## Evaluation discipline

Only Development selects parameters. Candidate capture retains up to 128 peaks above .005; evaluated candidate count/minimum response and all association settings are frozen in tracker_config.json. tracker_lock.json records SHA256 of config, manifest, tracker, extractor, worker and evaluator. Holdout inference and evaluation fail if any locked input changes. First report cannot be overwritten. Preserve rejected experimental captures separately.

Sparse GT is used only in evaluation. Unannotated frames are not negatives. Visibility recall can count a catastrophically wrong location as detected; localization error and outlier counts must always accompany it. Catastrophe buckets are diagonal-normalized thresholds corresponding to >20, >50 and >100 pixels at 1920×1080. Report per-match and aggregate metrics. Full-video usable trajectory coverage is not accuracy.

Reproduction from product root (explicit isolated vision runtime required):

```powershell
.venv/Scripts/python.exe scripts/cross_match_tracker.py prepare
.venv/Scripts/python.exe scripts/cross_match_tracker.py development
.venv/Scripts/python.exe scripts/cross_match_tracker.py tune
.venv/Scripts/python.exe scripts/cross_match_tracker.py cross_match_holdout
.venv/Scripts/python.exe scripts/cross_match_tracker.py evaluate
```

Reports and immutable captures are local ignored artifacts under outputs/vision/tracker_v2/. No personal database, model weights, official video or test exports are committed. Native GUI acceptance remains MANUAL_GUI_CHECK_REQUIRED; API/build evidence cannot verify Windows Save As or print.
