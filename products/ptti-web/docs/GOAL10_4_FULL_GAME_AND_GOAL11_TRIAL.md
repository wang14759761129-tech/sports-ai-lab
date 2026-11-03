# GOAL 10.4 synthetic full-game rehearsal / GOAL 11 trial

## Repeat the automated rehearsal

From `products/ptti-web`, run `npm run check:full-game-browser` with `PTTI_PLAYWRIGHT_MODULE` set to the installed Playwright `index.mjs`. Chrome, FFmpeg, Python and the read-only Integration Quick Annotation CLI/Golden fixture are required. The test creates its own **synthetic test-pattern MP4** and keeps all video, draft, converted statistics, screenshots and the action log in ignored `.alpha-qa/`. It does not use a real match or a person. It leaves the existing local review server alone; when it starts its own 4174 server, it stops that server afterward.

The test records 19 sequential points from 0:0 to a legal 11:8 finish, corrects one historical winner, removes and re-enters one point, and fills an omitted winner. Three points receive an observed coarse stage and two confirmed video boundaries; sixteen remain score-only. It checks statistic navigation, three-segment playback, cancellation on manual seek, immediate binding invalidation during edit and boundary revocation, export, refresh, import, reselect and reconfirm. A separate 24-point simulated deuce fixture ends 13:11 and checks alternating service after 10:10. The Integration CLI converts both drafts to its reference statistics for QA only; Web does **not** consume that statistics sidecar at runtime.

Browser actions and elapsed time are automation measurements, not a human usability measure. A `favicon.ico` 404 is separately recorded; aborted local blob reads during video replacement or refresh are also retained in the log. Any page exception, other failed request, outside request, write request or persisted annotation key fails the test.

## GOAL 11: first authorized real-recording trial

1. Use a training recording you own or may use, with the people filmed informed about this local test. Keep it on the test device; do not upload or share it through PTTI.
2. Open `http://127.0.0.1:4174/`, choose **专业分析 → 视频逐分复盘**, then select the local MP4. Confirm the page says it is bound only to this local session. This is not independent media identity verification.
3. In **第 1 遍 · 先记得分**, start from point 1 and record the winner of each observed rally. If the video does not show a fact, leave it UNKNOWN. Confirm full-game coverage and first server only when actually observed. Note the final score and whether it obeys the 11-point, two-point-lead rule.
4. In **第 2 遍 · 复核回合**, choose at least three important points. Seek to each true start/end and confirm each boundary separately. A six-second suggestion is only provisional. Click a loss statistic and a point to check navigation; play selected segments, then manually seek and confirm the old playlist stops.
5. Export the Quick Annotation JSON before refreshing. Refresh, import that file, and check that playback is unavailable until the same local video is selected and the boundaries are confirmed for the new session. Keep the JSON private and separate from the video. The draft is not a formal 21-field training report.
6. Record only observed facts: device/browser, approximate task time and click count, score/point count, unexpected errors, confusing step, playback result, UNKNOWN fields, and whether the participant wants to use it again. Do not record unnecessary personal information. Founder and external participants are separate cohorts; both remain **0 completed** until someone actually takes part.

## Evidence and release boundaries

Review four real-match metadata records and strict-public zero records remain separate. Current-session playback is `LOCAL_SESSION_ONLY`; independent media verification is 0. No real match video, independent video hash, copyright permission, geographic playback, Windows Vision result, or real-user success is established by the synthetic test. The MainDex Golden fixture has five simulated points and checks scoring, duration, playback and stage-stat denominators; it does not constitute a full-game or Web-sidecar acceptance test.
