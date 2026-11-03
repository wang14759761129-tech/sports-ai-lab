# Cinema original restoration — isolated QA candidate

Base: GEX03E `c6b0a94a3dbbb2306c3556e3d24a24a4faff8e60`, descendant of Founder QA `02196f19980915a1ba5f10c244609a26de1564d3` and original `5cc753886b112305736fcc14ea77b37662726c9f`. The San GEX06R `71ff6afb585937022fdeedfd25090bf85bdb87bd` branch shares 5cc history but diverges; no branch merge was performed.

## Scope
`VideoFeed.tsx` preserves its actual c6 implementation; the only change passes `qaMoment` into its already-existing Pro Lab space. `video-feed.css`, `feedCatalog.ts`, `thumbnailPermission.mjs`, original favorites/Story/official routing, Pro Lab notes and Fan Arena are unchanged. No new Cinema page, local file picker, or animated poster was added to the Cinema wall. Original approved-code Founder QA mode still permits the exact eight remote previews only under `INTERNAL_FOUNDER_QA`; it does not grant distribution, cache or embedding rights.

`ProLab.tsx` retains the existing HTML5 player and notes. In Founder QA only, after user selects and loads a local video, `GexMomentRestore.tsx` offers the `71ff6af` Moment backup preview/merge/replay module. It computes the full video content ID before matching a backup. It neither binds the local file to a professional match nor modifies official iframe behavior. Existing Pro Lab notes and its metadata-based identity remain separate and untouched. The copied `arena-events.mjs` is a dependency of the evidence module; it is not wired into the original Fan Arena in this revision. Original Fan Arena remains available.

## Local test results
- `tsc -b`: PASS.
- `node scripts/test-gex-moment-bridge.mjs`: PASS, including wrong content/time, invalid JSON, quota failure, stale preview and old Pro Lab storage preservation.
- `node scripts/test-pro-lab-view.mjs`: PASS after adapting its temporary SSR harness to the added module. No GUI implication.
- Existing Feed, Moment, Moment backup, Pro Lab notes, favorites, thumbnail permission, media distribution, Fan Arena and Grand Navigation checks: PASS.
- Exact bytes of the three GEX06R logic modules equal commit `71ff6af`.
- Original 71ff synthetic 12-second video plus its two-Moment fixture: content identity, preview and merge PASS at the logic layer. No real browser playback observed.
- No dependencies added; node_modules is a read-only-use junction to the existing Main installation, not a code copy. Do not run the delivery script `dev_sync.py`.

## Evidence boundaries
The historical GEX03E Founder screenshot and `thumbnail-results.json` are at `<LOCAL_USER_ROOT>/Documents/Codex/2026-10-17/referenced-chatgpt-conversation-this-is-an/outputs/GEX03E-20261027/`. The report records eight decoded YouTube thumbnails out of nine displayed cards; the other card uses fallback. These are **historical internal QA**, not evidence of this candidate or any public distribution permission.

An exact-commit 5cc screenshot was not located. No candidate screenshot, side-by-side comparison, actual file picker, video play, Moment import or Seek has been observed. `GUI_VISUAL=NOT_TESTED`, `REAL_PLAYBACK=NOT_TESTED`, `SIDE_BY_SIDE=NOT_TESTED`. RAM observation was 1.299 GiB, below the existing browser guard; no browser instance was launched. Do not represent old screenshots as the new candidate.

## HOST isolated manual QA preparation
The candidate is not currently running. Never point it at an existing `8765` server or real user storage. The Vite candidate requires an explicit `PTTI_FOUNDER_QA_API=http://127.0.0.1:<isolated-port>` and rejects missing/non-loopback targets in Founder QA mode. `PTTI_ENV=test` requires `PTTI_DB` under system temp; give the API a unique QA database and isolated LOCALAPPDATA. Check ports before launch and use strict ports, keeping all user processes alive. Use an approved resource window and the existing safety monitors; this document is not permission to bypass them. Do not deploy or package an EXE.

Suggested manual verification with the existing, PTTI-owned synthetic video and synthetic JSON fixture in `C:/PTTI-Worktrees/gex06r-moment-restore/products/ptti-web/prototypes/gex06/`:
1. Compare an actual original 5cc screenshot against candidate Cinema at the same 1440px viewport and scroll position. Record columns, image area, actual source cards, search/categories, density, stars, Story, scroll and match-entry path. The Founder QA remote image mode must stay internal and only load the approved list; image accessibility is separate from licensing.
2. From Cinema, open a match/Story then Pro Lab using existing navigation. Select `media/rally.mp4`; wait for video metadata and click Enable Moment Restore.
3. Import `qa/roundtrip-example.json`; preview two additions, cancel once, reselect the same file, confirm, and click a restored Moment. Observe the video frame/time and screenshot only the synthetic material. Then confirm return to Cinema. Do not imply the synthetic video belongs to that real match.
4. Check existing local Pro Lab note capture/replay, favorites and original Arena entry without touching real user data. Stop at any policy/tool restriction.

R4 source integration is MAIN's responsibility; this branch is a reviewable candidate, not a production patch or release authorization.
