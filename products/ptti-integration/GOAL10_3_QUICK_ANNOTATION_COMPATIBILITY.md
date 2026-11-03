# GOAL 10.3-M — Quick Annotation compatibility and golden baseline

## Read-only source snapshots checked

- San Web worktree: `codex/ptti-web-mvp-v0-1`, local HEAD `60ee6a30a6aa313249ddb3b2dad8f669cbaffcbd` (16 commits ahead of its remote tracking ref). It was clean at the first status check; at the end of this read-only audit, seven Web files had uncommitted changes, including the local-video runtime, declarations, adapter, UI, styles, and check script. These were not edited by Integration.
- Playback worktree: `codex/ptti-playback-recovery-sprint-0-3`, local HEAD `523891a127be5148f3f53ddade1648eb9a13e0fc` (2 commits ahead; unrelated untracked diagnostics are present and were left untouched).
- Integration source: `codex/ptti-goal10-2-review-reliability`, HEAD `98f3a78b695475d223c6e21e4ae8121b63546b70` before this handoff addition.

These are local read-only snapshots, not statements about the latest remote revisions.

## Versioned input contract

The authoritative machine-readable definitions are:

- v0.1 JSON Schema: `contracts/quick-annotation-v0.1.schema.json`
- v0.1 TypeScript: `runtime/quick-annotation-v0.1.d.ts`
- v0.2 JSON Schema: `contracts/quick-annotation-v0.2.schema.json`
- v0.2 TypeScript: `runtime/quick-annotation-v0.2.d.ts`
- Statistics sidecar: `contracts/quick-annotation-stats-v0.1.schema.json` and `runtime/quick-annotation-stats-v0.1.d.ts`
- Complete v0.1 sample: `fixtures/quick-annotation-v0.1-valid-simulated.json`
- Complete v0.2 sample: `fixtures/quick-annotation-v0.2-valid-simulated.json`
- Recalculation baseline: `fixtures/quick-annotation-v0.2-cross-endpoint-golden.json`

Both input versions require the same exact top-level keys: `contract_version`, `dataset_id`, `dataset_class`, `match_id`, `video_context`, `rules_context`, and `points`. Both require each point's `point_id`, `server`, `winner`, `observed_tactics`, `rally_start_ms`, and `rally_end_ms`. v0.2 adds only the optional `observed_rally_stage` point field. Its allowed labels are `END_AFTER_1_2_CONTACTS`, `END_AFTER_3_4_CONTACTS`, `END_AFTER_5_PLUS_CONTACTS`, and `UNKNOWN`; omission normalizes to `UNKNOWN`.

`observed_rally_stage` is an explicitly user-observed coarse contact-count bucket (serve included). It is not exact `rally_length`, does not establish that the server attacked the third ball, and must not populate any third-ball action/outcome fields.

The statistics output remains `ptti.quick-annotation-stats/0.1` for either input version. For v0.1, stage statistics are `NOT_AVAILABLE_INPUT_V0_1`; for v0.2 they count only explicit non-`UNKNOWN` stage values.

## Compatibility behavior observed

Integration validates the exact version string and exact fields: v0.1 rejects v0.2; v0.2 accepts its optional stage field; unknown versions and unsupported fields fail closed. Do not remove a field and retry under another version.

San's current JavaScript runtime supports both versions and defaults new exports to v0.2 (`createQuickAnnotationInput(..., requestedVersion?)`). Its import validator accepts v0.1 and v0.2, enforces exact per-version fields, and checks the stage enum. The current local `src/local-video-review.d.mts` declares the version union, v0.2 point/stage type, optional requested version, and imported stage field; it matches the inspected runtime surface. A no-emit TypeScript check passed from `products/ptti-web`. These declaration/runtime edits are uncommitted in San's worktree, so this verifies its local working tree only, not a committed Web release. San's inspected source does not currently consume the Integration statistics sidecar.

## Time-field semantics: do not auto-equate by name

| Field | Current meaning and binding | Safe mapping decision |
|---|---|---|
| San `LocalVideoPoint.start_seconds/end_seconds` | User-marked local review boundaries in seconds in the current selected-media session. The session identity is ephemeral. | Convert units only when producing Quick JSON; this alone is not durable source binding. |
| Quick `rally_start_ms/rally_end_ms` | Integer milliseconds from the selected browser video timeline. Input validation checks ordering and a user-reported duration. Generated Protocol v0.3 text remains `binding=UNBOUND`; source SHA, `timeline_id`, PTS, and `time_base` remain null. | Preserve as an unbound draft range. It is not a confirmed score index. |
| Playback Core `RallyPlaybackBinding.start_time/end_time` | Seconds from the beginning of the currently selected file. Core requires `BOUND`, matching `video_identity`, finite in-duration times; San's adapter additionally requires both boundary confirmation flags. | Quick ms can be converted to seconds only with matching current session identity, both explicit confirmations, and valid in-duration bounds. The adapter does not create durable PTS/time-base evidence. |
| Desktop Score Navigation `point_start_ms/point_end_ms` | Bound to a `video_asset_id`; persistence requires a verified source SHA and an available asset. Each boundary has field evidence; playlist use requires a `CONFIRMED` point and matching video SHA. These are point-segment boundaries, not merely an arbitrary quick-rally range. | No automatic field-name mapping. A human must confirm that both marks describe the same point segment on the exact same asset/version; then preserve source SHA and per-field evidence. |

The playback controller consumes seconds on a loaded file timeline, not raw PTS/time-base. Its generic validator permits equal endpoints, while San's adapter and Quick Annotation require strict `start < end`; keep the stricter Quick rule when adapting these records. Neither similar field names nor a duration-valid range proves same source, same edit, or same boundary definition.

## Golden counts for San to recalculate

Run Integration's adapter and statistics sidecar over the exact input fixture identified by SHA-256 in `quick-annotation-v0.2-cross-endpoint-golden.json`.

- Supplied points: 5.
- Explicit known winners: 4/5; winner `UNKNOWN`: 1.
- Duration-checked ranges: 2/4 known-winner records; missing ranges among that denominator: 2. These are not timeline-bound segments.
- Timeline-bound records: 0/4 known-winner records.
- Current-session-playable records: 0/5. The fixture has no loaded media session, source SHA, timeline binding, boundary confirmation receipt, or native playback receipt.
- Source references: 1; independently verified source references: 0/1. The fixture is `SIMULATED_ONLY`; source link is `USER_SELECTED_UNVERIFIED`, rights are `UNKNOWN`.
- Explicit observed stages: 3/5; stage-distribution denominator: 3; omitted or `UNKNOWN`: 2. Histogram: one in each defined coarse bucket.
- `third_ball_attack` explicitly observed as `yes`: 1/5 rows, numerator 1 over the one known-value denominator; four rows are unknown/unobserved and are excluded from the rate. Stage does not affect this metric.
- Timeline ID, source video SHA, PTS, and time base: null. Vision: `NOT_TESTED`.

The default display-caution threshold is N=5 per metric denominator: denominator 0 is `NOT_ESTIMABLE`; denominator 1–4 is `INSUFFICIENT_SAMPLE`; denominator >=5 is `DESCRIPTIVE_ONLY`. It is configurable via `--display-caution-threshold`, is a product warning only, and is not a significance test. Metrics retain their own valid-value denominator; do not use the overall point count as every denominator.

## Verification command and consumer handoff

From the repository root:

```powershell
python -m unittest discover -s products/ptti-integration/tests -p "test_quick_annotation_goal10_3_golden.py" -v
```

For a full draft and stats sample, run `products/ptti-integration/scripts/run_quick_annotation.py` with the v0.2 fixture and request `--output-stats-json`; the output remains a review-only sidecar, not San's formal training report. Golden test code verifies input bytes before calculating expected counts.

San should consume the v0.2 JSON only after its declaration file is updated to represent the runtime's version argument, v0.2 input/output types, and imported stage field. Until then, runtime acceptance exists but TypeScript declarations are stale. No native playback, independent source verification, or Vision result is asserted by this fixture.
