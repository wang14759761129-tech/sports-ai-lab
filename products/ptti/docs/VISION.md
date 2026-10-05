# PTTI v0.2 experimental visual perception

RacketVision is the official AAAI 2026 ball / racket / trajectory project by Linfeng Dong et al. TTI uses a pinned external runtime; it is a perception layer, not a replacement for the existing match/evidence engine. See THIRD_PARTY_NOTICES.md and VISION-PREFLIGHT.md for source/license/audit.

## Architecture

Local / licensed video → FFprobe metadata / centralized quality gate → optional H.264 CFR normalization preserving resolution → isolated worker / frame preparation → official BallTrack model → TTI observation schema → sparse GT benchmark → JSON / HTML / MP4 overlay → Chinese desktop UI.

FastAPI never imports torch, MMCV, MMDetection or MMPose. Existing CSV analytics / SQLite matches stay unchanged. Video observations do not automatically create serve, receive, bounce, third-ball, spin, shot-type, winner or tactical fields. VisionEvent only reserves typed evidence hooks; no fabricated events.

## Setup (Windows, explicitly opted in)

From products/ptti, after the normal desktop development environment exists:

```powershell
powershell -File scripts/setup_vision.ps1
powershell -File scripts/setup_vision.ps1 -Install -DownloadSample
.venv/Scripts/python.exe -m vision doctor
.venv/Scripts/python.exe -m vision benchmark --device cuda
.venv/Scripts/python.exe -m vision analyze path/to/owned.mp4 --device cpu
cmd /c scripts\build_vision_windows.bat
```

The first command only checks. Explicit -Install downloads the official 2.7 GiB Windows PyTorch 2.10/CUDA 12.8 wheel, verifies its published SHA256, and installs it into vision_worker/.venv. -DownloadSample fetches only one test rally, its sparse GT, test split index and 44.4 MiB BallTrack weights. No model/video download occurs at app startup or analysis submission. Failed downloads remain inspectable. Setup never upgrades desktop dependencies.

Paths are configurable via PTTI_VISION_HOME or individual PTTI_VISION_DATASET_ROOT, MODEL_ROOT, CACHE_ROOT, OUTPUT_ROOT, RUNTIME_ROOT and PYTHON. Defaults are product-local ignored folders. For the developer EXE set PTTI_VISION_HOME to the configured product workspace; the heavy worker is an external prerequisite, not bundled in the EXE. This is not a consumer v0.2 release or automatic installer.

## Inputs / model scope

MP4/MOV/MKV/AVI; experimental short clips up to 60 seconds / 1800 frames. No resolution downgrade is performed by normalization. The official neural network internally operates at 512×288, then decodes pixel coordinates into original frame dimensions. Each visible position includes frame, timestamp, pixel/normalized coordinates and model; invisible coordinates are null. Upstream confidence is an uncalibrated heatmap score, not a calibrated confidence probability.

RacketPose and TrajPred are not implemented. Installation is intentionally gated behind stable BallTrack evaluation. No MMCV source compilation, WSL setup or advanced model download is performed until needed. The core desktop remains available when a vision module is absent.

## Benchmark correctness

The official sample is tabletennis/match1/000 in test split. Ground truth is sparse: only annotated frames are evaluated; unannotated frames are not negatives. Report visibility recall and missed annotated balls, error mean/median/P90/P95 in original pixels, normalized error, annotated negative counts. False-detection assessment is unavailable when there are no negative annotations. No precision/F1 or PASS threshold is invented. This one-rally result is not the official full-dataset score or research validation.

## Bounded multi-clip suite

The downloader can select 5–10 rally clips from the pinned official table-tennis test split, round-robin across distinct match IDs before taking a second rally from any match. It downloads only each selected video and its paired ball CSV, validates the official file size and LFS SHA256, and never downloads the full dataset:

```powershell
.venv\Scripts\python.exe scripts\download_vision_sample.py --benchmark-suite --suite-clips 10
.venv\Scripts\python.exe -m vision suite --device cuda --force-recompute
```

Each suite writes `benchmark_suite.json`, `benchmark_suite.html`, and up to 20 annotated worst-case PNGs plus a contact sheet under `outputs/vision/benchmark_suite_<id>/`. GT crosses are green and predictions red. Misses and localization outliers are both retained for inspection; failure cause remains `unknown` until visually confirmed. Reports include per-clip and aggregate sparse-GT metrics, annotation-negative false detections, runtime phase totals, source hashes, pinned revisions and threshold status. `clips_passed` remains null because this experiment has no preregistered acceptance threshold. Reports stay `BASELINE_ONLY`.

The worker records frame extraction, bounded background sampling, model load, model inference and prediction serialization separately. The parent also records normalization, metric/CSV postprocessing and overlay encoding. `processing_fps` is end-to-end worker throughput, not model-only FPS; CUDA inference timing synchronizes at the measured inference boundaries.

Training source labels the last included frame; upstream inference excludes frame i yet labels i. TTI subclasses only preprocessing to include output frame i, with repeat padding at the beginning. The upstream checkout remains untouched. Background is a deterministic sample of up to 100 frames from this one rally; it differs from upstream full-match median preprocessing and is recorded explicitly.

Each run records source, video/checkpoint/GT hashes, pinned upstream commit, current TTI SHA and dirty flag, device/config/runtime, alignment/background method and elapsed time. Cache key combines video hash, model hash, pipeline version, upstream SHA and device. Normalization, frames, median and prediction are reused only for a complete matching cache. Reports/overlays are regenerated per analysis ID. No user source file is overwritten.

## Outputs / limits

outputs/vision/<analysis_id> contains source.json, video_meta.json, quality.json, ball_track.json/csv, metrics.json, analysis.json, report.html, benchmark_report.html where applicable, ball_overlay.mp4 and logs. Full traceback stays in logs; Chinese UI shows a short failure and retains existing match functionality. One worker job at a time; no false percentage progress. Restart interrupts an active process; complete results remain on disk. CPU mode is explicit and may be slow.

Baseline/regression policy must be derived from reproducible measured results. Do not call the first baseline PASS; do not declare BallTrack stable merely because inference completed. Pilot 1C remains REVISE/HOLD; Pilot 2 NOT STARTED. Kaikai Test 01 remains pending.

## Measured single-rally baseline (2026-10-05)

Host: Windows 11, RTX 5060 Laptop GPU (8 GiB, driver 616.64), CUDA 12.8, isolated PyTorch 2.10.0+cu128. Input: official `tabletennis/match1/000`, 1920×1080 H.264, 25 FPS, 5 seconds / 125 frames; 25 visible GT annotations and zero annotated negatives. Checkpoint SHA256: `00d707b9db7a49561c411e4765956e79bcd7c7e20c7a0a535073440b3e972342`.

GPU fresh inference: 25/25 annotated visible detections (recall 1.0), mean position error 2.44 px, P95 4.85 px; 8.76 processed FPS, 2.85× slower than input duration, peak allocated VRAM 0.685 GiB and process peak RAM 2.38 GiB. A repeated GUI-triggered cache run reproduced the same metrics. CPU fresh inference: same 25/25 recall, mean error 2.52 px, P95 4.85 px; 2.13 FPS, 11.72× slower than input duration and 2.95 GiB peak process RAM. Both reports remain `BASELINE_ONLY`; false detections cannot be assessed without negative annotations, and 25 frames from one rally do not establish model stability. The production GUI was clicked through the cached official benchmark; generated 1920×1080/125-frame MP4 played and displayed an overlaid ball path.

Measured run records are local under outputs/vision and are ignored by Git. Their initial inference provenance records TTI commit `87ff12b`; the working tree was dirty because setup and lockfile changes were pending. The documented media and weight SHA values let later runs check the exact inputs.

## Measured 10-clip test-split suite (2026-10-05)

This clean, forced-recompute CUDA run used 10 rallies selected round-robin from five distinct matches in the pinned official test split. It is a bounded engineering sample, not the full dataset or an independent research validation. See the [official RacketVision repository](https://github.com/OrcustD/RacketVision) and [dataset card](https://huggingface.co/datasets/linfeng302/RacketVision) for upstream data details. The exact run is `benchmark_suite_20261005T113747` under ignored local outputs.

Across 250 annotated frames there were 208 visible-ball annotations, 164 detections, and 44 misses (78.85% visible recall). There were 42 annotated-negative frames and 10 predictions on them. The 164 co-visible pairs had a 14.68 px weighted mean error, 2.24 px median, and 10.58 px P95. Metrics use sparse annotations only; unannotated frames are not negatives. Nine clips had at least one missed visible annotation or annotated-negative false detection. No pass threshold was preregistered, so `clips_passed` remains null and the suite is `BASELINE_ONLY`.

| Test rally | Visible GT | Detected | Recall | Mean / P95 error (px) | Worker pipeline (s) | Pipeline FPS | Misses | Annotated-negative false detections |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| match1/000 | 25 | 25 | 100.0% | 2.44 / 4.85 | 13.80 | 9.06 | 0 | — |
| match10/000 | 20 | 15 | 75.0% | 2.18 / 5.39 | 27.21 | 11.02 | 5 | 1 |
| match11/000 | 22 | 14 | 63.6% | 2.70 / 5.35 | 26.82 | 11.19 | 8 | 0 |
| match12/000 | 17 | 12 | 70.6% | 3.65 / 7.49 | 14.24 | 8.71 | 5 | 0 |
| match13/000 | 22 | 19 | 86.4% | 5.71 / 12.51 | 24.19 | 10.67 | 3 | 1 |
| match1/001 | 15 | 14 | 93.3% | 2.33 / 3.54 | 12.42 | 9.98 | 1 | 4 |
| match10/001 | 22 | 9 | 40.9% | 217.87 / 448.10 | 26.55 | 11.30 | 13 | 2 |
| match11/001 | 25 | 22 | 88.0% | 2.35 / 5.39 | 24.55 | 12.22 | 3 | — |
| match12/001 | 21 | 16 | 76.2% | 2.36 / 3.61 | 13.55 | 9.15 | 5 | 0 |
| match13/001 | 19 | 18 | 94.7% | 2.25 / 4.31 | 25.75 | 11.18 | 1 | 2 |

One outlier drives the difference between median and mean: visual review found six large-error frames in `match10/001` where predictions landed on a seated official's bright pink clothing behind the table while GT marked the ball. This is labelled background-person/clothing confusion. Other inspected misses remain unclassified where the cause was not clear; the review covers the 20 selected worst cases, not every frame. No evidence supports assigning motion blur, white-line confusion, camera-cut, or table-bounce causes to the remaining errors.

The worker processed 2,243 frames in 209.09 seconds, or 10.73 end-to-end worker FPS. CUDA model inference accounted for 114.50 seconds; frame extraction 50.25 seconds and background preprocessing 42.30 seconds were also substantial. Overlay encoding added 49.61 seconds outside worker throughput. Model-only rate is therefore not application end-to-end speed, and the suite does not demonstrate real-time analysis.

Compare compatible measured analysis.json files with `python -m vision regression baseline.json candidate.json --tolerance 0.05`. The explicit default 5% relative tolerance is an engineering regression policy, not a scientific accuracy threshold. Different video/GT/checkpoint/source/pipeline/device/runtime/GPU returns NOT_COMPARABLE; unavailable metrics remain unavailable. Report includes worker processing FPS, processing/video-duration factor, measured Windows process peak RAM and peak allocated CUDA memory (not total GPU reservation). Warm cache runs must not be described as new inference speed measurements.

Windows frame read/write uses NumPy file IO plus OpenCV encoding/decoding so Chinese paths are supported. Upstream source is not edited.
