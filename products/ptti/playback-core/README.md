# PTTI browser local playback core

`src/index.ts` is a framework-free browser module for a user-selected local MP4. It operates on one caller-owned `HTMLVideoElement`, creates a local object URL, exposes player state, and revokes each URL when the file changes or the controller is released. It contains no upload, storage, analysis, or server calls.

## Interface

```ts
const controller = createLocalVideoPlaybackController(videoElement);
const unsubscribe = controller.subscribe((snapshot) => render(snapshot));
const loaded = controller.loadFile(fileFromInput);

await controller.play();
controller.pause();
controller.seek(12.5);                   // seconds, clamped to [0, duration]
controller.setPlaybackRate(0.5);         // only 0.5 and 1 are accepted
controller.setPlaybackRate(1);

const started = controller.playRallyPlaylist(rallies);
if (started.ok) {
  started.value.pause();
  await started.value.resume();
  started.value.cancel();
  await started.value.done;
}

controller.release();
unsubscribe();
```

`RallyPlaybackBinding` is the portable timeline contract:

```ts
{
  point_id: string;
  video_identity: string | null;
  start_time: number | null;   // seconds from the beginning of the file
  end_time: number | null;     // seconds from the beginning of the file
  binding_status: 'BOUND' | 'PENDING_ANNOTATION' | 'UNBOUND' | 'STALE';
}
```

Only `BOUND` records with a nonempty matching identity and real finite bounds inside the loaded duration can play. A missing time stays `null` and fails closed. Start must be less than or equal to end. `revalidateRallyBindings` marks records for another file `STALE`; `playRallyPlaylist` independently rejects identity mismatches. `repeat_single: true` is accepted only for a one-rally list. The returned task supports pause, resume, cancel, and a completion result.

Seeking uses the browser media element's `currentTime`; actual landing and frame timing depend on the container, keyframe spacing, browser, and device. The controller does not claim millisecond-exact seeks or zero memory use. Unsupported/corrupt media enters an error state with Chinese guidance.

## Adapting the current PTTI contracts

San's `products/ptti-web/src/LocalVideoReview.tsx` owns an ephemeral `LocalVideoSession.session_id` and per-boundary confirmation state. Its adapter maps saved, explicitly confirmed boundaries to this contract. For data kept only in the current browser session, `session_id` may serve as `video_identity`; it changes when a file is selected and must not be treated as a durable media hash. Imported drafts must remain non-playable until both boundaries have been confirmed for the current file.

MainDex's saved score timeline uses integer `point_start_ms` / `point_end_ms`, per-field `field_evidence`, `verification_status`, and a verified video `source_sha256`. An adapter should admit only a `CONFIRMED` record whose two boundaries are independently confirmed, satisfy MainDex's strict start-before-end check, and match the loaded video's SHA. Convert milliseconds to seconds (`ms / 1000`) and use the verified SHA as `video_identity`. Nullable quick-annotation `rally_start_ms` / `rally_end_ms` remain unbound when missing. The playback core itself does not read, update, or promote MainDex records.

Recommended React seam for San is one controller instance per `<video>` ref: call `loadFile` on the user's file-input change, subscribe to `PlaybackSnapshot`, route the existing play/pause/seek/rate controls through the controller, and call both `unsubscribe()` and `release()` from the effect cleanup. San's Vite app is a separate package; a direct relative import from this shared directory may require its Vite `server.fs.allow` to include the shared module path. San should verify that in his integration change. The module does not own React state or alter San's worktree.

## Verification

- `npm run test:portable-playback` runs focused contract and lifecycle tests against the public TypeScript interface.
- `npm run test:portable-playback-browser` creates a four-second synthetic H.264/AAC MP4 in OS Temp, chooses it through an isolated headless Chrome/Edge file input, and exercises actual browser decode, play, pause, seek, 0.5x/1x, rally advance, pause/resume, single-rally repeat, replacement cancellation, decode error, and object URL release. It deletes only its own random temporary fixture/profile directory on exit.

The browser fixture proves the tested browser build can decode that H.264/AAC MP4. It does not certify all MP4 codecs or other browsers/devices. HEVC/H.265, AV1-in-MP4, ProRes, hardware decode, mobile browser limits, and files exceeding device resources remain dependent on the installed browser/OS codec stack and are not guaranteed by this module.

## GOAL 11-S: stable playback error and cancellation contract

Callers should branch on the exported `PlaybackIssueCode`, display the matching localized message, and keep playlist cancellation separate from media failure. `play()` and failed playlist starts classify the browser rejection name instead of labeling every rejection `play-rejected`.

| Signal | Meaning / UI action |
| --- | --- |
| `invalid-file-type`, `empty-file` | Reject selection before decoding. |
| `play-rejected` | `HTMLMediaElement.play()` returned `NotAllowedError`; ask the user to click Play again or check browser playback policy. |
| `unsupported-media` | Browser MediaError 4 or `NotSupportedError`: format/source not recognized; damaged bytes can also produce this. Do not assert a specific unsupported codec. |
| `decode-error` | MediaError 3, or unavailable error details; decoding failed, corruption versus codec cannot be determined here. |
| `file-read-error`, `media-aborted` | Local object-URL read failure (`NetworkError`/MediaError 2) or interrupted read (`AbortError`/MediaError 1); reselect the local file. This is not evidence of an internet outage. |
| `video-not-ready` | Metadata/source is not ready, including `InvalidStateError`; wait for the current file to load. |
| `playback-failed` | An unclassified browser exception; show a neutral retry message and retain the diagnostic code. |
| `duration-unavailable` | Metadata duration is missing/nonfinite/nonpositive; do not admit a rally queue. |
| `not-bound`, `missing-timestamp` | Do not invent boundaries. `PENDING_ANNOTATION` needs confirmation, `UNBOUND` needs binding, `STALE` needs revalidation; the caller retains that binding status. |
| `video-mismatch` | Current file session differs; revalidate rather than reuse the old playlist. |
| `invalid-time`, `time-out-of-range`, `start-after-end` | Reject the entire playlist before it starts; do not silently clamp rally boundaries. |
| `seek-failed`, `seek-timeout`, `media-ended-early`, `play-rejected` | Explain the failed operation and allow retry; do not skip silently into a different rally. |

Task `done` reports `cancelled` with `cancelled-by-user`, `manual-seek`, `video-replaced`, `playlist-replaced`, or `released`. Cancellation is not a decode error. Subscribe for visual state; await `done` for cancellation reason and completion count.

The Core accepts a user-selected local `File` through `loadFile()` and plays its owned object URL. It does not fetch official URLs, embed remote streams, or inspect DRM, login, or territory restrictions. San's official source link is a separate canonical HTTPS navigation; its catalog/evidence status may be `RESTRICTED`, while a click alone does not prove the destination loaded or video playback succeeded. Browser media errors cannot reliably identify a licensing or regional restriction, so do not infer `source-restricted` from `NotAllowedError` or MediaError 4.

The controller snapshots/copies its input playlist. It cannot observe mutations to San's annotation store or a backend revision. On edit, deletion, undo or revocation, San must call the active task's `cancel()` **before** changing eligibility, clear selected old bindings, then build a new queue only from the current confirmed records. This does not add backend revision monitoring to Core. Route all user seek controls through `controller.seek()`; direct assignments/native controls bypass that explicit cancellation API. Use a single controller per video element and release it on unmount.

### Comparing two clips in one player

Keep one controller for the current `<video>` and one reference to its active task. On each comparison selection, increment the UI request generation and cancel the old task immediately, even if the clicked point has since become stale. Read that point's binding again from current state; require `BOUND`, matching `video_identity`, confirmed boundaries and in-range seconds. Then call `setPlaybackRate(0.5)` if requested and `playRallyPlaylist([binding])`. A new playlist call itself replaces/cancels the prior active task before validating the new request, so an invalid selection cannot leave the old clip playing. Report its returned error code/message. When awaiting `done`, update UI only if both the task reference and request generation are still current. On source replacement, call `loadFile`; it cancels the active task and gives the new media a new identity. Do not reuse old bindings. San still owns annotation/revision invalidation and must cancel before changing a boundary, winner or target membership.

Minimal selection handler:

```ts
async function playSelectedPoint(pointId: string) {
  const generation = ++selectionGeneration.current;
  activeTask.current?.cancel();
  activeTask.current = null;
  const binding = currentBindings.current.get(pointId);
  if (!binding || binding.binding_status !== 'BOUND') return showBindingError();
  const rate = controller.setPlaybackRate(0.5);
  if (!rate.ok) return showPlaybackError(rate.error.code, rate.error.message);
  const started = controller.playRallyPlaylist([binding]);
  if (!started.ok) return showPlaybackError(started.error.code, started.error.message);
  activeTask.current = started.value;
  const result = await started.value.done;
  if (generation === selectionGeneration.current && activeTask.current === started.value) showTaskResult(result);
}
```

Reproduction: from `products/ptti/frontend`, run `npm run test:portable-playback`; strict module check: `node node_modules/typescript/bin/tsc --noEmit --strict --target ES2022 --module ES2022 --moduleResolution node --lib ES2022,DOM ../playback-core/src/index.ts`. Browser matrix: `npm run test:portable-playback-browser`, only when resource conditions permit. This matrix creates temporary synthetic assets, owns its browser/profile and does not use San's preview service.
