# GOAL 10.3-M2 — stale score clips and active queues

Baseline: `47db68e0187c5f2e4cdd562daf424b32afb422f7`. Changes are restricted to the Integration worktree; no Windows candidate, CI, deployment, or other owner's worktree is used.

## Reproduction

`test_score_playlist_rebuild_uses_latest_boundaries` failed before the fix: create a confirmed point at 10000–12000 ms, build its score clip, edit to 14000–17000 ms, and request a new playlist. The clip remained 10000–12000 ms. The old playlist code skipped saving whenever `score:<point_id>` already existed; point edits/deletes never invalidated that generated reference.

## Fix and compatibility

- Point edits, undo (through the same save path), boundary confirmation revocation, and draft deletion invalidate the owned score clip in the same SQLite transaction. Existing evidence/audit schemas are unchanged; invalidation is recorded with an additional audit action.
- Ownership requires the exact score key, matching `score_moment_id`, `MANUAL_SCORE_SEGMENT`, and `MANUAL_CONFIRMED` source. An unrelated manual clip is neither deleted nor overwritten, including an ID collision. Collections retain their ID references; missing/deleted clips cannot be played and must be rebuilt from valid points.
- An explicit boundary revocation overrides whole-point confirmation and leaves the record `REVIEW_REQUIRED`. Existing policy still permits deleting only review drafts; confirmed records are corrected rather than silently deleted.
- Playlist construction reads current points and videos and writes generated clips under `BEGIN IMMEDIATE`, with rollback of partial results. It checks point state, both boundary evidence values/status/SHA, source hash verification, availability, and duration. Existing generated clips are refreshed from that snapshot, including legacy clips lacking revisions.
- Existing `evidence_ids` remain. Additive `score_references` entries contain `evidence_id` and `score_revision`. The revision binds point ID, asset ID/SHA, boundaries, verification/evidence, and update time. It is a freshness token, not proof of annotation truth or authorization.
- `POST /api/video-evidence/scores/playlist/validate` checks each revision against both the current point and generated clip. Deleted points, changed versions, revoked evidence, or changed media fail closed.
- The Integration player validates generated score clips before opening them and monitors active score queues every 1000 ms. Conflict, failed validation, or a 2500 ms validation timeout pauses media, clears pending playback/loops/queue state, and requests rebuilding the queue. Cleanup ignores late responses; request generations prevent an older validation response reopening a clip after navigation.

## Remaining risk and acceptance boundary

This is polling, not immediate server push. Normally detection takes up to one polling interval plus request/timeout time; browser timer throttling or a blocked event loop can delay it. The media stream itself is not revoked. Already-installed or other cross-platform players that do not call the revision endpoint can still retain cached queues. They must adopt the validation contract before claiming the same protection.

No native window or real media playback was started. Guard callback tests and type checking do not prove native media pause behavior; integrated browser/native acceptance remains NOT_TESTED. No existing desktop version contains this local source fix until separately built and accepted.

## Reproduction commands

Python uses an isolated temporary virtual environment with pytest 8.4.2 and the host's existing application dependencies. Fixtures create only temporary QA SQLite databases and synthetic test bytes with mocked metadata; they do not decode real matches or read personal databases.

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'products/ptti')
<isolated-python> -m pytest products/ptti/tests/test_score_navigation.py products/ptti/tests/test_video_evidence.py -q
```

From `products/ptti/frontend`:

```powershell
node scripts/test-score-playlist-guard.mjs
```

Final score regression: 35 passed (41.34 s); standard video-evidence regression: 30 passed (22.58 s). Both used the final backend code. The frontend guard regression, full frontend no-emit TypeScript check, Python compile check, and `git diff --check` passed. TypeScript used existing dependencies read-only with a temporary compiler configuration; no dependency installation or source edit was made in other worktrees. TestClient emitted an existing httpx deprecation warning; no test failure was suppressed.

Protocol v0.3, Quick Annotation v0.1/v0.2, Golden Fixtures, existing formal audit interfaces, R4, Launcher, and user data are unchanged. Dev-sync is deliberately not invoked because this task explicitly authorizes a local commit only and prohibits candidate startup/deployment.
