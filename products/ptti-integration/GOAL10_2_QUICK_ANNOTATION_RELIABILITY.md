# GOAL 10.2-M — Quick Annotation reliability handoff

This change adds a descriptive statistics sidecar and the versioned optional coarse stage input while preserving `ptti.quick-annotation/0.1`, Protocol v0.3's exact 21 CSV fields, and the existing `ptti.training-review/0.1` / GOAL09 audit path.

## Files San can consume

- v0.1 input remains `contracts/quick-annotation-v0.1.schema.json` and `runtime/quick-annotation-v0.1.d.ts`.
- v0.2 input is `contracts/quick-annotation-v0.2.schema.json` and `runtime/quick-annotation-v0.2.d.ts`.
- The optional descriptive output is `contracts/quick-annotation-stats-v0.1.schema.json` and `runtime/quick-annotation-stats-v0.1.d.ts`.
- A synthetic v0.2 input and its reproducible outputs are under `fixtures/quick-annotation-v0.2-valid-simulated.json` and `generated/goal10-2-review-reliability/`.

Consumers must negotiate by exact `contract_version`. The v0.1 schema/consumer rejects a v0.2 payload; do not strip `observed_rally_stage` or silently treat v0.2 as v0.1. The integration CLI explicitly supports both versions and emits the matching draft version.
Synthetic match, dataset, and non-null source IDs must all stay inside the `SIMULATED_ONLY:` namespace; the adapter rejects a synthetic source selected for a human draft.

Run from the repository root in PowerShell:

```powershell
python products/ptti-integration/scripts/run_quick_annotation.py `
  --input products/ptti-integration/fixtures/quick-annotation-v0.2-valid-simulated.json `
  --output-json products/ptti-integration/generated/goal10-2-review-reliability/draft.json `
  --output-csv products/ptti-integration/generated/goal10-2-review-reliability/protocol-v0.3-draft.csv `
  --output-stats-json products/ptti-integration/generated/goal10-2-review-reliability/expected-stats.json `
  --force
```

`--output-stats-json` is optional. Omitting it preserves the previous CLI outputs and behavior. Existing outputs are not overwritten unless `--force` is supplied.
The product caution threshold can be changed with `--display-caution-threshold N` (integer >= 1); it only changes `sample_status` and is always marked `threshold_is_significance_test: false`.

## Counting and evidence rules

- `score_record_coverage`: explicit `point_winner` values `player` or `opponent` divided by all supplied point rows. Video timestamps are not required for a recorded result.
- `recorded_point_wins`: counts by player/opponent, with denominator equal to rows with a known winner. This does not claim match identity or match completion.
- `sample.protocol_sequence_valid` carries the adapter's contiguous-sequence check. Known explicit winner rows remain countable if a point is missing, but score-before derivation stops across a gap until the missing point is supplied and the draft is re-run.
- `time_range_coverage`: known-winner rows with both start and end values passing `0 <= start < end <= user-reported duration`, divided by known-winner rows. Its evidence status is `RANGE_CHECKED_UNBOUND` because the source/timeline is not independently bound.
- `timeline_bound_review_coverage`: this quick-input contract cannot supply source-file SHA, `timeline_id`, PTS, or `time_base`; its confirmed numerator therefore remains zero. Do not display range coverage as confirmed video replayability.
- Serving/receiving win rates use only rows where both the relevant side and the winner are known. Unknown tactical fields never count as a known technique. `not_applicable` is counted separately.
- Third-ball attack rate uses only explicit yes/no labels; immediate-success rate uses explicit successful/unsuccessful labels and is not point-win rate; server point conversion uses only explicit `third_ball_attack=yes` rows with known serving side and winner. All remain draft-level observations, not audited conclusions.
- Close-score candidates reuse the existing rule-derived pre-point score checks. Candidates are not independently confirmed key-point facts.
- Exact `rally_length` statistics use only explicitly entered positive integers. v0.2 stage buckets do not enter that denominator.
- Every numeric metric includes numerator, denominator, sample count, missing count, rule, evidence state, and an `INSUFFICIENT_SAMPLE` caution below N=5. N=5 is the existing product display warning only, not a significance test.

The optional `observed_rally_stage` values in v0.2 are `END_AFTER_1_2_CONTACTS`, `END_AFTER_3_4_CONTACTS`, `END_AFTER_5_PLUS_CONTACTS`, or `UNKNOWN`. They describe a manually observed coarse end-of-rally contact bucket (serve included as contact one). Omission becomes `UNKNOWN`. Stage is copied to the review draft only; it never populates Protocol v0.3 `rally_length`, serve spin, placement, shot type, or third-ball fields.

`review_candidates` is capped at two. It cites `point_id`, supplied time range, and explicitly entered labels, but status stays `REVIEW_CANDIDATE_NOT_VIDEO_BOUND`; the selected source identity and timeline remain unverified.

## Example output excerpt

The committed fixture is synthetic and reports `SIMULATED_ONLY`. Its five rows contain four explicit winners, two winner rows with range-checked endpoints, zero timeline-bound video points, three observed stage buckets, and two unknown/missing stage values. Its serve/receiver and stage denominators are small and marked `INSUFFICIENT_SAMPLE`.

The stats sidecar is not `ptti.training-review/0.1`. It cannot be sent to San's Pro report renderer as a completed training report. Real human annotations still require the existing source binding, file hash, rights declaration, formal CSV import, quality review, and GOAL09 audit. No real video decode, timeline binding, or Vision result is claimed by this synthetic fixture.
