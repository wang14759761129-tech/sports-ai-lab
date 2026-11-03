# GOAL 10.5-S Playback Experience — 2026-10-15

Base: 523891a127be5148f3f53ddade1648eb9a13e0fc. Only Playback Core, its tests and handoff documentation changed.

## Source result

Existing point-ID/range validation, playlist order, half speed, pause/resume, single loop, explicit seek cancellation, replacement cancellation and cleanup are reused. Boundary changes remain owned by San's adapter: cancel before publishing an edit/revocation; Core copies input and does not monitor external annotations.

Reproduced error-classification defect: simulated MediaError 1 during an active rally produced decode-error rather than a read-interruption explanation. New tests failed before the fix and pass afterward. MediaError 1/2/3/4 now maps to media-aborted/file-read-error/decode-error/unsupported-media; absent details retain decode-error. Invalid metadata duration has duration-unavailable. Neither browser signal proves a file is corrupt or a particular codec unsupported.

## Actual verification

- PASS: Node public-interface regression, including all existing controls/lifecycle cases plus five error-code paths, three invalid durations, active-task failure/pause, URL/listener release, and owner-driven boundary cancellation/reconfirmation.
- PASS: strict TypeScript module check with moduleResolution=node. Initial standalone command lacked module resolution and failed on the installed React csstype declaration; corrected command passed without dependency changes.
- PARTIAL browser run: H.264 fixtures, real decode/play/pause/seek/rates, rapid file replacement, direct seek cancellation, three-rally order and pause/resume passed.
- Browser run overall FAIL: an obsolete message assertion required the exact decode wording after the code assertion already accepted unsupported-media. The assertion is corrected. Final corrected browser suite was NOT_TESTED: live RAM had fallen below the guard; no new Chrome was launched.
- Current-run real-browser loop replacement, post-error recovery and final all-URL release are NOT_TESTED after that stop. Node equivalents pass. Prior QA remains historical evidence only.

## Bounded Chrome matrix (real generated synthetic media)

| profile/fps/audio | duration/resolution | GOP | first frame ms | seek-to-presented-frame ms |
|---|---|---|---:|---:|
| Baseline/30/AAC | 4s/320x240 | 60 | 152.1 | baseline seek passed |
| Baseline/24/none | 3s/160x120 | 48 | 90.1 | 15.9 |
| Main/30/AAC | 6s/640x360 | 90 | 113.7 | 13.9 |
| High/30/AAC | 12s/960x540 | 180 | 129.2 | 31.8 |
| High/60/none | 2s/160x120 | 30 | 79.2 | 14.6 |

FFmpeg 8.1.1, Node 24.15.0, installed Chrome. Total fixture bytes 1,601,554. New 60fps fixture SHA256 6bf9b54d7f8750352c7defd4284a97c05a6ae1f56f3b07f9c6ac5ccdfd67bb38. Other fixture identities match GOAL_10_2_S_CHROME_QA.md. No VFR fixture was needed for this change; VFR, real phone video, HEVC/HDR/rotation and long-recording limits remain NOT_TESTED.

Resource snapshots: initial available RAM 3.630GiB, before browser 3.380GiB, after 2.550GiB, guarded retry 2.432GiB (refused). These snapshots do not attribute the system-wide decrease to Chrome and are not a leak measurement or peak working-set measurement. Page JS heap in the sequential matrix rose from 920649 to 973415 bytes; this excludes decoder/GPU/process RAM. Each matrix replacement revoked the preceding URL. Browser script's finally cleanup closed its owned browser and removed its temporary profile/fixtures after failure. No user processes were ended.

## San handoff / boundaries

README contains exact codes and cancellation reasons. API signatures unchanged; San should allow the three additive media codes and may render message directly. Keep LOCAL_SESSION_ONLY separate from SHA authentication. No automatic server upload, no invented timestamps, no automatic promotion of unconfirmed bindings. This task does not fix the previously reported Integration direct-single-score revision gap.

No San/Integration source, Windows executable/installer, desktop entry, formal database, push or CI touched. Four untracked drafts preserved. Dev-sync is intentionally not run: this task authorizes local module work and commit only and prohibits deployment/Launcher changes.
