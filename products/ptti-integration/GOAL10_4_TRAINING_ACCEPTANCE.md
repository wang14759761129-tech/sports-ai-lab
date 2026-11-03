# GOAL 10.4-M — training review acceptance package

All new inputs are original `SIMULATED_ONLY` data. No real match, media decoding, native playback, Vision or rights claim is made. Work is restricted to Integration; no push, CI, deployment or Windows launch was performed.

## New defect and minimal fix

At baseline `7c197edbe78147f17ade10cd0f0c814b3f5775e5`, Quick Annotation accepted an additional point in a game whose complete known score had already ended at 11:0 or 12:10. The new failing regression reproduced that missing rejection. The adapter now raises `GAME_ALREADY_ENDED` before accepting the next same-game record. It does so only when the prior score chain is known; missing points or unknown winners still produce unknown later scores, never an invented game ending.

No field/schema/protocol/statistical formula changed. v0.1 and v0.2 valid inputs remain supported. One previous denominator test used 12 consecutive wins followed by eight losses in the same game, which was itself impossible under 11-point rules; its winners were corrected to a valid 11:9 sequence while keeping its intended 20 scores / 12 timestamp ranges / 8 missing ranges assertions.

## Reproducible data and commands

`fixtures/goal10-4-acceptance/complete-11-9.json` and `deuce-12-10.json` contain full input games with unknown technical labels and no media bindings. `post-game-invalid.json` is the minimal terminal-score validation difference: 11 consecutive player wins, then an invalid next same-game point.

From the Integration repository root:

```powershell
python products/ptti-integration/scripts/run_goal10_4_acceptance.py --san-worktree C:/PTTI-Worktrees/web-mvp-v0-1
python -m unittest discover -s products/ptti-integration/tests -p test_goal10_4_training_acceptance.py -q
python -m unittest discover -s products/ptti-integration/tests -p 'test_quick_annotation*.py' -q
python -m unittest discover -s products/ptti-integration/tests -p test_training_review_goal08.py -q
python -m unittest discover -s products/ptti-integration/tests -p test_annotation_audit_goal09.py -q
python -m unittest discover -s products/ptti-integration/tests -p test_match_intelligence_goal07.py -q
```

The runner reads San's existing local pure consumer functions without editing its worktree. `generated/goal10-4-acceptance/acceptance.json` records input hashes, engine hash, San consumer module hash/HEAD, exact counts, complete score/service traces and the terminal-rule difference. It does not start a browser/server or claim rendered UI acceptance. If a shared-count comparison differs, it includes the complete small input JSON and expected/actual fields in `unexpected_differences`.

## Golden comparison and minimum San handoff

Read-only San snapshot: `6b8ee235191b0f686d4f47f0d3d2340aba78a0f7`, clean at the time of comparison. The `LocalVideoReview.tsx` display reads `summarizeLocalQuickPoints`; its pure function was executed against both existing Golden inputs after the existing importer.

| Existing Golden input | Known winners / rows | A:B wins | Duration-checked known-score ranges | Current-session playable | Known third-ball labels |
|---|---|---|---|---|---|
| v0.1 | 4/5 | 2:2 | 4/4 | 0 | 2 |
| v0.2 | 4/5 | 2:2 | 2/4 | 0 | 1 |

Shared score counts, win counts, current-session-playable counts, explicit serve-side counts (0 in both samples), and known third-ball-label counts match. San's importer preserves the time ranges and v0.2's three observed stages; these preservation checks are not claims that the UI displays aggregate stage statistics. No media file is loaded in this comparison, so playable and independently verified media-point counts remain zero.

San does not currently consume the statistics sidecar's serve/receive rates, third-ball immediate success/conversion, key-point rates, aggregated stage distribution or configurable per-metric sample statuses. Its visible technical-sample warning uses a fixed `<5` check, agreeing only with the sidecar's default threshold of 5; custom thresholds are not wired across endpoints.

**Required San fix:** reject a new same-game point after a complete known prior score has reached at least 11 with a margin of two. The supplied negative JSON is rejected by Integration but currently accepted by San (`ok: true`). This is a validation alignment Gate, not a new JSON field or permission change. The runner reports `COUNT_BASELINES_PASS_VALIDATION_ALIGNMENT_PENDING` rather than full cross-end acceptance. No San file was changed.

Independent verified source counts are per source; San's `independently_verified_media_points` counts points. Both are zero here but must not be treated as the same unit. Quick `rally_start_ms/end_ms`, San's local session binding, Desktop asset-bound point boundaries, and PTS/time_base remain separate evidence; names and valid ranges do not establish equivalence.

## Denominators and uncertainty

- Known winners count without requiring video times. Unknown winners do not become wins/losses.
- Time-range coverage uses known-winner records as its denominator. A range checked against reported duration remains unbound and does not prove current-session playability or an independently verified source.
- Tactical distributions use only explicit applicable known labels. `unknown`, `unclear` and `not_applicable` do not become observed technique usage. Third-ball rates do not derive from stage buckets.
- Stage distribution denominator is the number of explicit non-UNKNOWN stage observations; sample_count and missing_count still disclose all rows and omissions.
- Each metric uses its own denominator. Default caution threshold 5: N=0 `NOT_ESTIMABLE`, 0<N<5 `INSUFFICIENT_SAMPLE`, N>=5 `DESCRIPTIVE_ONLY`. Configurable UI caution is not a significance test or evidence of stable long-term ability.

## Executed regressions and remaining Gates

- New training acceptance: 9 tests passed, including 100 seeded complete simulated games checked against an independent score/service state machine, both input versions, 11:9, deuce 12:10, first-server changes (serve-win numerator changes 9/20 to 11/20), winner edits, gaps/backfill, delete/restore, time coverage and N=0/4/5.
- Existing Quick/schema/Golden regressions: 37 passed; GOAL08: 11; GOAL09 formal quality/audit: 27; GOAL07 Protocol/statistics: 25. Total Integration scope: 109 passed.
- M2 targeted regression: 11 passed, 24 deselected, covering latest clip bounds, deletion/recreation, boundary revocation, boundary SHA/value mismatch, changed media and protection of unrelated user clips. Existing frontend queue guard regression passed. This reuses regression coverage rather than duplicating the separate read-only audit.
- M2 remains polling-based: 1 second interval, 2.5 second validation timeout; background throttling or blocked event loops can delay detection. Other or installed players must adopt the revision check. No native acceptance was run.
- Quick statistics are recomputed from supplied snapshots; deleted/edited inputs change their counts and invalidate later score derivation until backfilled. There is **no automatic database ScoreMoment revision-to-Quick dataset binding or report invalidation subscription**. Therefore tests of recomputed statistics and M2 clip invalidation do not prove an atomic cross-contract sync. A consumer holding an old exported report must regenerate it; this remains an integration Gate before real-data end-to-end acceptance.
- Real-video identity, permission, timeline binding and actual training-review accuracy remain unverified. UI rendering, Windows build and deployment are out of this task's scope.
