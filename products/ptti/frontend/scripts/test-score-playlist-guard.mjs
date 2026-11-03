import assert from 'node:assert/strict';
import { scorePlaylistReferences, watchScorePlaylist } from '../src/scorePlaylistGuard.mjs';

const score = { evidence_id: 'score:p1', score_moment_id: 'p1', score_revision: 'r1',
  event_type: 'MANUAL_SCORE_SEGMENT', source: 'MANUAL_CONFIRMED' };
assert.deepEqual(scorePlaylistReferences([score, { ...score, source: 'MANUAL' }]),
  [{ evidence_id: 'score:p1', score_revision: 'r1' }]);
assert.equal(scorePlaylistReferences([{ ...score, score_revision: undefined }])[0].score_revision, '');

const flush = () => new Promise(resolve => setImmediate(resolve));
let tick, calls = 0, stopped = 0, cancelled = 0, stale = false;
const cleanup = watchScorePlaylist(scorePlaylistReferences([score]), async () => {
  calls++; if (stale) throw new Error('409 stale revision');
}, () => stopped++, { schedule: callback => { tick = callback; return 1; }, cancel: () => cancelled++ });
await flush();
assert.equal(calls, 1);
assert.equal(stopped, 0);
stale = true;
await tick();
assert.equal(stopped, 1);
assert.equal(cancelled, 1);
await tick();
assert.equal(calls, 2, 'invalid queue never resumes polling/playback');
cleanup();

let rejectPending;
stopped = 0;
const release = watchScorePlaylist(scorePlaylistReferences([score]), () => new Promise((_, reject) => {
  rejectPending = reject;
}), () => stopped++, { schedule: () => 1, cancel: () => {} });
release();
rejectPending(new Error('network unavailable'));
await flush();
assert.equal(stopped, 0, 'unmounted player ignores late validation failure');

stopped = 0;
watchScorePlaylist(scorePlaylistReferences([score]), async () => { throw new Error('network unavailable'); },
  () => stopped++, { schedule: () => 1, cancel: () => {} });
await flush();
assert.equal(stopped, 1, 'unavailable service stops score playback rather than trusting stale timestamps');
stopped = 0;
watchScorePlaylist(scorePlaylistReferences([score]), () => new Promise(() => {}), () => stopped++,
  { timeoutMs: 5, schedule: () => 1, cancel: () => {} });
await new Promise(resolve => setTimeout(resolve, 20));
assert.equal(stopped, 1, 'stalled validation cannot leave stale playback running indefinitely');
console.log('PASS: ownership filter, legacy revision rejection input, revision invalidation, cleanup, offline fail-closed');
