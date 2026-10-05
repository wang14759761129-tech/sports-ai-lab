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

Training source labels the last included frame; upstream inference excludes frame i yet labels i. TTI subclasses only preprocessing to include output frame i, with repeat padding at the beginning. The upstream checkout remains untouched. Background is a deterministic sample of up to 100 frames from this one rally; it differs from upstream full-match median preprocessing and is recorded explicitly.

Each run records source, video/checkpoint/GT hashes, pinned upstream commit, current TTI SHA and dirty flag, device/config/runtime, alignment/background method and elapsed time. Cache key combines video hash, model hash, pipeline version, upstream SHA and device. Normalization, frames, median and prediction are reused only for a complete matching cache. Reports/overlays are regenerated per analysis ID. No user source file is overwritten.

## Outputs / limits

outputs/vision/<analysis_id> contains source.json, video_meta.json, quality.json, ball_track.json/csv, metrics.json, analysis.json, report.html, benchmark_report.html where applicable, ball_overlay.mp4 and logs. Full traceback stays in logs; Chinese UI shows a short failure and retains existing match functionality. One worker job at a time; no false percentage progress. Restart interrupts an active process; complete results remain on disk. CPU mode is explicit and may be slow.

Baseline/regression policy must be derived from reproducible measured results. Do not call the first baseline PASS; do not declare BallTrack stable merely because inference completed. Pilot 1C remains REVISE/HOLD; Pilot 2 NOT STARTED. Kaikai Test 01 remains pending.

Compare compatible measured analysis.json files with `python -m vision regression baseline.json candidate.json --tolerance 0.05`. The explicit default 5% relative tolerance is an engineering regression policy, not a scientific accuracy threshold. Different video/GT/checkpoint/device returns NOT_COMPARABLE; unavailable metrics remain unavailable. Report includes worker processing FPS, processing/video-duration factor, measured Windows process peak RAM and peak allocated CUDA memory (not total GPU reservation). Warm cache runs must not be described as new inference speed measurements.

Windows frame read/write uses NumPy file IO plus OpenCV encoding/decoding so Chinese paths are supported. Upstream source is not edited.
