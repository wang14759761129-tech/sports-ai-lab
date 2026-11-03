# GOAL 10 — Quick Annotation adapter v0.1

`ptti.quick-annotation/0.1` is a compact input adapter for Web point capture. It outputs a review-only draft whose CSV has the exact 21 Protocol v0.3 columns. It does not create a `ptti.training-review/0.1` report or modify the existing quality-review/audit formats.

## San contract check

The San Web worktree was read-only inspected at HEAD `0824acbb8bcb80d8ab3eec3ef34d45aaaff0c725`. Its current Pro path imports `ptti.training-review/0.1`, displays point IDs and unbound timestamps, and routes accepted reports through the existing training quality-review flow. No GOAL10 Quick Annotation input schema or point-entry API was found in the inspected Web files. This v0.1 contract is therefore a concrete handoff proposal derived from the requested Web fields, not a claim that San has already integrated it.

## Run

From the repository root:

```powershell
python products/ptti-integration/scripts/run_quick_annotation.py `
  --input products/ptti-integration/fixtures/quick-annotation-v0.1-valid-simulated.json `
  --output-json products/ptti-integration/generated/goal10-quick-annotation/draft.json `
  --output-csv products/ptti-integration/generated/goal10-quick-annotation/protocol-v0.3-draft.csv
```

The sample is explicitly `SIMULATED_ONLY`. It writes a draft JSON and a CSV that round-trips through the existing strict 21-column parser. `protocol.sequence_valid` separately reports whether the row IDs form sequences beginning at game 1, point 1 without gaps; parser compatibility alone does not imply a valid analysis sequence. The output is not a valid formal Match Intelligence bundle: it has no human manifest, source-byte verification, rights review, or completed quality audit. Existing training report import remains the next step after the user completes those gates.

## Input shape

The JSON Schema and TypeScript declaration are `contracts/quick-annotation-v0.1.schema.json` and `runtime/quick-annotation-v0.1.d.ts`. The top-level input has an explicit `dataset_id`, `dataset_class`, `match_id`, video duration context, per-game rule context and `points`.

Each point needs a canonical PTTI `point_id` in the form `quote(match_id, safe='')/gNN/pNNN` (UTF-8 percent encoding, leaving only RFC 3986 unreserved characters), observed `server` and `winner` sides (or `unknown`), a partial `observed_tactics` object, and both rally time endpoints in integer milliseconds or both null. Missing tactical fields become `unknown`. Only exact existing Protocol v0.3 values are accepted; unknown labels and extra fields are rejected. The player/opponent labels are role labels, not proof of athlete identity.

`source_id`, if supplied, is only a user-selected reference. Rights, local analysis permission and embed permission remain `UNKNOWN`; source hash, local path, timeline ID, PTS and `time_base` remain null. The reported player duration is used only for range validation and is marked unverified. The accepted timestamp range is `0 <= rally_start_ms < rally_end_ms <= duration_ms`; the Protocol v0.3 text field carries an `UNBOUND` marker.

## Rule derivation and promotion boundary

- Scores derive from 0:0 only when the game context explicitly says `COMPLETE_FROM_GAME_START`, point 1 is present, the point sequence has no gap, prior winners are known, and the current server side is known. Once a winner or preceding point is missing, later scores remain `unknown`.
- Server rotation derives only with complete-from-start context and a known first server (explicit in game context or observed at point 1). The adapter checks every supplied known server against that rule and rejects a conflict. It represents the serving side/team, not an individual server identity.
- Receiver is the opposite known side. Point outcome maps directly from the explicitly supplied winner. These derivations carry per-field provenance in the draft.
- A key-point candidate appears only when the derived player/opponent pre-point score is known, both sides have at least 7 and differ by no more than 1. This is a derived candidate, not an independently confirmed competitive fact.
- Spin, placement, receive action, third-ball action/result and rally length are copied only when explicitly observed. Result does not infer technique.
- Every output remains `LIGHT_ANNOTATION_DRAFT` / `REVIEW_REQUIRED` (or `SIMULATED_ONLY`) with `formal_report_eligibility.eligible=false`. The consumer must not feed it to the Pro report renderer as a completed report. After identity/source/rights declarations, source-file SHA verification and existing formal import/audit pass, the resulting `ptti.training-review/0.1` can be consumed through San's current path.

## Samples and test command

- Valid simulated sample: `fixtures/quick-annotation-v0.1-valid-simulated.json`.
- Invalid time range: `fixtures/quick-annotation-v0.1-bad-time-range.json`.
- Invalid tactical label: `fixtures/quick-annotation-v0.1-bad-tactic.json`.

Run the regression from the existing test directory so GOAL09 can import its GOAL08 test helper:

```powershell
Push-Location products/ptti-integration/tests
python -m unittest test_quick_annotation_goal10 test_training_review_goal08 test_match_intelligence_goal07 test_annotation_audit_goal09
Pop-Location
```
