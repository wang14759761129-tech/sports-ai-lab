# Hit Event Engine v0.1 — Baseline

Status: `HIT_EVENT_V0_1_PARTIAL`

Baseline commit (Player Motion v0.1): `76489ee339f065a2275e09ed4207e39921449c69`

Dataset: Extended OpenTTGames, revision `36471a76b969a0340df59258a813bf8214e68e7c`, CC BY-NC-SA 4.0, research/non-commercial only.

This is an evidence-fusion baseline for *suggesting when a hit may have happened and which side may have hit it*. It does not classify strokes, and it does not establish confirmed hit events. The score is a rule evidence score, not a calibrated probability. All candidates remain `SUGGESTED` until a person reviews them.

## Data boundary and split

Only five ten-second videos from the official TRAIN split were read. The official TEST split was not accessed. Match-level separation was used:

| Use | Clip | Start | Video SHA256 | Stroke GT |
|---|---|---:|---|---:|
| Development | `game_1-t60` | 60 s | `8a47edc38efcbcc58b74abdfac538e01951aa3260727e407f9172bc54b19a904` | 0 |
| Development | `game_2-t60` | 60 s | `d181bd9f735b51f482c450242234766e3629e3cbcdc71bc79bb3befa86ffd60c` | 3 |
| Development | `game_3-t60` | 60 s | `4d1537234ec2279bc5c6e433cec43802f0f81a9883d556827087a21212748b6c` | 4 |
| Validation | `game_4-t30` | 30 s | `562caee412d402c9096410dc9b06391d80e53e5316676a3827f328709f047f48` | 2 |
| Validation | `game_5-t60` | 60 s | `3082d087d73b216c07db8c6be85c1157c98f7fe3d3780387a9919ce15702eadb` | 4 |

The three development clips contain 7 stroke events; the two frozen validation clips contain 6. Each clip was processed as 300 frames at 30 FPS from a 120 FPS source. The frozen RacketVision RAW BallTrack checkpoint was used without tuning: upstream commit `c44af2a08524d3cb54d818f19686f4cdea4d2793`, checkpoint SHA256 `00d707b9db7a49561c411e4765956e79bcd7c7e20c7a0a535073440b3e972342`.

## Timeline and side mapping

All module observations join through `timestamp_ms` on a source-video SHA256-checked canonical timeline. The 30 FPS processing video timestamps were probed; BallTrack, tracking and pose observations were checked against the same source and aligned within 3 ms in the recorded audits. Native annotation timestamps were derived from the dataset source-frame number at 120 FPS because complete source presentation timestamps were unavailable. They are therefore marked `SOURCE_FRAME_RATE_ESTIMATE`; this limits how strongly sub-frame timing should be interpreted.

Left/right was reviewed per match and never assumed to mean Near/Far: `game_2` right→Near, left→Far; `game_3` left→Near, right→Far; `game_4` right→Near, left→Far; `game_5` left→Near, right→Far. `game_1` has no stroke events in this clip and its mapping was not reviewed.

## Frozen rule configuration

Configuration: [HIT_EVENT_V0_1_CONFIG.json](../configs/evidence-fusion/HIT_EVENT_V0_1_CONFIG.json)

Configuration SHA256: `a263f0702584d325cf0673c5d18a5be76771109ee6aba49e956f3c02630d971e`

Lock record: [HIT_EVENT_V0_1_LOCK.json](../configs/evidence-fusion/HIT_EVENT_V0_1_LOCK.json)

The engine combines ball-to-player proximity, ball-to-wrist *racket-side proxy*, ball trajectory direction/speed change, wrist speed, pose quality, and tracking health. Missing inputs remain null and are omitted from the weighted score. Local peak suppression uses a one-frame radius and candidate separation is 140 ms. The locked threshold is 0.62. Configuration was tuned only against the three development matches; the two validation matches were evaluated after the lock and were not used for further changes.

## Development results

Matching is one-to-one within each clip; predictions are never matched across different videos.

| Tolerance | Predicted | GT | Matched | FP | FN | Precision | Recall | F1 | Median / P90 timing error | Side correct |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ±1 processing frame (33.3 ms) | 14 | 7 | 4 | 10 | 3 | 0.286 | 0.571 | 0.381 | 25.0 / 33.3 ms | 4/4 |
| ±2 frames (66.7 ms) | 14 | 7 | 4 | 10 | 3 | 0.286 | 0.571 | 0.381 | 25.0 / 33.3 ms | 4/4 |
| ±3 frames (100 ms) | 14 | 7 | 5 | 9 | 2 | 0.357 | 0.714 | 0.476 | 33.3 / 73.3 ms | 5/5 |

At ±3 frames, `game_2-t60` matched 1 of 3 strokes (4 FP); `game_3-t60` matched 4 of 4 strokes (5 FP). `game_1-t60` had no GT stroke and no suggestion.

## Frozen validation results

| Tolerance | Predicted | GT | Matched | FP | FN | Precision | Recall | F1 | Median / P90 timing error | Side correct |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ±1 processing frame (33.3 ms) | 12 | 6 | 3 | 9 | 3 | 0.250 | 0.500 | 0.333 | 25.0 / 31.7 ms | 3/3 |
| ±2 frames (66.7 ms) | 12 | 6 | 6 | 6 | 0 | 0.500 | 1.000 | 0.667 | 33.3 / 45.8 ms | 6/6 |
| ±3 frames (100 ms) | 12 | 6 | 6 | 6 | 0 | 0.500 | 1.000 | 0.667 | 33.3 / 45.8 ms | 6/6 |

At ±1 frame, `game_4-t30` matched 0/2 and `game_5-t60` matched 3/4. At ±2 and ±3, `game_4-t30` matched 2/2 (5 FP) and `game_5-t60` matched 4/4 (1 FP). This small validation set does not support a reliable stroke-type difficulty ranking. The apparent ±1 misses become matches at ±2 frames, and GT time is estimated from source frame rate rather than full source PTS.

## Pose ablation and error review

An exploratory development-only ablation at ±3 frames compared the same rule engine with Pose evidence versus Pose fields set to null. With Pose: 14 suggestions, 5/7 matched, 9 FP, 2 FN, F1 0.476. Without Pose: 4 suggestions, 3/7 matched, 1 FP, 4 FN, F1 0.545. Pose increased recall in this tiny sample but also produced many more false suggestions; it has not demonstrated a net product improvement. Pose remains optional evidence, and skipped/low-quality pose is not fabricated.

Nine development false-positive previews were visually reviewed. Their exact cause was not reliably attributable from those frames alone, so the review is recorded as `UNKNOWN` rather than assigning unsupported taxonomy counts. Visible patterns included wrist-proximity candidates during serve/preparation and occasional suspicious ball observations near a body or table edge. Future error labels should be confirmed against the surrounding video, not inferred from a still alone.

## Runtime and outputs

On prebuilt 300-frame evidence records, a warm CPU microbenchmark over 20 calls measured 6.87–16.40 ms per clip for clips that produced candidates (approximately 18,294–43,701 frames/s). The zero-candidate clip took 0.55 ms and is excluded from that throughput range. This measures only the Python candidate engine, not video decoding, BallTrack, tracking, pose inference, or disk I/O. Research outputs remain under `%LOCALAPPDATA%\PTTI-Dev\vision-v2-evidence-fusion\evaluation\` and are not product data.

Development report: `%LOCALAPPDATA%\PTTI-Dev\vision-v2-evidence-fusion\evaluation\dev\20261007T024323_411950Z\hit_event_evaluation.html`

Frozen validation report: `%LOCALAPPDATA%\PTTI-Dev\vision-v2-evidence-fusion\evaluation\validation\20261007T024911_529183Z\hit_event_evaluation.html`

The desktop preview exposes candidate markers, a per-event evidence panel, video seeking, and append-only human confirm/reject/time/side corrections. The UI was exercised in the browser-hosted desktop frontend. The native Windows executable was built, but native-window interaction was not verified in this environment.

## Limitations and decision

- Official TEST split: `NOT ACCESSED`.
- Production database: `NOT ACCESSED`; evaluation artifacts use `PTTI-Dev`.
- Event time inherits source-frame-rate estimation uncertainty.
- Precision and F1 are too low for automatic confirmation; every event remains reviewable.
- No racket detector is used; wrist distance is explicitly a proxy.
- No stroke classification, bounce/net classifier, serve classifier, or tactical conclusion is produced.
- The validation set has only two matches and six strokes; it is a frozen internal validation, not a broad generalization claim.

Decision: `HIT_EVENT_V0_1_PARTIAL`. Keep all results as suggestions and collect more independently annotated TRAIN-only examples before considering a stronger gate.
