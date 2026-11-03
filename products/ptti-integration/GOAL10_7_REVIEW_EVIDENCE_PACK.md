# GOAL 10.7 — Review Evidence Pack handoff

The evidence pack is a small presentation/export adapter over the existing `ptti.review-targets/0.1` result. It does not alter Quick Annotation, statistics, Review Targets, or GOAL09. The JSON artifact uses `ptti.review-evidence-pack/0.1`; unsupported input versions continue to be rejected by the existing adapter.

## Reproduce

Run from the Integration repository root:

```powershell
python products/ptti-integration/scripts/export_review_evidence_pack.py --input products/ptti-integration/fixtures/review-targets-11-8-input.json --json-output products/ptti-integration/generated/goal10-7-review-evidence/review-evidence-pack.json --markdown-output products/ptti-integration/generated/goal10-7-review-evidence/review-evidence-report.md --generated-at-utc 2026-10-15T04:25:29Z
```

The CLI preserves existing outputs: identical content is accepted, different content requires new output paths. The timestamp above reproduces the committed artifacts; choose a new timestamp and new output paths for a fresh export. The report’s generation time and hashes are in the JSON artifact.

Regression inputs are under `fixtures/goal10-7-review-evidence/`:

- `winner-edited-10-9.json`: p001 winner changes A→B. The sequence becomes 10:9 and is `IN_PROGRESS`, not a completed game.
- `unknown-winner-p014.json`: p014 winner becomes UNKNOWN. It stays outside known score denominators and makes sequence completion `INDETERMINATE`.

Run the focused tests:

```powershell
python -m unittest discover -s products/ptti-integration/tests -p "test_review_evidence_pack_goal10_7.py" -v
```

## Consumer fields

The machine artifact contains:

- `input`: input/statistics/Review Targets versions, canonical semantic SHA-256, raw input byte SHA-256 and their separate meanings.
- `match.game`: one-game score, game progress status, coverage declaration and ordered point IDs.
- `source_and_rights`: source ID, rights, source-video SHA, timeline/PTS/time_base, Vision and current-session playback eligibility. Null/UNKNOWN values remain unpromoted.
- `sample.score_by_role` and `sample.service_by_role`: A→`player`, B→`opponent`; each carries the existing `ReviewCount` counts, partitions and complete point-ID lists.
- `sample.observed_rally_stages`: the existing three explicit coarse stage buckets, both roles and their full partitions. `sample.unknown_stage` separately counts all rows with UNKNOWN stage.
- `sample.time_range_coverage`: existing 12/19 duration-range check plus IDs for checked/missing ranges. This is not timeline binding or playback readiness.
- `sample.point_evidence_index`: per-point winner/server derivation, pre-point score, observed stage, unbound times and key-point status.
- `review_candidates`: at most two existing Review Targets observations, with full loss IDs and `NOT_EVALUATED_CURRENT_SESSION` playback eligibility.

Golden example: A (`player`) has 11 wins / 8 losses, N=19. For `END_AFTER_3_4_CONTACTS`, A has 0 wins / 3 losses, N=3, unknown=2, and loss IDs p002/p004/p006. The threshold is N<5 and is a display caution, not significance testing. These records are `SIMULATED_ONLY`; the example cannot be used as a real match report.

## Safety boundary

`canonical_input_sha256` changes when semantic JSON values change and ignores whitespace/key-order formatting. `raw_input_sha256` binds exact source bytes and may therefore change after a formatting-only edit. Neither hash establishes match identity, rights, annotation truth, video identity or playback. The exporter includes no video bytes or absolute local path. It always preserves `playback_eligibility=NOT_EVALUATED_CURRENT_SESSION`; San must independently validate the active media session and confirmed boundaries before offering replay.

Only one declared game is accepted by this report view. The game is described as score-terminal only when the existing adapter confirms a contiguous full-from-start sequence with known winners and the final score reaches 11 with a two-point lead. Coverage declaration alone does not mean the game ended.

No real-video decode, timeline binding, current-session playback, native Windows playback, rights verification or Vision analysis was performed.
