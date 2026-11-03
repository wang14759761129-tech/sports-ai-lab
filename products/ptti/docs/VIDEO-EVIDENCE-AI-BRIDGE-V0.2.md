# PTTI Video Evidence v0.2 — AI Evidence Bridge

This Preview imports cached Hit Event v0.3 D suggestions into the local video evidence player. It does not run vision models or change the frozen algorithm. Each imported row remains an `AI_SUGGESTION` until a person confirms or rejects it.

## Supported source package

The local adapter writes a streaming JSONL package from the already cached D outputs for Extended OpenTTGames TRAIN `game_1` through `game_3`. It pins the original video SHA256, decoded result SHA256, full frozen-config file SHA256, canonical frozen-config SHA256, source frame rate, and source-to-time mapping. Import rejects a video/result/config mismatch, a changed local source file, unknown timebase, duplicate event IDs, unsupported roles, and GAME_4, GAME_5, or official TEST references.

Source: [moamal01/table_tennis_data](https://github.com/moamal01/table_tennis_data), pinned adapter revision `36471a76b969a0340df59258a813bf8214e68e7c`. License: CC BY-NC-SA 4.0. Use is research/non-commercial only. Videos, annotations, model weights, and generated packages stay outside Git and are not bundled with Preview builds. Preserve source attribution and do not redistribute or use commercially.

## Athlete workflow

1. Register or select a local video; its full SHA256 must be verified.
2. Select the local frozen JSONL package. The original video SHA must exactly match the registered video.
3. Review paged suggestions inside the embedded player. Candidate timestamps are canonical source timestamps in milliseconds; the 120 FPS source frame is checked against that time.
4. Adjust event time and clip range if needed, choose Near/Far/Unknown, then confirm or reject. The raw candidate and source provenance remain read-only; a separate audit entry stores the human decision and each edit.
5. Apply manual tags such as `关键分`, save a point with optional game/score and multiple evidence clips, then add confirmed critical clips to `关键分复盘` for continuous playback.

The candidate score is a rule evidence score, not a calibrated probability. Unknown player side stays UNKNOWN. Point score, game number, and critical-point labels are entered by the user; Hit sequences never synthesize score or match structure.

## Local persistence and recovery

The preview uses the existing SQLite database behind the ProductionDatabaseGuard. New tables are additive: `ai_import_batches`, `ai_import_keys`, and `evidence_points`. Import progress is committed incrementally. Cancel or application shutdown pauses the batch; resume verifies that both the package SHA and source video identity are unchanged. A stable source-video/event/config key prevents duplicate suggestions. Algorithm-filtered rows remain queryable under the explicit `算法已过滤` view and are excluded from the ordinary athlete clip list.

## Gates and limits

This desktop workflow demonstrates human review of cached candidate evidence. It does not establish `HIT_EVENT_AUTO_READY`, tactical recognition, calibrated confidence, official-test performance, or product accuracy. GAME_5 and the official TEST split remain locked. The Preview build contains no research media, AI result package, or model weights and is not a formal release.
