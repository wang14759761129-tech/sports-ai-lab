# Hit Event v0.2 — Temporal Decoder

## Purpose and guardrails

v0.2 is a TRAIN-only research iteration intended to reduce false hit candidates while preserving recall. The v0.1 engine and its report remain frozen at commit `b24af71618ebacd31931055bb7aad8fa01e6baef`. v0.2 does not train a model or classify forehand, backhand, serve technique, spin, or tactics. BallTrack RAW remains the observation source. Pose candidate generation is off; any future Pose use may only rerank a candidate already created from ball evidence.

The video-level split is recorded in [`HIT_EVENT_V0_2_SPLIT.json`](../configs/evidence-fusion/HIT_EVENT_V0_2_SPLIT.json), with a SHA256 sidecar. It assigns games 1–3 to development, game 4 to calibration, and game 5 to internal holdout. All five matches were previously exposed through v0.1 ten-second slices. Therefore game 5 is a post-lock internal holdout with historical v0.1 slice exposure, not a pristine project-history holdout. The official TEST split remains untouched.

## TRAIN annotation inventory

The pinned Extended OpenTTGames revision is `36471a76b969a0340df59258a813bf8214e68e7c`, licensed CC BY-NC-SA 4.0 for research/non-commercial use. Only official TRAIN annotation files were read. They contain 1,133 stroke events across five videos: game 1 161, game 2 399, game 3 152, game 4 173, game 5 248. The complete event inventory contains 1,546 bounce labels, 1,171 net labels, 223 rally-ending labels, 106 empty-event rows, and one unknown native event. No dataset media belongs in Git or product release assets.

Development-only priors are recorded in [`HIT_EVENT_V0_2_DEV_PRIORS.json`](../configs/evidence-fusion/HIT_EVENT_V0_2_DEV_PRIORS.json). Within 684 consecutive strokes that fall inside the dataset's derived serve-to-ending segments in games 1–3, the observed interval minimum is 275 ms, P1 316.667 ms, P5 375 ms, median 733.333 ms, and P95 15,391.667 ms. That unusually long tail is not treated as a physical maximum; the adapter's derived rally segments can be incomplete or temporally ambiguous. The development ending-to-next-serve gap minimum is 3,966.667 ms. The observed GT-ball normalized-speed P99.5 is 2.779 image diagonals/s across 29,843 adjacent visible pairs, but this is only a provisional gross-jump diagnostic, not a calibrated physical limit.

## v0.2 components

- `RawHitCandidateGenerator` uses pre- and post-event BallTrack observations, local direction and speed changes, ball-gap checks, and player-side proximity. It does not use wrist or Pose to create events. Suspicious jumps remain in raw output with `BALLTRACK_JUMP` evidence; the sequence decoder now excludes those rows from filtered hit output and records the suppression reason.
- `TemporalCandidateClusterer` groups nearby raw peaks and keeps the strongest while preserving every suppressed member and its reason. Its window comparison accounts for the 0.001 ms timestamp serialization precision at an inclusive boundary; it still anchors groups to prevent chaining across contacts.
- `HitSequenceDecoder` uses a development-derived soft interval floor and soft Near/Far alternation only when role identity is confident. Accepted and suppressed candidates include path-utility traces and explicit rejection reasons. Ambiguous or near-optimal alternatives enter a separate review queue; they do not count as automatic hits.
- Optional Pose reranking remains off by default. If explicitly enabled for a controlled ablation, a `GOOD` pose alone cannot add score: the timestamp-aligned frame must also have an observed ball and a valid wrist keypoint near that ball. The bounded increase is recorded as a `WRIST_PROXIMITY_PROXY`, not racket-contact evidence.
- Bounce and net labels are available only for post-hoc TRAIN development diagnostics. They are never inference inputs.
- The config is [`HIT_EVENT_V0_2_DRAFT_CONFIG.json`](../configs/evidence-fusion/HIT_EVENT_V0_2_DRAFT_CONFIG.json), status `DRAFT_DEV_ONLY`. The cluster window and decoder penalties are provisional and must not be described as calibrated or frozen.

## Evaluation boundary

At this checkpoint, the 10-second v0.1 frame-evidence artifacts provide only seven stroke labels across the three development clips. Replaying the v0.2 smoke on those cached inputs checks wiring and rejection diagnostics only; it is explicitly insufficient for tuning or validation. Evaluation uses a 0.001 ms comparison epsilon solely to account for timestamps serialized to three decimal places, and reports that epsilon with its metrics. Complete game 1–3, game 4, and game 5 inference artifacts are required before making v0.2 performance claims. At the last file inventory, only game 4 was a complete local video; game 1 had a resumable partial transfer and games 2, 3, and 5 were not staged. The resumable downloader is allowlisted to `game_1`–`game_5` and refuses paths outside `%LOCALAPPDATA%\PTTI-Dev\research-datasets\ExtendedOpenTTGames\videos\train`.

Do not run calibration or internal holdout before full development evaluation and config lock. Do not read official TEST. Do not access the Production database. Do not build or publish a v0.2 release until the holdout gate is evaluated and the application integration is reviewed.
