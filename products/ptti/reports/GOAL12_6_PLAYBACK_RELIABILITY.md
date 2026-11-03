# GOAL12.6-P Playback reliability — 2026-10-16

Core source remains unchanged at `304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe`.
Source SHA256: `a59df06b688d75885bfb8ed51364e73edbaedaaa2b3746b5f7fd1d1edf67caf2`.
Playback tooling base: `fd8da99d7dbca03726d1449e88255a4a3b59539e`.
San read-only review: `e788e2f4c4ac0d6677155a2d3a43d0d22491f2a3`.

## Results and coverage gaps closed

- PASS: existing 17 Core groups plus four new groups (21 total), using the actual TypeScript module and a fake media element. No decoder/browser claim.
- PASS: 24 rapid file selections retain only the latest identity and revoke each superseded URL once; repeated release removes all listeners.
- PASS: repeatedly cancelled old task handles cannot pause/cancel/resume a newer task; invalid replacement stops the old queue.
- PASS: a stalled Seek fails with `seek-timeout`, removes temporary listeners, and cannot restart after a late `seeked` event. The test uses 20 ms; the unchanged production default is 5000 ms. Timer scheduling is not a hard real-time deadline.
- PASS: Object URL creation and `video.load()` exceptions report `file-read-error`; selecting a valid file recovers; all created URLs are released once.
- PASS: San-style cancel-then-pause retains the current local media, rejects resuming the cancelled queue, and permits explicit ordinary viewing on return.
- PASS: strict TypeScript no-emit check of the Core module.
- PASS: Core Git object/source pin verification and lock-tool regression. Fixed the regression harness's incorrect assumption that the tooling branch HEAD must remain the historical Core commit; a different HEAD is now tested as an expected strict-worktree rejection.
- PASS: San existing `check-playback-core-pin.mjs --self-test` (seven negative cases), and `check-review-navigation.mjs`.
- NOT_TESTED: fresh production bundle, Chrome runtime navigation/decoder behavior, real-phone media, Native R4. No Chrome, Native, build, push, CI, or promotion performed.

## Current San contract

`products/ptti-web/src/App.tsx` forwards `${page}:${proFocus}` through ProWorkbench to LocalVideoReview. Its navigation effect cancels the queue then calls `pause()`; inactive workspace also cancels/pauses. Unchanged navigation is a no-op. Component cleanup cancels, unsubscribes, then calls `release()`.

Core owns local object URLs, source identity, validated queue snapshots, task cancellation, Seek/rate controls, media error classification and listener cleanup. San owns navigation, current annotation/Review Target eligibility, boundary confirmations, stale async UI updates and cancelling before eligibility changes. Core cannot observe external annotation revisions. User Seek must call `controller.seek()`; plain `pause()` pauses media but does not cancel a queue. Navigation therefore needs both operations. Returning to a route must not automatically resume a cancelled task.

San now vendors the pinned source and archive and validates the configured Vite override against those bytes. Its package has prebuild/postbuild pin checks. This review ran the read-only self-test, not a new bundle build. Web Pro and Native R4 remain separate engines.

## Minimal runtime diagnosis, default off

On a browser fault, first record San commit and Core hash, route category, user action and exact issue code. Observe only a bounded sequence (at most 20 entries) of allowlisted `getSnapshot()` fields: status, duration/current time, playing flag, rate, playlist status/index and error code; pair task `done` status/reason with a local operation counter. Never dump the complete snapshot: it contains local file metadata. For media state record only readyState, networkState, MediaError.code and whether currentSrc matches the owned source; omit file names, blob URLs, private paths and full session identities. No uploads or background collection.

On failure cancel and pause once, preserve the diagnostic record, and distinguish user cancellation from decode/read errors. Official-platform navigation/login/region failures are outside the local-file Core. A paused retained workspace keeping its selected source is expected; after actual unmount/release the source and listeners must be detached.

## Risks and San observations

No new P0/P1 reproduced in these bounded checks. Remaining runtime observations: navigate during metadata loading/pending Play/Seek and while looping; return without automatic playback or lost notes; rapidly choose another file and confirm no old frame/queue returns; verify normal explicit Play still works; check unmount releases resources. These require Chrome/real-media evidence and are not marked PASS here. Browser buffering, memory return to the OS, hardware decode and background-tab scheduling are not proved by fake-media tests. Retain the 2.5 GiB browser guard.
