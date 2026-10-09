# Score Navigation v0.1 — Native Windows QA

This checklist is for the isolated `PTTI-Score-Navigation-v0.1-Preview` build. It is not a release sign-off. Use a video you own or are authorized to review. Do not use a production database or package research videos.

## Before starting

- Verify the window title contains `比分导航 v0.1 Preview` and the short commit ID.
- The preview database must be `%LOCALAPPDATA%\PTTI-Dev\ScoreNavigation-v01-Preview\matches.db`.
- Record the EXE SHA256 and selected MP4 path in the result table below.
- Do not enter a confirmed score unless the score and both point boundaries are visible and checked in the video.

## Under 10-minute acceptance

| Step | Action | Expected result | Result |
|---|---|---|---|
| 1 | Open `视频证据` and choose an authorized local MP4 using the file picker. | Video is registered locally; metadata and SHA256 appear; no upload occurs. | PASS / FAIL / NOT_TESTED |
| 2 | Play, pause, seek to a known time, set 0.5× speed, and play again. | The picture changes to the chosen time; the displayed source time follows playback. | PASS / FAIL / NOT_TESTED |
| 3 | In `按比分找球`, mark the current time as point start. Mark a later time as point end. Enter game, point number, pre-point score, and winner only if verified. | The start/end are stored separately from the scoreboard-display time. | PASS / FAIL / NOT_TESTED |
| 4 | Save an incomplete entry as a draft, then try to confirm it without both boundaries. | Draft is saved; confirmation is blocked with a clear message. | PASS / FAIL / NOT_TESTED |
| 5 | Confirm one fully checked score entry. Click `定位`, then `播放这一分`. | Playback seeks to about 1.5 seconds before the marked start and reaches the correct rally. | PASS / FAIL / NOT_TESTED |
| 6 | Mark a second verified score entry, select both confirmed entries, and start continuous playback. | Both segments play in selected order, including across videos if both are selected. | PASS / FAIL / NOT_TESTED |
| 7 | Select a score entry and save it to an existing or new playlist/topic using the existing evidence playlist controls. | The score segment remains findable in the existing playlist. | PASS / FAIL / NOT_TESTED |
| 8 | Close the application completely and reopen the same Preview. | The video registration, score entries, review status, and playlist references remain. | PASS / FAIL / NOT_TESTED |

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
