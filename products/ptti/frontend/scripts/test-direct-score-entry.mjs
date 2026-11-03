import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import * as guard from '../src/scorePlaylistGuard.mjs';

const require = createRequire(import.meta.url);
const compiler = process.env.PTTI_TYPESCRIPT_MODULE || '../node_modules/typescript/lib/typescript.js';
const ts = require(compiler);
const source = ts.createSourceFile('VideoEvidencePlayer.tsx', readFileSync(new URL('../src/VideoEvidencePlayer.tsx', import.meta.url), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const names = new Set(['jumpToScore', 'playConfirmedScore', 'openClip', 'invalidateScorePlayback', 'seek', 'selectVideo', 'playCandidateContext', 'enforcePlaybackBoundary']);
const functions = [];
const visit = node => { if (ts.isFunctionDeclaration(node) && names.has(node.name?.text)) functions.push(node.getText(source)); ts.forEachChild(node, visit); };
visit(source);
const javascript = ts.transpileModule(functions.join('\n'), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;

const cached = { point_id: 'p1', video_id: 'v1', video_sha256: 'sha', point_start_ms: 10000, point_end_ms: 12000,
  verification_status: 'CONFIRMED', availability_status: 'AVAILABLE' };
const clip = { evidence_id: 'score:p1', score_moment_id: 'p1', score_revision: 'new-version', video_id: 'v1', video_sha256: 'sha',
  start_ms: 14000, end_ms: 17000, representative_ms: 14000, tags: [], notes: '', event_type: 'MANUAL_SCORE_SEGMENT', source: 'MANUAL_CONFIRMED', review_status: 'CONFIRMED' };

function harness() {
  const state = { selected: null, range: false, playlist: false, pauses: 0, plays: 0, calls: [], invalid: false, notice: '' };
  const media = { readyState: 1, duration: 120, currentTime: 0, paused: false, pause() { state.pauses++; }, play() { state.plays++; return Promise.resolve(); } };
  const box = { ...guard, videos: [{ video_id: 'v1', source_sha256: 'sha', availability_status: 'AVAILABLE', duration_ms: 120000, title: 'SIMULATED_ONLY test' }],
    videoId: 'v1', videoRef: { current: media }, scorePlaybackGeneration: { current: 0 },
    previewEndMs: { current: null }, previewEndNotice: { current: '' }, pending: { current: null },
    pendingScorePlaylist: { current: [] }, boundaryBusy: { current: false }, context: 2, initial: {},
    setSelected(value) { state.selected = value; }, setRangePlayback(value) { state.range = value; },
    setPlaylistMode(value) { state.playlist = value; }, setNotice(value) { state.notice = value; },
    setError(value) { state.error = value; },
    canPlayConfirmedScore: () => true, observationAnchorMs: row => row.point_start_ms,
    observationSeekMs: row => row.point_start_ms - 1500, clock: value => String(value),
    api: async (path, body) => {
      state.calls.push(path);
      if (state.invalid) throw new Error('409 deleted/revoked/changed media');
      if (path === '/scores/playlist') {
        assert.deepEqual(Array.from(body), ['p1'], 'only point identity, never cached boundaries, is submitted');
        return { evidence_ids: [clip.evidence_id], score_references: guard.scorePlaylistReferences([clip]) };
      }
      if (path === '/evidence') return [clip];
      if (path === '/scores/playlist/validate') {
        assert.equal(body[0].score_revision, 'new-version');
        return { valid: true };
      }
      throw new Error('Unexpected request ' + path);
    },
  };
  for (const setter of ['setScoreReviewContext', 'setLoopClip', 'setPlaylistOverride', 'setDraft', 'setReviewStamp', 'setReviewSide', 'setVideoId', 'setCurrent', 'setPointStart', 'setPointEnd', 'setContext', 'setClips']) box[setter] = () => {};
  runInNewContext(javascript, box);
  box.openRef = { current: box.openClip };
  return { state, media, box };
}

const current = harness();
await current.box.jumpToScore(cached, true);
assert.equal(current.media.currentTime, 14, 'direct score playback must resolve latest 14–17s rather than cached 10–12s');
assert.ok(current.state.calls.includes('/scores/playlist'));
assert.equal(current.state.selected.score_revision, 'new-version');
assert.equal(current.state.range, true, 'direct playback joins existing range/version monitoring');
assert.equal(current.box.previewEndMs.current, 17000, 'single-point playback uses exact current end');

let tick;
const stop = guard.watchScorePlaylist(guard.scorePlaylistReferences([current.state.selected]),
  refs => current.box.api('/scores/playlist/validate', refs), () => current.box.invalidateScorePlayback(),
  { schedule: callback => { tick = callback; return 1; }, cancel: () => {} });
await new Promise(resolve => setImmediate(resolve));
current.state.invalid = true;
await tick();
assert.ok(current.state.pauses > 0);
assert.equal(current.state.range, false);
assert.equal(current.state.selected, null);
assert.equal(current.box.pending.current, null);
stop();

for (const reason of ['deleted', 'revoked start', 'revoked end', 'changed media', 'request failed']) {
  const rejected = harness(); rejected.state.invalid = true;
  await rejected.box.jumpToScore(cached, true);
  assert.equal(rejected.state.plays, 0, reason);
  assert.equal(rejected.media.currentTime, 0, reason);
}

const wrongMedia = harness();
wrongMedia.box.videos[0].source_sha256 = 'different-media';
await wrongMedia.box.jumpToScore(cached, true);
assert.equal(wrongMedia.state.plays, 0, 'loaded video metadata must also match fresh clip SHA');

const observation = harness();
await observation.box.jumpToScore(cached, false);
assert.equal(observation.media.currentTime, 8.5);
assert.equal(observation.state.plays, 0, 'review clues remain ordinary paused observations');
assert.equal(observation.state.calls.length, 0);

const manual = harness();
await manual.box.openClip({ ...clip, evidence_id: 'manual', score_moment_id: undefined, source: 'MANUAL', event_type: 'KEY_CLIP' }, true);
assert.equal(manual.state.plays, 1);
assert.equal(manual.state.calls.length, 0, 'independent manual clips do not require score ownership');

const contextPreview = harness();
contextPreview.box.selected = clip;
contextPreview.box.active = contextPreview.box.videos[0];
contextPreview.state.invalid = true;
contextPreview.box.playCandidateContext();
await new Promise(resolve => setImmediate(resolve));
assert.equal(contextPreview.state.plays, 0, 'score context action cannot bypass validation');
assert.ok(contextPreview.state.calls.includes('/scores/playlist/validate'));

const looping = harness();
looping.box.playback = { current: { selected: clip, active: looping.box.videos[0], rangePlayback: true,
  loopClip: true, context: 0, playlistMode: false } };
looping.media.currentTime = 18;
looping.state.invalid = true;
looping.box.enforcePlaybackBoundary();
await new Promise(resolve => setImmediate(resolve));
assert.equal(looping.state.plays, 0, 'loop transition must revalidate a score clip');
assert.ok(looping.state.calls.includes('/scores/playlist/validate'));

const activeTimeout = harness();
await activeTimeout.box.jumpToScore(cached, true);
const pausesBeforeTimeout = activeTimeout.state.pauses;
guard.watchScorePlaylist(guard.scorePlaylistReferences([activeTimeout.state.selected]), () => new Promise(() => {}),
  () => activeTimeout.box.invalidateScorePlayback(), { timeoutMs: 5, schedule: () => 1, cancel: () => {} });
await new Promise(resolve => setTimeout(resolve, 20));
assert.ok(activeTimeout.state.pauses > pausesBeforeTimeout);
assert.equal(activeTimeout.state.selected, null);

const navigated = harness();
const originalApi = navigated.box.api;
let completeRequest;
navigated.box.api = async (path, ...args) => {
  if (path === '/scores/playlist') await new Promise(resolve => { completeRequest = resolve; });
  return originalApi(path, ...args);
};
const pendingOpen = navigated.box.jumpToScore(cached, true);
navigated.box.selectVideo(navigated.box.videos[0]);
completeRequest();
await pendingOpen;
assert.equal(navigated.state.plays, 0, 'late score resolution must not resume playback after navigation');

await assert.rejects(guard.loadLatestScoreClip('p1', async path => {
  if (path === '/scores/playlist') return { evidence_ids: [clip.evidence_id], score_references: [{ evidence_id: clip.evidence_id, score_revision: 'old-version' }] };
  return [clip];
}), /score changed while loading/);
await assert.rejects(guard.loadLatestScoreClip('p1', () => new Promise(() => {}), 5), /timeout/);

const stalled = harness();
stalled.box.api = () => new Promise(() => {});
await stalled.box.jumpToScore(cached, true); // exercise the production 2500ms timeout policy
assert.equal(stalled.state.plays, 0);
assert.equal(stalled.state.range, false);
assert.match(stalled.state.notice, /停止复盘/);
console.log('PASS: direct fresh 14–17s, active invalidation, failures/timeouts, SHA, revision race, observation/manual isolation');
