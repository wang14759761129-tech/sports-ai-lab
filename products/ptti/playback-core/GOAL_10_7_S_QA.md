# GOAL 10.7-S Playback Core review

Baseline `fdaf7dfbc17e18f823f0b71c4c5a2a417ebef759`.

## Finding and change

Core already supports one-clip playlists, repeat/speed/pause/resume, explicit seek cancellation, and source replacement cleanup. A real fail-closed gap existed in `playRallyPlaylist`: it validated the requested new list before cancelling the active list. If a player was comparing p002 and a click supplied a now-stale p004 binding, the API returned `video-mismatch` but p002 kept playing and its task stayed pending. This conflicts with clip switching semantics.

Moved active-task cancellation to the beginning of each playlist request. A failed selection now stops its predecessor, reports the validation error, and cannot leave stale playback running. API shape unchanged; no ComparisonEngine/telemetry added. San must still cancel immediately on annotation/video/target mutations and re-resolve the current binding before calling Core.

## Verification

- Regression RED before change: active clip + stale-session selection returned `video-mismatch`, but prior task did not settle; Node reported unsettled top-level await.
- GREEN: `node products/ptti/frontend/scripts/test-portable-playback.mjs` passed existing lifecycle coverage plus p002→p004→p002, pause/resume/cancel, three rapid valid selections (last wins), stale identity rejection stops previous task, source replacement cancels, old identity rejects, and playback works again only with new identity.
- PASS: strict TypeScript compile of Playback Core with installed compiler; `git diff --check`.
- RAM: 3.46 GiB at initial audit; 2.21 GiB after Node/type checks. Chrome/real media browser run NOT_TESTED because it fell below the 2.5 GiB guard. No Windows process launched or stopped.

San contract and code sample are appended to `products/ptti/playback-core/README.md`. Core does not infer Quick Annotation edits; San must cancel before edits/revocation and guard async task completion by selection generation/reference.

No San/Integration source changed. Four existing Playback diagnostic drafts remain untracked and untouched. No push, CI, deployment or Windows Native.
