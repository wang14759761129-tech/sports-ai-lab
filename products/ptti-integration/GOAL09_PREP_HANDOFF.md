# GOAL09-Prep: manual annotation quality and private handoff

This is executable preparation for a future locally authorized training video. No real coach, athlete, match, rights evidence or training video was supplied. Real operation, complete video decoding and Vision remain NOT_TESTED. TEST_ONLY fixtures use a mocked metadata probe, never a verified real video.

## Contracts for San

`runtime/training-handoff-v0.1.d.ts` describes the new private envelope. Exact root keys:

`package_version`, `visibility`, `protocol_fields`, `csv_utf8`, `csv_sha256`, `inputs`, `report`, `quality`.

Only `ptti.training-handoff/0.1`, `PRIVATE_REVIEW_ONLY`, and the ordered existing 21 fields are supported. `report` remains the unmodified GOAL08 `ptti.training-review/0.1` shape. San can extract `package.report` for the existing import renderer; no San files were changed. It must keep SIMULATED_ONLY / DECLARED_NOT_INDEPENDENTLY_AUDITED visible and never publish this private envelope into a match-media feed.

`quality.coverage` gives per-field known/unknown/unclear/not_applicable counts. `quality.findings` gives exact point ID, CSV record ordinal, normalized row SHA and fields requiring review. `quality.metric_flags` preserves denominator, missing count and low-sample status. Five observations is a display threshold, not statistical significance. unknown and unclear remain separate; not_applicable is not a failed action. CSV record ordinal includes header and is not a physical line offset when notes contain embedded newlines.

CSV must be UTF-8 without BOM for exact byte round-trip in this envelope. `validate_package` reconstructs import, report and quality from CSV and declarations and compares all content; hashes locate bytes and do not prove truth, authorship or rights. Human verification requires the separately selected local source file and ffprobe. Do not accept a new version or merely trust supplied statistics/hash strings.

## Reproduce the committed simulated example

From repository root:

```powershell
python products/ptti-integration/scripts/training_handoff.py verify --package products/ptti-integration/fixtures/goal09-simulated-handoff/simulated-handoff.json
python products/ptti-integration/scripts/training_handoff.py demo --output-dir products/ptti-integration/generated/goal09-new-demo
python -m unittest discover -s products/ptti-integration/tests -p 'test*goal*.py' -v
```

The example contains 24 original simulated points. It has no real source binding. The demo refuses an existing output directory; every output operation uses exclusive creation.

## Future coach/athlete local workflow

1. Select only a video you are authorized to analyze locally. Assign explicit private dataset/match/source IDs; names do not establish identity. No video download or network is involved. Initiate a NEW draft:

```powershell
python products/ptti-integration/scripts/training_handoff.py init --source-file 'D:/authorized/video.mp4' --output-dir products/ptti-integration/generated/my-training-draft --dataset-id private-session-001 --match-id private-match-001 --source-id private-video-001 --annotator-ref private-coach-ref
```

This probes metadata and hashes bytes; it does not decode or play the video. The source is unchanged. `points.csv` has the exact header; `row-draft.json` has all 21 fields. Game/point counters start at 1; all unobserved values remain unknown. Edit the draft row after actually watching the video. Use unknown for not observed, unclear for an ambiguous observation, and not_applicable only when protocol eligibility allows. Never replace uncertainty with a guess. Use an observation note.

2. Append one manually completed row to a NEW CSV. The existing importer checks duplicate IDs, required fields, categories, scoreboard/service order and third-ball dependency consistency before writing. Each subsequent append uses the preceding CSV as input and a new output name:

```powershell
python products/ptti-integration/scripts/training_handoff.py append --csv products/ptti-integration/generated/my-training-draft/points.csv --row-json products/ptti-integration/generated/my-training-draft/row-draft.json --manifest products/ptti-integration/generated/my-training-draft/manifest.json --source-file 'D:/authorized/video.mp4' --output products/ptti-integration/generated/my-training-draft/points-01.csv
```

3. The coach/reviewer must actually confirm the video depicts the privately identified session and identify a permission basis. Keep `match_link_status` and `local_analysis_permission` UNKNOWN until that review occurs. Set binding to HUMAN_REVIEWED_DECLARATION / DECLARED_ALLOWED only after the actual review; supply local_asset_id, rights_basis_ref, reviewer_ref and timezone-qualified reviewed_at. Fill manifest evidence_ref and annotated_at with the actual annotation evidence/time. Never put secret URLs or credentials in these references. These are declarations, not independent verification or public distribution rights. Missing/draft references are rejected.

4. Pack the final CSV with the reviewed declarations. Existing manual manifest/source binding versions stay unchanged:

```powershell
python products/ptti-integration/scripts/training_handoff.py pack --csv products/ptti-integration/generated/my-training-draft/points-01.csv --manifest products/ptti-integration/generated/my-training-draft/manifest.json --binding products/ptti-integration/generated/my-training-draft/binding.json --source-file 'D:/authorized/video.mp4' --generated-at '2026-10-14T12:00:00+08:00' --output products/ptti-integration/generated/my-training-draft/handoff.json
python products/ptti-integration/scripts/training_handoff.py verify --package products/ptti-integration/generated/my-training-draft/handoff.json --source-file 'D:/authorized/video.mp4'
```

Replace the example report time with the actual generation time. Keep the source path local; it is not included in the envelope. No source video is copied into the package.

5. To record review decisions, use `ptti.annotation-review/0.1` with CSV hash, reviewer reference, timezone-qualified review time and a nonempty decisions array. Every decision names a point ID, exact row SHA, protocol field, reason and disposition (UNRESOLVED / NEEDS_REANNOTATION / REVIEWED_DECLARATION). Run `review --package handoff.json --decisions decisions.json --source-file ... --output new-receipt.json`. Stale CSV/row hashes, duplicate point+field decisions and blank reasons are rejected. The receipt retains dataset class and DECLARED_NOT_INDEPENDENTLY_AUDITED; it never edits the CSV. Correct labels in a new source CSV and recompute a new package before reviewing again.

## Boundaries

No Web public contract, desktop, DB or San workspace changes; no push, CI or deployment. Report time is a declaration; source hash is byte identity. PTS/time_base remains UNBOUND, precise video seek is unavailable, complete decoding NOT_TESTED and Vision NOT_TESTED. Human accuracy/rights/identity and actual coach usability remain NOT_TESTED until real evidence and operation exist.
