# BallTrack v1 frozen: Official RAW remains default

Vision Gate: `BALLTRACK_V1_FROZEN_RAW`. Release Gate: `HISTORICAL_DB_UNVERIFIED`. This finite tuning pass is complete. No production database access, release, merge, tag, RacketPose or TrajPred.

## A. Background reproduction

Upstream `create_median.py` sorts rally directories and frame paths, optionally chooses global evenly spaced indices from the combined frame list, computes a uint8 per-pixel median, and writes match-level `median.npz` (key `median`) plus PNG. The loader prefers this match-level asset, then a rally-level fallback. The earlier experiment sampled up to 100 frames inside each rally. This pass used the global sampling/median operation across all selected rally videos available for each match. It is the closest reproducible source-backed approximation, not a complete-match median: missing rallies and breaks are absent.

## B. Expanded TRAIN / DEV

TRAIN: 24 clips / 16 matches; DEV: 12 clips / 9 matches; KNOWN: 25 clips / 11 matches. Match IDs are disjoint across roles. Frames are 1920×1080. Venue, camera, lighting, apparel and referee metadata were not reliably available and remain UNKNOWN.

## C–E. Fine-tuning and decoder

One architecture-preserving run: Adam 1e-5, batch 2, seed 20261005, 15-epoch cap, patience 4, unchanged loss/mixup and upstream metric. It stopped after 10 epochs; best epoch 6 by DEV F1 0.930057; training took 1629.70s on NVIDIA GeForce RTX 5060 Laptop GPU (2.10.0+cu128, CUDA 12.8). DEV decoder study covered five thresholds (.35–.55), contour-box/global-max decoding and no/weighted-centroid/soft-argmax refinement. Selected setting stayed at threshold .50, largest contour box, no refinement. The 5×5 subpixel methods worsened mean/median error; threshold .40 raised recall but also >20px errors. No complex temporal tracker was reintroduced.

## F. KNOWN evaluation: A Official RAW vs D tuned candidate

| Measure | A RAW | D candidate |
|---|---:|---:|
| Recall | 87.4286% | 86.6667% |
| False positives / negative frames | 15/100 | 15/100 |
| Mean px | 8.020 | 12.399 |
| Median px | 2.236 | 2.236 |
| P95 px | 7.635 | 7.867 |
| >20 px | 8 | 11 |
| >50 px | 8 | 11 |
| >100 px | 7 | 10 |
| Official F1 | 0.898899 | 0.888442 |

Peak ranks (out of 525 visible frames), cumulative: A `{'1': 477, '4': 488, '8': 493, '16': 497, '32': 499, '64': 504, 'visible': 525, 'greater_than64': 6, 'no_nearby_peak': 15}`; D `{'1': 479, '4': 494, '8': 502, '16': 505, '32': 509, '64': 513, 'visible': 525, 'greater_than64': 2, 'no_nearby_peak': 10}`.

Fixed `match10/001 frame184` regression: A ball/clothing heatmap response .0445/.6646, GT rank 35; D .0517/.6504, rank 19. D improved ranking, but decoder landed at the same distractor coordinate with 429.79px error. This did not resolve the pink-referee failure. Heatmap responses are not calibrated confidence.

The candidate failed acceptance: recall fell, mean/P95 and all catastrophic buckets worsened, while FP count stayed level. Official RAW remains default.

## G. Final untouched evaluation

Not selected or run: D failed KNOWN acceptance, and the pinned official match pool had already been exposed. No >=5-match unseen authorized test was consumed.

## H–I. Frozen default and hashes

Default checkpoint SHA256: `00d707b9db7a49561c411e4765956e79bcd7c7e20c7a0a535073440b3e972342`. Rejected D checkpoint SHA256: `d325ab5e1a179b3c7369f3cfffd9cf02626020ad4bbf177dd481f6868bdb6775`. Frozen config SHA256: `439a8f36fd37a47e780e32f2ae437bf367d3e05d997aeac879b69d548f60cacb`.

## J–L. Verification and gates

Prior full suite: 124 passed, 0 failed, one existing Starlette/httpx deprecation warning. Training, GPU inference, decoder sweep and KNOWN evaluation completed. See Git history for code/test state; this report does not claim native GUI verification.

Branch: `codex/ptti-v0.2-racketvision`. Release Gate remains `HISTORICAL_DB_UNVERIFIED`; Vision Gate is `BALLTRACK_V1_FROZEN_RAW`. No main merge, tag or release.

## M. Limitations and real-match phase

This is a bounded rally dataset, not full-match validation. Cross-match venue/camera/apparel diversity is unverified. Sparse annotations limit interpretation between labeled frames. Existing worker is capped at 1,800 frames and does not segment points/rallies. The only local personal MP4 found was a 22.45-second clip and was not used; no complete authorized WTT match was identified. The real professional-match pipeline therefore awaits a full-match local video path. Development and QA databases remain isolated from Production.
