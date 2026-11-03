# GOAL 10.6 — Same-input Review Targets handoff acceptance

## Scope and reproducible check

Main starting commit: `6ea97363b83940e8699fb7a2f40ef4b00a795418`.
Read-only San snapshot: `55024045089037c8f3aff3f05866befa83b6453d`, clean at inspection.
San files read: `src/local-video-review.mjs`, `src/local-loss-insights.mjs`, `src/playback-adapter.mjs`, `src/LocalVideoReview.tsx`, `src/i18n.ts`, `docs/GOAL10_5_INSIGHT_TO_VIDEO.md`.

Run from the Integration repository root (Python jsonschema and Node already installed):

```powershell
$env:PTTI_SAN_WEB_ROOT='C:/PTTI-Worktrees/web-mvp-v0-1/products/ptti-web'
python -m unittest discover -s products/ptti-integration/tests -p test_review_targets_san_goal10_6.py -v
```

The Python check regenerates Main output and sends the **same input** to a Node test importing San's actual pure validation/import/grouping/playback-binding functions. No Web files, servers, browser, media, databases or Playback worktrees are changed. If the local San source is absent, cross-runtime cases explicitly skip; they are not PASS. `acceptance_binding_matches` is a test-only receiver oracle, not an implemented San consumer.

## Exact input and versions

Use **only** `fixtures/review-targets-11-8-input.json` and its corresponding `review-targets-11-8-output.json` for this comparison. Raw input SHA-256:

`f77471f5e572242f9308853cfbb55d685739fdec6da6075edc4332e1f88d8c45`

San's other 19-point demo has p002/p008/p010 in its 3–4 group. It is different data and is not a comparison baseline.

| Layer | Actual version / definition |
|---|---|
| Raw annotation | `ptti.quick-annotation/0.2`, `contracts/quick-annotation-v0.2.schema.json`; v0.1 also accepted without stage inference |
| Existing statistics | `ptti.quick-annotation-stats/0.1`; existing Schema/TS remain unchanged |
| Main view | `ptti.review-targets/0.1`; exact fields in `runtime/review-targets-v0.1.d.ts` |
| View JSON Schema | No separate review-targets JSON Schema exists; do not claim otherwise. The view is typed by TS and exercised by Golden/semantic tests. TS declarations alone do not validate untrusted JSON at runtime. |

Match the entire raw Quick input, not just dataset name: contract version, dataset_id, dataset_class, match_id, source_id, all rules context and ordered point records. Never join by title/player names. Compare `canonical_input_sha256` using the documented Python canonical JSON algorithm, not ordinary unsorted JSON.stringify. Also bind the **original input bytes** when byte-change invalidation is required (see below).

## Role, stage and Golden correspondence

San `PLAYER_A` ↔ Main `player`; `PLAYER_B` ↔ `opponent`; `UNKNOWN` ↔ `unknown`. This applies to winner and server, not verified athlete identity. Main may derive a server under the existing complete-from-start/first-server rules; San's local loss grouping does not compute that service metric.

Exact stage values: `END_AFTER_1_2_CONTACTS`, `END_AFTER_3_4_CONTACTS`, `END_AFTER_5_PLUS_CONTACTS`, `UNKNOWN`. Missing v0.2 stage is UNKNOWN; v0.1 has no stage. No third-ball or exact-length inference.

Golden results from the same input:

| View | A / player | B / opponent |
|---|---|---|
| Known score | 11 wins, 8 losses, N=19 | 8 wins, 11 losses, N=19 |
| 3–4 stage | 0 wins, 3 losses, N=3 | 3 wins, 0 losses, N=3 |
| A 3–4 loss point IDs | `SIMULATED_ONLY%3Areview-targets-11-8/g01/p002`, `/g01/p004`, `/g01/p006` (same match prefix) | no losses in this stage |
| Current-session playable after import | 0 | 0 |

The original input has 2 UNKNOWN-stage rows and no UNKNOWN winners; 12 rows have reported-duration-checked time ranges and 7 lack time. All 19 remain in score counts.

Main per-metric `point_ids.valid/won/lost/unknown/excluded` fully partitions source IDs, with valid=won∪lost and `denominator+unknown_count+excluded_count=sample_count`. Target `point_ids` is exactly the loss set, not all group IDs. For Golden A 3–4: denominator=3, unknown_count=2, excluded_count=14.

**UNKNOWN population difference:** Main `unknown_stage_count` counts all supplied rows. San `unknown_stages` counts only known-winner rows whose stage is unknown. If p014 (already UNKNOWN stage) winner becomes unknown, Main remains 2 and San becomes 1, while both known-score denominators become 18. This is an explicit population difference, not a counting bug; do not map these fields as synonyms. Main stage `unknown_count` also includes unknown winners within that stage plus unknown group membership, not just San's top-level unknown-stage count. San's local warning is currently fixed N<5; Main's configurable threshold is not consumed by San yet.

## Invalidation and game completion

Changing only p001 winner from player to opponent changes both implementations to **10:9, N=19**, changes Main canonical input SHA and moves p001 to A's first-stage loss set. This is **ongoing**, not a finished eleven-point game. Neither existing summary exports a game-finished flag. San's `COMPLETE_FROM_GAME_START` label says “确认从本局第一分完整记录”; it declares recording coverage, not completion. To display a completed game requires reliable ordered winners from 0:0 and final max(score)>=11 with a lead of at least 2. Unknown/gapped history cannot establish completion. Never retain a static “11:8 complete” label after an edit.

Main's current canonical hash intentionally ignores byte-only JSON formatting changes. Appending a newline changes raw bytes but leaves `canonical_input_sha256` unchanged. Therefore **byte-exact invalidation is not implemented by this hash alone**. Minimal receiver requirement: keep an import receipt `{raw_input_sha256, dataset_id, match_id, input_contract_version, canonical_input_sha256}` alongside the view. On any original-byte change, invalidate/regenerate before display and issue a fresh receipt. On any semantic edit, unknown view version, changed identity/reference, or edited view counts, reject the old view. The tests demonstrate a passing unchanged receipt and rejection for winner edit, byte-only edit, altered view and unknown version. No new engine or production consumer was added in this acceptance sprint.

## Playback safety and remaining integration Gate

Every Main target retains `playback_eligibility=NOT_EVALUATED_CURRENT_SESSION`. San currently obtains playable IDs only from `playbackBindings` with `binding_status=BOUND` for matching current-session identity, available duration and separately confirmed boundaries. Import resets boundary confirmations and session binding, so even the 12 supplied ranges yield 0 playable records. `LOCAL_SESSION_ONLY` remains session evidence, not independently verified media or Vision.

San currently computes local loss groups directly and does **not** load Review Targets at runtime. Cross-runtime pure-function agreement is PASS; actual Main view runtime consumption, receipt enforcement and freshness invalidation remain NOT_IMPLEMENTED in San. San must add these checks in its own workspace before claiming cross-end view acceptance. Browser/native/real-video behavior is NOT_TESTED here.

## Actual local checks

See the accompanying six acceptance tests (one Golden comparison, one single-winner edit, byte/semantic/view freshness oracle, v0.1/UNKNOWN compatibility, UNKNOWN population distinction, actual input Schema/unknown versions). The Node assertions compare both roles and all three stage groups using the same payload and verify fresh imports are UNBOUND. Existing GOAL10.5 tests remain unchanged. No engine edits, push, CI, deployment or Native launch.

Executed locally: `python -m unittest discover -s products/ptti-integration/tests -p 'test_review_targets*.py' -v` — **17 passed, 0 skipped, 0.855s** (11 existing + 6 new). Cross-runtime cases imported the pinned San modules read-only. `git diff --check` passed. This is not browser or media playback testing.

At final status San remained at the same HEAD, with newly appearing untracked `scripts/fixtures/review-targets/` and `src/contracts/` (the latter contains copied declaration files). These concurrent San-owned additions were left untouched. The runtime findings above apply to the tracked snapshot and tested pure functions, not future or unfinished San changes.
