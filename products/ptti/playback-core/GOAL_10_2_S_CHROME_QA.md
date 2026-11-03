# PTTI Playback Core — GOAL 10.2-S Chrome QA

Date: 2026-10-14
Scope: isolated headless Chrome automation using FFmpeg-generated synthetic MP4 files. No PTTI Windows executable was launched and no video bytes were sent to the local test server.

## Browser and fixture matrix

Browser: Chrome 155.0.8059.79 (`C:\Program Files\Google\Chrome\Application\chrome.exe`); FFmpeg/FFprobe 8.1.1 full build; Node.js 24.15.0. The browser used a temporary profile and was closed at test completion.

| Fixture | Duration / size | Video | Audio | GOP | First presented frame | Seek to visible frame |
| --- | --- | --- | --- | --- | ---: | ---: |
| `synthetic-playback.mp4` | 4 s / 263,024 B | 320×240, 30 fps, H.264 Constrained Baseline | AAC | 2 s | 157.9 ms | baseline control seek passed |
| `short-baseline-no-audio.mp4` | 3 s / 65,328 B | 160×120, 24 fps, H.264 Constrained Baseline | none | 48 frames / 2 s | 90.1 ms | 15.4 ms, frame 2.000 s for target 2.01 s |
| `medium-main-aac.mp4` | 6 s / 281,310 B | 640×360, 30 fps, H.264 Main | AAC | 90 frames / 3 s | 130.3 ms | 14.3 ms, frame 4.000 s for target 4.02 s |
| `long-high-aac.mp4` | 12 s / 957,190 B | 960×540, 30 fps, H.264 High | AAC | 180 frames / 6 s | 112.1 ms | 31.3 ms, frame 8.033 s for target 8.04 s |

The four verified synthetic fixtures total 1,566,852 bytes. Their SHA-256 values are:

- `synthetic-playback.mp4`: `cde05d2e7d550c3f3928048ff8f9e3d021540638c69d14fc44b2507b8fe8103f`
- `short-baseline-no-audio.mp4`: `9ae0a2c18e0e43f3f9446711c14930bad91893f34451d8233e7e91ff00c9ba3c`
- `medium-main-aac.mp4`: `f7b19cc7c3c98a2a82c2f87a2d7284f6d28eb05e8530970d4149998d72b9fdd1`
- `long-high-aac.mp4`: `fa5792d6738b71f031f04ff1ec214d5a6841940262e1498b1d9bd44abaa1524b`

## Interaction results

- PASS: rapid replacement by three local files; the final selection became ready and superseded URLs were revoked.
- PASS: a direct seek from the first rally to a later point cancelled the old playlist and did not jump back.
- PASS: three-rally playlist order, pause, resume, and completion.
- PASS: single-rally loop; replacing its video cancelled the loop.
- PASS: malformed MP4 produced a decode error, then a valid file recovered successfully.
- PASS: 9 of 9 object URLs were revoked after replacements and controller release.
- PASS: the page made no video upload request; media stayed on the browser File/Object URL path.
- PASS: unit regression tests reject metadata, `canplay`, `timeupdate`, and `seeked` events while the source URL is blank or the current source has not reached metadata readiness.

## Resource and evidence limits

The Chrome page's reported JavaScript heap rose from 919,562 B to 956,818 B during the sequential matrix (+37,256 B, about 36.4 KiB). This is page JavaScript heap only; it does not measure Chrome's total working set, decoded frame buffers, or GPU memory. All local object URLs were revoked and the isolated Chrome process exited. No full-process peak RAM measurement was captured.

Seek figures measure the time from the seek request to a nearby presented frame using `requestVideoFrameCallback`. They describe this synthetic test run, not a millisecond-accuracy guarantee. The run covers Chrome on this Windows host and H.264 MP4 Baseline/Main/High with AAC or no audio. It does not establish compatibility with real phone footage, variable-frame-rate recordings, HEVC/H.265, AV1, HDR, rotated media, or other devices/browsers.

All fixtures are deterministic synthetic test material (`SYNTHETIC_TEST_ONLY`); they do not test table-tennis recognition or real-match analysis.
