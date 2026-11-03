# GOAL 10.4-M3 — direct score playback version protection

Actual starting HEAD was `ca6cfa263d3e097e1f5f9ffe3dad3bd637d11ab9`, clean, including the completed GOAL10.4 acceptance work. The reported `7c197ed...` was an ancestor; no work was reset or overwritten.

## Reproduction and fix

The new regression extracts the actual component function declarations with the TypeScript AST and executes them with controlled media/API state. Before the fix, clicking direct confirmed-point playback with a cached 10000–12000ms row set the playhead to 8.5 seconds (the cached start minus its 1.5-second pre-roll), without a latest-fragment request. The test expected the updated 14-second start and failed (`8.5 !== 14`). This is a deterministic production-function test, not a rendered-browser or decoded-media test.

Direct playback now submits only `point_id` to the existing score playlist builder, loads its current owned clip, checks the returned revision, and invokes the existing validation endpoint. It refreshes the local clip cache and uses the existing `openClip` path in exact-point mode: 14–17 seconds, no context pre-roll. It does not read playable times from the cached score row.

The existing backend remains responsible for video SHA/availability and independent start/end evidence checks. Deleted, unconfirmed, revoked or changed-media points fail the existing API gates. Missing/mismatched revisions fail closed; a concurrent edit during retrieval cannot fall back to old cached times. The frontend additionally compares the fresh clip SHA with loaded video metadata.

The direct selected clip is now in `rangePlayback`, so it participates in `watchScorePlaylist`. Failed validation, timeout or invalidation pauses media and clears pending seeks, selected clip, range/loop/queue state. Loading and pre-opening score clips use the same 2500ms timeout policy. Request generations prevent late resolutions reopening playback after navigation/unmount. Normal observations remain paused clue navigation and are not promoted to confirmed-point playback.

## Entry coverage (Integration desktop frontend)

| Entry | Route / protection | Verification scope |
|---|---|---|
| ScoreNavigation “播放已确认的一分” | `jumpToScore(true)` → latest score clip → `openClip(exact)` → active guard | Actual component function regression + existing API regressions |
| Five fixed score buttons | Same `jumpToScore(true)` handler | Shared handler tested; component wiring inspected |
| MatchVideoLibrary direct point | `_playConfirmedPoint` → `main` target prop → same direct handler | Wiring inspected; shared handler tested |
| ScoreNavigation continuous playback | Existing builder → pending score IDs → `openClip` → active guard | Existing API/guard regression; wiring inspected |
| MatchVideoLibrary continuous playback | `main` builder → initial playlist prop → `openClip` → active guard | Existing API/guard regression; wiring inspected |
| Score clips in cards, collections, ordinary playlist | Owned score clip → `openClip` revision check → active guard | Common function/guard tested; collection wiring inspected |
| Previous / next / replay / automatic next | `openClip` / `openRef` with revision check | Wiring inspected; shared validation path tested |
| Current-score loop (boundary / ended) | Score clips re-enter `openRef`; manual clips keep their ordinary seek | Boundary-loop function tested; ended callback inspected |
| Context preview if selected clip is score-owned | `openClip(exact)` instead of unvalidated direct seek | Actual context function rejection tested |
| “查看视频线索” | Paused observation seek, no automatic point playback | Actual function tested; no evidence promotion |
| Legacy non-ScoreMoment point editing | Paused seek only | Wiring inspected; not a confirmed-score playback path |
| Whole video, free seek, native media controls, AI/manual non-score clips | Ordinary local viewing; score guard applies while an owned score segment is active | Manual-clip isolation tested; no claim of score confirmation outside range mode |
| Vision / separate Playback Core / installed old versions | No ScoreMoment direct-time playback route found in this frontend search; independent runtimes not modified | Not covered by this local delivery; no cross-runtime/native PASS claimed |

## Actual tests and resource boundary

- Before fix: direct-entry regression FAIL, cached 8.5s seek instead of fresh 14s.
- After fix: `test-direct-score-entry.mjs` PASS: latest bounds, exact end, stale/error rejection, loaded SHA mismatch, revision race, real default pre-play timeout, active timeout pause/clear, navigation cancellation, score loop/context checks, observation and manual-clip isolation.
- Existing `test-score-playlist-guard.mjs` PASS: revision invalidation, offline/timeout fail-closed, cleanup and ownership filtering.
- Existing score API Python regression: 35 passed, including edits/deletes/undo, both boundary revocations, media identity changes and unrelated user clip protection. Backend code was not changed by M3.
- Full frontend no-emit TypeScript check passed using the existing dependency runtime read-only and the temporary compiler configuration from M2. No other worktree source was modified.
- Isolated browser check: **BLOCKED**. Available physical RAM measured 1.59 GiB, below the existing browser regression's 2.75 GiB startup / 2 GiB runtime guards. No browser or Windows candidate was launched; no media decode, DOM integration or native GUI acceptance is claimed.

From `products/ptti/frontend` (normal installed frontend dependencies):

```powershell
node scripts/test-direct-score-entry.mjs
node scripts/test-score-playlist-guard.mjs
```

This worktree has no local node_modules. The executed direct-entry command used `PTTI_TYPESCRIPT_MODULE` pointing to the existing TypeScript compiler in the original repository; it only reads it. Backend tests used the existing isolated temporary pytest 8.4.2 environment, with `PYTHONPATH=products/ptti` and `pytest products/ptti/tests/test_score_navigation.py -q`.

## Remaining risks / release status

Active detection remains polling-based: nominal 1-second checks and 2.5-second request timeout, with delays possible under background-tab throttling or a blocked event loop. This is not instantaneous stream revocation. Timed-out requests are ignored for playback but may complete at the transport layer later. Old installed players and other clients without revision monitoring remain unprotected until separately integrated, built and accepted.

No San LOCAL_SESSION_ONLY semantics, Quick Annotation schemas, Protocol v0.3, training acceptance fixtures or formal audit interfaces changed. No push, CI, build, deployment, Launcher update or native candidate startup was performed. Browser/native release Gates remain unverified.
