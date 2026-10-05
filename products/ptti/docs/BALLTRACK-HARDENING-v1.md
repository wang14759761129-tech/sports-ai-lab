# BallTrack postprocessing v1 — development and holdout (2026-10-05)

Status: **BASELINE_ONLY**. The optional TTI layer is implemented, but rejection is **EXPERIMENTAL_NOT_ENABLED**. No RacketVision upstream model/source was modified. No RacketPose, TrajPred, release or main merge occurred.

## Frozen inputs and leakage control

Development is the original ten `/000` and `/001` rallies across match1, match10, match11, match12 and match13. Development reused the original saved raw predictions, whose hashes are recorded; the original baseline files are unchanged. The five holdout rallies are `/002` from those five matches, selected solely by pinned official split order before reading their GT or predictions. They are rally-disjoint, not match-disjoint, and cannot establish generalization to new camera/match environments.

Parameter SHA256: `8ae9f064aba4d29320127c4a9f2bb5aceb039e137c4ba9d2a5a9e5e0e6e214e7`. Split SHA256: `2edbc1b18cff6e9603921e10831704fff21aa403de1fa4acd7ae38317fbd156c`. Holdout inference/evaluation ran from clean commit `8fbbbc201bee20525958420ca57840323dc1f56a`, with matching lock. Development evaluation originally recorded dirty source at fc7df79 while implementation was pending; that provenance is retained. No parameters changed after viewing holdout. Future tuning requires a new untouched holdout.

## Raw versus explicit experimental rejection

| Set / mode | Visible GT | Detected | Recall | Negative GT / false predictions | Mean / median / P95 px |
|---|---:|---:|---:|---:|---|
| Development RAW | 208 | 164 | 78.85% | 42 / 10 | 14.68 / 2.24 / 10.58 |
| Development FILTERED | 208 | 162 | 77.88% | 42 / 8 | 11.13 / 2.24 / 8.60 |
| Holdout RAW | 90 | 84 | 93.33% | 35 / 3 | 4.13 / 2.24 / 6.91 |
| Holdout FILTERED | 90 | 84 | 93.33% | 35 / 3 | 4.13 / 2.24 / 6.91 |

Visibility recall counts any visible prediction, even a catastrophically wrong coordinate. The two development visible-GT predictions rejected at match10/001 frames 208 and 243 were known catastrophic outliers, not accurately localized detections. Removing them still reduces the formally defined visibility recall. Four other clothing outliers, including frame 184, survive the filter. Error metrics are conditional on co-visible retained predictions and must not be interpreted independently of recall. Annotation-only/default behavior preserves all RAW observations and metrics.

## Rules and limits

TTIBallTrackPostProcessor retains each raw prediction, filtered prediction, suspect flag, rejected flag, filter reason and measured velocities. A candidate is a TEMPORAL_OUTLIER only when both neighbor jumps exceed a robust local velocity allowance while neighbors form a plausible bridge. All distances are normalized by frame diagonal and time by FPS; the allowance uses nearby median velocity and a dimensionless floor, not fixed pixels. This is an offline bidirectional plausibility test, not a physical law; fast balls, contacts and occlusion can invalidate the assumption.

STATIC_PERSISTENCE uses a time window, visibility fraction and normalized spatial radius. A real slow ball can satisfy this prior, so it is advisory by default. It did not trigger on these fifteen clips. Smoothly moving clothing can pass both rules. No table ROI clipping is applied: inspected frames include annotated balls outside table geometry, and no validated table detector is available. Scene context remains a future soft-prior seam, not a claimed implemented detector.

## Complete error dataset and taxonomy

Development collected all 44 missed visible annotations, all 10 annotated-negative false detections and all 6 errors exceeding the reporting-only threshold of 1% of frame diagonal: 60 error records. Holdout has 6 misses, 3 annotated-negative false detections and one high-error record: 10 records. Each includes image, video/frame, GT, raw prediction, previous/next predictions, real model confidence when present, error and filtered observation.

Development taxonomy: REFEREE_CLOTHING=6; UNKNOWN=54. Holdout: UNKNOWN=10. PLAYER_CLOTHING, WHITE_TABLE_LINE, NET, BACKGROUND_LIGHT, MOTION_BLUR, OCCLUSION, CAMERA_MOTION, BALL_NEAR_BODY and BALL_NEAR_TABLE each remain 0 **confirmed** causes; zero does not prove absence. All error contact sheets were inspected; ambiguous cases remain UNKNOWN. Existing full-frame referee-clothing review was retained without assigning that cause to unreviewed frames.

## Real heatmap diagnosis

The adapter now optionally saves actual sigmoid heatmaps and all thresholded component summaries without modifying upstream inference. The upstream decoder chooses the largest thresholded component bounding box and reports its mean heatmap value; this is not calibrated probability. The diagnostic replay of match10/001 exactly reproduced all 300 baseline predictions.

At annotated frame 184, the 5×5 model-grid region centered on GT had peak **0.037384**, while the clothing component had global peak **0.645996**, bounding-box mean **0.543945**, and was the only candidate above 0.5. The real ball was absent from thresholded candidates. Changing largest-box to highest-peak selection would not recover this frame. Heatmaps for 184/186/188/189/191/194 and all 300 candidate summaries are retained; only frame 184 among those maps has sparse GT for direct local-response comparison. No confidence was fabricated.

## Artifacts and reproduction

Local ignored artifacts:

- outputs/vision/hardening_v1/development/failure_analysis.html
- outputs/vision/hardening_v1/holdout/failure_analysis.html
- Both sets contain raw-vs-filtered.json, per-frame raw/filtered JSON and benchmark_errors/ with all images, contact sheets and errors.json.
- outputs/vision/diagnostics_match10_001/ contains raw_prediction.json, candidate_diagnostics.json, heatmaps/*.npz and gt-vs-heatmap.json.

```powershell
.venv/Scripts/python.exe scripts/download_vision_holdout.py
.venv/Scripts/python.exe -m vision.hardening --baseline outputs/vision/benchmark_suite_20261005T113747/benchmark_suite.json --split-manifest datasets/racketvision/balltrack-split-v1.json --output outputs/vision/new-evaluation/development --split development
.venv/Scripts/python.exe -m vision.hardening --baseline outputs/vision/benchmark_suite_20261005T113747/benchmark_suite.json --split-manifest datasets/racketvision/balltrack-split-v1.json --output outputs/vision/new-evaluation/holdout --split holdout
```

The standalone analyse command accepts optional --postprocess annotate or --postprocess reject; no GUI/product rejection toggle is enabled. Raw ball_track.json/csv and raw overlay remain unchanged. Rejection is not promoted because the holdout showed no benefit and development misses increased under visibility-recall semantics.

## Performance and desktop verification

Original development worker pipeline: 2,243 frames / 209.09 seconds = 10.73 FPS; model inference 114.50 seconds, extraction 50.25, background 42.30; overlay adds 49.61 seconds outside that throughput. Fresh holdout worker pipeline: 1,149 frames / 106.83 seconds = 10.76 FPS. These are worker pipeline rates, not live GUI throughput or postprocessor-only timings. No new speed optimization was applied.

Core/backend regression: 99 passed, 0 failed, one Starlette httpx deprecation warning. Native Save As, GUI click paths, independently browser-opened exported HTML and PDF/print remain MANUAL_GUI_CHECK_REQUIRED. API export-content evidence from the preceding run remains valid but does not verify OS dialogs. Pilot 1C REVISE/HOLD; Pilot 2 NOT STARTED.
