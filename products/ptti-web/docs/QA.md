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

## Sprint 0.3 — Direct-source and first-use audit

Validated 2026-10-12 in the sports-ai-lab destination worktree. Four Cinema records and existing Pulse/Stars links were reviewed against publisher pages. WTT event pages for Doha 2023 and Singapore 2021 list the associated match video items; direct WTT YouTube search results verified the specific Lin Gaoyuan semifinal and Wang Yidi–Sun Yingsha final pages. The Doha Fan–Wang final remains an event-page route because no stable direct URL was verified. Chongqing 2025 remains source-only because the WTT story has only generic event viewing options. All video playback flags remain `false` / NOT_TESTED.

- Post-change checks: `npm run build` passed; `npm run check:sources` passed 95 checks across four match records; `npm run check:feedback` passed; `npm audit --audit-level=low` reported 0 vulnerabilities; `git diff --check` passed. The Sprint 0.3 diff secret scan found no credential or private-key patterns.

- The Chinese “查找比赛” button focused the search field. Search for `樊振东` returned two records. Selecting 女单 while the unrelated player query remained active produced a clear empty state; “显示全部样本” cleared the query and filters and restored all four records.
- Following the WTT Fan Zhendong–Lin Gaoyuan semifinal card opened `youtube.com/watch?v=qIXmFTzXcs0`. The page title matched the semifinal and the channel showed World Table Tennis with a verification badge. The player remained at 0:00 / 8:31; Play was not activated, so playback remains NOT_TESTED and territory availability is unknown.
- The WTT Fan Zhendong–Wang Chuqin final remains an event-page action. The official Doha event page lists a separately titled MS Final video item inside Related Videos, but no stable direct video URL was verified for PTTI; the card does not claim to be a video page.
- Narrow mobile browser preview showed single-column match cards; the direct-video button and source-only button fit their cards, with the no-route explanation visible. No horizontal clipping was visible. Sprint 0.2 had measured 1440×960, 768×900 and 390×844 without horizontal overflow; Sprint 0.3 changed no layout CSS.
- The five-minute real-user script is in `docs/USER_TEST_PLAN.md`. No participants were recruited and no user feedback result was recorded in this run.
- Feedback form inspection found the return-intent options reused match-found labels. The dropdown now says 愿意 / 不确定 / 不愿意 (Yes / Not sure / No), while the separate match-found question keeps its own labels.
- Updated source checks require video-page records to use the same direct URL as both `platformUrl` and `videoOriginalUrl`, and to include that URL in source evidence.
- Pulse item audit: one official highlight compilation (not a match replay) and two WTT articles. Stars facts link to WTT event/article sources; the Wang Chuqin Weibo profile remains labelled candidate because platform verification is absent.
- The official source pages were opened, but no “play” control was activated and no media decode or regional availability was tested. Browser screenshot export remains unavailable under the existing safety boundary; no bypass was attempted.

## Sprint 0.4 — Playback observation and design integration preparation

Validated 2026-10-12 in the current Codex in-app browser and independent Web worktree.

- Fan Zhendong vs Lin Gaoyuan: final URL stayed `https://www.youtube.com/watch?v=qIXmFTzXcs0`; the page title matched the semifinal and the publisher was the verified World Table Tennis channel. After pressing Play, the visible match frames changed and the timeline advanced from 0:02 to 1:01. No login, region, or verification prompt appeared. Visual playback: PLAYBACK_PASS.
- Wang Yidi vs Sun Yingsha: final URL stayed `https://www.youtube.com/watch?v=XHGCGiAyKkc`; title and verified publisher matched the women's final. After pressing Play, visible match frames changed and the timeline advanced from 0:02 to 0:20. No login, region, or verification prompt appeared. Visual playback: PLAYBACK_PASS.
- Both player UIs showed unmuted at 100%. Actual speaker output was not independently confirmed. The browser's geographic territory was not identified; territory availability remains UNKNOWN. No gate was bypassed and no video or screenshot asset was saved.
- Cinema retains the Fan–Wang event-page route and the Sun–Chen WTT article source-only route. Their playback status remains NOT_TESTED.
- No seed users were available; no real user session or feedback result was recorded. The test plan now contains invitation copy and local-device instructions for the first 1–3 participants.
- The specified Premium Design commit `ae9b84e8da5e9ebd91fceabc2eaa17c67e070ba9` was reviewed from committed Git objects only. Its worktree had unrelated uncommitted changes; those were not inspected or modified. A minimal Web token, navigation, cover, status/error and mobile integration plan is in `docs/PREMIUM_DESIGN_INTEGRATION.md`.
- The optional remote preview is a plan only. Cloudflare Pages Free static hosting is estimated at $0/month for this small trial using the provider's generated HTTPS subdomain, with no custom domain, Functions, database or online feedback collection. It is not deployed pending explicit user approval. The deployment and request-metadata notes are in `docs/USER_TEST_PLAN.md`.
- After the 0.4 changes, `npm run build` passed (TypeScript plus Vite), `npm run check:sources` passed 111 checks across four matches, `npm run check:feedback` passed, and `npm audit --audit-level=low` reported 0 vulnerabilities. The source checker now requires direct URL and at-least-five-second timeline/frame evidence for any `PLAYBACK_PASS` status.
- The local page at `http://127.0.0.1:4174/` was reloaded and visibly showed the two video records as “画面播放已实测”; the event-page and source-only records remained untested. Browser screenshot captures were used for visual observation of the video frames but not saved or exported as files.
