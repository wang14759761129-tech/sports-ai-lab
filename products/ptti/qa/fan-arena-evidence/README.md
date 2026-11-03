# Fan Arena 0.1 in original R4

Open http://127.0.0.1:5173/ and choose **Fan Arena** above the original wall.
The existing Windows browser page is left in Arena. Refresh returns to Cinema;
re-enter Arena to resume the saved game and history. No EXE was built.

Playable verification: select NEXT_POINT / 雷霆, lock, fast-forward to 9:9.
The first-point prediction is settled once, correctly. At 9:9 select
FIRST_TO_GAME_POINT / 雷霆, lock, advance to 10:9 (game point), then 10:10.
Select GAME_WINNER / 雷霆, lock and advance through 11:10 to 12:10. This is
one fictional game. Refresh, re-enter, inspect the three resolved records,
start a new simulation, and return to Cinema. Search/category remain intact.

Persistence is transactional from the UI's perspective: write succeeds before
score, predictions, history or success feedback change. Initialization is one
complete lazy snapshot, with no mount-save effect. Corrupt/unreadable/conflicting
archives are preserved and writes disabled; equivalent legacy prediction types
are normalized to the same event ID. Storage remains the existing isolated
`ptti-fan-arena-v1` localStorage key, with no SQLite or Journal writes.

Real browser StrictMode testing mounted the actual component twice with a
read-only injected archive, not a fake component: two reads per dev StrictMode
mount, zero writes, three history rows retained, original bytes unchanged.
Quota and malformed-archive checks also used scoped storage interception and
restored the original methods in finally blocks. Existing user records were
not cleared. Screenshot capture timed out; interaction PASS is separate from
screenshots and Native acceptance.

From `products/ptti/frontend`:

```powershell
npm run test:fan-arena
npm run test:fan-arena-storage
npm run test:cinema-viewing
npm run test:feed
npm run test:goal99-story
npm run test:favorite-persistence
npm run test:media-distribution
npm run build
node scripts/check-media-distribution.mjs dist --windows
```

SQLite regression was run with explicit system-temp PTTI_DB,
PTTI_ENV=test and isolated LOCALAPPDATA, using
`tests/test_muse_favorite_http.py`. No backend import against a default DB.

`RESULTS.json` records the supplied patch hashes, actual browser observations,
build hashes and remaining limits. Arena is lazy-loaded under the existing
WorkspaceFrame/returnToWall pattern; it introduces no initial-mount scroll
effect and does not replace the Cinema route. The original media gates and
Founder QA/distributable split are unchanged. Roll back this sprint with
`git revert <the commit containing this evidence>`, preserving prior history.
