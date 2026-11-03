import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { readFileSync } from 'node:fs';
import ts from '../node_modules/typescript/lib/typescript.js';

const dir = mkdtempSync(join(tmpdir(), 'ptti-moment-adapter-'));
try {
  const compile = spawnSync(process.execPath, ['node_modules/typescript/bin/tsc', 'src/vendor/playback/momentPlaybackAdapter.ts', '--target', 'ES2022', '--module', 'ES2022', '--strict', '--skipLibCheck', '--outDir', dir], { encoding: 'utf8' });
  assert.equal(compile.status, 0, compile.stdout + compile.stderr);
  writeFileSync(join(dir, 'package.json'), '{"type":"module"}');
  const { MomentPlaybackAdapter } = await import(pathToFileURL(join(dir, 'momentPlaybackAdapter.js')));
  class Media extends EventTarget { currentTime = 0; seeking = false; readyState = 1; error = null; paused = true; }
  const media = new Media(); let identity = 'sha256:verified'; let status = 'ready';
  const core = { getSnapshot: () => ({ status, video_identity: identity, duration_seconds: 30 }),
    seek: t => { media.seeking = media.currentTime !== t; media.currentTime = t; return { ok: true }; },
    pause: () => { media.paused = true; }, play: async () => { media.paused = false; return { ok: true }; } };
  const adapter = new MomentPlaybackAdapter(core, media); const states = [];
  adapter.subscribeState(s => states.push(s.status));
  assert.equal(adapter.load('other').error, 'identity-mismatch');
  status = 'error'; assert.equal(adapter.load(identity).error, 'not-ready'); status = 'ready';
  assert.equal(adapter.load(identity).ok, true);
  const exact = adapter.seekExact(12.34); assert.equal(media.currentTime, 12.34);
  media.seeking = false; media.dispatchEvent(new Event('seeked')); assert.deepEqual(await exact, { ok: true, value: 12.34 });
  const pre = adapter.seekWithPreRoll(12.34, 1.5); assert.equal(media.currentTime, 10.84);
  media.seeking = false; media.dispatchEvent(new Event('seeked')); assert.equal((await pre).ok, true);
  assert.equal((await adapter.seekExact(10.84)).ok, true, 'already at target');
  const first = adapter.seekExact(3); const second = adapter.seekExact(4); assert.equal((await first).error, 'cancelled');
  let finished = false; second.then(() => { finished = true; });
  media.currentTime = 4; media.dispatchEvent(new Event('seeked')); await Promise.resolve(); assert.equal(finished, false, 'stale event while still seeking cannot complete newer request');
  media.seeking = false; media.dispatchEvent(new Event('seeked')); assert.equal((await second).value, 4);
  const cancelled = adapter.seekExact(5); adapter.cancelPendingSeek(); assert.equal((await cancelled).error, 'cancelled'); media.dispatchEvent(new Event('seeked'));
  let timer, delay; const realSet = globalThis.setTimeout, realClear = globalThis.clearTimeout;
  try { globalThis.setTimeout = (fn, ms) => { timer = fn; delay = ms; return 1; }; globalThis.clearTimeout = () => {};
    const timeout = adapter.seekExact(6); assert.equal(delay, 12000); timer(); assert.equal((await timeout).error, 'seek-timeout');
  } finally { globalThis.setTimeout = realSet; globalThis.clearTimeout = realClear; }
  const error = adapter.seekExact(7); media.error = {}; media.dispatchEvent(new Event('error')); assert.equal((await error).error, 'media-error'); media.error = null;
  identity = 'replacement'; assert.equal((await adapter.seekExact(8)).error, 'identity-mismatch'); identity = 'sha256:verified';
  assert.equal((await adapter.play()).ok, true); assert.equal(adapter.pause().ok, true);
  const returned = adapter.seekExact(9); media.seeking = false; media.dispatchEvent(new Event('seeked')); assert.equal((await returned).ok, true); assert.equal(media.paused, true, 'Arena return remains paused');
  assert(states.includes('seeked')); assert.equal(adapter.getCurrentTime().value, 9);
  assert.equal((await adapter.seekWithPreRoll(31, 5)).error, 'out-of-range');
  assert.equal((await adapter.seekExact(NaN)).error, 'invalid-time');

  // Exercise the adapter against the real Core, with only the browser element faked.
  const coreSource = readFileSync('src/vendor/playback/index.ts', 'utf8');
  const coreJs = ts.transpileModule(coreSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
  const { createLocalVideoPlaybackController } = await import(`data:text/javascript;base64,${Buffer.from(coreJs).toString('base64')}`);
  class CoreMedia extends EventTarget {
    src = ''; currentSrc = ''; duration = 30; readyState = 0; paused = true; seeking = false; playbackRate = 1; error = null; _time = 0;
    get currentTime() { return this._time; }
    set currentTime(t) { this._time = t; this.seeking = true; queueMicrotask(() => { this.seeking = false; this.dispatchEvent(new Event('seeked')); }); }
    load() { if (!this.src) return; this.currentSrc = this.src; this.readyState = 1; this.dispatchEvent(new Event('loadedmetadata')); this.readyState = 3; this.dispatchEvent(new Event('canplay')); }
    pause() { this.paused = true; this.dispatchEvent(new Event('pause')); }
    async play() { this.paused = false; this.dispatchEvent(new Event('play')); }
    removeAttribute() { this.src = ''; this.currentSrc = ''; this.readyState = 0; }
  }
  const video = new CoreMedia();
  const realCore = createLocalVideoPlaybackController(video, { createObjectURL: () => 'blob:test', revokeObjectURL: () => {}, createVideoIdentity: () => 'local-session:test' });
  assert.equal(realCore.loadFile({ name: 'synthetic.mp4', type: 'video/mp4', size: 1, lastModified: 0 }).ok, true);
  const integrated = new MomentPlaybackAdapter(realCore, video); assert.equal(integrated.load('local-session:test').ok, true);
  assert.equal((await integrated.seekExact(12.34)).value, 12.34);
  assert.equal((await integrated.seekWithPreRoll(12.34, 1.5)).value, 10.84);
  integrated.pause(); assert.equal(video.paused, true); realCore.release();
  console.log('Moment Playback Adapter: targeted seek, cancellation, 12s timeout, identity and paused return PASS');
} finally { rmSync(dir, { recursive: true, force: true }); }
