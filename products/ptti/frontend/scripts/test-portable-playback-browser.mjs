import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import { createServer } from 'node:http';
import { access, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { createServer as createNetServer } from 'node:net';
import { createHash } from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import ts from '../node_modules/typescript/lib/typescript.js';

const chromeCandidates = [
  process.env.PTTI_PLAYBACK_CHROME,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
].filter(Boolean);
let chromePath;
for (const candidate of chromeCandidates) {
  try { await access(candidate); chromePath = candidate; break; } catch { /* Try the next installed browser path. */ }
}
if (!chromePath) throw new Error('Chrome or Edge executable was not found. Set PTTI_PLAYBACK_CHROME to its executable path.');

const tempRoot = await mkdtemp(path.join(os.tmpdir(), 'ptti-playback-browser-'));
const profilePath = path.join(tempRoot, 'browser-profile');
const mp4Path = path.join(tempRoot, 'synthetic-playback.mp4');
const brokenPath = path.join(tempRoot, 'broken.mp4');
const compatibilityCases = [
  { name: 'short-baseline-no-audio', path: path.join(tempRoot, 'short-baseline-no-audio.mp4'), seconds: 3, width: 160, height: 120, fps: 24, gop: 48, profile: 'baseline', audio: false },
  { name: 'medium-main-aac', path: path.join(tempRoot, 'medium-main-aac.mp4'), seconds: 6, width: 640, height: 360, fps: 30, gop: 90, profile: 'main', preset: 'veryfast', audio: true },
  { name: 'long-high-aac', path: path.join(tempRoot, 'long-high-aac.mp4'), seconds: 12, width: 960, height: 540, fps: 30, gop: 180, profile: 'high', preset: 'veryfast', audio: true },
  { name: 'short-high-60-no-audio', path: path.join(tempRoot, 'short-high-60-no-audio.mp4'), seconds: 2, width: 160, height: 120, fps: 60, gop: 30, profile: 'high', preset: 'veryfast', audio: false },
];

function generateMp4({ path: outputPath, seconds, width, height, fps, gop, profile, preset = 'ultrafast', audio }) {
  const args = [
    '-hide_banner', '-loglevel', 'error', '-y',
    '-f', 'lavfi', '-i', `testsrc2=size=${width}x${height}:rate=${fps}`,
  ];
  if (audio) args.push('-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100');
  args.push(
    '-t', String(seconds), '-c:v', 'libx264', '-preset', preset, '-crf', '32',
    '-pix_fmt', 'yuv420p', '-profile:v', profile, '-g', String(gop), '-keyint_min', String(gop),
    '-sc_threshold', '0',
  );
  if (audio) args.push('-c:a', 'aac', '-b:a', '64k');
  else args.push('-an');
  args.push('-movflags', '+faststart', outputPath);
  const result = spawnSync('ffmpeg', args, { encoding: 'utf8', windowsHide: true });
  if (result.status !== 0) throw new Error(`Could not make ${path.basename(outputPath)}: ${result.stderr || result.error}`);
}

try {
  generateMp4({ path: mp4Path, seconds: 4, width: 320, height: 240, fps: 30, gop: 60, profile: 'baseline', audio: true });
  for (const testCase of compatibilityCases) generateMp4(testCase);
} catch (error) {
  await rm(tempRoot, { recursive: true, force: true });
  throw error;
}
await writeFile(brokenPath, 'synthetic file that is not an MP4 stream');
const ffmpegVersion = spawnSync('ffmpeg', ['-version'], { encoding: 'utf8', windowsHide: true }).stdout.split(/\r?\n/, 1)[0];

async function probeFixture(filePath) {
  const result = spawnSync('ffprobe', [
    '-v', 'error', '-show_streams', '-show_format', '-of', 'json', filePath,
  ], { encoding: 'utf8', windowsHide: true });
  if (result.status !== 0) throw new Error(`Could not inspect ${path.basename(filePath)}: ${result.stderr || result.error}`);
  const media = JSON.parse(result.stdout);
  const video = media.streams.find((stream) => stream.codec_type === 'video');
  const audio = media.streams.find((stream) => stream.codec_type === 'audio');
  if (!video) throw new Error(`${path.basename(filePath)} has no video stream`);
  const [rateNumerator, rateDenominator] = video.avg_frame_rate.split('/').map(Number);
  const framesResult = spawnSync('ffprobe', [
    '-v', 'error', '-select_streams', 'v:0', '-show_frames',
    '-show_entries', 'frame=key_frame,best_effort_timestamp_time', '-of', 'json', filePath,
  ], { encoding: 'utf8', windowsHide: true });
  if (framesResult.status !== 0) throw new Error(`Could not inspect keyframes for ${path.basename(filePath)}`);
  const keyframes = JSON.parse(framesResult.stdout).frames
    .filter((frame) => frame.key_frame === 1)
    .map((frame) => Number(frame.best_effort_timestamp_time));
  const keyframeGaps = keyframes.slice(1).map((time, index) => time - keyframes[index]);
  return {
    name: path.basename(filePath),
    duration_seconds: Number(media.format.duration),
    bytes: Number(media.format.size),
    codec: video.codec_name,
    profile: video.profile,
    width: video.width,
    height: video.height,
    fps: rateNumerator / rateDenominator,
    audio_codec: audio?.codec_name ?? null,
    max_keyframe_gap_seconds: keyframeGaps.length ? Math.max(...keyframeGaps) : null,
    sha256: createHash('sha256').update(await readFile(filePath)).digest('hex'),
  };
}

let probedFixtures;
try {
  probedFixtures = [];
  for (const [filePath, expected] of [
    [mp4Path, { seconds: 4, width: 320, height: 240, fps: 30, gop_seconds: 2, profile: 'baseline', audio: 'aac' }],
    ...compatibilityCases.map((testCase) => [testCase.path, {
      seconds: testCase.seconds,
      width: testCase.width,
      height: testCase.height,
      fps: testCase.fps,
      gop_seconds: testCase.gop / testCase.fps,
      profile: testCase.profile,
      audio: testCase.audio ? 'aac' : null,
    }]),
  ]) {
    const inspected = await probeFixture(filePath);
    assert.equal(inspected.codec, 'h264', `${inspected.name} uses H.264`);
    assert.ok(inspected.profile.toLowerCase().includes(expected.profile), `${inspected.name} has requested H.264 profile`);
    assert.equal(inspected.width, expected.width);
    assert.equal(inspected.height, expected.height);
    assert.ok(Math.abs(inspected.duration_seconds - expected.seconds) < 0.12);
    assert.ok(Math.abs(inspected.fps - expected.fps) < 0.01);
    assert.equal(inspected.audio_codec, expected.audio, `${inspected.name} audio stream matches fixture`);
    assert.ok(Math.abs(inspected.max_keyframe_gap_seconds - expected.gop_seconds) < 0.05, `${inspected.name} GOP interval matches fixture`);
    probedFixtures.push(inspected);
  }
  console.log(`SYNTHETIC_FIXTURES ffmpeg=${ffmpegVersion} details=${JSON.stringify(probedFixtures)}`);
} catch (error) {
  await rm(tempRoot, { recursive: true, force: true });
  throw error;
}

const source = await readFile(new URL('../../playback-core/src/index.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText;
const html = `<!doctype html><html><head><meta charset="utf-8"><title>PTTI playback QA</title></head><body>
<input id="file" type="file" accept="video/mp4,.mp4"><video id="video" controls playsinline preload="auto"></video>
<script type="module">
import { createLocalVideoPlaybackController } from '/controller.js';
const video = document.querySelector('#video');
const originalCreate = URL.createObjectURL.bind(URL);
const originalRevoke = URL.revokeObjectURL.bind(URL);
window.__urls = { created: [], revoked: [] };
URL.createObjectURL = (file) => { const value = originalCreate(file); window.__urls.created.push(value); return value; };
URL.revokeObjectURL = (url) => { window.__urls.revoked.push(url); return originalRevoke(url); };
window.__controller = createLocalVideoPlaybackController(video);
window.__snapshot = window.__controller.getSnapshot();
window.__playlistOrder = [];
window.__controller.subscribe((snapshot) => {
  window.__snapshot = snapshot;
  const pointId = snapshot.playlist?.point_id;
  if (pointId && window.__playlistOrder.at(-1) !== pointId) window.__playlistOrder.push(pointId);
});
window.__fileResult = null;
document.querySelector('#file').addEventListener('change', (event) => {
  window.__fileResult = window.__controller.loadFile(event.currentTarget.files[0]);
});
window.__seekCount = 0;
video.addEventListener('seeked', () => { window.__seekCount += 1; });
</script></body></html>`;

let server;
let chrome;
let cdp;
const pageRequests = [];

function reservePort() {
  return new Promise((resolve, reject) => {
    const probe = createNetServer();
    probe.once('error', reject);
    probe.listen(0, '127.0.0.1', () => {
      const { port } = probe.address();
      probe.close((error) => error ? reject(error) : resolve(port));
    });
  });
}

async function waitUntil(check, description, timeoutMs = 8000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await check()) return;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error(`Timed out waiting for ${description}`);
}

function connectCdp(url) {
  const socket = new WebSocket(url);
  const pending = new Map();
  let nextId = 1;
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (!message.id) return;
    const request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message));
    else request.resolve(message.result);
  });
  const ready = new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true });
    socket.addEventListener('error', reject, { once: true });
  });
  return {
    socket,
    async ready() { await ready; },
    command(method, params = {}) {
      const id = nextId++;
      const result = new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
      socket.send(JSON.stringify({ id, method, params }));
      return result;
    },
    close() { socket.close(); },
  };
}

async function evaluate(expression) {
  const response = await cdp.command('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
    userGesture: true,
  });
  if (response.exceptionDetails) {
    throw new Error(response.exceptionDetails.exception?.description ?? response.exceptionDetails.text);
  }
  return response.result?.value;
}

async function setSelectedFile(filePath) {
  const tree = await cdp.command('DOM.getDocument', { depth: 2 });
  const queried = await cdp.command('DOM.querySelector', { nodeId: tree.root.nodeId, selector: '#file' });
  await cdp.command('DOM.setFileInputFiles', { files: [filePath], nodeId: queried.nodeId });
}

try {
  const port = await reservePort();
  server = createServer(async (request, response) => {
    const requestPath = new URL(request.url ?? '/', `http://127.0.0.1:${port}`).pathname;
    pageRequests.push({ method: request.method, path: requestPath });
    response.setHeader('Access-Control-Allow-Origin', '*');
    response.setHeader('Cache-Control', 'no-store');
    if (requestPath === '/') {
      response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      response.end(html);
    } else if (requestPath === '/controller.js') {
      response.writeHead(200, { 'Content-Type': 'text/javascript; charset=utf-8' });
      response.end(compiled);
    } else if (requestPath === '/synthetic-playback.mp4') {
      response.writeHead(200, { 'Content-Type': 'video/mp4' });
      response.end(await readFile(mp4Path));
    } else {
      response.writeHead(404);
      response.end('not found');
    }
  });
  server.listen(port, '127.0.0.1');

  const debugPort = await reservePort();
  chrome = spawn(chromePath, [
    '--headless=new', '--disable-gpu', '--disable-extensions', '--disable-background-networking',
    '--no-first-run', '--no-default-browser-check', '--disable-default-apps', '--mute-audio',
    '--autoplay-policy=no-user-gesture-required', `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${profilePath}`, 'about:blank',
  ], { stdio: 'ignore', windowsHide: true });

  const versionUrl = `http://127.0.0.1:${debugPort}/json/version`;
  await waitUntil(async () => {
    if (chrome.exitCode !== null) throw new Error(`Browser exited during startup (${chrome.exitCode})`);
    try { return (await fetch(versionUrl)).ok; } catch { return false; }
  }, 'isolated browser DevTools endpoint');
  const targets = await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json();
  const page = targets.find((target) => target.type === 'page');
  assert.ok(page?.webSocketDebuggerUrl, 'isolated browser page target exists');
  cdp = connectCdp(page.webSocketDebuggerUrl);
  await cdp.ready();
  await cdp.command('Page.enable');
  await cdp.command('Runtime.enable');
  await cdp.command('DOM.enable');
  await cdp.command('Page.navigate', { url: `http://127.0.0.1:${port}/` });
  await waitUntil(() => evaluate('Boolean(window.__controller)'), 'playback module load');

  await evaluate('window.__selectionStarted = performance.now()');
  await setSelectedFile(mp4Path);
  await waitUntil(() => evaluate("window.__snapshot.status === 'ready'"), 'real MP4 browser decode readiness');
  const identity = await evaluate('window.__snapshot.video_identity');
  const duration = await evaluate('window.__snapshot.duration_seconds');
  assert.ok(duration > 3.8 && duration < 4.2, `browser reports expected synthetic duration; got ${duration}`);
  const codecSupport = await evaluate("document.querySelector('#video').canPlayType('video/mp4; codecs=\"avc1.42E01E, mp4a.40.2\"')");
  assert.notEqual(codecSupport, '', 'browser reports support for H.264/AAC MP4');

  const firstFrame = await evaluate(`(async() => {
    const video=document.querySelector('#video');
    const frame=new Promise((resolve, reject) => {
      const timer=setTimeout(() => reject(new Error('first presented frame timed out')), 5000);
      video.requestVideoFrameCallback((now, metadata) => {
        clearTimeout(timer);
        resolve({ latency_ms: performance.now() - window.__selectionStarted, media_time: metadata.mediaTime });
      });
    });
    const result=await window.__controller.play();
    if (!result.ok) throw new Error(result.error.message);
    return await frame;
  })()`);
  await waitUntil(() => evaluate("document.querySelector('#video').currentTime > 0.25 && !document.querySelector('#video').paused"), 'decoded video playback');
  assert.equal((await evaluate('window.__controller.setPlaybackRate(0.5)')).value, 0.5);
  assert.equal(await evaluate("document.querySelector('#video').playbackRate"), 0.5);
  assert.equal((await evaluate('window.__controller.setPlaybackRate(1)')).value, 1);
  await evaluate('window.__controller.pause()');
  const pausedAt = await evaluate("document.querySelector('#video').currentTime");
  await new Promise((resolve) => setTimeout(resolve, 250));
  const stayedPausedAt = await evaluate("document.querySelector('#video').currentTime");
  assert.ok(Math.abs(stayedPausedAt - pausedAt) < 0.12, 'pause stops time progression');
  const seeked = await evaluate(`new Promise((resolve) => { const v=document.querySelector('#video'); v.addEventListener('seeked', () => resolve(v.currentTime), { once:true }); window.__controller.seek(1.25); })`);
  assert.ok(Math.abs(seeked - 1.25) < 0.12, `seek lands near target; got ${seeked}`);
  console.log(`PASS real browser local MP4: ${path.basename(mp4Path)}, ${duration.toFixed(2)}s, first-frame=${firstFrame.latency_ms.toFixed(1)}ms, identity=${identity}, play/pause/seek, rates 0.5x/1x`);

  const compatibilityResults = [];
  for (const testCase of compatibilityCases) {
    const previousUrl = await evaluate('window.__urls.created.at(-1)');
    await evaluate('window.__selectionStarted = performance.now()');
    await setSelectedFile(testCase.path);
    await waitUntil(() => evaluate("window.__snapshot.status === 'ready'"), `${testCase.name} ready`, 10000);
    const mediaInfo = await evaluate('({ duration: window.__snapshot.duration_seconds, width: document.querySelector("#video").videoWidth, height: document.querySelector("#video").videoHeight })');
    assert.ok(Math.abs(mediaInfo.duration - testCase.seconds) < 0.12, `${testCase.name} duration matches fixture`);
    assert.equal(mediaInfo.width, testCase.width, `${testCase.name} width matches fixture`);
    assert.equal(mediaInfo.height, testCase.height, `${testCase.name} height matches fixture`);
    assert.equal(await evaluate(`window.__urls.revoked.includes(${JSON.stringify(previousUrl)})`), true, `${testCase.name} replacement released the prior object URL`);

    const first = await evaluate(`(async() => {
      const video=document.querySelector('#video');
      const frame=new Promise((resolve, reject) => {
        const timer=setTimeout(() => reject(new Error('first presented frame timed out')), 5000);
        video.requestVideoFrameCallback((now, metadata) => {
          clearTimeout(timer);
          resolve({ latency_ms: performance.now() - window.__selectionStarted, media_time: metadata.mediaTime });
        });
      });
      const result=await window.__controller.play();
      if (!result.ok) throw new Error(result.error.message);
      return await frame;
    })()`);
    await evaluate('window.__controller.pause()');
    const target = Number((mediaInfo.duration * 0.67).toFixed(3));
    const tolerance = Math.max(0.12, 2 / testCase.fps);
    const seek = await evaluate(`(() => {
      const video=document.querySelector('#video');
      const target=${target};
      const tolerance=${tolerance};
      return new Promise((resolve, reject) => {
        const started=performance.now();
        const timer=setTimeout(() => reject(new Error('seeked visible frame timed out')), 5000);
        const checkFrame=(now, metadata) => {
          if (Math.abs(metadata.mediaTime - target) <= tolerance) {
            clearTimeout(timer);
            resolve({ latency_ms: performance.now() - started, media_time: metadata.mediaTime });
          } else video.requestVideoFrameCallback(checkFrame);
        };
        video.requestVideoFrameCallback(checkFrame);
        const result=window.__controller.seek(target);
        if (!result.ok) { clearTimeout(timer); reject(new Error(result.error.message)); }
      });
    })()`);
    assert.ok(Math.abs(seek.media_time - target) <= tolerance, `${testCase.name} presents a frame near the seek target`);
    const previousUrlRevoked = await evaluate('window.__urls.revoked.length');
    const urlCount = await evaluate('window.__urls.created.length');
    const fixtureBytes = (await readFile(testCase.path)).length;
    const fixtureHash = createHash('sha256').update(await readFile(testCase.path)).digest('hex');
    compatibilityResults.push({
      name: testCase.name,
      bytes: fixtureBytes,
      sha256: fixtureHash,
      audio: testCase.audio ? 'AAC' : 'none',
      profile: testCase.profile,
      fps: testCase.fps,
      gop_frames: testCase.gop,
      first_frame_ms: Number(first.latency_ms.toFixed(1)),
      seek_visible_frame_ms: Number(seek.latency_ms.toFixed(1)),
      seek_frame_time: Number(seek.media_time.toFixed(3)),
      revoked_urls: previousUrlRevoked,
      created_urls: urlCount,
      js_heap_used_bytes: await evaluate('performance.memory?.usedJSHeapSize ?? null'),
    });
  }
  console.log(`PASS Chrome compatibility matrix: ${JSON.stringify(compatibilityResults)}`);

  const createdBeforeRapidSwitch = await evaluate('window.__urls.created.length');
  await setSelectedFile(compatibilityCases[0].path);
  await setSelectedFile(compatibilityCases[1].path);
  await setSelectedFile(mp4Path);
  await waitUntil(() => evaluate("window.__snapshot.status === 'ready' && window.__snapshot.file?.name === 'synthetic-playback.mp4'"),
    'rapid multi-video replacement settles on the last selection', 10000);
  const rapidSwitchState = await evaluate(`({
    created: window.__urls.created.slice(${createdBeforeRapidSwitch}),
    revoked: window.__urls.revoked,
    currentSrc: document.querySelector('#video').currentSrc,
    snapshotName: window.__snapshot.file.name,
    duration: window.__snapshot.duration_seconds,
    playlist: window.__snapshot.playlist
  })`);
  assert.equal(rapidSwitchState.created.length, 3, 'each rapid selection created one local object URL');
  assert.ok(rapidSwitchState.created.slice(0, -1).every((url) => rapidSwitchState.revoked.includes(url)), 'superseded rapid selections release their object URLs');
  assert.equal(rapidSwitchState.currentSrc, rapidSwitchState.created.at(-1), 'the active source belongs to the final selection');
  assert.equal(rapidSwitchState.snapshotName, 'synthetic-playback.mp4');
  assert.equal(rapidSwitchState.duration, 4);
  assert.equal(rapidSwitchState.playlist, null, 'switching media clears any prior playlist state');
  console.log('PASS real Chrome rapid switching: latest selection wins and superseded URLs are revoked');

  const seekCancelStart = await evaluate(`(() => {
    const id=window.__snapshot.video_identity;
    const result=window.__controller.playRallyPlaylist([
      { point_id:'seek-p1', video_identity:id, start_time:0.4, end_time:0.7, binding_status:'BOUND' },
      { point_id:'seek-p2', video_identity:id, start_time:1.2, end_time:1.5, binding_status:'BOUND' },
      { point_id:'seek-p3', video_identity:id, start_time:2.3, end_time:2.6, binding_status:'BOUND' }
    ]);
    window.__playlistTask=result.ok?result.value:null;
    return result.ok;
  })()`);
  assert.equal(seekCancelStart, true);
  await waitUntil(() => evaluate("window.__snapshot.playlist?.point_id === 'seek-p1' && !document.querySelector('#video').paused"), 'real Chrome seek-cancel first rally');
  assert.equal((await evaluate('window.__controller.seek(2.35)')).ok, true);
  const seekCancelled = await evaluate('window.__playlistTask.done');
  assert.deepEqual(seekCancelled, { status: 'cancelled', reason: 'manual-seek', completed_rallies: 0 });
  await new Promise((resolve) => setTimeout(resolve, 350));
  const seekCancelState = await evaluate('({ time: document.querySelector("#video").currentTime, status: window.__snapshot.playlist.status, point_id: window.__snapshot.playlist.point_id })');
  assert.ok(Math.abs(seekCancelState.time - 2.35) < 0.12, 'real media remains at the manually selected later point');
  assert.equal(seekCancelState.status, 'cancelled');
  console.log('PASS real Chrome direct point switch: seek cancels old playlist without jumping back');
  await evaluate('window.__playlistOrder = []');

  const playlist = await evaluate(`(() => {
    const id=window.__snapshot.video_identity;
    const result=window.__controller.playRallyPlaylist([
      { point_id:'qa-p1', video_identity:id, start_time:0.4, end_time:0.8, binding_status:'BOUND' },
      { point_id:'qa-p2', video_identity:id, start_time:1.2, end_time:1.6, binding_status:'BOUND' },
      { point_id:'qa-p3', video_identity:id, start_time:2.0, end_time:2.4, binding_status:'BOUND' }
    ]);
    window.__playlistTask=result.ok?result.value:null;
    return result.ok;
  })()`);
  assert.equal(playlist, true);
  await waitUntil(() => evaluate("window.__snapshot.current_time_seconds >= 0.55 && window.__snapshot.playlist?.current_index === 0"), 'first bound rally playback');
  await evaluate('window.__playlistTask.pause()');
  const rallyPausedAt = await evaluate("document.querySelector('#video').currentTime");
  await new Promise((resolve) => setTimeout(resolve, 250));
  const rallyPauseStable = await evaluate("Math.abs(document.querySelector('#video').currentTime - " + rallyPausedAt + ") < 0.12");
  assert.equal(rallyPauseStable, true);
  assert.equal((await evaluate('window.__playlistTask.resume()')).ok, true);
  const playlistDone = await evaluate(`Promise.race([
    window.__playlistTask.done,
    new Promise((_, reject) => setTimeout(() => reject(new Error('playlist timeout')), 9000))
  ])`);
  assert.deepEqual(playlistDone, { status: 'completed', completed_rallies: 3 });
  assert.equal(await evaluate("window.__snapshot.playlist.status"), 'completed');
  assert.deepEqual(await evaluate('window.__playlistOrder.slice(0, 3)'), ['qa-p1', 'qa-p2', 'qa-p3']);
  console.log('PASS real browser rally playlist: three bound points played in order with pause/resume');

  const repeatStart = await evaluate(`(() => {
    const id=window.__snapshot.video_identity;
    window.__seekCount=0;
    const result=window.__controller.playRallyPlaylist([
      { point_id:'qa-loop', video_identity:id, start_time:0.3, end_time:0.7, binding_status:'BOUND' }
    ], { repeat_single:true });
    window.__playlistTask=result.ok?result.value:null;
    return result.ok;
  })()`);
  assert.equal(repeatStart, true);
  await waitUntil(() => evaluate('window.__seekCount >= 2'), 'single rally loop seek');
  const loopPosition = await evaluate("document.querySelector('#video').currentTime");
  assert.ok(Math.abs(loopPosition - 0.3) < 0.15, `loop returned to rally start; got ${loopPosition}`);
  const oldIdentity = await evaluate('window.__snapshot.video_identity');
  await setSelectedFile(brokenPath);
  await waitUntil(() => evaluate("window.__snapshot.status === 'error'"), 'clear unsupported stream error');
  const replacement = await evaluate('window.__fileResult');
  assert.equal(replacement.ok, true);
  assert.ok(['decode-error', 'unsupported-media'].includes(await evaluate('window.__snapshot.error.code')),
    'a malformed MP4 can fail browser format recognition or decoding; neither proves the codec alone is at fault');
  assert.notEqual(await evaluate('window.__snapshot.video_identity'), oldIdentity);
  const replacedTask = await evaluate("window.__playlistTask.done");
  assert.equal(replacedTask.status, 'cancelled');
  assert.equal(replacedTask.reason, 'video-replaced');
  assert.ok((await evaluate('window.__snapshot.error.message')).includes('浏览器无法'));
  await setSelectedFile(mp4Path);
  await waitUntil(() => evaluate("window.__snapshot.status === 'ready' && window.__snapshot.file?.name === 'synthetic-playback.mp4'"), 'valid browser media recovery after decode failure');
  assert.equal(await evaluate('window.__snapshot.error'), null);
  console.log('PASS real browser recovery: loop cancellation, clear decode error, and valid selection after failure');

  await evaluate('window.__controller.release()');
  const urlCounts = await evaluate('({ created: window.__urls.created.length, revoked: window.__urls.revoked.length })');
  assert.equal(urlCounts.created, urlCounts.revoked);
  console.log(`PASS real browser release: all local object URLs revoked (${urlCounts.revoked}/${urlCounts.created})`);
  assert.equal(pageRequests.every((request) => request.method === 'GET'), true, 'the browser page made no upload request');
  assert.equal(pageRequests.some((request) => request.path.includes('synthetic-playback.mp4') || request.path.includes('broken.mp4')), false,
    'video bytes stayed in the browser File/object-URL path');
  console.log('PASS local privacy boundary: selected MP4 bytes were not sent to the local test server');
  console.log(`BROWSER=${chromePath}`);
  console.log(`FIXTURE_SHA256=${createHash('sha256').update(await readFile(mp4Path)).digest('hex')}`);
} finally {
  if (cdp) {
    try { await cdp.command('Browser.close'); } catch { /* Browser may have already exited. */ }
    cdp.close();
  }
  if (chrome && chrome.exitCode === null) {
    await Promise.race([once(chrome, 'exit'), new Promise((resolve) => setTimeout(resolve, 6000))]);
    if (chrome.exitCode === null) chrome.kill();
  }
  if (server) await new Promise((resolve) => server.close(resolve));
  await rm(tempRoot, { recursive: true, force: true });
}
