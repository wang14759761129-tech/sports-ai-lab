# Score Navigation v0.1 — Native Windows QA

This checklist is for the isolated `PTTI-Score-Navigation-v0.1-Preview` build. It is not a release sign-off. Use a video you own or are authorized to review. Do not use a production database or package research videos.

## Before starting

- Verify the window title contains `比分导航 v0.1 Preview` and the short commit ID.
- The preview database must be `%LOCALAPPDATA%\PTTI-Dev\ScoreNavigation-v01-Preview\matches.db`.
- Record the EXE SHA256 and selected MP4 path in the result table below.
- Do not enter a confirmed score unless the score and both point boundaries are visible and checked in the video.

## 5–8 minute acceptance

| Step | Action | Expected result | Result |
|---|---|---|---|
| 1 · 30 秒 | Open the Preview; check its title/commit, then choose an authorized local MP4. | Correct Preview is running; the video is local, available, and SHA256-bound. | PASS / FAIL / NOT_TESTED |
| 2 · 1 分钟 | Play, pause, seek to a known time, and set 0.5× speed. | The decoded picture changes to the target scene; the source time follows playback. | PASS / FAIL / NOT_TESTED |
| 3 · 1 分钟 | Mark one fully observed point: game, point number, pre-point score, start, end, and separate scoreboard-display time. Confirm only if all are checked in the video. | The saved record links the right video hash; UNKNOWN stays UNKNOWN. | PASS / FAIL / NOT_TESTED |
| 4 · 1 分钟 | Click `定位`, then `播放这一分`; compare the picture at the beginning, middle, and end with the known rally. | Playback starts with about 1.5 seconds of pre-roll and reaches the intended point; record observed offset. | PASS / FAIL / NOT_TESTED |
| 5 · 1 分钟 | Save a second verified point, select both confirmed points, then start continuous playback and pause once. | Order is stable, the next clip advances at the boundary, and manual pause stops advancement. | PASS / FAIL / NOT_TESTED |
| 6 · 1 分钟 | Add the selected score clips to a topic using the existing evidence playlist controls. | Both clips remain findable from that topic. | PASS / FAIL / NOT_TESTED |
| 7 · 1–2 分钟 | Exit the Preview fully, reopen the same build, and revisit the video, score entries, and topic. | Entries, SHA binding, review status, and playlist references persist. | PASS / FAIL / NOT_TESTED |

If no real point score and both boundaries can be verified, mark steps 3–6 `NOT_TESTED`; do not invent a confirmed sample to complete the checklist.

## Evidence correctness checks

- Confirm the indexed record shows the same video SHA256 as the selected source.
- `UNKNOWN` remains unknown until explicitly corrected.
- A second save request with the same request ID must not create another score record.
- Editing a score must add a history entry; it must not erase the prior values.
- A missing or changed video must show unavailable and must not be treated as the old source.
- A score shown on the broadcast overlay is not automatically the score before a point. Mark its display time separately.
- If the source does not provide a verifiable score or point boundary, leave the record as a draft or do not create it.

## Results to record

- Preview version / commit:
- EXE SHA256:
- QA MP4 path:
- QA MP4 SHA256:
- Confirmed score entry IDs:
- Actual seek offset observed:
- Restart persistence:
- Failures / notes:
- Tester and date:
- Screenshot / log folder:
