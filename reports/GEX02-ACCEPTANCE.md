# Grand Experience 02 — 2026-10-26

Source baseline: `4468b26d7b0ca8630381b00c477d76892b32d601`, branch `codex/goal99-r4-cinema-evolution`. Final source identity: the Git commit containing this report. No formal installation, launcher, user database, media or release change.

## Product change

Founder QA only: the small camera control beside the four-space navigation opens four screenshot targets, explicit human verdicts and metadata-only local JSON export. It does not collect screenshots, recordings, notes, favorites or private file paths. Feedback survives dialog close/reopen, but is intentionally volatile across refresh; the panel says to export first. Browser download completion is not asserted. Export is self-reported, reviewer-unverified and source-unbound: pair it with this Git receipt; it never constitutes automated Founder approval.

Navigation gains a restrained gold accent; cover containers gain focus/hover contrast without image manipulation. Arena separates critical-score headline from point-count details. No scoring engine, grid, media rights or storage semantics changed. New panel remains lazy-loaded.

## Executed evidence

- Browser reused existing loopback Founder QA service at http://127.0.0.1:5173/ and existing Ego page. Dialog: four targets, export request notice, hostile feedback rendered as text (zero injected images), Arena target opens existing 10:10 simulated state, feedback retained on reopen, Escape closes and restores focus to camera. Automated test verdict/feedback cleared afterward; no Founder verdict invented.
- Responsive DOM/layout: 1440px=4 columns, 768px=2, 390px=1; four navigation controls and no horizontal document overflow at each size. Screenshot capture attempted once: `Page.captureScreenshot` CDP timeout. Visual taste remains Founder review, not screenshot PASS.
- During the tested session: eight YouTube cards reported LOADED with `YOUTUBE_INTERNAL_QA_REMOTE`, Bilibili reported FALLBACK. This is image-loading evidence only, not distribution permission. After final reload the immediate sample still showed eight LOADING; no later observation was claimed.
- Dev reload DOMContentLoaded ~65.6ms/load ~66.4ms (warm local observation only), zero initial optional-space/panel requests. Measured automation click-to-ready round trips: Arena448ms, ProLab971ms, Moments1023ms, Cinema655ms. These include automation overhead and are not performance targets.
- One controlled official 0Q page visit: exact ID/title present; ad=true, currentTime23.40s/duration57.90s, readyState4,589 frames. Browser tree reached1743.6MiB, above existing1536MiB budget: immediately navigated back to QA and stopped. Official page OPEN PASS; AD PLAYBACK OBSERVED; MATCH PLAYBACK NOT_TESTED; complete-watch NOT_TESTED. No ad skipping, challenge bypass or repeated attempt.
- Screenshot: BLOCKED; manual screenshot workflow available. Native EXE: NOT_BUILT, heavy guard BLOCKED. See `GEX02-NATIVE-PREPARATION.json` for actual interface/dependency gaps.

## Tests

PASS: `npm run test:founder-review`; `test:feed`; `test:goal99-story`; `test:favorite-persistence` (6 scenarios); `test:official-theater`; `test:youtube-thumbnail`; `test:media-distribution`; `test:moments`; `test:pro-lab`; `test:fan-arena`; `test:fan-arena-storage`; `test:grand-navigation`.

PASS: `.venv/Scripts/python.exe -m pytest tests/test_muse_favorite_http.py tests/test_external_links.py -q` from `products/ptti`, explicit PYTHONPATH, PTTI_ENV=test, PTTI_DB and LOCALAPPDATA bound to fresh OS-temp `PTTI-GEX02-pytest-20261026`; 13 passed. Real HTTP/SQLite test uses pytest temp DB. Initial system Python lacked pytest; first venv invocation from repository root lacked backend import path. Both setup errors corrected before the successful run; no production database imported.

PASS: `npm run build` (TypeScript project check + Vite), main498.17kB, new lazy review chunk4.70kB; `git diff --check`. No threshold increase. Final build includes the download-request wording correction.

## Founder handoff

Open existing QA URL → camera icon. Capture Cinema fullscreen, Arena critical point, Pro Lab with a video you own, and narrow navigation (~390px). Windows: F11 then Win+Shift+S; choose only the intended window, avoid private filenames/notes. Set optional verdicts, export feedback before refresh, attach the four chosen screenshots manually. Export does not upload anything.

Next priorities: (1) use those four images for bounded Founder-led visual correction; (2) Host-owned isolated stable-origin/profile verification for Native local records; (3) resource-budgeted actual match playback check. Highest immediate value is Founder visual feedback, since build/DOM checks cannot judge the intended flagship feel.

Rollback: keep formal R4 untouched. On a clean isolated branch, revert this sprint's single commit to restore the prior source; do not reset/clean, modify browser storage, or delete QA/user databases. No Host rebuild or release activation has been performed.
