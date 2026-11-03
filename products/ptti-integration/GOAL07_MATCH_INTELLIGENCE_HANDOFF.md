# GOAL 07 — Match Intelligence sidecar

This is a local descriptive-analysis sidecar. It does not change `ptti.match-media/0.2`, the Web catalog, Desktop databases, Vision, or research algorithms. The input follows the existing Serve & Third-Ball Analytics Protocol v0.3, schema revision `1b30e8ea0f8a90a745fb6c30105599f0334fdf7c` and preserves its 21 point fields.

## Run the deterministic demo

From the repository root:

```powershell
python products/ptti-integration/scripts/run_match_intelligence.py --write-demo-fixture products/ptti-integration/fixtures/goal07-simulated-points.json
python products/ptti-integration/scripts/run_match_intelligence.py --demo-mutation --output products/ptti-integration/generated/goal07-simulated-analysis.json
```

The fixture is 24 generated rows, one complete synthetic game, and has `dataset_class: SIMULATED_ONLY`, `match_id: SIMULATED_ONLY:goal07-match-001`, null source SHA and null timeline. No real athlete, match, media source, or PTS is associated. The writer is idempotent for identical bytes and refuses to replace a different existing file.

Use `--force` only when intentionally regenerating one of these explicitly selected output files after changing the generator.

To print an analysis for a bundle:

```powershell
python products/ptti-integration/scripts/run_match_intelligence.py --input products/ptti-integration/fixtures/goal07-simulated-points.json
```

Focused regression command:

```powershell
python -m unittest products.ptti-integration.tests.test_match_intelligence_goal07 -v
```

To import a human-annotated CSV, select the exact source video locally and provide a manifest. The importer streams SHA-256 over the selected source file, compares the declared hash, hashes the CSV, enforces all 21 Protocol v0.3 columns and validates point order and scores. It does not copy or transmit the source video. Example command:

```powershell
python products/ptti-integration/scripts/run_match_intelligence.py --csv C:\review\points.csv --manifest C:\review\manifest.json --source-file C:\authorized\match.mp4
```

The manifest must use `manifest_version: ptti.manual-point-annotation/0.1` and include `dataset_id`, explicit `match_id`, `source_id`, exact lowercase `source_sha256`, `annotator_ref`, timezone-qualified `annotated_at`, `evidence_ref`, and `timestamp_semantics: PROTOCOL_TEXT_ONLY_UNBOUND`. The importer verifies file identity and structure, not the annotator's visual judgment; output remains `DECLARED_NOT_INDEPENDENTLY_AUDITED`.

## Stable input contract

The full input definition is [match-intelligence-v0.1.schema.json](contracts/match-intelligence-v0.1.schema.json), with consumer types in [match-intelligence-v0.1.d.ts](runtime/match-intelligence-v0.1.d.ts). Root fields are exactly:

```json
{
  "contract_version": "ptti.match-intelligence/0.1",
  "dataset": {
    "dataset_id": "SIMULATED_ONLY:goal07-dataset-v1",
    "dataset_class": "SIMULATED_ONLY",
    "match_id": "SIMULATED_ONLY:goal07-match-001",
    "source_protocol": {
      "id": "serve-third-ball-analytics",
      "version": "0.3",
      "schema_revision": "1b30e8ea0f8a90a745fb6c30105599f0334fdf7c"
    },
    "provenance": {"method": "DETERMINISTIC_ORIGINAL_GENERATOR", "seed": 20261013, "generated_on": "2026-10-13"},
    "source_binding": {
      "status": "NOT_APPLICABLE_SIMULATED",
      "source_id": null, "source_sha256": null, "timeline_id": null, "time_base": null
    }
  },
  "points": ["exactly the existing 21 Protocol v0.3 fields per row"]
}
```

The v0.3 protocol has no `point_id`; the sidecar derives a stable display/reference key from the exact natural key `(match_id, game_number, point_number)`, for example `SIMULATED_ONLY%3Agoal07-match-001/g01/p001`. It never associates a match by title, athlete name, or video timestamp. The 21-field `video_timestamp` remains free text. PTS, `time_base`, `timeline_id`, precise source binding, and Vision evidence are not inferred.

The importer cannot verify that a caller-supplied real `match_id` or `source_id` equals an ID in San's catalog or the Windows library. A consuming app must require an explicit reviewed ID mapping before displaying imported real annotations alongside a catalog match. `player` / `opponent` remain protocol roles and are not athlete identities; the Protocol v0.3 row has no event or athlete-ID fields.

Every analysis result includes `input_sha256`, computed over canonical UTF-8 JSON for the exact input bundle. Consumers can retain this value with the displayed analysis; it identifies the annotation input and does not prove that the annotation is factually correct.

For San's Web client: consume the result as a separate `ptti.match-intelligence/0.1` object and keep `dataset_class` attached to every view. Do not append these point rows or summaries to `ptti.match-media/0.2` Match/VideoSource records. Do not show a simulated dataset under a real match or athlete. A future opt-in manual import can be displayed only with its actual match/source IDs and its `DECLARED_NOT_INDEPENDENTLY_AUDITED` state.

When a `SIMULATED_ONLY` bundle is interactively edited, its derived dataset receives a new synthetic dataset ID and `provenance.method = SIMULATED_INTERACTIVE_EDIT`, with `parent_dataset_id`, the canonical `parent_input_sha256`, and one exact `{point_id, field, before, after}` edit. This is lineage metadata, not a human review or factual validation claim. Consumers must keep the derived dataset in the synthetic namespace. Edits to a `HUMAN_ANNOTATION` bundle are rejected; update the source CSV and re-import it so the annotation CSV SHA remains accurate.

For 次Dex's Desktop client: the sidecar is not player/Vision evidence. `third_ball_outcome` is the immediate annotated third-ball outcome; point conversion is calculated separately as `server_won_point / confirmed third_ball_attack=yes points with known server and point_winner`. No metric can set Desktop Native Playback, Vision, or `match-media` playback statuses.

## Metrics and denominators

- `point_wins`: counts of `point_winner=player/opponent`; denominator is rows with a known winner. It describes recorded rows, not the match's final score.
- `server_point_win_rate`: server won the point divided by rows with a known server and winner.
- Serve and receive distributions: categories divided by observed values only. `unknown` and `unclear` are reported in uncertainty counts; `not_applicable` is reported separately and excluded.
- `third_ball_attack_rate`: yes divided by confirmed `yes + no`. `unknown`/`unclear` attack eligibility is reported separately; `not_applicable` is excluded.
- Third-ball side distribution: only rows with `third_ball_attack=yes`; uncertain values remain counted, not guessed.
- `third_ball_immediate_outcome`: `successful / (successful + unsuccessful)` only among confirmed attacks with a resolved immediate outcome. This is not point conversion.
- `third_ball_point_conversion`: server won the point divided by confirmed third-ball attacks with known server and point winner. Missing winner/server rows are excluded and counted.
- `rally_length.mean`: sum of positive contact counts divided by rows with a numeric `rally_length`; unknown/unclear/N/A counts are reported separately.
- Status is `NOT_ESTIMABLE` for denominator zero, `INSUFFICIENT_SAMPLE` for a resolved denominator below five, otherwise `DESCRIPTIVE_ONLY`. Five is the existing product display threshold, not a scientific reliability criterion.

No confidence intervals, significance tests, causal claims, strategic superiority claims, or model outputs are implemented. The existing Pilot 1C review marked this video/method unsuitable for tactical inference; this generated demo only exercises formulas.

## Import and validation safeguards

- Contract version and source Protocol version/revision must match exactly; unknown versions reject.
- One bundle contains one explicit match ID. Every row must match it.
- Natural point IDs must be unique; game/point order is sequential and rows must be in order.
- Server/receiver contradictions, point winner/outcome contradictions, incompatible third-ball labels, service order, and known adjacent score progression are rejected.
- Missing categorical/numeric evidence must use a protocol uncertainty value; blank CSV fields reject.
- The importer requires a selected source file and a matching source SHA for manual annotations. Paths never enter output. v0.3 timestamps remain text-only, so claiming a PTS/time-base binding rejects.
- `SIMULATED_ONLY` IDs require a synthetic namespace and a null source binding. An explicit guard refuses exporting simulated analysis into real match-media data.
- Interactive simulated edits produce a provenance-linked child snapshot. A parent hash identifies the exact parent JSON bytes under canonical serialization; consumers may not treat that hash as independent authorship verification.
- Metrics never alter provenance, evidence, rights, Web playback, Desktop playback, or Vision status.

## Files

- Input schema: `products/ptti-integration/contracts/match-intelligence-v0.1.schema.json`
- Manual import manifest schema: `products/ptti-integration/contracts/manual-point-annotation-v0.1.schema.json`
- TypeScript definitions: `products/ptti-integration/runtime/match-intelligence-v0.1.d.ts`
- Engine and CSV importer: `products/ptti-integration/match_intelligence.py`
- CLI: `products/ptti-integration/scripts/run_match_intelligence.py`
- Deterministic data: `products/ptti-integration/fixtures/goal07-simulated-points.json`
- Before/after output: `products/ptti-integration/generated/goal07-simulated-analysis.json`
- Focused regression: `products/ptti-integration/tests/test_match_intelligence_goal07.py`
