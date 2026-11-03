# Extended OpenTTGames research adapter

## Source and use boundary

PTTI's adapter targets [moamal01/table_tennis_data](https://github.com/moamal01/table_tennis_data), pinned to commit `36471a76b969a0340df59258a813bf8214e68e7c`. The dataset license is **CC BY-NC-SA 4.0**. This integration is for research and non-commercial evaluation only. Dataset media and annotations must not be committed to Git or included in an installer, portable package, or commercial release. Preserve attribution and the license when sharing allowed adaptations. See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

The official README describes five training videos (`game_1`–`game_5`) and seven test videos (`test_1`–`test_7`), with event annotations stored as JSON objects keyed by frame number. It describes Full-HD static side-view video at 120 fps, while noting small camera differences and that event annotation may choose the frame after the visually exact event. PTTI probes each local file and does not assume these nominal properties are exact. The official download script uses `https://lab.osai.ai/datasets/openttgames/data/{game_X,test_X}.mp4`.

## Local staging

PTTI keeps this dataset outside the checkout, under `%LOCALAPPDATA%\PTTI-Dev\research-datasets\ExtendedOpenTTGames`. Stage only the official training annotations while developing the adapter. The official test split must remain unread until the inference code and configuration are locked. Do not stage the test files as part of the initial training-set diagnosis.

Expected local training structure:

```text
annotations/train/game_data/game_1.json ... game_5.json
annotations/train/ball_data/train_1.json ... train_5.json
videos/train/game_1.mp4 ... game_5.mp4
```

The Research page reports which training assets are locally present and marks the test split `LOCKED_NOT_ACCESSED`.

## Annotation schema and adapter

Native game events are `{ "frame-number": "native label" }`. Labels include `bounce`, an unprefixed `net` hit, and player-side-prefixed stroke labels such as `left_forehand_loop neutral both_feet_planted`. Rally endings include `winner`, `double_bounce`, side-prefixed `net`, `not_hitting_ball`, `out`, and `miss_on_own_side`. PTTI distinguishes a plain `net` event from `left_net` / `right_net` rally endings. It retains the complete native label, frame, side, stroke hand/technique when parsed, remaining native attributes, source, and ground-truth designation. Unrecognized labels remain `UNKNOWN_NATIVE_EVENT`; they are not dropped.

`ExtendedOpenTTGamesAdapter` converts events to TTI records. When a source PTS map is supplied, it is authoritative. Otherwise a timestamp derived from the probed frame rate is labeled `FRAME_RATE_ESTIMATE`, never source PTS. Original ball-coordinate annotations are adapted separately; `(-1, -1)` represents a missing ball annotation.

## Derived rally definition

The extension supplies frame-level events, not native rally segments. PTTI derives a segment from a serve stroke annotation to the next rally-ending annotation and records `ground_truth_type: DERIVED`, `start_source: serve_annotation`, and `end_source: rally_ending_annotation`. These intervals must never be described as native rally ground truth. Missing serves/endings, an ending before a serve, or a new serve before the prior ending are retained as `INCOMPLETE_GROUND_TRUTH` and excluded from complete-segment accuracy. Annotation definitions and timing caveats mean the boundary is an operational proxy.

Ground-truth serves and endings are used only to score predictions. They must not be passed to MatchStructureEngine or BallTrack as inference input.

The `game_data/game_N.json` and `ball_data/train_N.json` same-index relationship is followed as published; PTTI does not heuristically swap annotation files. Before using ball coordinates to attribute a structure error to BallTrack, compare their frame ranges and event/ball annotated-frame overlap. A weak or suspicious alignment keeps the failure class `UNKNOWN` and is reported as a limitation.

## Evaluation protocol

1. Use training videos for initial diagnostics and any justified algorithm changes.
2. Run frozen `BALLTRACK_V1_FROZEN_RAW` and the current MatchStructureEngine without event-label input.
3. Match proposed and derived intervals using maximum-weight one-to-one temporal-IoU assignment; report unmatched predictions and ground-truth intervals separately.
4. Report precision, recall, F1, boundary errors, and interval IoU. Report tolerance results at ±1 and ±3 frames and ±100, ±250, and ±500 ms, converting frames using measured media timing where available.
5. Only after code and configuration are frozen may the official test split be accessed. Test results may be run once; any subsequent tuning makes that split development data.

Review effort is a proxy only: boundary edits for matched segments, new segments for misses, and rejections for false suggestions. No review-time savings are claimed without a human study.

## Limitations and excluded claims

This dataset is not automatically a legal source for commercial distribution. This evaluation does not train a model and does not validate contact detection, bounce detection, scoreboard OCR, stroke recognition, serve classification, or tactical conclusions. Frame labels can be temporally approximate or incomplete. Any failure attributed to BallTrack versus structure logic must be supported by the adjacent raw tracking evidence; otherwise classify it as annotation ambiguity or unknown.

Semantic-mask files were not found in the extension's staged file listing during this integration. Availability in the original OpenTTGames materials remains unverified.
