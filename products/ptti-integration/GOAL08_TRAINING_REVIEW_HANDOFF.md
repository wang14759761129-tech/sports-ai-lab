# GOAL 08 — Training Match Review local Pro sidecar

This executable path extends the existing Protocol v0.3 and `ptti.match-intelligence/0.1` analyzer. It emits a separate `ptti.training-review/0.1` object for local, private San Pro review. It does not change `ptti.match-media/0.2`, publish a match, grant rights, or create Vision evidence.

## Fill the point CSV

Run from the repository root:

```powershell
python products/ptti-integration/scripts/run_training_review.py --write-template products/ptti-integration/fixtures/goal08-manual-points-template.csv
```

The committed template contains the exact 21 Protocol v0.3 headers and is accepted by the CSV header reader. Fill one point per record. An empty template has no analyzable points. Blank cells are rejected; write `unknown` when the fact should exist but was not observed, `unclear` for ambiguous footage, and `not_applicable` only when the event does not apply. These values are counted separately.

| Protocol field | Meaning / accepted values |
| --- | --- |
| `match_id` | Explicit stable local match ID; every row must agree with the manifest. Do not use title or athlete-name matching. |
| `game_number`, `point_number` | Positive integers; games/points ordered and contiguous from 1. Together with `match_id`, they form the natural point ID. |
| `server`, `receiver` | `player`, `opponent`, `unknown`; known sides must differ. The two-point/deuce serve pattern is checked where known. |
| `server_score_before`, `receiver_score_before` | Nonnegative integers or `unknown` / `unclear`; scores are **before this point** from the current server/receiver perspectives. Known adjacent scores are reconciled with the known winner. |
| `serve_side` | `forehand`, `backhand`, or uncertainty value. |
| `serve_length` | `short`, `half_long`, `long`, or uncertainty value. |
| `serve_location` | `forehand`, `middle`, `backhand`, or uncertainty value. |
| `serve_spin` | `backspin`, `sidespin`, `topspin`, `no_spin`, `mixed`, or uncertainty value. Do not infer spin from the result. |
| `receive_type` | `push`, `flick`, `chiquita`, `drive`, `loop`, `long_push`, `short_touch`, `other`, or uncertainty value. |
| `receive_location` | `forehand`, `middle`, `backhand`, or uncertainty value. |
| `third_ball_attack` | `yes`, `no`, or uncertainty value. |
| `third_ball_side` | For confirmed attack: `forehand`, `backhand`, `other`, `unknown` or `unclear`; `not_applicable` when no attack applies. |
| `third_ball_outcome` | For confirmed attack: `successful`, `unsuccessful`, `unknown` or `unclear`; `not_applicable` when no attack applies. Immediate action outcome is distinct from who won the point. |
| `rally_length` | Positive number of ball contacts including the serve as contact 1, or an uncertainty value. |
| `point_winner` | `player`, `opponent`, `unknown`; no winner is inferred from the next scoreboard picture. |
| `point_outcome` | `win`, `loss`, `unknown`, from the `player` perspective; must not contradict a known winner. |
| `video_timestamp` | Free text such as `unknown`; Protocol v0.3 has no PTS/time-base semantics. |
| `notes` | Nonblank observation or explicit uncertainty note. Flag any partial point here. |

Allowed uncertainty values are `unknown`, `unclear`, `not_applicable`, except identity and winner fields with their narrower values above. The authoritative checks are in `match_intelligence.py` (`POINT_FIELDS`, `CATEGORIES`, `validate_bundle`) and the existing v0.3 Schema. No separate incompatible point protocol is introduced.

## Deterministic end-to-end demo

```powershell
python products/ptti-integration/scripts/run_training_review.py --demo --output-dir products/ptti-integration/generated/goal08-training-review
```

This generates an original 24-point `SIMULATED_ONLY` CSV and declaration, re-imports it, writes JSON and Chinese Markdown reports, changes only point 1 `rally_length` from 5 to 7, re-imports the edited CSV, and writes a comparison. Running again with identical output is safe; different existing bytes require the explicit `--force` flag. The edited input remains `SIMULATED_ONLY`, with its parent hash and edit recorded by the GOAL 07 provenance mechanism. No real match, athlete, video, local permission, or Vision result is attached.

The generated files are `simulated-points.csv`, `simulated-declaration.json`, `simulated-report.json`, `simulated-report.md`, the corresponding `*-edited` files, and `comparison.json`. The comparison records both CSV and bundle SHA-256 values and the predictable rally-length mean change.

## Future manual training-match import

Choose a local source file that the user is permitted to analyze. The existing `ptti.manual-point-annotation/0.1` manifest requires `dataset_id`, exact `match_id`, `source_id`, declared lowercase `source_sha256`, `annotator_ref`, timezone-qualified `annotated_at`, `evidence_ref`, and `timestamp_semantics: PROTOCOL_TEXT_ONLY_UNBOUND`. A separate local binding record is also required:

```json
{
  "binding_version": "ptti.training-source-binding/0.1",
  "dataset_id": "<same exact ID as annotation manifest>",
  "match_id": "<same exact ID as annotation manifest and every CSV row>",
  "source_id": "<same exact ID as annotation manifest>",
  "local_asset_id": "<reviewed local asset ID>",
  "source_sha256": "<actual lowercase SHA-256 of the selected source file>",
  "match_link_status": "HUMAN_REVIEWED_DECLARATION",
  "local_analysis_permission": "DECLARED_ALLOWED",
  "rights_basis_ref": "<local reference to the specific permission evidence>",
  "reviewer_ref": "<local reviewer ID>",
  "reviewed_at": "2026-10-13T12:00:00+08:00",
  "analysis_method": "HUMAN_MANUAL"
}
```

These placeholders are **not** a claim of permission. The command rejects missing or conflicting IDs, UNKNOWN analysis permission, a false Vision method, source-byte SHA mismatch, and a file without identifiable video-stream metadata. `ffprobe` is required for the lightweight metadata probe. It does not decode the full video or check that it actually depicts the claimed match. The output status remains `DECLARED_NOT_INDEPENDENTLY_AUDITED` even when byte identity and explicit review references pass.

```powershell
python products/ptti-integration/scripts/run_training_review.py --csv C:\review\points.csv --manifest C:\review\annotation-manifest.json --source-file C:\authorized\match.mp4 --binding C:\review\binding.json --output-json C:\review\training-report.json --output-md C:\review\training-report.md
```

The source file and original CSV are never overwritten. The local JSON report includes the SHA of the original CSV, canonical input bundle SHA, source-file SHA after reading and comparison, explicit point references and each row's normalized 21 fields. The importer does not add the selected source-file path; caller-supplied `evidence_ref`, `rights_basis_ref`, and free-text notes remain in this private report and must be reviewed before any further sharing. Human data editing must change the CSV and re-import; the old annotation hash is never silently retained.

## San Pro fields and interpretation

TypeScript types: `runtime/training-review-v0.1.d.ts`. Keep the sidecar in a **local/private Pro view**. Root fields: `report_version`, `generated_at`, `dataset`, `sample`, `metrics`, `distributions`, `serve_turns`, `game_summaries`, `score_trace`, `key_points`, `watchlist`, `point_refs`, `point_records`, `limitations`, `summary_cn`.

- `dataset` has exact dataset/match/source IDs, protocol revision, provenance, CSV/bundle/source hashes, declared rights/link status, `video_timeline.status=UNBOUND`, `vision_status=NOT_TESTED`, and null event/player identity until separately reviewed.
- Every metric has `numerator`, `denominator`, `sample_count`, `missing_count`, `computation_rule`, `evidence_status`, `sample_status`, and a number/null `value` for scalar metrics. Distribution numerators are category count maps. Five resolved rows is a **product display threshold**, not proof of a stable tactical pattern.
- `key_points` require observed pre-point score for both roles, each at least 7 and at most one point apart. Unknown score or winner is never filled. `score_trace.score_after` is derived only when both pre-point scores and winner are known.
- `point_refs` bind derived natural `point_id` to CSV record ordinal, row SHA and unbound free-text video timestamp. `point_records` preserves exact normalized v0.3 fields for private review. No timestamp is a verified video seek target.
- `watchlist` holds questions to review, not video-confirmed coaching diagnoses. A review suggestion cites a `point_id` that San can resolve through `point_records` and the original CSV.
- A report with `dataset_class=SIMULATED_ONLY` cannot enter a real match or athlete record. A human report is a declaration whose visual labels, match identity and rights still need independent human acceptance. Neither class is a Vision algorithm result or permission to publish private video/annotations.

The `ptti.match-media/0.2` review/public projections and source rights remain separate. Do not promote `UNKNOWN` media rights, public listing, embedding, or native playback from this local analysis report.

## Verification

```powershell
python -m unittest products.ptti-integration.tests.test_training_review_goal08 -v
python -m unittest products.ptti-integration.tests.test_match_intelligence_goal07
```

The GOAL 08 tests exercise template importability, synthetic before/after CSV replay, per-point trace, manual-import byte and binding gates using ephemeral **test-only** bytes, invalid media metadata, duplicate IDs, invalid labels, wrong scores/order, source tampering, unsupported version, and synthetic/Vision misclassification. No actual training video or real manual point record is present in these tests.
