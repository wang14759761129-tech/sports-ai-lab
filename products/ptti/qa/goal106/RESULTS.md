# Actual isolated browser results — 2026-10-25

Environment: ChatGPT in-app Chromium browser, localhost QA page, 1000×850
viewport, iframe 640×360. Pre-build available RAM 4.90 GiB. No Windows candidate
or backend was started. The earlier os error 3 did not recur this run.

| Check | Actual result |
|---|---|
| Local QA page and controls render | PASS |
| Official preview contains Wang Chuqin / Felix Lebrun graphic | PASS; preview-browser.png |
| Official iframe identity | 0QgbtsBWZhk; title FULL MATCH / MS Final / ChinaSmash 2025 |
| Publisher attribution | World Table Tennis; visible channel link UC9ckyA_A3MfXUa0ttxMoIZw |
| Play after explicit click | PASS; actual table-tennis match picture observed |
| Time progression | screenshot first showed 0:01 / 18:42; later AX showed 0:13 and paused at 0:16 / 18:42 |
| Pause control | PASS; state changed to Play after pause; playback-browser.png |
| Full viewing | NOT_TESTED; observed seconds only |
| Provider forbids embedding | NOT_TESTED; no such error observed; not artificially manufactured |
| Offline failure | PASS; tab-scoped DevTools offline simulation then reload iframe showed “未连接到互联网”; offline-browser.png |
| Fallback while offline | official anchor and manual copy field remained visible; load event did not claim playback |
| Official watch navigation | PASS; click opened exact /watch?v=0QgbtsBWZhk page with matching title; player initially showed an advertisement; watch-page match playback NOT_TESTED |
| Clipboard | click feedback observed, clipboard read returned empty; end-to-end copy/paste NOT_TESTED |
| Windows normal browser / Native R4 | NOT_TESTED |
| Independent thumbnail permission | unchanged; zero new cover admissions |

Offline simulation was restricted to the QA tab and restored Online. Temporary
viewport was reset; both agent-created tabs closed; local QA server stopped.
No screenshots are runtime assets; these are internal QA evidence outside Vite
public/src. No provider image was separately downloaded or cached by app code.

Automated: 6 stdlib tests PASS (0.556s), node syntax check PASS, existing full
TypeScript + Vite build PASS (659 modules; Vite 4.47s), git diff --check PASS.
These automated checks remain separate from the observations above.

Conclusion: one real video can present its own official preview and play in an
intact, sufficiently sized iframe in this environment, without Cloud credentials.
This does not restore eight independent homepage thumbnails or change existing
embed permissions. No inference about a different video, installation, region,
full-match availability, downloads, or media redistribution is made.
