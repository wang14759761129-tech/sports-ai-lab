# Practical person detector pivot — 2026-10-06

Current person gate: `PERSON_DETECTOR_PARTIAL`. Scene gate: `SCENE_BOOTSTRAP_PARTIAL`. Release gate: `HISTORICAL_DB_UNVERIFIED`. BallTrack v1 remains frozen RAW. No SAM2, pose, OCR, new release, main merge or production database access.

## Actual runtime and product behavior

RT-DETR R18 ran on CUDA using the existing isolated Transformers packages. It is the detector used by the new **Person Preview research gallery**, not a broadly validated production default. Grounding DINO table boxes and frozen person comparison evidence remain unchanged. The desktop imports no torch/Transformers; it reads versioned worker artifacts and records separate user corrections. A missing/invalid artifact is an explicit unavailable state; existing scene evidence remains accessible. RTMDet stays blocked and preserved.

`PersonDetector` is a framework-neutral contract. Grounding DINO and RT-DETR implementations use injected worker inference; the existing RTMDet adapter remains available. RT-DETR postprocessing scales boxes once to original image dimensions, clips to the source, filters COCO person, and preserves raw scored observations. The display projection uses IoU 0.7 duplicate suppression. Scores are uncalibrated detector scores.

## Fixed development evaluation

The original 5 Extended OpenTTGames training games / exact 20 frames are identified by manifest SHA256 `67bc35a5a1570d4610e524141030f1c93aa5b2a8516767f12023d4eb9f75276f`. The manifest was not overwritten. Test split remains unread. Data use is CC BY-NC-SA 4.0 research/non-commercial; data and annotations remain outside Git and packages.

All 20 frames were visually inspected. Four show no players, two show one player, and fourteen show two visible players, including partially cropped bodies. Approximate visible-body boxes were drawn by Codex into `person_detector_dev_gt.json`. This is **ASSISTANT_VISUAL_ANNOTATION_DRAFT**, not independent human ground truth. Near/far physical depth is not established for this side-view data; that accuracy is unavailable. The actor/source must not be relabeled human-verified.

Primary matching is one-to-one box IoU >=0.3; IoU >=0.5 is also saved. No forced two-player denominator in empty/off-camera frames. The frozen 55% metric is opposing-side candidate coverage from old role rules, not person detection recall.

| Same approximate visual matching, primary IoU 0.3 | Grounding DINO | RT-DETR R18 |
| --- | ---: | ---: |
| Matched visible player boxes | 30/30 | 30/30 |
| Both players matched when both visible | 14/14 | 14/14 |
| Both matched over all 20 frames | 14/20 | 14/20 |
| Mean matched box IoU | 0.8967 | 0.9018 |
| Non-player human candidates (mostly referees; not detector false positives) | 24 | 15 |
| Player-role proposals matching player boxes | 20/20 | 20/20 |
| Referee proposed as player | 0 | 0 |
| High-priority review frames, same new resolver | 12/20 | 10/20 |

Only thresholds 0.25 / 0.4 / 0.55 were compared on development. At 0.25: 30 player matches, 27 non-player candidates; at 0.4: 30 and 15; at 0.55: 29 and 8. Choose 0.4 to retain the clipped player. `person_detector_config.json` SHA256 `5e38438eaf163478cfce7da6e1f42e1b75c45154ef1cef549e1db33466d27800` was frozen before selecting/inferencing new matches. No validation tuning.

## Independent match-source check

Extended OpenTTGames contains only five official training game sources, already all used by development. Do not relabel new timestamps as independent matches or access its official test split. Instead select five already local official **RacketVision TRAIN** clips, in train-index order: `match20/001`, `match21/002`, `match22/002`, `match23/002`, `match24/002`. They are new to this person development set but were exposed in earlier BallTrack research, so they are not universally untouched. Dataset card declares MIT; use is research only, with no independent WTT broadcast-license assertion. No broadcast download is performed.

Manifest was written before inference, records source SHA/size/media, frame hashes, official train-index hash and frozen config hash. Four deterministic frames per clip (20%,40%,60%,80%), 20 frames total. Both models are run in stages: table detector unloads before RT-DETR. No parameters were changed afterward.

| Match | Table candidates | Both role candidates | High-priority review |
| --- | ---: | ---: | ---: |
| match20 | 4/4 | 4/4 | 4/4 |
| match21 | 4/4 | 3/4 | 1/4 |
| match22 | 4/4 | 0/4 | 4/4 |
| match23 | 4/4 | 4/4 | 0/4 |
| match24 | 4/4 | 0/4 | 4/4 |
| Total | 20/20 | 11/20 | 13/20 |

Post-inference Codex visual review of the 20 frames also created an explicitly provisional box draft: 40/40 visible players matched, 20/20 both-player frames matched, mean IoU 0.8883. Of 22 near/far role proposals, 22 matched the corresponding visually assigned player. These are sparse provisional measurements, not independent human-certified accuracy. Role recall is only 22/40: the detector sees the players, but front-on crowded scenes leave them UNKNOWN. Background spectators are legitimate person detections; they must not be falsely reported as detector false positives.

## Role and review limits

The resolver uses opposing horizontal table-side context and an image-footpoint depth proxy. Central/closely competing people remain UNKNOWN; centrally seated people above the table can be OTHER, never a proven referee. It fails to assign many actual players in frontal views and crowds. Do not tune against this validation set; a next resolver experiment needs separate broadcast development data and a new frozen validation set. R50 is unnecessary at this point because person-box recall is not the observed bottleneck.

The desktop provides development/new-match galleries, table/person layers, anomaly filtering, previous/next anomaly, role corrections, rejection projection and **确认本帧**. Only that explicit review action creates `USER_VERIFIED`; later edits invalidate confirmation. Audit events bind frame hash and config hash. Raw model artifacts remain intact. Ordinary video UI uses Chinese person-recognition labels; model comparisons live in Research Center.

## Performance and reproduction

Development batch-1 FP32: model construction/load 0.270s (excludes Python/package startup), mean preprocessor+inference+postprocess 67.57ms with cold first frame, 42.69ms excluding first frame; 14.80 FPS including first frame. Torch peak allocated VRAM 206,806,528 bytes, reserved 306,184,192 bytes. Whole-process RAM was not captured. New-match RT-DETR stage averaged 47.61ms/frame. This is keyframe/post-match processing, not a real-time claim.

Scripts: `evaluate_person_detector.py` writes raw immutable development observations; `finalize_person_development.py` writes the once-frozen config/comparison; `validate_person_sources.py` writes a pre-inference source manifest and refuses to overwrite it. Artifacts under `%LOCALAPPDATA%/PTTI-Dev/vision-v2/scene-bootstrap` are local research files, not distribution assets. Reruns must use a new named run; do not overwrite previous evidence.
