# Specialist v1 — completed pilot

Release Gate: HISTORICAL_DB_UNVERIFIED
Vision Gate: BALLTRACK_MODEL_IMPROVEMENT_FAILED

Neither candidate passes. No final untouched test was selected or run. RAW remains default; rejected Tracker V1 remains disabled. No production DB access, merge, tag, release, RacketPose or TrajPred.

These are 625 sparse annotated frames, not all video frames. Recall below is visibility coverage: wrong-position detections also count as detected and are penalized by error buckets. Official F1 includes wrong-localization failures. Error percentiles use visible GT with a decoded prediction; misses are reported separately. All frames are 1920×1080. Responses are uncalibrated sigmoid heatmap outputs.

| Model | Detected / 525 | Recall | FP / 100 | Mean px | Median px | P95 px | >20 | >50 | >100 | Official F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 456 | 86.8571% | 15 | 7.7602 | 2.2361 | 7.1233 | 8 | 8 | 8 | 0.897590 |
| B | 457 | 87.0476% | 20 | 10.2454 | 2.2361 | 7.6547 | 10 | 9 | 9 | 0.890220 |
| C | 452 | 86.0952% | 17 | 10.8565 | 2.2361 | 7.4312 | 10 | 10 | 10 | 0.887324 |

## Peak ranks (cumulative counts / 525)

| Model | 1 | ≤4 | ≤8 | ≤16 | ≤32 | ≤64 | >64 | No nearby peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 475 | 485 | 491 | 497 | 500 | 507 | 5 | 13 |
| B | 478 | 495 | 501 | 501 | 506 | 511 | 1 | 13 |
| C | 479 | 495 | 502 | 504 | 506 | 512 | 3 | 10 |

## Clothing witness: match10/001 frame184

| Model | True response | Clothing response | GT rank | Pixel error |
|---|---:|---:|---:|---:|
| A | 0.037323 | 0.645508 | 57 | 428.78899239602686 |
| B | 0.046631 | 0.561035 | 32 | 428.78899239602686 |
| C | 0.043365 | 0.546387 | 35 | 428.78899239602686 |

## Per-match known evaluation (not untouched generalization)

| Match | Model | Detected / visible | FP | Mean | Median | P95 | >20 / >50 / >100 |
|---|---|---:|---:|---:|---:|---:|---|
| match1 | A | 64/65 | 4 | 2.440 | 2.236 | 4.243 | 0 / 0 / 0 |
| match1 | B | 64/65 | 5 | 2.303 | 2.236 | 4.147 | 0 / 0 / 0 |
| match1 | C | 64/65 | 4 | 2.381 | 2.236 | 4.921 | 0 / 0 / 0 |
| match10 | A | 37/55 | 4 | 55.316 | 2.828 | 363.292 | 6 / 6 / 6 |
| match10 | B | 38/55 | 4 | 82.884 | 2.532 | 479.258 | 7 / 7 / 7 |
| match10 | C | 38/55 | 3 | 69.244 | 2.699 | 433.617 | 7 / 7 / 7 |
| match11 | A | 48/60 | 2 | 2.182 | 2.000 | 4.762 | 0 / 0 / 0 |
| match11 | B | 45/60 | 4 | 3.169 | 2.000 | 6.719 | 1 / 0 / 0 |
| match11 | C | 45/60 | 3 | 2.228 | 2.236 | 3.606 | 0 / 0 / 0 |
| match12 | A | 44/56 | 0 | 5.113 | 2.532 | 6.288 | 1 / 1 / 1 |
| match12 | B | 46/56 | 0 | 4.830 | 2.236 | 6.264 | 1 / 1 / 1 |
| match12 | C | 46/56 | 0 | 4.717 | 2.236 | 6.083 | 1 / 1 / 1 |
| match13 | A | 55/62 | 3 | 4.061 | 3.162 | 8.224 | 0 / 0 / 0 |
| match13 | B | 55/62 | 4 | 4.183 | 3.162 | 8.019 | 0 / 0 / 0 |
| match13 | C | 55/62 | 4 | 4.001 | 3.162 | 9.110 | 0 / 0 / 0 |
| match14 | A | 41/44 | 0 | 9.116 | 2.000 | 3.606 | 1 / 1 / 1 |
| match14 | B | 41/44 | 0 | 9.147 | 2.000 | 3.606 | 1 / 1 / 1 |
| match14 | C | 41/44 | 0 | 8.954 | 2.000 | 5.000 | 1 / 1 / 1 |
| match15 | A | 38/43 | 0 | 1.758 | 1.707 | 3.024 | 0 / 0 / 0 |
| match15 | B | 39/43 | 0 | 1.800 | 1.414 | 4.047 | 0 / 0 / 0 |
| match15 | C | 37/43 | 0 | 1.654 | 1.414 | 3.032 | 0 / 0 / 0 |
| match16 | A | 40/46 | 2 | 2.433 | 2.000 | 5.099 | 0 / 0 / 0 |
| match16 | B | 43/46 | 3 | 2.516 | 2.236 | 5.001 | 0 / 0 / 0 |
| match16 | C | 42/46 | 3 | 22.457 | 2.000 | 5.056 | 1 / 1 / 1 |
| match17 | A | 44/47 | 0 | 2.157 | 2.236 | 3.941 | 0 / 0 / 0 |
| match17 | B | 44/47 | 0 | 2.139 | 2.000 | 3.941 | 0 / 0 / 0 |
| match17 | C | 44/47 | 0 | 2.143 | 2.000 | 4.105 | 0 / 0 / 0 |
| match18 | A | 20/22 | 0 | 2.541 | 2.532 | 4.599 | 0 / 0 / 0 |
| match18 | B | 17/22 | 0 | 2.584 | 2.828 | 5.211 | 0 / 0 / 0 |
| match18 | C | 16/22 | 0 | 2.221 | 2.236 | 3.979 | 0 / 0 / 0 |
| match19 | A | 25/25 | 0 | 3.963 | 3.162 | 8.296 | 0 / 0 / 0 |
| match19 | B | 25/25 | 0 | 3.953 | 3.162 | 8.296 | 0 / 0 / 0 |
| match19 | C | 24/25 | 0 | 3.538 | 3.162 | 6.614 | 0 / 0 / 0 |

## Runtime and limits

Evaluation time includes dataset IO, CUDA inference, candidate-rank extraction and compressed heatmap evidence writing; it is not pure model FPS. Training time includes DEV evaluation. No stage profiler or real-time claim.

TRAIN: match20–27,16 clips,400 annotations. DEV: match28–31,7 clips,175 annotations. KNOWN:11 matches,25 clips,625 annotations. All three roles are match-disjoint; official parent exposure is separately tracked. Official metadata covers all50 matches, so genuinely model-unseen final games must come from a new trustworthy source.

C changes only TRAIN sampling weight1→3 for four mined peaks; DEV has three mined peaks and is never sampled for training. Both use identical parent, seed, architecture, loss, mixup, learning rate1e-5, batch2,3 epochs and400 draws/epoch. Seven reviewed crops remain UNKNOWN; no color rule or claimed referee category is inferred from a cropped object alone.

Small training coverage and GT-free rally-median proxy limit interpretation. Stop this pilot; do not tune against KNOWN results or claim all model fine-tuning is disproven. Future training needs broader TRAIN/DEV coverage and reproducible backgrounds before a separately preregistered experiment. Native GUI remains MANUAL_GUI_CHECK_REQUIRED. Original111 tests retained;124 passed,0 failed,1 existing Starlette deprecation warning.

B: best DEV epoch 2, training+DEV 293.78s, checkpoint SHA256 `69ba51636a56ae87d0c2d0ba02377a2bda009e9ac7aeb93aaa7c27a8aa6fd041`; known evaluation 126.65s.
C: best DEV epoch 1, training+DEV 299.33s, checkpoint SHA256 `7c67a9f12b39e55b8dd4751133488c88ca9a208d7dcd41e8e5b4eb94a28eebd2`; known evaluation 114.94s.
