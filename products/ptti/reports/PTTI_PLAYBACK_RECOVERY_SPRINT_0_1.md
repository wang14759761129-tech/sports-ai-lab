# PTTI Playback Recovery Sprint 0.1

## Scope and safety

- Repair branch: `codex/ptti-playback-recovery-sprint-0-1`.
- Browser QA used a temporary SQLite backup of the authorized R4 DEV database. Production DB, restricted official TEST, GAME_5, and frozen research configuration were not accessed.
- The active R4 desktop pointer and rollback package were left unchanged. R5.1 was not activated.
- Native Windows playback remains `NOT_TESTED`; the playback regression ran in a headless Edge browser host.

## Reproduced defects and fixes

1. **A source limitation masked a live official-player failure.** Reproduction: render an embeddable official source with a non-empty `playback_limitation`, then trigger the YouTube player's `onError` callback. The old `source.playback_limitation || status` expression kept showing the static limitation instead of the current player error. The UI now displays the live status and retains the limitation as separate context.
2. **A failed desktop browser handoff had no direct recovery action.** Reproduction: make the pywebview `open_official_video` bridge return `false` or throw. The anchor was intercepted, but the user had no copy control. Failed handoffs now show a visible copy-link action; if clipboard APIs are unavailable, a selectable URL field is shown. Without the desktop bridge, the ordinary official anchor remains browser-operable.

## Playback evidence

The authorized DEV `game_1.mp4` source was present and SHA-256 verified as `1297b3db91f2e3e160337643695dff07eabf9785ea2d88c2f7b59687ba511148`. The isolated browser regression observed `loadedmetadata`, `canplay`, and HTTP 206 range responses.

- Vision source player: play advanced to 0.502 s; pause stopped advancement; seek to 2.500 s landed at 2.500 s; 0.25x, 0.5x and 1x were accepted; fullscreen enter/exit passed; unmount cleared the media source; re-entry loaded again.
- Cinema player: play advanced to 0.526 s; pause stopped advancement; seek to 5.250 s landed at 5.250 s; 0.5x was accepted; fullscreen enter/exit passed; unmount cleared the media source.
- Analysis View remained disabled because no verified result was bound to this source.
- These are browser-host timing measurements, not frame-accurate claims and not native Windows GUI evidence.
- External-platform navigation was verified through isolated unit tests for native-anchor fallback, bridge success/failure, and copy recovery. No claim is made that an external match page played in this run.

## Environment note

During browser QA the optional `POST /api/video-evidence/library/videos/{id}/opened` request returned 403, while video listing, analysis reads, and media range requests succeeded. The evidence router's local-only guard rejects a mismatched `Origin`; the Vite browser host and proxied API use different local ports. This is a development proxy/origin mismatch, not a media-read or decode failure. The guard was not weakened. The UI already treats recent-view telemetry as best-effort and continues to the player.

## Verification performed

- Frontend feed, studio, review, score, and score-observation tests: 74 passed.
- New official playback recovery tests: passed.
- Python external-link tests: 13 passed.
- TypeScript and Vite production build: passed.
- Browser-host real-media regression: 9 checks passed.
- Native Windows GUI/player acceptance: `NOT_TESTED`.
