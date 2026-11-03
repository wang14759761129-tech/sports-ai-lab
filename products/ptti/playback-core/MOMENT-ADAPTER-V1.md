# Moment Playback Adapter v1

`adapters/momentPlaybackAdapter.ts` wraps an existing `LocalVideoPlaybackController` and the same HTML media element; it does not create a player, load files, or calculate hashes. First load the media through Core, wait for Core `ready`, independently verify its identity, then call `load(identity)` with the exact `video_identity` in the Core snapshot. A local-session identifier is not a verified SHA. The host must bind an independently verified SHA to that session before enabling a SHA-protected Moment.

- `play()` / `pause()` return explicit results. For an Arena return, pause first, then `seekExact(savedSeconds)`; do not call play automatically.
- `seekExact(seconds)` uses the requested source time. `seekWithPreRoll(seconds, preRollSeconds)` explicitly subtracts the requested context and clamps only the resulting start at zero. Both reject out-of-range source times.
- A new seek cancels the preceding pending seek. `cancelPendingSeek()` returns its pending promise as `cancelled`. `seeked` is reported only after the media event and a position check (within 0.1 s), or when already stationary within 0.01 s of the target. The default timeout is 12 seconds.
- `getCurrentTime()` returns the observed media time. `subscribeState()` provides `unloaded`, `ready`, `seeking`, `seeked`, `error` and a bounded error code; unsubscribe when the view unmounts. The caller must cancel pending work when navigating or replacing media.
- Identity, readiness, duration and media errors are rechecked before operations and when `seeked` arrives. Playback Core remains responsible for file loading, URL lifecycle and playlist cancellation. This adapter neither grants media rights nor proves decoding, frame accuracy, or SHA authenticity.

Run from `products/ptti/frontend`: `node scripts/test-moment-playback-adapter.mjs`. The test uses a fake media element and the actual compiled adapter; real browser/media decoding remains NOT_TESTED.
