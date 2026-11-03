# Grand Experience 01 — original R4

Open http://127.0.0.1:5173/ . Four-space navigation is above the original wall.
It stays below the original header while scrolling. Click a space, or use
Tab / Left / Right / Home / End to focus its button and Enter to activate.
The old entries remain under **快捷入口**.

First entry loads each optional module. Later switches hide the same mounted
panel, retaining drafts and selected video. Pro Lab pauses when inactive;
returning does not autoplay. Refresh still requires reselecting a local video;
saved browser records remain. No video bytes are uploaded or persisted.

`BASELINE.json` pins the accepted 30834c4 source, local annotated checkpoint,
committed configuration hashes and prior receipts. `RESULTS.json` records this
sprint's actual browser observations and built-file hashes. The checkpoint does
not copy, migrate or erase a database, browser record or video. Recover with
new local revert commits for this sprint (reverse order), or create a separate
recovery worktree from the checkpoint. Never reset a dirty worktree or switch
the formal launcher.

Important evidence boundaries:

- Eight Founder QA thumbnails really decoded; normal distribution still
  approves zero photographic assets. No media permission changed.
- The exact YouTube page opened with the matching title, then displayed an ad.
  Resource Policy V2 stopped further playback QA when the existing browser
  exceeded its budget. This is not match-footage playback PASS.
- Original synthetic local video proved pause-on-switch before natural end.
- Moment/Pro Lab saved bytes and all three prior Arena history entries remained.
  Arena's current fictional game was advanced to 10:10 for phase-style QA.
- System screenshot discovery exposed no existing Ego/PTTI window. The known
  CDP capture timeout was not repeatedly retried. Pixel/Founder approval and
  Native acceptance remain separate from DOM/layout and interaction PASS.

For a manual screenshot, open the QA page in the existing browser, select
Cinema, and capture the browser window at a desktop width above 1150px. Also
capture Arena at 10:10. No installation or formal entry change is required.

Run checks from `products/ptti/frontend`: `npm run test:grand-navigation`, the
existing Feed / Story / favorites / Moment / Pro Lab / Arena / media scripts,
then `npm run build` and `node scripts/check-media-distribution.mjs dist --windows`.
`cached-covers.mjs` exports `verifyCachedCovers(page)` for the supported browser
tool: on the isolated Founder wall with all eight cards, it checks real decode
and LOADED state, then repeats across two reloads. It reproduced FAIL before
the fix and PASS after it. No raster is downloaded into the repository.

SQLite tests ran with explicit system-temp PTTI_DB, PTTI_ENV=test and isolated
LOCALAPPDATA, using `tests/test_muse_favorite_http.py`. Desktop sync, push,
deployment and Native packaging were not executed.
