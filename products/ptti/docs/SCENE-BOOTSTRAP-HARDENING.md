# Scene Bootstrap hardening (research-only)

## Baseline and use boundary

The initial desktop scene-bootstrap implementation is preserved in commit `39d5960aba34015702a6ffefd3a4d59b6ffe653e`. This evaluation uses only the official Extended OpenTTGames training split, pinned to dataset repository revision `36471a76b969a0340df59258a813bf8214e68e7c`. The data license is CC BY-NC-SA 4.0; use is research/non-commercial. No dataset media or extracted images are stored in Git, a product installer, or a release.

The local artifacts live under `%LOCALAPPDATA%\PTTI-Dev\vision-v2\scene-bootstrap`. The evaluation manifest records the source URL, source byte size, media probe, each sampled-frame SHA-256, and full source SHA-256 when the complete local file is available. `game_4.mp4` has a verified full-file SHA-256. The other four videos were read by sparse HTTP range seeks only; their full-file SHA-256 values are intentionally null. Their server ETags are not SHA-256 hashes.

## Sample and detector setup

Five different official training game files were sampled at 3%, 34%, 66%, and 97% of source duration, for 20 frames total. Each probed file was 1920×1080 at 120 fps; observed durations were 526–1435 seconds. The test split was not accessed. This is a sparse development evaluation, not an accuracy benchmark. Games 1–4 share a similar blue-curtain side-view setup; game 5 visibly differs in venue colors and background, but all samples remain fixed-camera indoor matches.

Grounding DINO remained isolated. Model, checkpoint, and threshold were unchanged: `IDEA-Research/grounding-dino-base`, revision `a062f8edaf7f3aa52714a8f80cb8db7de1e5e170`, checkpoint SHA-256 `5548f844c928c4b6f411fa8cbcc2bfa8dbbba437cb1d513975519f93c2a9ed21`, detector/text thresholds 0.25. The only selection refinement is geometric sanity: reject table candidates narrower than 20% of image width or smaller than 3% of image area, then select the highest-scoring remaining table candidate. It is still a coarse candidate box, not a mask.

## Observed candidate coverage

| Prompt | Table candidate frames | Both screen-side player candidates | Extra non-player-region boxes |
|---|---:|---:|---:|
| Existing prompt A / `person` | 20/20 | 11/20 (55%) | 25 |
| `player` term | 20/20 | 8/20 (40%) | 12 |
| `athlete` term | 20/20 | 10/20 (50%) | 13 |

Prompt A and the short `person` wording produced the same result. The alternate prompts did not improve both-side candidate coverage, so prompt A remains selected. These are screen-side candidate counts; there is no frame-level person ground truth, so the values are not recall or accuracy.

Prompt A per-game two-side candidate coverage was: game 1, 1/4 (25%); game 2, 2/4 (50%); game 3, 3/4 (75%); game 4, 4/4 (100%); game 5, 1/4 (25%). Small samples and the game 1/5 decline show that cross-match behavior is not stable enough for product readiness. In the 20 sampled frames, 15 had a screen-left candidate, 12 a screen-right candidate, 11 both, 4 left-only, 1 right-only, and 4 neither. These screen directions do not identify near/far or athlete identity.

The five manually estimated table boxes (one frame per game) use the complete visible table, including support legs. Exploratory visual box comparison produced mean IoU 0.933, mean width overshoot 0.5%, mean height overshoot 6.8%, and mean center deviation 9.7 px. These hand-estimated boxes are explicitly not calibrated annotations or a formal benchmark. They indicate the geometric filter selects a useful coarse prompt box in the sampled setup; the detector does not yet provide a validated precise tabletop boundary.

## Failures and unavailable evidence

`player_detection_failure_analysis.html` contains all 20 baseline sample frames, source images, detector overlays, and side-candidate status. The missing screen-side candidates are recorded; cause classes such as referee confusion, clothing contrast, occlusion, crop truncation, or duplicate detection remain `UNKNOWN` unless a human can verify them. Candidate output alone cannot distinguish these causes.

No real scene-cut source was found in this static-camera dataset sample. The current dataset cannot validate replay, close-up, between-point camera switching, or cut-triggered redetection; synthetic unit tests remain engineering checks only.

Scoreboard detections were 0/20 across all four prompts. The inspected game 1–4 sample frames visibly show small physical score displays near the umpire, so this is a detector miss on visible targets, not proof that the dataset lacks a scoreboard. OCR remains disabled.

## Desktop review behavior

The desktop Research Center now shows the five-game per-game candidate matrix and a cross-match image/overlay gallery. Users can review each frame, assign Near Player, Far Player, Referee, Other, or Unknown, and reject a false box. Corrections are stored separately from raw detections. The main 28-frame scene run yields 14 HIGH and 14 MEDIUM review-priority frames, with zero LOW / `LIKELY_OK` frames; the high-priority filter therefore reduces the initial list to 14, but automatic acceptance is not yet useful enough to claim.

## Gate

`SCENE_BOOTSTRAP_PARTIAL`. Table candidates are consistently available and the coarse boxes look suitable as prompts in this narrow sample. Dual-player candidate coverage is inconsistent, scoreboard detection misses visible displays, the cross-match sample is sparse, full source hashes are incomplete for four remote-read files, and real scene-cut behavior is untested. Do not start SAM 2 until a broader and independently reviewable player-evaluation set supports the product-readiness decision.
