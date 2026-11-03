# GOAL 10.5 — San review-targets handoff

## Executable interface

From the Integration repository root:

```powershell
python products/ptti-integration/scripts/run_review_targets.py --input products/ptti-integration/fixtures/review-targets-11-8-input.json --output products/ptti-integration/fixtures/review-targets-11-8-output.json
python -m unittest discover -s products/ptti-integration/tests -p "test_review_targets_goal10_5.py" -v
```

The CLI reads raw Quick Annotation v0.1 or v0.2 input, calls the existing strict adapter and statistics sidecar, then emits `ptti.review-targets/0.1`. It refuses an input/output path collision or overwriting different output. Select a new output filename after editing input. It never edits the original annotation.

Python API: `review_targets.build_review_targets(payload, display_caution_threshold=5)`.
TypeScript: `runtime/review-targets-v0.1.d.ts`, exported `ReviewTargetsV01`.
This is a local private draft view, not an audited GOAL09 report or media permission grant. Existing protocols and stats stay unchanged.

## Fixed field semantics

- `athletes[].role`: original `player` / `opponent` input roles (A/B only by the producer's explicit role assignment). No names or real player identity are inferred. `identity_status=INPUT_ROLE_ONLY`.
- `score`: explicit known winners, even without video time. `won_count + lost_count = denominator`.
- `service`: resolved serving role from the existing adapter, including rule-derived rotation only when the original context supports it. Known other serving side is excluded; unknown serving side remains unknown for both roles. It is not evidence that the serve itself was observed or independently verified.
- `observed_stages[stage]`: coarse stage entered by the user; v0.1 has no stage and yields UNKNOWN. Never converted into third-ball attack or exact stroke count.
- Each count contains `point_ids.valid/won/lost/unknown/excluded`. `denominator + unknown_count + excluded_count = sample_count`. Known nonmatching groups are excluded, not unknown. Unknown group-membership rows recur in multiple group summaries; do not sum unknown counts across buckets.
- `review_targets[]`: every nonempty stage-loss group; `point_ids` contains only explicit losses in that known stage. `denominator` is known winners in the same stage. It does not mean all supplied points, all losses, or current-session playable segments.
- `observations[]`: at most two descriptive messages linked by `target_id` and loss point IDs, sorted by loss count and stable ID. They are candidates for record/video review, not diagnoses, priorities validated by video, or training prescriptions.
- `sample_status`: N=0 `NOT_ESTIMABLE`; 0<N<threshold `INSUFFICIENT_SAMPLE`; N>=threshold `DESCRIPTIVE_ONLY`. Threshold defaults to 5 and is configurable. No significance test or long-term performance inference.
- `canonical_input_sha256`: SHA-256 of canonical UTF-8 JSON (`sort_keys=True`, compact separators, Unicode preserved). This is not the raw-file-byte hash, truth proof, copyright evidence or media hash. Whitespace/key-order changes do not alter it; changing a winner does.
- `dataset`, `sample` and `time_range_coverage` reuse existing stats output. Selected source IDs remain unverified, rights UNKNOWN, source hash/timeline/PTS/time_base null and Vision NOT_TESTED. `evidence_status` remains SIMULATED_ONLY or REVIEW_REQUIRED.
- Consumers must check `contract_version === 'ptti.review-targets/0.1'` and reject unsupported versions. This output is not a new Quick Annotation input version.

## San playback boundary

`playback_eligibility=NOT_EVALUATED_CURRENT_SESSION` on every target. Join point IDs only to the exact active annotation dataset/match and current source/session. San independently checks session media, user-confirmed start/end boundaries and its own evidence/version rules before enabling playback. No timestamp or media URL is supplied by this view; no Desktop evidence is inherited. Missing eligibility means disabled, never assumed playable.

## Golden example

The original SIMULATED_ONLY input has 19 points and a legal 11:8 finish, player first serve, 12 duration-checked time ranges and 7 points without time. There is no real video or verified athlete.

- player score: 11 wins / 8 losses, N=19; opponent: 8 / 11, N=19.
- player service: 6 / 4, N=10; opponent service: 4 / 5, N=9.
- player `END_AFTER_3_4_CONTACTS`: 0 wins / 3 losses, N=3, unknown=2; loss IDs end in p002,p004,p006. Small-sample warning applies.
- Stage UNKNOWN: 2. These are not included as observed stage usage.
- Change only p001 winner from player to opponent: score becomes 10:9, same N=19; first stage becomes 10 wins/1 loss, p001 moves into its loss target, canonical input hash changes. This edited sequence is an ongoing game, not falsely labelled completed.

All fixtures, output and observations retain SIMULATED_ONLY. There is no real-match, native-playback, timeline or Vision acceptance claim.

## Scope and checks

Only Integration adapter/view, CLI, TypeScript declaration, original synthetic fixture/output and targeted tests are added. No San/Playback source, existing Protocol v0.3, Quick Annotation v0.1/v0.2, statistics sidecar or GOAL09 audit API is changed. No push, CI, deployment or Native launch.

Final local checks: 11 new review-target tests passed (0.428s); 37 existing Quick Annotation v0.1/v0.2, statistics and Golden tests passed (0.357s). TypeScript strict/noEmit compilation of the new declaration and its stats dependency passed with the existing installed compiler, read-only; no new dependencies were installed. Demo generation/CLI and git whitespace checks passed. Browser, San runtime adoption and real-media playback are NOT_TESTED by this data-only delivery.
