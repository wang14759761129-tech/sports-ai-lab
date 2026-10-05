# TTI Ball Tracker experiment v2

Release Gate: **HISTORICAL_DB_UNVERIFIED**. Production database stays frozen. Existing forensic artifacts are retained; this experiment never imports the backend or opens a match database.

Vision Gate: **CROSS_MATCH_GENERALIZATION_REQUIRED**. Frozen evaluation completed and failed promotion criteria. No main merge, tag, release, TrajPred or RacketPose is authorized by this experiment.

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


## First frozen evaluation — 2026-10-05

The experimental tracker is **not promoted**. It lowers cross-match recall and increases false positives. RacketPose remains blocked by the Vision Gate; Release Gate is independently unchanged. No configuration was changed after the first cross-match run. Keep the current Cross-Match Holdout consumed/frozen: if it informs subsequent development, it must not be reused as a fresh holdout.

Selected configuration: K=16, minimum response=.01, NMS radius=5 on 512×288 model grid, beam=12; response=.2, motion=1, capped acceleration=.5, persistence=.4, missing cost=.35, speed scale=3 frame diagonals/second, history gap=.1 seconds, interpolation OFF. Twelve development-only combinations explored K={16,64,128}, response={.1,.2}, missing={.35,.6}. Selection objective: 2×misses + 2×FP + 4×>50px outliers + >20px outliers. Other coefficients were fixed engineering priors evaluated on Development, not estimated scientific constants.

Config SHA256: `3a48b41dad4f99c84bbdda38dde876037770e6e4c48554c6e59379a2f6a42ad1`. Frozen inputs were committed at `bfeaa01` before cross-match inference. Fresh Development RAW matched every preserved baseline point exactly (2,243 frames); the original 78.85% baseline was not rewritten.

| Set | Pipeline | Detected / visible GT | Recall | FP / negative GT | Mean px | Median px | P95 px | >20 / >50 / >100px | Full-video coverage |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| Development | RAW | 164/208 | 78.85% | 10/42 | 14.68 | 2.24 | 10.58 | 6 / 6 / 6 | 67.32% |
| Development | TTI | 156/208 | 75.00% | 8/42 | 11.27 | 3.75 | 8.85 | 4 / 4 / 4 | 59.61% |
| Cross-Match | RAW | 208/227 | 91.63% | 2/23 | 3.76 | 2.00 | 5.10 | 1 / 1 / 1 | 83.90% |
| Cross-Match | TTI | 202/227 | 88.99% | 6/23 | 4.83 | 3.23 | 6.40 | 1 / 1 / 1 | 81.03% |

Visibility recall counts any detected location, even a wrong one. Coverage counts all video frames with output, not correctness. Sparse GT does not support declaring unannotated frames negative. Thresholds are normalized by frame diagonal; all current clips are 1920×1080, so reference pixel thresholds equal actual thresholds. Interpolation contributes zero observations in this run.

### Per-match matrix (Cross-Match)

| Match | Pipeline | Recall | FP / negative | Mean px | Median px | P95 px | >100px |
|---|---|---:|---:|---:|---:|---:|---:|
| match14 | RAW | 93.18% | 0/6 | 9.12 | 2.00 | 3.61 | 1 |
| match14 | TTI | 95.45% | 0/6 | 10.05 | 3.05 | 5.29 | 1 |
| match15 | RAW | 88.37% | 0/7 | 1.76 | 1.71 | 3.02 | 0 |
| match15 | TTI | 81.40% | 2/7 | 2.63 | 2.70 | 4.15 | 0 |
| match16 | RAW | 86.96% | 2/4 | 2.39 | 2.00 | 5.10 | 0 |
| match16 | TTI | 91.30% | 3/4 | 4.04 | 4.07 | 6.71 | 0 |
| match17 | RAW | 93.62% | 0/3 | 2.16 | 2.24 | 3.94 | 0 |
| match17 | TTI | 80.85% | 0/3 | 2.98 | 3.03 | 4.71 | 0 |
| match18 | RAW | 90.91% | 0/3 | 2.54 | 2.53 | 4.60 | 0 |
| match18 | TTI | 95.45% | 1/3 | 2.90 | 3.16 | 5.83 | 0 |
| match19 | RAW | 100.00% | 0/0 | 3.97 | 3.16 | 8.30 | 0 |
| match19 | TTI | 96.00% | 0/0 | 4.89 | 4.60 | 8.05 | 0 |

### Worst cases and diagnosis

- match10/001 frame184: RAW 428.79px error; TTI 427.64px. Current image confirms pink background official clothing. Weak actual-ball peak is rank56 (.03769); selected K16 excludes it. K64/128 were tested on all Development clips and were worse under the declared joint objective. Merely exposing more peaks does not solve association.
- match10/001 frames219,243,254: TTI suppresses wrong RAW observations but does not recover the ball. Frame208 changes to another wrong clothing candidate (113.97px); frame266 remains clothing confusion (462.13px). Three original catastrophic points remain and a new match12/001 frame83 error (164.06px, UNKNOWN cause) appears. Net count 6→4 must not be sold as recovered detections.
- Cross-Match match14/000 frame107: both tracks choose far-player clothing; TTI error286.85px. This is the one cross-match catastrophic error, not fixed.
- match17 recall drops 93.62%→80.85%. Aggregate recall hides this 12.77 percentage-point loss.
- Median localization worsens with alternative peak coordinates. Replacing box centers with discrete 512×288 heatmap peaks changes coordinate precision; association and coordinate refinement need separate development experiments.

TTI failure taxonomy sidecars: Development 64 failure records, 3 manually confirmed REFEREE_CLOTHING and 61 UNKNOWN (including misses/FP); Cross-Match 32 records, 1 confirmed PLAYER_CLOTHING and 31 UNKNOWN. UNKNOWN does not assert an absence of clothing effects. Raw and TTI errors remain separate; reviewed labels do not modify first benchmark JSON. Development has 78 unique union-error frames; cross-match has36. All have annotated images and neighbor/raw/TTI evidence.

Development-only motion probe: six RAW >20px cases have mean normalized GT-patch adjacent-frame difference .33484 versus wrong-target patch .09949 (global difference .02987). This is a small correlated sample affected by camera movement and contains GT-based diagnostic patches. It is not tracker input and was not enabled after freezing. No generalization claim follows.

Manual scene contact sheet shows elevated end-on, high end-on and lower side-oblique broadcast views with different shirt/background arrangements. Players/venue identities, exact camera movement and referee labels are UNKNOWN unless independently established. Frame rates span 25,30,50,59.94 and60fps. Manual scene metadata is a separate supplement, not retroactive predictor input.

### Performance (measured)

| Stage seconds | Development 2243 frames | Cross-Match 2267 frames |
|---|---:|---:|
| Decode + JPEG extraction | 50.456 | 52.949 |
| Background preprocessing | 44.634 | 44.486 |
| Model loading | 2.004 | 1.848 |
| Model phase including internal preprocess and candidate extraction | 118.622 | 118.639 |
| Candidate extraction (128 retained peaks, included above) | 5.162 | 4.990 |
| Prediction serialization | 0.261 | 0.254 |
| TTI tracker CPU replay (K16) | 0.884 | 0.907 |

Worker pipeline: Development216.016s /10.38fps; Cross-Match218.211s /10.39fps. Tracker CPU ~0.40ms/frame excluding JSON IO. GPU is RTX5060 Laptop, Torch2.10/CUDA12.8. Decode and JPEG write are not independently separated; the model phase includes internal preprocessing/decoding and extraction overhead. These are experiment timings, not live GUI throughput or calibrated performance claims. Some tests/build activity overlapped capture; no speed optimization claim.

Representative overlay generation only (MJPEG write + H.264 encode + subprocess overhead):
- tabletennis/match10/001 RAW: 6.417s, 300 frames; ffprobe frame count and dimensions verified.
- tabletennis/match10/001 TTI: 6.385s, 300 frames; ffprobe frame count and dimensions verified.
- tabletennis/match14/000 RAW: 3.389s, 144 frames; ffprobe frame count and dimensions verified.
- tabletennis/match14/000 TTI: 3.311s, 144 frames; ffprobe frame count and dimensions verified.

### Verification / delivery boundary

Full core/backend suite: **111 passed, 0 failed, 0 skipped, 1 warning** (existing Starlette httpx deprecation). Includes optional worker-runtime candidate checks and frozen-lock mutation test. Frontend TypeScript/Vite build passed. Windowed PyInstaller developer EXE built; PE subsystem WINDOWS_GUI. Fresh EXE API health, diagnostics and empty match library passed with OS-temp database and DEVELOPMENT banner; QA process stopped afterward. Native windows/menu/Save As/browser-open HTML/PDF remain MANUAL_GUI_CHECK_REQUIRED. No new GUI acceptance claimed.

Developer executable: dist/PTTI-Vision-Dev-tracker-v2/PTTI-Vision-Dev/PTTI-Vision-Dev.exe; size7,610,429 bytes; SHA256 `794b1c229bc0fa23dbc64ca2939b8521734d9f60b115a1125a57e0ce31ab1633`; embedded source commit `ac8ec05de571d63249de620cfdf96c7747183369` (before later evaluation-only scripts/config/results documentation). It is a local R&D build, not a release or Kaikai distribution.

Production DB was not connected during this experiment. QA used C:\Users\wang\AppData\Local\Temp\PTTI-tracker-v2-QA-c0f647ea317748b9973e176e37930670\matches.db. pytest used temporary isolation. No database migration/reset/recovery was attempted; prior forensic artifacts retained. Pilot1C REVISE/HOLD and Pilot2 NOT STARTED unchanged.

Main remains `2e709019911384b103124dc938beee72aa1deef5`; stable ptti-v0.1.2 tag object `5f6471b1da663d0b699091f18887da7cd92c9181` unchanged. Only local codex/ptti-v0.2-racketvision commits were made. No push/main merge/v0.2 tag/Release.

Local outputs/vision/tracker_v2 includes development_benchmark.json/html, cross_match_benchmark.json/html, failure_analysis.html, immutable RAW/candidate observations, tracker_config.json and SHA lock, all error-frame evidence, scene/review sidecars, official GT blob verification (20 files), development motion probe, overlays/profiles, build/test logs and temporary-QA evidence. Original forensic, baseline and Internal Holdout artifacts are retained.

Next step remains BallTrack development with new untouched cross-match evaluation after any further tuning. Do not begin RacketPose or TrajPred. Current gate decisions are engineering acceptance outcomes, not new research conclusions.
