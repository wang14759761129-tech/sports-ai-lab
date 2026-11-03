# PTTI Cinema v0.7.1 implementation and acceptance

## Implemented
- Removed sidebar DOM, collapse preference and reserved width; horizontal main navigation and native details menu preserve secondary routes.
- Default home preference opens Watch for video-first builds; existing recent preference is not rewritten.
- Existing Video Evidence media node remains mounted across tool toggles. Native media controls preserve volume, seek and keyboard focus. Fullscreen API fails with visible feedback.
- Viewport-bound contain video; no crop. Analysis editor sits beside video on wide windows, below on smaller windows.
- Library shelves use actual available local videos, last-opened metadata, favorites, platform provenance and existing verified-full-match field. Empty shelves are omitted.
- No remembered playback position is overwritten. Recent video action explicitly opens from beginning; automatic resume position is not implemented.

## Actual automated checks
Existing frontend: 40 passed; shell/layout/contracts: 17 checks passed; TypeScript and Vite passed.
Python related suites: 40 passed; subsequently preview suite including new Cinema isolation case: 10 passed (overlapping suite, not 50 unique).
pip check and compile passed. Initial test collection failed because temporary PYTHONUTF8 changed decoding of existing Windows helper output; removing that environment override restored tests, no database guard weakened.

## Browser-host acceptance only
Isolated TEST database. Authorized TRAIN game_1 local reference only; no copying or upload.
Actual playback progressed to 7.379s; opening/closing analysis preserved paused position. Fullscreen entered/exited, no reset. No sidebar DOM, contain video, no horizontal document overflow at 1366 and 1024 checks.
1366 first pass player box 1301x608; viewport-height budget subsequently reduced to keep bottom inside screen. 1920 check also performed; 2560 resize returned stale viewport and is not claimed verified.
Fixed scores remained unindexed; Vision disabled. No point/identity/algorithm gate upgraded.

## Limits / native checklist
MANUAL_GUI_CHECK_REQUIRED. No native clicks have been performed.
1. Open authorized local video and verify full table/player frame at 1366, 1920, 2560 and Windows 125/150 percent DPI.
2. Play, seek, volume, speed and full screen; verify keyboard controls remain accessible.
3. Open and close review, ensure time persists; save a pending observation and restart same QA launcher.
4. Switch library sources, verify platform restrictions, UNKNOWN and unconfirmed point guards remain visible.
Custom auto-fading controls, persisted playback resume and a dedicated narrow tool drawer are not implemented; platform-native controls and below-player panels remain.
Old previews and frozen research configuration unchanged. No official TEST, GAME_5 or Production DB access.
