import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import ts from '../node_modules/typescript/lib/typescript.js';

const sourceUrl = new URL('../../playback-core/src/index.ts', import.meta.url);
const source = await readFile(sourceUrl, 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText;
const moduleUrl = `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`;
const {
  createLocalVideoPlaybackController,
  revalidateRallyBindings,
  validateRallyPlaybackBinding,
} = await import(moduleUrl);

class FakeVideo extends EventTarget {
  src = '';
  currentSrc = '';
  duration = 4;
  readyState = 0;
  paused = true;
  seeking = false;
  playbackRate = 1;
  _currentTime = 0;
  nextPlayFailure = null;
  trackedListeners = new Map();

  addEventListener(type, listener, options) {
    super.addEventListener(type, listener, options);
    if (listener) {
      if (!this.trackedListeners.has(type)) this.trackedListeners.set(type, new Set());
      this.trackedListeners.get(type).add(listener);
    }
  }

  removeEventListener(type, listener, options) {
    super.removeEventListener(type, listener, options);
    this.trackedListeners.get(type)?.delete(listener);
  }

  get listenerCount() {
    return [...this.trackedListeners.values()].reduce((count, listeners) => count + listeners.size, 0);
  }

  get currentTime() { return this._currentTime; }
  set currentTime(value) {
    this._currentTime = value;
    this.seeking = true;
    queueMicrotask(() => {
      this.seeking = false;
      this.dispatchEvent(new Event('seeked'));
      this.dispatchEvent(new Event('timeupdate'));
    });
  }

  load() {
    if (!this.src) {
      this.currentSrc = '';
      return;
    }
    const requestedSource = this.src;
    queueMicrotask(() => {
      if (this.src !== requestedSource) return;
      this.currentSrc = requestedSource;
      if (requestedSource === 'blob:bad') {
        this.dispatchEvent(new Event('error'));
        return;
      }
      this.readyState = 1;
      this.dispatchEvent(new Event('loadedmetadata'));
      this.readyState = 3;
      this.dispatchEvent(new Event('canplay'));
    });
  }

  async play() {
    if (this.nextPlayFailure) {
      const failure = this.nextPlayFailure;
      this.nextPlayFailure = null;
      throw failure;
    }
    this.paused = false;
    this.dispatchEvent(new Event('play'));
  }

  pause() {
    this.paused = true;
    this.dispatchEvent(new Event('pause'));
  }

  removeAttribute(name) {
    if (name === 'src') {
      this.src = '';
      this.currentSrc = '';
      this.readyState = 0;
    }
  }

  tick(seconds) {
    this._currentTime = seconds;
    this.dispatchEvent(new Event('timeupdate'));
  }
}

const flush = async () => {
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));
};
async function waitFor(predicate, label) {
  for (let i = 0; i < 40; i += 1) {
    if (predicate()) return;
    await flush();
  }
  assert.fail(`timed out waiting for ${label}`);
}

function file(name = 'local-review.mp4', type = 'video/mp4', size = 1024) {
  return { name, type, size, lastModified: 1700000000000 };
}
function rally(point_id, video_identity, start_time, end_time, binding_status = 'BOUND') {
  return { point_id, video_identity, start_time, end_time, binding_status };
}

const fixture = JSON.parse(await readFile(new URL('../../playback-core/fixtures/synthetic-rally-playlist.json', import.meta.url), 'utf8'));
assert.equal(fixture.fixture_status, 'SYNTHETIC_TEST_ONLY');
const valid = fixture.rallies[0];
assert.equal(validateRallyPlaybackBinding(valid, fixture.video_identity, 4).ok, true);
assert.equal(validateRallyPlaybackBinding({ ...valid, binding_status: 'PENDING_ANNOTATION' }, fixture.video_identity, 4).error.code, 'not-bound');
assert.equal(validateRallyPlaybackBinding({ ...valid, start_time: null }, fixture.video_identity, 4).error.code, 'missing-timestamp');
assert.equal(validateRallyPlaybackBinding({ ...valid, start_time: 2, end_time: 1 }, fixture.video_identity, 4).error.code, 'start-after-end');
assert.equal(validateRallyPlaybackBinding({ ...valid, end_time: 4.1 }, fixture.video_identity, 4).error.code, 'time-out-of-range');
assert.equal(validateRallyPlaybackBinding(fixture.unmarked_point, fixture.video_identity, 4).error.code, 'not-bound');
assert.equal(revalidateRallyBindings([valid], 'another-video', 4)[0].binding_status, 'STALE');
assert.equal(revalidateRallyBindings([{ ...valid, binding_status: 'PENDING_ANNOTATION' }], 'another-video', 4)[0].binding_status, 'PENDING_ANNOTATION');
console.log('PASS timeline contract: real timestamps, bounds, ordering, and replacement invalidation');

let unexpectedUrlCreation = 0;
const noIdentityController = createLocalVideoPlaybackController(new FakeVideo(), {
  createObjectURL: () => { unexpectedUrlCreation += 1; return 'blob:should-not-exist'; },
  revokeObjectURL: () => undefined,
  createVideoIdentity: () => '',
});
assert.equal(noIdentityController.loadFile(file()).error.code, 'identity-unavailable');
assert.equal(unexpectedUrlCreation, 0, 'a file object URL is not created without an identity');
noIdentityController.release();

const pendingVideo = new FakeVideo();
const pendingUrls = [];
const pendingController = createLocalVideoPlaybackController(pendingVideo, {
  createObjectURL: () => 'blob:pending-load',
  revokeObjectURL: (url) => pendingUrls.push(url),
  createVideoIdentity: () => 'local-session:pending-load',
});
assert.equal(pendingController.loadFile(file('pending-load.mp4')).ok, true);
pendingController.release();
await flush();
pendingVideo.currentSrc = '';
pendingVideo._currentTime = 3.25;
pendingVideo.dispatchEvent(new Event('loadedmetadata'));
pendingVideo.dispatchEvent(new Event('canplay'));
pendingVideo.dispatchEvent(new Event('seeked'));
pendingVideo.dispatchEvent(new Event('timeupdate'));
assert.equal(pendingController.getSnapshot().status, 'empty', 'release cancels an in-flight media load');
assert.deepEqual(pendingUrls, ['blob:pending-load']);
assert.equal(pendingVideo.listenerCount, 0, 'release removes all media element listeners');
console.log('PASS load cancellation and cleanup: release revokes its URL and removes media listeners');

const video = new FakeVideo();
const created = [];
const revoked = [];
let nextIdentity = 0;
const controller = createLocalVideoPlaybackController(video, {
  createObjectURL: (item) => { created.push(item.name); return `blob:${item.name === 'broken.mp4' ? 'bad' : `fixture-${created.length}`}`; },
  revokeObjectURL: (url) => revoked.push(url),
  createVideoIdentity: () => `local-session:test-${++nextIdentity}`,
  seek_timeout_ms: 50,
});
const updates = [];
const unsubscribe = controller.subscribe((snapshot) => updates.push(snapshot));
const loaded = controller.loadFile(file());
assert.equal(loaded.ok, true);
await waitFor(() => controller.getSnapshot().status === 'ready', 'local MP4 metadata and decode readiness');
assert.equal(controller.getSnapshot().file.name, 'local-review.mp4');
assert.equal(controller.getSnapshot().duration_seconds, 4);
assert.equal((await controller.play()).ok, true);
assert.equal(controller.getSnapshot().is_playing, true);
controller.pause();
assert.equal(video.paused, true);
assert.equal(controller.getSnapshot().is_playing, false);
assert.deepEqual(controller.seek(99), { ok: true, value: 4 });
assert.equal(controller.setPlaybackRate(0.5).value, 0.5);
assert.equal(controller.setPlaybackRate(1).value, 1);
assert.equal(controller.setPlaybackRate(2).error.code, 'unsupported-rate');
assert.equal(updates.some((snapshot) => snapshot.status === 'ready'), true);
console.log('PASS local player controls: play, pause, bounded seek, 0.5x/1x, and observable state');

for (const [failureName, expectedCode] of [
  ['NotAllowedError', 'play-rejected'],
  ['NotSupportedError', 'unsupported-media'],
  ['AbortError', 'media-aborted'],
  ['NetworkError', 'file-read-error'],
  ['InvalidStateError', 'video-not-ready'],
  ['UnexpectedError', 'playback-failed'],
]) {
  const failedVideo = new FakeVideo();
  const failedController = createLocalVideoPlaybackController(failedVideo, {
    createObjectURL: () => `blob:play-${failureName}`,
    revokeObjectURL: () => undefined,
    createVideoIdentity: () => `local-session:play-${failureName}`,
  });
  failedController.loadFile(file());
  await waitFor(() => failedController.getSnapshot().status === 'ready', `${failureName} play rejection readiness`);
  failedVideo.nextPlayFailure = Object.assign(new Error('browser media error'), { name: failureName });
  const playResult = await failedController.play();
  assert.equal(playResult.ok, false);
  assert.equal(playResult.error.code, expectedCode, `${failureName} must retain its actionable category`);
  failedController.release();
}
console.log('PASS play rejection classification: browser policy, unsupported media, abort, local read, readiness, and unknown failure');

const rejectedPlaylistVideo = new FakeVideo();
const rejectedPlaylistController = createLocalVideoPlaybackController(rejectedPlaylistVideo, {
  createObjectURL: () => 'blob:rejected-playlist',
  revokeObjectURL: () => undefined,
  createVideoIdentity: () => 'local-session:rejected-playlist',
});
rejectedPlaylistController.loadFile(file());
await waitFor(() => rejectedPlaylistController.getSnapshot().status === 'ready', 'rejected playlist readiness');
rejectedPlaylistVideo.nextPlayFailure = Object.assign(new Error('unsupported media'), { name: 'NotSupportedError' });
const rejectedPlaylist = rejectedPlaylistController.playRallyPlaylist([
  rally('unsupported-point', 'local-session:rejected-playlist', 0, 1),
]);
assert.equal(rejectedPlaylist.ok, true);
const rejectedPlaylistOutcome = await rejectedPlaylist.value.done;
assert.equal(rejectedPlaylistOutcome.status, 'failed');
assert.equal(rejectedPlaylistOutcome.error.code, 'unsupported-media');
rejectedPlaylistController.release();
console.log('PASS playlist start failure preserves the browser media error category');

const identity = controller.getSnapshot().video_identity;
const first = [rally('p-1', identity, 0.4, 0.8), rally('p-2', identity, 1.2, 1.7)];
const taskResult = controller.playRallyPlaylist(first);
assert.equal(taskResult.ok, true);
await waitFor(() => !video.paused && video.currentTime === 0.4, 'first rally start');
taskResult.value.pause();
video.tick(0.8);
assert.equal(controller.getSnapshot().playlist.current_index, 0, 'pause holds the current rally');
assert.equal((await taskResult.value.resume()).ok, true);
await waitFor(() => !video.paused && video.currentTime === 1.2, 'automatic next rally');
assert.equal(controller.getSnapshot().playlist.current_index, 1);
video.tick(1.7);
assert.deepEqual(await taskResult.value.done, { status: 'completed', completed_rallies: 2 });
assert.equal(video.paused, true);
console.log('PASS rally playlist: first item, pause/resume, auto-next, and normal completion');

const skipPlaylist = controller.playRallyPlaylist([
  rally('skip-p1', identity, 0.3, 0.5),
  rally('skip-p2', identity, 1.2, 1.4),
  rally('skip-p3', identity, 2.3, 2.6),
]);
assert.equal(skipPlaylist.ok, true);
await waitFor(() => !video.paused && video.currentTime === 0.3, 'skip playlist first rally');
assert.equal(controller.seek(2.35).ok, true);
assert.equal(controller.getSnapshot().playlist.status, 'cancelled', 'a user seek to another point cancels the stale playlist');
assert.deepEqual(await skipPlaylist.value.done, { status: 'cancelled', reason: 'manual-seek', completed_rallies: 0 });
await flush();
assert.ok(Math.abs(video.currentTime - 2.35) < 0.01, 'the selected third rally position remains selected');
assert.equal(controller.getSnapshot().playlist.status, 'cancelled', 'late timeupdate cannot restart the old playlist');
console.log('PASS direct point switch: seeking away from rally one cancels the old playlist');

const interrupted = controller.playRallyPlaylist([rally('early-end', identity, 0.4, 2.5)]);
assert.equal(interrupted.ok, true);
await waitFor(() => !video.paused && video.currentTime === 0.4, 'early-end test start');
video.dispatchEvent(new Event('ended'));
assert.equal((await interrupted.value.done).error.code, 'media-ended-early');
console.log('PASS early media end: playlist fails with a specific recoverable error');

let loopSeekCount = 0;
const countLoopSeek = () => { loopSeekCount += 1; };
video.addEventListener('seeked', countLoopSeek);
const repeating = controller.playRallyPlaylist([rally('loop-1', identity, 0.3, 0.6)], { repeat_single: true });
assert.equal(repeating.ok, true);
await waitFor(() => !video.paused && video.currentTime === 0.3, 'loop start');
video.tick(0.6);
await waitFor(() => loopSeekCount >= 2 && !video.paused && video.currentTime === 0.3, 'single-rally repeat');
repeating.value.cancel();
assert.deepEqual(await repeating.value.done, { status: 'cancelled', reason: 'cancelled-by-user', completed_rallies: 1 });
video.removeEventListener('seeked', countLoopSeek);
console.log('PASS playlist lifecycle: single-rally loop and explicit cancel');

const oldIdentity = controller.getSnapshot().video_identity;
const oldTask = controller.playRallyPlaylist([rally('replace-me', oldIdentity, 0.5, 2)], { repeat_single: true });
assert.equal(oldTask.ok, true);
assert.equal(controller.setPlaybackRate(0.5).ok, true);
const nextFile = controller.loadFile(file('next.mp4'));
assert.equal(nextFile.ok, true);
assert.equal(video.playbackRate, 1, 'new files reset playback speed');
assert.deepEqual(await oldTask.value.done, { status: 'cancelled', reason: 'video-replaced', completed_rallies: 0 });
assert.notEqual(nextFile.value, oldIdentity);
assert.equal(revoked.includes('blob:fixture-1'), true);
assert.equal(validateRallyPlaybackBinding(rally('stale', oldIdentity, 0.2, 0.4), nextFile.value, 4).error.code, 'video-mismatch');
await waitFor(() => controller.getSnapshot().status === 'ready', 'replacement video readiness');
assert.equal(controller.playRallyPlaylist([]).error.code, 'empty-playlist');
assert.equal(controller.playRallyPlaylist([rally('old', oldIdentity, 0.2, 0.4)]).error.code, 'video-mismatch');
assert.equal(controller.playRallyPlaylist([
  rally('a', nextFile.value, 0.2, 0.4), rally('b', nextFile.value, 0.5, 0.8),
], { repeat_single: true }).error.code, 'repeat-requires-single');
console.log('PASS video replacement: old playlist cancelled, old object URL released, old binding rejected');

const racingFile = controller.loadFile(file('rapid-switch-first.mp4'));
assert.equal(racingFile.ok, true);
const supersededUrl = video.src;
const latestRacingFile = controller.loadFile(file('rapid-switch-latest.mp4'));
assert.equal(latestRacingFile.ok, true);
assert.equal(revoked.includes(supersededUrl), true, 'rapid replacement revokes the superseded object URL');
video._currentTime = 2.75;
const emitQueuedEvents = () => {
  video.dispatchEvent(new Event('loadedmetadata'));
  video.dispatchEvent(new Event('canplay'));
  video.dispatchEvent(new Event('timeupdate'));
  video.dispatchEvent(new Event('seeked'));
};
video.currentSrc = video.src;
video.readyState = 0;
emitQueuedEvents();
assert.equal(controller.getSnapshot().status, 'loading', 'metadata events are ignored until the current source has metadata');
assert.equal(controller.getSnapshot().duration_seconds, null, 'queued metadata cannot ready a source before HAVE_METADATA');
video.currentSrc = '';
emitQueuedEvents();
assert.equal(controller.getSnapshot().status, 'loading', 'events without a selected current source cannot ready the replacement');
assert.equal(controller.getSnapshot().duration_seconds, null, 'stale metadata cannot set the replacement duration');
assert.equal(controller.getSnapshot().current_time_seconds, 0, 'stale timeupdate cannot move the replacement playhead');
await waitFor(() => controller.getSnapshot().status === 'ready', 'rapid-switch replacement readiness');
assert.equal(controller.getSnapshot().file.name, 'rapid-switch-latest.mp4');
console.log('PASS source-switch race: unselected-source metadata, readiness, and time events are ignored');

assert.equal(controller.loadFile(file('notes.txt', 'text/plain')).error.code, 'invalid-file-type');
assert.equal(controller.getSnapshot().status, 'error');
assert.equal(controller.loadFile(file('broken.mp4')).ok, true);
await waitFor(() => controller.getSnapshot().status === 'error', 'decode error state');
assert.equal(controller.getSnapshot().error.message.includes('浏览器无法解码'), true);
console.log('PASS invalid and undecodable file: explicit failure state and Chinese guidance');

const recovered = controller.loadFile(file('recovered.mp4'));
assert.equal(recovered.ok, true);
await waitFor(() => controller.getSnapshot().status === 'ready', 'valid video recovery after decode failure');
assert.equal(controller.getSnapshot().error, null);
assert.equal(revoked.includes('blob:bad'), true, 'failed media URL is released when a valid file replaces it');
console.log('PASS media recovery: valid selection works after a decode failure and releases the failed URL');

unsubscribe();
const activeUrlBeforeRelease = video.src;
controller.release();
assert.equal(revoked.includes(activeUrlBeforeRelease), true, 'final active object URL is revoked on release');
assert.equal(revoked.includes('blob:bad'), true);
assert.equal(controller.getSnapshot().status, 'empty');
assert.equal(video.listenerCount, 0, 'controller release removes all media element listeners');
console.log('PASS release: listeners removed, media reset, and active object URL revoked');

// Browser MediaError codes are actionable signals, not proof of file corruption.
for (const [mediaCode, expected] of [[1, 'media-aborted'], [2, 'file-read-error'],
  [3, 'decode-error'], [4, 'unsupported-media'], [undefined, 'decode-error']]) {
  const media = new FakeVideo();
  const released = [];
  const player = createLocalVideoPlaybackController(media, {
    createObjectURL: () => 'blob:error-case', revokeObjectURL: url => released.push(url),
    createVideoIdentity: () => 'error-case',
  });
  player.loadFile(file());
  await flush();
  const running = player.playRallyPlaylist([rally('error-point', 'error-case', 0, 3)]);
  await flush();
  media.error = mediaCode === undefined ? null : { code: mediaCode };
  media.dispatchEvent(new Event('error'));
  assert.equal(player.getSnapshot().error.code, expected);
  assert.equal((await running.value.done).error.code, expected);
  assert.equal(media.paused, true);
  player.release();
  assert.deepEqual(released, ['blob:error-case']);
  assert.equal(media.listenerCount, 0);
}
for (const duration of [NaN, Infinity, 0]) {
  const media = new FakeVideo();
  media.duration = duration;
  const player = createLocalVideoPlaybackController(media, {
    createObjectURL: () => 'blob:duration', revokeObjectURL: () => {},
    createVideoIdentity: () => 'duration',
  });
  player.loadFile(file());
  await flush();
  assert.equal(player.getSnapshot().error.code, 'duration-unavailable');
  assert.equal(player.playRallyPlaylist([rally('p', 'duration', 0, 1)]).ok, false);
  player.release();
}
console.log('PASS distinct media errors, unknown duration, active-task failure, and cleanup');

const boundaryVideo = new FakeVideo();
const boundaryPlayer = createLocalVideoPlaybackController(boundaryVideo, {
  createObjectURL: () => 'blob:boundaries', revokeObjectURL: () => {},
  createVideoIdentity: () => 'boundaries',
});
boundaryPlayer.loadFile(file());
await flush();
const boundaryTask = boundaryPlayer.playRallyPlaylist([rally('point', 'boundaries', 0.3, 1)]);
await flush();
// The annotation owner must cancel before publishing changed/revoked boundaries.
boundaryTask.value.cancel();
assert.equal((await boundaryTask.value.done).reason, 'cancelled-by-user');
assert.equal(boundaryPlayer.playRallyPlaylist([rally('point', 'boundaries', 0.4, 1.2, 'PENDING_ANNOTATION')]).error.code, 'not-bound');
boundaryVideo.tick(1.5);
assert.equal(boundaryVideo.paused, true);
assert.equal(boundaryPlayer.getSnapshot().playlist.status, 'cancelled');
const rebound = boundaryPlayer.playRallyPlaylist([rally('point', 'boundaries', 1.4, 1.8)]);
await flush();
assert.equal(boundaryVideo.currentTime, 1.4);
boundaryVideo.tick(1.8);
assert.equal((await rebound.value.done).status, 'completed');
boundaryPlayer.release();
console.log('PASS boundary owner handoff: cancel, reject unconfirmed range, replay only the newly bound range');

const compareVideo = new FakeVideo();
let comparisonIdentity = '';
let comparisonSession = 0;
const compareController = createLocalVideoPlaybackController(compareVideo, {
  createObjectURL: () => 'blob:compare-session-a', revokeObjectURL: () => {},
  createVideoIdentity: () => `local-session:compare-${++comparisonSession}`,
});
comparisonIdentity = compareController.loadFile(file('compare-a.mp4')).value;
await flush();
const firstComparisonIdentity = comparisonIdentity;
const comparePoint = (id, start, end, identity = comparisonIdentity) =>
  rally(id, identity, start, end);
const firstClip = compareController.playRallyPlaylist([comparePoint('p002', 0.4, 0.8)]);
await waitFor(() => !compareVideo.paused && compareVideo.currentTime === 0.4, 'comparison first clip');
const secondClip = compareController.playRallyPlaylist([comparePoint('p004', 1.2, 1.6)]);
assert.equal((await firstClip.value.done).reason, 'playlist-replaced');
await waitFor(() => !compareVideo.paused && compareVideo.currentTime === 1.2, 'comparison second clip');
const backToFirst = compareController.playRallyPlaylist([comparePoint('p002', 0.4, 0.8)]);
assert.equal((await secondClip.value.done).reason, 'playlist-replaced');
await waitFor(() => !compareVideo.paused && compareVideo.currentTime === 0.4, 'comparison return to first clip');
assert.equal(compareController.setPlaybackRate(0.5).ok, true);
backToFirst.value.pause();
assert.equal(compareVideo.paused, true);
assert.equal((await backToFirst.value.resume()).ok, true);
backToFirst.value.cancel();
assert.equal((await backToFirst.value.done).reason, 'cancelled-by-user');
assert.equal(compareVideo.paused, true);

const beforeStaleRequest = compareController.playRallyPlaylist([comparePoint('valid-before-stale', 0.6, 1)]);
await waitFor(() => !compareVideo.paused && compareVideo.currentTime === 0.6, 'active clip before stale request');
assert.equal(compareController.playRallyPlaylist([
  comparePoint('stale-session', 0.4, 0.8, 'local-session:old'),
]).error.code, 'video-mismatch');
assert.equal((await beforeStaleRequest.value.done).reason, 'playlist-replaced');
assert.equal(compareVideo.paused, true, 'rejecting a stale selection also stops the previous clip');

const rapid = [
  compareController.playRallyPlaylist([comparePoint('rapid-old', 0.3, 0.5)]),
  compareController.playRallyPlaylist([comparePoint('rapid-middle', 0.9, 1.1)]),
  compareController.playRallyPlaylist([comparePoint('rapid-last', 2.1, 2.4)]),
];
assert.equal((await rapid[0].value.done).reason, 'playlist-replaced');
assert.equal((await rapid[1].value.done).reason, 'playlist-replaced');
await waitFor(() => !compareVideo.paused && compareVideo.currentTime === 2.1, 'last valid rapid comparison action');
assert.equal(compareController.setPlaybackRate(2).error.code, 'unsupported-rate');
const activeBeforeReplacement = rapid[2].value;
const comparisonReplacement = compareController.loadFile(file('compare-b.mp4'));
assert.equal(comparisonReplacement.ok, true);
assert.equal((await activeBeforeReplacement.done).reason, 'video-replaced');
comparisonIdentity = comparisonReplacement.value;
await waitFor(() => compareController.getSnapshot().status === 'ready', 'replacement comparison media ready');
assert.equal(compareController.playRallyPlaylist([comparePoint('old-session', 0.4, 0.8, firstComparisonIdentity)]).error.code, 'video-mismatch');
assert.equal(compareVideo.paused, true);
const reentered = compareController.playRallyPlaylist([comparePoint('new-session', 1.7, 2)]);
await waitFor(() => !compareVideo.paused && compareVideo.currentTime === 1.7, 'comparison after media replacement');
reentered.value.cancel();
compareController.release();
assert.equal(compareVideo.listenerCount, 0);
console.log('PASS clip compare: p002→p004→p002, rapid last-action-wins, pause/resume/cancel, invalid identity, replace and replay');

// GOAL12.6: bounded burst selection must retain only the latest owned source.
const burstVideo = new FakeVideo();
const burstRevoked = [];
let burstId = 0;
const burstPlayer = createLocalVideoPlaybackController(burstVideo, {
  createObjectURL: () => `blob:burst-${burstId}`,
  createVideoIdentity: () => `burst-${++burstId}`,
  revokeObjectURL: url => burstRevoked.push(url),
});
for (let index = 0; index < 24; index += 1) burstPlayer.loadFile(file(`burst-${index}.mp4`));
await flush();
assert.equal(burstPlayer.getSnapshot().video_identity, 'burst-24');
assert.equal(burstPlayer.getSnapshot().file.name, 'burst-23.mp4');
assert.equal(burstRevoked.length, 23);
assert.equal(new Set(burstRevoked).size, 23);
const cancelled = burstPlayer.playRallyPlaylist([rally('old', 'burst-24', 0.2, 0.7)]).value;
cancelled.cancel();
cancelled.cancel();
assert.equal((await cancelled.done).reason, 'cancelled-by-user');
const currentTask = burstPlayer.playRallyPlaylist([rally('current', 'burst-24', 1, 2)]).value;
await flush();
cancelled.cancel();
cancelled.pause();
assert.equal((await cancelled.resume()).ok, false);
assert.equal(burstVideo.paused, false, 'obsolete task handles cannot pause the current task');
assert.equal(burstPlayer.getSnapshot().playlist.point_id, 'current');
burstPlayer.loadFile(file('not-video.txt', 'text/plain'));
assert.equal((await currentTask.done).reason, 'video-replaced');
assert.equal(burstPlayer.getSnapshot().error.code, 'invalid-file-type');
burstPlayer.release();
burstPlayer.release();
await flush();
assert.equal(burstRevoked.length, 24);
assert.equal(new Set(burstRevoked).size, 24);
assert.equal(burstVideo.listenerCount, 0);
console.log('PASS burst selection and repeated cancellation: latest media only, obsolete task handles inert, invalid replacement stops queue, release idempotent');

class StalledSeekVideo extends FakeVideo {
  get currentTime() { return this._currentTime; }
  set currentTime(value) { this._currentTime = value; this.seeking = true; }
}
const stalledVideo = new StalledSeekVideo();
const stalledPlayer = createLocalVideoPlaybackController(stalledVideo, {
  createObjectURL: () => 'blob:stalled', revokeObjectURL: () => {},
  createVideoIdentity: () => 'stalled', seek_timeout_ms: 20,
});
stalledPlayer.loadFile(file());
await flush();
const baselineListeners = stalledVideo.listenerCount;
const stalledTask = stalledPlayer.playRallyPlaylist([rally('stalled', 'stalled', 1, 2)]).value;
const stalledResult = await stalledTask.done;
assert.equal(stalledResult.status, 'failed');
assert.equal(stalledResult.error.code, 'seek-timeout');
assert.equal(stalledVideo.paused, true);
assert.equal(stalledVideo.listenerCount, baselineListeners, 'seek timeout removes its temporary listeners');
stalledVideo.dispatchEvent(new Event('seeked'));
assert.equal(stalledVideo.paused, true, 'late seek completion cannot resurrect a failed task');
stalledPlayer.release();
assert.equal(stalledVideo.listenerCount, 0);
console.log('PASS stalled seek: bounded failure, temporary listeners removed, late completion cannot restart queue');

class ThrowingLoadVideo extends FakeVideo {
  failNextLoad = false;
  load() {
    if (this.src && this.failNextLoad) { this.failNextLoad = false; throw new Error('synthetic load failure'); }
    super.load();
  }
}
const faultVideo = new ThrowingLoadVideo();
let failUrl = true;
let faultId = 0;
const faultRevoked = [];
const faultPlayer = createLocalVideoPlaybackController(faultVideo, {
  createObjectURL: () => { if (failUrl) throw new Error('synthetic URL failure'); return `blob:fault-${faultId}`; },
  createVideoIdentity: () => `fault-${++faultId}`,
  revokeObjectURL: url => faultRevoked.push(url),
});
assert.equal(faultPlayer.loadFile(file()).error.code, 'file-read-error');
assert.equal(faultPlayer.getSnapshot().status, 'error');
failUrl = false;
faultVideo.failNextLoad = true;
assert.equal(faultPlayer.loadFile(file()).error.code, 'file-read-error');
assert.equal(faultPlayer.loadFile(file('valid-again.mp4')).ok, true);
await flush();
assert.equal(faultPlayer.getSnapshot().status, 'ready');
assert.equal(faultPlayer.getSnapshot().error, null);
faultPlayer.release();
assert.equal(faultRevoked.length, 2);
assert.equal(new Set(faultRevoked).size, 2);
assert.equal(faultVideo.listenerCount, 0);
console.log('PASS URL/load exceptions: explicit local-read errors, valid-file recovery, failed and active URLs each released once');

const navigationVideo = new FakeVideo();
const navigationPlayer = createLocalVideoPlaybackController(navigationVideo, {
  createObjectURL: () => 'blob:navigation', revokeObjectURL: () => {}, createVideoIdentity: () => 'navigation',
});
navigationPlayer.loadFile(file());
await flush();
await navigationPlayer.play();
navigationPlayer.pause();
assert.equal(navigationVideo.paused, true);
assert.equal(navigationPlayer.getSnapshot().video_identity, 'navigation');
const navigationTask = navigationPlayer.playRallyPlaylist([rally('point', 'navigation', 0.5, 1.5)]).value;
await flush();
navigationTask.cancel();
navigationPlayer.pause();
await flush();
assert.equal((await navigationTask.done).reason, 'cancelled-by-user');
assert.equal(navigationVideo.paused, true);
assert.equal(navigationVideo.src, 'blob:navigation', 'navigation pause retains the selected local media');
assert.equal((await navigationTask.resume()).ok, false, 'returning to a route must not resume the cancelled queue');
assert.equal((await navigationPlayer.play()).ok, true, 'explicit ordinary viewing remains available on return');
navigationPlayer.release();
assert.equal(navigationVideo.listenerCount, 0);
console.log('PASS navigation contract: cancel then pause retains local media, never resumes the old queue, explicit ordinary viewing still works');
