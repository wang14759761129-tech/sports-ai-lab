# Moment Cards integration candidate

Baseline: `dcf88aa3a43293bf356f21d15f75a3468ffe79d4`.
Patch input byte hash and browser observations: `RESULTS.json`.

## Open the product

Existing isolated Founder QA service: <http://127.0.0.1:5173/>.
Cinema -> **时刻卡片** (beside 刷新目录) -> select a registered source -> enter `12:34`, name, note and tags -> save -> edit to `13:01` -> save.
The return button restores Cinema's existing query/filter state and stored scroll position. Top navigation exits Moment Cards normally.

Local records use the origin-scoped `ptti-moment-cards-v1` key. The standalone QA demo uses `ptti-moment-cards-demo-v1`; neither uses SQLite. Keep the same localhost origin/port to read the same browser records. Changing browser, profile or origin does not copy these records. No automatic data migration occurs.

## Implemented corrections

- Manually integrated the VideoFeed hunks into the actual baseline; retained favorite request epochs, failure reconciliation, media gates, Founder QA mode and original CSS. No `source/` directory was created.
- Renamed the React view to `MomentCardsPage.tsx`: Windows/Vite otherwise resolves the case-similar `momentCards.mjs` before the intended view and fails the default import.
- Lazy, read-only initialization; no mount or autosave effects. A save/delete updates React state only after synchronous storage success. Unreadable/corrupt existing storage remains untouched. Missing storage, quota exhaustion and write errors remain visible, and failed input is retained.
- QA demo uses `createElement`, `textContent`, property assignment and `replaceChildren`, never `innerHTML`. React renders user strings as escaped text. Malicious titles, notes and tags are regression tested.
- YouTube timestamps require exact registered ID, HTTPS official domain, matching source URL and non-conflicting nested source identity. Mismatches return no link. Bilibili gets only its exact registered plain HTTPS page, no time parameter. Other/unrecognized platforms fail closed.
- Existing Windows desktop bridge accepts plain YouTube URLs only. It was not widened. A rejected timed link exposes a copy action and the original official page for manual positioning. Native execution remains untested.

## Actual tests

From `products/ptti/frontend`:

```text
npm run test:moments
npm run test:moment-view
npm run test:feed
npm run test:goal99-story
npm run test:favorite-persistence
npm run test:official-theater
npm run test:youtube-thumbnail
npm run test:media-distribution
npm run build
node scripts/check-media-distribution.mjs dist --windows
```

All commands passed. `npm run build` includes complete TypeScript and Vite; Vite built 665 modules in 3.14s. A non-fatal 502.46 kB main-chunk size warning remains. `git diff --check` passed. Distribution media check remains `approvedAssets=0`.

The new tests cover create 12:34, edit 13:01, save/re-read, delete/re-read, tag filtering, official URL mismatches, absent/read-blocked/write-blocked/quota storage, corrupt records, duplicate IDs and malicious DOM text. React SSR verifies initial persisted records are immediately rendered and repeated renders under a StrictMode wrapper make zero writes. This is not a browser Strict Mode lifecycle test.

## Browser acceptance and remaining work

Reused existing Vite PID 37212 and backend PID 29784. Backend diagnostics confirmed a physical temporary QA database, not PTTI-Dev/user data.
One agent-owned Ego task opened the actual original Cinema at 1142px; its three columns match the unchanged <=1150px rule. The Moment Cards entry appeared. All eight remote Founder QA images returned `LOADED` and decoded natural width 480. Bilibili retained the original fallback. No official video playback or new media permission was inferred.

Runtime monitoring returned `OBSERVED_PROCESS_BUDGET_EXCEEDED`: shared Ego process tree 1,427,173,376 bytes vs the admitted 1,073,741,824-byte budget. The monitor and thumbnail observation were in the same tool batch; the image read had run when the stop was processed. No subsequent UI testing was performed; only the agent-owned task was closed. User pages/processes and existing QA services were left running.

Thus real create/edit/filter/delete confirmation/refresh/return, browser Strict Mode lifecycle, storage failure feedback and screenshots are **BLOCKED / NOT_TESTED**. No screenshot was fabricated. The old Story/favorite behavior passed source/Node regression; it was not re-clicked in this browser run.

When the existing resource guard permits a session, execute the product path above; check deletion cancellation and acceptance, refresh persistence, search/filter restoration, quota failure without a false success, then capture Moment Cards and the wide original Cinema. Keep all testing in the isolated QA origin/database. Do not bypass the budget or change formal R4/Launcher.

Rollback: revert this one integration commit in a clean isolated branch. Existing Moment Cards storage is not deleted or migrated by rollback. No backend/schema/database or media permission change needs reversal.
