# MVP verification record

Checked 2026-10-12 in the independent `products/ptti-web` worktree.

## Automated checks

- `npm run build` — passed; TypeScript check and Vite production build completed.
- `npm run check:sources` — passed, 79 source, route, status and media-boundary checks across four match records.
- `npm audit` during install — 0 vulnerabilities in 22 packages.
- `npm audit --omit=dev` — 0 production dependency vulnerabilities.
- `git diff --cached --check` — passed with no whitespace errors.
- Secret scan — no credential or private-key patterns found. The only `sqlite` match is the README statement that the Web app does not access the desktop database.

## Browser interaction checks

- Player search for `Fan Zhendong` showed the two matching sample cards.
- Women’s singles filter showed the Wang Yidi–Sun Yingsha and Sun Yingsha–Chen Xingtong records.
- The no-route sample showed a clear message and no watch button.
- Cinema, Pulse, Stars and Feedback navigation rendered the expected content; Pulse showed three attributed items and Stars showed three source-backed profiles.
- Feedback storage was empty before testing. No test response was submitted or recorded.
- Outbound Cinema links use `_blank` with `noopener noreferrer`. The YouTube destination opened the named Wang Yidi–Sun Yingsha video on the verified World Table Tennis channel. The player remained at 0:00; playback was not tested.
- Desktop viewport: 1265×715, document width 1250 px.
- Mobile viewport: 390×844, document width 375 px; no horizontal overflow.

## Screenshot status

Desktop and mobile screenshots were captured from the local browser for visual inspection in the current Codex session. The browser safety layer rejected the `data:` navigation used to export those captures as files. No screenshot files are included in this commit, and no alternative export path was attempted.

## Sprint 0.2 — Chinese-first bilingual UX

Validated 2026-10-12 in the sports-ai-lab destination worktree at C:\PTTI-Worktrees\web-mvp-v0-1, branch codex/ptti-web-mvp-v0-1.

- A first visit showed Simplified Chinese. The English and Chinese controls switched the current page immediately; each selected language was restored after a browser refresh.
- Search found two Fan Zhendong records in English and two 樊振东 records in Chinese. The women’s singles filter showed two matches. A deliberately unmatched query produced the localized empty state.
- Pulse showed three source-attributed items and a non-live curation note. Categories without verified records showed the empty state. Returning to Pulse resets its filter to All.
- Stars showed three source-backed profiles. The candidate Weibo link remains clearly marked as unverified.
- Feedback controls displayed all requested issue categories in both languages. No browser feedback response was submitted. The local-storage helper passed an isolated in-memory storage check for append, restore, issue category persistence, and malformed-data recovery; this left no synthetic user response in browser storage.
- Event-page actions pointed to the official WTT event page; the direct-video action pointed to the recorded WTT YouTube URL; a source-only record linked only to its evidence article and showed no watch action. Outbound links use target=_blank and rel=noopener noreferrer. Playback remains untested.
- At 1440×960, document width was 1425 px; at 768×900, it was 753 px with two match columns; at 390×844, it was 375 px with one column and 44 px minimum primary controls. No horizontal overflow was observed.
- npm run build passed. npm run check:sources passed 89 checks across four records. npm run check:feedback passed. npm audit reported zero vulnerabilities. git diff --check passed after whitespace cleanup.
- Browser screenshots were captured for visual inspection at all three viewport widths. No screenshot files were saved or added to Git; no alternate export route was used.
- The app remains local-only on 127.0.0.1:4174. No playback, deployment, desktop launcher, Vision, or backend code was changed.
