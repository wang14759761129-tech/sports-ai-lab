#!/usr/bin/env node
// Bounded, local-only Edge/CDP playback regression for the isolated DEV app.
// No external sources, model jobs, uploads, or persistent browser profile are used.
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { existsSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { mkdtemp, rm } from 'node:fs/promises';

const baseUrl = process.env.PTTI_QA_BASE_URL || 'http://127.0.0.1:53087';
const minAvailableBytes = 2 * 1024 ** 3;
const minStartupBytes = 2.75 * 1024 ** 3;
const timeoutMs = 30_000;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function record(name, status, details = {}) {
  results.push({ name, status, ...details });
}

function edgeExecutable() {
  const candidates = [
    process.env.PTTI_EDGE_PATH,
    path.join(process.env['PROGRAMFILES(X86)'] || 'C:\\Program Files (x86)', 'Microsoft/Edge/Application/msedge.exe'),
    path.join(process.env.PROGRAMFILES || 'C:\\Program Files', 'Microsoft/Edge/Application/msedge.exe'),
    path.join(process.env.LOCALAPPDATA || '', 'Microsoft/Edge/Application/msedge.exe'),
  ].filter(Boolean);
  return candidates.find((candidate) => existsSync(candidate));
}

async function freePort() {
  const server = createServer();
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const { port } = server.address();
  await new Promise((resolve) => server.close(resolve));
  return port;
}

async function waitFor(check, message, timeout = timeoutMs) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (os.freemem() < minAvailableBytes) {
      throw new Error('RESOURCE_GUARD: available physical RAM fell below 2 GiB');
    }
    const value = await check();
    if (value) return value;
    await sleep(250);
  }
  throw new Error(`Timed out waiting for ${message}`);
}

function connectCdp(url) {
  const socket = new WebSocket(url);
  let nextId = 0;
  const pending = new Map();
  const subscribers = new Map();
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result || {});
      return;
    }
    for (const handler of subscribers.get(message.method) || []) handler(message.params || {});
  });
  return new Promise((resolve, reject) => {
    socket.addEventListener('open', () => resolve({
      socket,
      on(method, handler) {
        const handlers = subscribers.get(method) || [];
        handlers.push(handler);
        subscribers.set(method, handlers);
      },
      send(method, params = {}) {
        const id = ++nextId;
        socket.send(JSON.stringify({ id, method, params }));
        return new Promise((accept, fail) => pending.set(id, { resolve: accept, reject: fail }));
      },
      async evaluate(expression, { userGesture = false } = {}) {
        const result = await this.send('Runtime.evaluate', {
          expression,
          awaitPromise: true,
          returnByValue: true,
          userGesture,
        });
        if (result.exceptionDetails) {
          throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
        }
        return result.result?.value;
      },
      close() { socket.close(); },
    }));
    socket.addEventListener('error', reject, { once: true });
  });
}

async function main() {
  const healthResponse = await fetch(`${baseUrl}/api/health`, { signal: AbortSignal.timeout(5000) });
  assert(healthResponse.ok, `Local PTTI health endpoint returned ${healthResponse.status}`);
  const health = await healthResponse.json();
  const videosResponse = await fetch(`${baseUrl}/api/video-evidence/videos`, { signal: AbortSignal.timeout(10000) });
  assert(videosResponse.ok, `Local DEV video list returned ${videosResponse.status}`);
  const videos = await videosResponse.json();
  const source = videos.find((row) => row.title?.includes('game_1')
    && row.rights_status === 'RESEARCH_NONCOMMERCIAL'
    && row.availability_status === 'AVAILABLE'
    && row.hash_status === 'VERIFIED');
  assert(source, 'No available, SHA-verified, research-authorized DEV game_1 source is registered');
  const edge = edgeExecutable();
  assert(edge, 'Microsoft Edge executable was not found; no browser was installed');
  assert(os.freemem() >= minStartupBytes, 'RESOURCE_GUARD: need at least 2.75 GiB available RAM before starting isolated Edge');

  const port = await freePort();
  const profile = await mkdtemp(path.join(os.tmpdir(), 'ptti-r51-edge-'));
  const browser = spawn(edge, [
    '--headless=new',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-background-networking',
    '--remote-debugging-address=127.0.0.1',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    baseUrl,
  ], { stdio: 'ignore', windowsHide: true });
  let cdp;
  try {
    const targets = await waitFor(async () => {
      try {
        const response = await fetch(`http://127.0.0.1:${port}/json/list`, { signal: AbortSignal.timeout(800) });
        const rows = await response.json();
        return rows.find((row) => row.type === 'page' && row.webSocketDebuggerUrl);
      } catch { return null; }
    }, 'headless Edge devtools target');
    cdp = await connectCdp(targets.webSocketDebuggerUrl);
    await cdp.send('Runtime.enable');
    await cdp.send('Page.enable');
    await cdp.send('Network.enable');
    const mediaResponses = [];
    cdp.on('Network.responseReceived', (event) => {
      if (event.response.url.includes('/api/video-evidence/videos/') && event.response.url.endsWith('/media')) {
        mediaResponses.push({ status: event.response.status, contentRange: event.response.headers['content-range'] || null });
      }
    });
    await waitFor(async () => cdp.evaluate("document.readyState === 'complete' && !!document.querySelector('.studio-topbar')"), 'Cinema homepage');
    await waitFor(async () => cdp.evaluate(`document.title.includes(${JSON.stringify(health.product_name)})`), 'PTTI startup hydration');
    record('home_loaded', 'PASS', { product: health.product_name, build_commit: health.build_commit });

    const clickButton = async (label, selector = 'button', userGesture = false) => cdp.evaluate(`(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})].find(x=>x.textContent.trim()===${JSON.stringify(label)});if(!e)return false;e.click();return true})()`, { userGesture });
    const selectVideo = async () => cdp.evaluate(`(()=>{const e=document.querySelector('.vision-player select');if(!e)return false;const s=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set;s.call(e,${JSON.stringify(source.video_id)});e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return e.value})()`);
    const readVideo = () => cdp.evaluate("(()=>{const v=document.querySelector('video');return v?{readyState:v.readyState,networkState:v.networkState,currentTime:v.currentTime,duration:v.duration,paused:v.paused,width:v.videoWidth,height:v.videoHeight,rate:v.playbackRate,src:v.currentSrc,srcAttr:v.getAttribute('src'),error:v.error?{code:v.error.code,message:v.error.message}:null}:null})()");
    const waitVideo = async (selector, label) => waitFor(async () => {
      const status = await cdp.evaluate(`(()=>{const v=document.querySelector(${JSON.stringify(selector)});return v?{readyState:v.readyState,error:v.error?{code:v.error.code,message:v.error.message}:null}:null})()`);
      if (status?.error) throw new Error(`${label} media error ${JSON.stringify(status.error)}`);
      return status && status.readyState >= 2 ? status : null;
    }, `${label} canplay`);

    assert(await clickButton('Vision', '.cinema-nav button'), 'Top navigation has no Vision entry');
    const activeVision = await waitFor(async () => cdp.evaluate("[...document.querySelectorAll('.cinema-nav button')].some(x=>x.textContent.trim()==='Vision'&&x.getAttribute('aria-current')==='page')"), 'Vision navigation activation', 3000).catch(() => false);
    if (!activeVision) {
      const navState = await cdp.evaluate("({active:[...document.querySelectorAll('.cinema-nav button[aria-current=page]')].map(x=>x.textContent.trim()),buttons:[...document.querySelectorAll('.cinema-nav button')].map(x=>x.textContent.trim()),body:document.body.innerText.slice(0,500)})");
      throw new Error(`Vision navigation did not activate: ${JSON.stringify(navState)}`);
    }
    await waitFor(async () => cdp.evaluate("!!document.querySelector('.vision-player')"), 'Vision player root');
    const visionPickerDiagnostic = await cdp.evaluate("({selectCount:document.querySelectorAll('.vision-player select').length,body:document.body.innerText.slice(0,900),route:document.querySelector('.cinema-nav [aria-current=page]')?.textContent||null})");
    assert(visionPickerDiagnostic.selectCount > 0, `Vision player has no source picker: ${JSON.stringify(visionPickerDiagnostic)}`);
    await waitFor(async () => cdp.evaluate(`Array.from(document.querySelector('.vision-player select')?.options||[]).some(option=>option.value===${JSON.stringify(source.video_id)})`), 'authorized game_1 option');
    const selected = await selectVideo();
    assert(selected === source.video_id, 'Vision picker did not select the authorized game_1 source');
    await waitVideo('.vision-player video', 'Vision Source Video');
    record('vision_metadata_canplay', 'PASS', { video_id: source.video_id, sha256: source.source_sha256, media_responses: mediaResponses.slice() });

    await cdp.evaluate("(async()=>{const v=document.querySelector('.vision-player video');await v.play();return true})()", { userGesture: true });
    const visionAdvance = await waitFor(async () => {
      const state = await readVideo();
      return state && state.currentTime >= 0.35 ? state : null;
    }, 'Vision currentTime to advance', 12_000);
    await cdp.evaluate("document.querySelector('.vision-player video').pause()");
    const visionPausedAt = (await readVideo()).currentTime;
    await sleep(700);
    const visionPausedAfter = (await readVideo()).currentTime;
    assert(Math.abs(visionPausedAfter - visionPausedAt) < 0.05, 'Vision currentTime continued after pause');
    record('vision_play_pause', 'PASS', { advanced_to_seconds: visionAdvance.currentTime, paused_delta_seconds: Math.abs(visionPausedAfter - visionPausedAt) });

    const seekResult = await cdp.evaluate("(async()=>{const v=document.querySelector('.vision-player video');const done=new Promise(resolve=>{v.addEventListener('seeked',()=>resolve(v.currentTime),{once:true});setTimeout(()=>resolve(v.currentTime),7000)});v.currentTime=2.5;return await done})()");
    const visionSeekErrorMs = Math.abs(seekResult - 2.5) * 1000;
    assert(visionSeekErrorMs <= 150, `Vision seek error ${visionSeekErrorMs.toFixed(1)} ms exceeds 150 ms`);
    for (const rate of [0.25, 0.5, 1]) {
      const button = `${rate}×`;
      assert(await clickButton(button, '.vision-player button'), `Vision ${button} control is missing`);
      const actualRate = await cdp.evaluate("document.querySelector('.vision-player video').playbackRate");
      assert(actualRate === rate, `Vision requested ${rate}x but media element reports ${actualRate}x`);
    }
    let visionFullscreen = 'NOT_SUPPORTED_IN_HEADLESS_EDGE';
    if (await clickButton('全屏', '.vision-player button', true)) {
      const entered = await waitFor(async () => cdp.evaluate('Boolean(document.fullscreenElement)'), 'Vision fullscreen', 3000).catch(() => false);
      if (entered) {
        visionFullscreen = 'PASS';
        await clickButton('全屏', '.vision-player button', true);
        await waitFor(async () => cdp.evaluate('!document.fullscreenElement'), 'Vision fullscreen exit', 3000);
      }
    }
    const analysisDisabled = await cdp.evaluate("[...document.querySelectorAll('.vision-player button')].find(x=>x.textContent.includes('Analysis View'))?.disabled === true");
    assert(analysisDisabled, 'Vision Analysis View must remain unavailable without source-bound verified results');
    record('vision_seek_rates_fullscreen_and_no_fake_analysis', visionFullscreen === 'PASS' ? 'PASS' : 'NOT_TESTED', { target_seconds: 2.5, actual_seconds: seekResult, seek_error_ms: visionSeekErrorMs, rates: [0.25, 0.5, 1], fullscreen: visionFullscreen, analysis_view: 'CORRECTLY_DISABLED_NO_VERIFIED_RESULT' });

    await cdp.evaluate("window.__pttiVisionVideoForCleanup = document.querySelector('.vision-player video')");
    assert(await clickButton('返回 Cinema', '.vision-player button'), 'Vision return-to-Cinema control is missing');
    await waitFor(async () => cdp.evaluate("!!document.querySelector('.feed-grid') && !document.querySelector('.vision-player')"), 'return to Cinema feed');
    const cleanup = await cdp.evaluate("(()=>{const v=window.__pttiVisionVideoForCleanup;return v?{paused:v.paused,src_attribute:v.getAttribute('src'),current_src:v.currentSrc,network_state:v.networkState}:null})()");
    record('vision_unmount_cleanup', cleanup?.paused && cleanup.src_attribute === null && cleanup.network_state === 0 ? 'PASS' : 'FAIL', cleanup || {});

    assert(await clickButton('Vision', '.cinema-nav button'), 'Could not re-enter Vision after return to Cinema');
    await waitFor(async () => cdp.evaluate("!!document.querySelector('.vision-player')"), 'Vision re-entry player');
    assert(await cdp.evaluate("document.querySelectorAll('.vision-player select').length>0"), 'Vision re-entry player has no source picker');
    await waitFor(async () => cdp.evaluate(`Array.from(document.querySelector('.vision-player select')?.options||[]).some(option=>option.value===${JSON.stringify(source.video_id)})`), 'authorized game_1 re-entry option');
    assert(await selectVideo() === source.video_id, 'Vision could not re-select the authorized source after navigation');
    await waitVideo('.vision-player video', 'Vision re-entry Source Video');
    const visionReentry = await readVideo();
    assert(visionReentry && visionReentry.readyState >= 2, 'Vision re-entry did not create a usable media element');
    record('vision_reentry', 'PASS', { ready_state: visionReentry.readyState, current_time_seconds: visionReentry.currentTime, current_source_matches: visionReentry.src.includes(source.video_id) });
    assert(await clickButton('返回 Cinema', '.vision-player button'), 'Could not return from Vision re-entry');
    await waitFor(async () => cdp.evaluate("!!document.querySelector('.feed-grid') && !document.querySelector('.vision-player')"), 'Cinema after Vision re-entry');

    const feedCardClicked = await cdp.evaluate(`(()=>{const e=[...document.querySelectorAll('.feed-watch')].find(x=>x.textContent.includes(${JSON.stringify(source.title)}));if(!e)return false;e.click();return true})()`);
    assert(feedCardClicked, 'Cinema feed does not render the registered authorized local game_1 card');
    await waitVideo('.vep-video', 'Cinema player');
    record('cinema_metadata_canplay', 'PASS', { media_responses: mediaResponses.slice() });
    await cdp.evaluate("(async()=>{const v=document.querySelector('.vep-video');await v.play();return true})()", { userGesture: true });
    const cinemaAdvance = await waitFor(async () => {
      const state = await readVideo();
      return state && state.currentTime >= 0.35 ? state : null;
    }, 'Cinema currentTime to advance', 12_000);
    await cdp.evaluate("document.querySelector('.vep-video').pause()");
    const cinemaPausedAt = (await readVideo()).currentTime;
    await sleep(700);
    const cinemaPausedAfter = (await readVideo()).currentTime;
    assert(Math.abs(cinemaPausedAfter - cinemaPausedAt) < 0.05, 'Cinema currentTime continued after pause');
    const cinemaSeek = await cdp.evaluate("(async()=>{const v=document.querySelector('.vep-video');const done=new Promise(resolve=>{v.addEventListener('seeked',()=>resolve(v.currentTime),{once:true});setTimeout(()=>resolve(v.currentTime),7000)});v.currentTime=5.25;return await done})()");
    const cinemaSeekErrorMs = Math.abs(cinemaSeek - 5.25) * 1000;
    assert(cinemaSeekErrorMs <= 150, `Cinema seek error ${cinemaSeekErrorMs.toFixed(1)} ms exceeds 150 ms`);
    const rateSelect = await cdp.evaluate("(()=>{const e=document.querySelector('select[aria-label=\"播放倍速\"]');if(!e)return false;const s=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set;s.call(e,'0.5');e.dispatchEvent(new Event('change',{bubbles:true}));return document.querySelector('.vep-video').playbackRate})()");
    assert(rateSelect === 0.5, `Cinema 0.5x control reports ${rateSelect}`);
    let cinemaFullscreen = 'NOT_SUPPORTED_IN_HEADLESS_EDGE';
    if (await clickButton('全屏 / 退出全屏', '.vep-watch button', true)) {
      const entered = await waitFor(async () => cdp.evaluate('Boolean(document.fullscreenElement)'), 'Cinema fullscreen', 3000).catch(() => false);
      if (entered) {
        cinemaFullscreen = 'PASS';
        await clickButton('全屏 / 退出全屏', '.vep-watch button', true);
        await waitFor(async () => cdp.evaluate('!document.fullscreenElement'), 'Cinema fullscreen exit', 3000);
      }
    }
    record('cinema_play_pause_seek_rate_fullscreen', cinemaFullscreen === 'PASS' ? 'PASS' : 'NOT_TESTED', { advanced_to_seconds: cinemaAdvance.currentTime, paused_delta_seconds: Math.abs(cinemaPausedAfter - cinemaPausedAt), seek_target_seconds: 5.25, seek_actual_seconds: cinemaSeek, seek_error_ms: cinemaSeekErrorMs, playback_rate: rateSelect, fullscreen: cinemaFullscreen });
    await cdp.evaluate("window.__pttiCinemaVideoForCleanup = document.querySelector('.vep-video')");
    assert(await clickButton('视频', '.cinema-nav button'), 'Top navigation has no video entry to return from Cinema player');
    await waitFor(async () => cdp.evaluate("!!document.querySelector('.feed-grid') && !document.querySelector('.vep-video')"), 'return to video feed');
    const cinemaCleanup = await cdp.evaluate("(()=>{const v=window.__pttiCinemaVideoForCleanup;return v?{paused:v.paused,src_attribute:v.getAttribute('src'),current_src:v.currentSrc,network_state:v.networkState}:null})()");
    record('cinema_unmount_cleanup', cinemaCleanup?.paused && cinemaCleanup.src_attribute === null && cinemaCleanup.network_state === 0 ? 'PASS' : 'FAIL', cinemaCleanup || {});

    const final = {
      schema_version: 1,
      scenario: 'R5.1 local DEV game_1 browser playback regression',
      status: results.some((item) => item.status === 'FAIL') ? 'FAIL' : 'PASS',
      build_commit: health.build_commit,
      video_id: source.video_id,
      source_sha256: source.source_sha256,
      rights_status: source.rights_status,
      result_count: results.length,
      results,
      media_responses: mediaResponses,
      analysis_overlay: 'NOT_TESTED_NO_VERIFIED_ANALYSIS_BOUND_TO_SOURCE',
      native_gui: 'NOT_TESTED_HEADLESS_EDGE_ONLY',
    };
    console.log(JSON.stringify(final, null, 2));
    if (final.status !== 'PASS') process.exitCode = 1;
  } finally {
    try { if (cdp) { await cdp.send('Browser.close').catch(() => {}); cdp.close(); } } catch {}
    if (browser.exitCode === null) {
      browser.kill();
      await Promise.race([new Promise((resolve) => browser.once('exit', resolve)), sleep(3000)]);
    }
    await rm(profile, { recursive: true, force: true });
  }
}

main().catch((error) => {
  const blocked = error.message.startsWith('RESOURCE_GUARD:');
  console.error(JSON.stringify({ status: blocked ? 'BLOCKED' : 'FAIL', message: error.message, completed: results }, null, 2));
  if (!blocked) process.exitCode = 1;
});
