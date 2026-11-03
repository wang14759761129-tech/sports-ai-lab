import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const qa = path.join(root, '.alpha-qa');
const base = 'http://127.0.0.1:4174/';
const inputPath = path.join(root, 'scripts/fixtures/review-targets/quick-input.json');
const targetPath = path.join(root, 'scripts/fixtures/review-targets/targets.json');
const videoPath = path.join(qa, 'goal10-6-SYNTHETIC-TEST-PATTERN-60s.mp4');
const exportPath = path.join(qa, 'goal10-6-edited-quick.json');
const reportPath = path.join(qa, 'goal10-6-review-targets-browser.json');
const compareExportPath = path.join(qa, 'goal10-7-review-comparison-browser.json');
const main = JSON.parse(await readFile(targetPath, 'utf8'));
const ids = [2, 4, 6].map((n) => `SIMULATED_ONLY%3Areview-targets-11-8/g01/p${String(n).padStart(3, '0')}`);
const stage = 'END_AFTER_3_4_CONTACTS';
const actions = [], errors = [], requests = [], consoleErrors = [];
let browser, server;
let phase = 'setup';
const started = Date.now();
await mkdir(qa, { recursive: true });
try {
  const memory = spawnSync('powershell', ['-NoProfile', '-Command', '(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'], { encoding: 'utf8', windowsHide: true });
  const freeGiB = Number(memory.stdout.trim()) / (1024 * 1024);
  if (!Number.isFinite(freeGiB) || freeGiB < 2.5) throw new Error(`BLOCKED: available RAM ${freeGiB.toFixed(2)} GiB is below the existing 2.5 GiB guard`);
  const generated = spawnSync('ffmpeg', ['-y', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=12:duration=60', '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', videoPath], { windowsHide: true });
  assert.equal(generated.status, 0);
  let ready = false;
  try { ready = (await fetch(base)).ok; } catch {}
  if (!ready) {
    server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--mode', 'internal-review', '--host', '127.0.0.1', '--port', '4174', '--strictPort'], { cwd: root, windowsHide: true, stdio: 'ignore' });
    for (let n = 0; n < 60; n++) { await new Promise((resolve) => setTimeout(resolve, 200)); try { ready = (await fetch(base)).ok; } catch {} if (ready) break; }
  }
  assert(ready);
  const playwrightModule = await import(pathToFileURL(process.env.PTTI_PLAYWRIGHT_MODULE).href);
  const chromium = playwrightModule.chromium ?? playwrightModule.default?.chromium;
  assert(chromium, 'PTTI_PLAYWRIGHT_MODULE must export Playwright chromium');
  browser = await chromium.launch({ executablePath: process.env.PTTI_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, acceptDownloads: true });
  const page = await context.newPage();
  page.setDefaultTimeout(12000);
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(`${m.text()} @ ${m.location().url}`); });
  page.on('dialog', (d) => d.accept());
  page.on('request', (r) => { if (!/^(http:\/\/127\.0\.0\.1:4174\/|blob:|data:)/.test(r.url()) || !['GET', 'HEAD'].includes(r.method())) requests.push(`${r.method()} ${r.url()}`); });
  const review = page.locator('.local-video-review');
  const row = (n) => review.locator(`.local-video-point-row[data-point-id$="/p${String(n).padStart(3, '0')}"]`);
  async function act(label, fn) { await fn(); actions.push(label); }
  async function openPro() { await page.locator('main[data-catalog-mode="review"]').waitFor(); await act('open Pro', () => page.locator('.primary-nav .nav-link').filter({ hasText: '专业分析' }).click()); }
  async function importQuick(file = inputPath) { await act('import exact Quick input bytes', () => review.getByLabel('导入已有 Quick Annotation JSON 草稿', { exact: true }).setInputFiles(file)); await review.locator('[data-imported-draft-summary]').waitFor(); }
  async function importTargets(file = targetPath) { await act('import local producer Review Targets', () => review.locator('[data-import-review-targets]').setInputFiles(file)); }
  async function video() { await act('select original synthetic test pattern', () => review.getByLabel('选择本机 MP4 视频', { exact: true }).setInputFiles(videoPath)); await page.getByText('视频已就绪', { exact: true }).waitFor({ timeout: 15000 }); await review.locator('video').evaluate((v) => { v.muted = true; }); }
  const save = () => review.getByRole('button', { name: '保存本分', exact: true }).click();
  await page.goto(base); await openPro();
  phase = 'exact Golden input and report negative imports';
  await importQuick();
  for (const [name, mutate, expected] of [
    ['version', (r) => { r.contract_version = 'ptti.review-targets/9'; }, 'unsupported-version'],
    ['hash', (r) => { r.canonical_input_sha256 = '0'.repeat(64); }, 'input-hash-mismatch'],
    ['identity', (r) => { r.dataset.dataset_id = 'other-dataset'; }, 'identity-mismatch'],
    ['duplicate', (r) => { r.review_targets.push(r.review_targets[0]); }, 'target-conflict'],
    ['missing-point-ids', (r) => { delete r.review_targets[0].point_ids; }, 'invalid-fields'],
    ['unknown-point-id', (r) => { r.review_targets[0].point_ids[0] = 'unrelated/g01/p999'; }, 'target-conflict'],
  ]) {
    const invalid = structuredClone(main); mutate(invalid);
    await importTargets({ name: `${name}.json`, mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(invalid)) });
    await page.waitForFunction((issue) => document.querySelector('[data-targets-error]')?.textContent.includes(issue), expected);
    assert.equal(await review.locator('[data-target-play]').count(), 0);
  }
  await importTargets({ name: 'broken.json', mimeType: 'application/json', buffer: Buffer.from('{broken') });
  await review.locator('[data-targets-error]').waitFor();
  await importTargets();
  await review.locator('[data-targets-match="MATCHED"]').waitFor();
  assert.match(await review.locator('[data-targets-match]').innerText(), new RegExp(main.canonical_input_sha256));
  await video();
  phase = 'real producer IDs with separate local binding';
  await act('filter producer 3–4-contact loss group', () => review.locator(`[data-target-stage="${stage}"]`).click());
  assert.deepEqual(await review.locator('[data-target-point-id]').evaluateAll((nodes) => nodes.map((n) => n.dataset.targetPointId)), ids);
  assert.equal(await review.locator('[data-target-point-id][data-target-playable="true"]').count(), 0);
  for (const n of [2, 4]) {
    await act(`open producer point ${n}`, () => row(n).locator('.local-video-point').click());
    await act(`confirm point ${n} start`, () => review.locator('[data-confirm-boundary="start"]').click());
    await act(`confirm point ${n} end`, () => review.locator('[data-confirm-boundary="end"]').click());
    await act(`save point ${n}`, save);
  }
  assert.equal(await review.locator('[data-targets-match="MATCHED"]').count(), 1);
  assert.equal(await review.locator('[data-target-point-id][data-target-playable="true"]').count(), 2);
  assert.match(await review.locator(`[data-target-point-id="${ids[2]}"]`).innerText(), /尚未在当前视频会话确认/);
  assert.match(await review.locator(`[data-target-stage="${stage}"]`).innerText(), /失 3 分 · 有效 N=3 · 分组归属或胜者未核定 2 分 · 当前可回看 2 段/);
  phase = 'single-player compare controls and split export';
  const compareNote = '我比较了p002与p004的回放操作，具体动作与技术差异需要在真实比赛录像中继续观察。';
  await act('write safe demo comparison note', () => review.locator('[data-comparison-note]').fill(compareNote));
  assert.equal(await review.locator(`[data-comparison-point="${ids[2]}"]`).isEnabled(), false);
  await act('switch to p002 clip', () => review.locator(`[data-comparison-point="${ids[0]}"]`).click());
  await page.waitForFunction(() => { const v = document.querySelector('.local-video-review video'); return v?.paused && v.currentTime >= 5.4 && v.currentTime < 5.7; }, undefined, { timeout: 5000 });
  assert.equal(await review.locator('video').evaluate((v) => v.currentTime >= 5.4 && v.currentTime < 5.7), true);
  await act('switch to p004 clip', () => review.locator(`[data-comparison-point="${ids[1]}"]`).click());
  await page.waitForFunction(() => { const v = document.querySelector('.local-video-review video'); return v?.paused && v.currentTime >= 9.4 && v.currentTime < 9.7; }, undefined, { timeout: 5000 });
  assert.equal(await review.locator('video').evaluate((v) => v.currentTime >= 9.4 && v.currentTime < 9.7), true);
  const compareDownload = page.waitForEvent('download');
  await act('export split facts and user note', () => review.locator('[data-export-comparison]').click());
  await (await compareDownload).saveAs(compareExportPath);
  const compareExport = JSON.parse(await readFile(compareExportPath, 'utf8'));
  assert.deepEqual(compareExport.system_facts.target.point_ids, ids);
  assert.deepEqual(compareExport.system_facts.point_rows.map((row) => row.current_session_playback), ['LOCAL_SESSION_ONLY', 'LOCAL_SESSION_ONLY', 'NOT_PLAYABLE']);
  assert.equal(compareExport.user_observation.text, compareNote);
  assert.equal(compareExport.system_facts.current_video_session.playback_authorization_persists_in_export, false);
  await review.locator('[data-review-targets-panel]').evaluate((panel) => window.scrollTo(0, scrollY + panel.getBoundingClientRect().top - 85));
  await page.screenshot({ path: path.join(qa, 'goal10-7-comparison-1366x768.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('[data-review-targets-panel]').evaluate((panel) => window.scrollTo(0, scrollY + panel.getBoundingClientRect().top - 85));
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
  await page.screenshot({ path: path.join(qa, 'goal10-7-comparison-390.png') });
  await page.setViewportSize({ width: 1366, height: 768 });
  await act('observe B', () => review.locator('[data-targets-observer]').selectOption('PLAYER_B'));
  assert.match(await review.locator('[data-targets-score]').innerText(), /得分 8 \/ 失分 11/);
  assert.equal(await review.locator(`[data-target-play="${stage}"]`).count(), 0);
  await act('observe A', () => review.locator('[data-targets-observer]').selectOption('PLAYER_A'));
  await act('select the three actual IDs again', () => review.locator(`[data-target-stage="${stage}"]`).click());
  await act('select 0.5x', () => review.locator('[data-playback-speed]').selectOption('0.5'));
  await act('play only the two confirmed producer candidates', () => review.locator(`[data-target-play="${stage}"]`).click());
  await page.getByText('已完成所选回合回放', { exact: true }).waitFor({ timeout: 20000 });
  assert.equal(await review.locator('video').evaluate((v) => v.currentTime >= 9.4 && v.currentTime < 12 && v.playbackRate === 0.5), true);
  await act('restart report playlist', () => review.locator(`[data-target-play="${stage}"]`).click());
  await act('pause', () => review.locator('[data-target-pause]').click());
  assert.equal(await review.locator('video').evaluate((v) => v.paused), true);
  await act('resume', () => review.locator('[data-target-pause]').click());
  await act('seek manually cancels', () => review.getByLabel('定位视频', { exact: true }).press('Home'));
  await page.getByText('连续回放已取消', { exact: true }).waitFor();

  phase = 'revoke changes eligibility only';
  await act('open point 2 for boundary review', () => row(2).locator('.local-video-point').click());
  await act('restart before revoke', () => review.locator(`[data-target-play="${stage}"]`).click());
  await act('revoke start confirmation before save', () => review.locator('[data-confirm-boundary="start"]').click());
  await page.getByText('连续回放已取消', { exact: true }).waitFor();
  assert.equal(await review.locator('[data-targets-match="MATCHED"]').count(), 1);
  assert.equal(await review.locator('[data-target-point-id][data-target-playable="true"]').count(), 1);
  assert.match(await review.locator('[data-targets-score]').innerText(), /N=19/);
  assert.equal(await review.locator('.local-video-point').count(), 3);
  await act('save revoked boundary', save);
  await act('reconfirm start', () => review.locator('[data-confirm-boundary="start"]').click());
  await act('save re-confirmed point', save);
  assert.equal(await review.locator('[data-target-point-id][data-target-playable="true"]').count(), 2);

  phase = 'screenshots and bilingual mobile';
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  await review.locator('[data-review-targets-panel]').evaluate((p) => window.scrollTo(0, scrollY + p.getBoundingClientRect().top - 85));
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(r)));
  const desktopPanelTop = await review.locator('[data-review-targets-panel]').evaluate((p) => p.getBoundingClientRect().top);
  assert(desktopPanelTop >= 80 && desktopPanelTop < 105, 'desktop evidence must show producer groups beside the video');
  await page.screenshot({ path: path.join(qa, 'goal10-6-targets-1366x768.png') });
  await review.locator('[data-target-point-list]').screenshot({ path: path.join(qa, 'goal10-6-exact-point-ids.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  await review.locator('[data-review-targets-panel]').evaluate((p) => window.scrollTo(0, scrollY + p.getBoundingClientRect().top - 135));
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
  const targets = await review.locator('[data-target-stage], [data-target-play], [data-targets-observer]').evaluateAll((nodes) => nodes.map((n) => n.getBoundingClientRect().height));
  assert(targets.every((height) => height >= 44));
  await page.screenshot({ path: path.join(qa, 'goal10-6-targets-390.png') });
  await act('English', () => page.getByRole('button', { name: 'English', exact: true }).click());
  assert.match(await review.locator(`[data-target-stage="${stage}"]`).innerText(), /Lost 3 · Valid N=3 · Unresolved group or winner 2 · Replayable now 2/);
  await act('Chinese', () => page.getByRole('button', { name: '中文', exact: true }).click());
  await page.setViewportSize({ width: 1366, height: 768 });

  phase = 'media replacement cancels queue without changing source Insight';
  await act('start producer playlist before video replacement', () => review.locator(`[data-target-play="${stage}"]`).click());
  const oldObjectUrl = await review.locator('video').evaluate((v) => v.currentSrc);
  await video(); // Reselecting even the same bytes must create a fresh local session.
  assert.equal(await review.locator('[data-comparison-note]').inputValue(), '', 'manual notes do not carry over to a new local video session');
  assert.equal(await review.locator('video').evaluate((v, previous) => v.currentSrc !== previous && v.paused, oldObjectUrl), true);
  assert.equal(await review.locator('[data-targets-match="MATCHED"]').count(), 1);
  assert.equal(await review.locator('[data-current-session-reviewable]').getAttribute('data-current-session-reviewable'), '0');
  assert.equal(await review.locator('[data-target-play]').count(), 0);
  assert.equal(await review.locator('[data-target-pause]').count(), 0);
  await page.waitForTimeout(250);
  assert.equal(await review.locator('video').evaluate((v) => v.paused && v.currentTime < 0.1), true, 'old playlist cannot resume on the newly selected media');
  await act('select producer category in fresh session', () => review.locator(`[data-target-stage="${stage}"]`).click());
  assert.deepEqual(await review.locator('[data-target-point-id]').evaluateAll((nodes) => nodes.map((n) => n.dataset.targetPointId)), ids);
  for (const n of [2, 4]) {
    await act(`open point ${n} in new session`, () => row(n).locator('.local-video-point').click());
    await act(`reconfirm point ${n} start for new session`, () => review.locator('[data-confirm-boundary="start"]').click());
    await act(`reconfirm point ${n} end for new session`, () => review.locator('[data-confirm-boundary="end"]').click());
    await act(`save point ${n} for new session`, save);
  }
  assert.equal(await review.locator('[data-target-point-id][data-target-playable="true"]').count(), 2);

  phase = 'winner edit invalidates Insight immediately';
  await act('clear producer filter', () => review.locator('[data-clear-target-filter]').click());
  await act('open historical point 1', () => row(1).locator('.local-video-point').click());
  await act('start category playlist before correction', () => review.locator(`[data-target-play="${stage}"]`).click());
  await act('change point 1 winner', () => review.getByLabel('得分方', { exact: true }).selectOption('PLAYER_B'));
  await review.locator('[data-targets-match="STALE"]').waitFor();
  await page.getByText('连续回放已取消', { exact: true }).waitFor();
  assert.equal(await review.locator('[data-target-play]').count(), 0);
  assert.match(await review.locator('[data-targets-unavailable]').innerText(), /已失效/);
  assert.equal(await review.locator('[data-insight-mode="targets"]').getAttribute('aria-pressed'), 'true');
  assert.equal(await review.locator('[data-loss-insights]').count(), 0, 'invalid Main Insight never silently becomes basic Web counts');
  await act('save corrected winner', save);
  const download = page.waitForEvent('download');
  await act('export edited Quick draft', () => review.locator('[data-export-draft]').click());
  await (await download).saveAs(exportPath);
  const exported = JSON.parse(await readFile(exportPath, 'utf8'));
  assert.equal(exported.points[0].winner, 'opponent');
  assert.equal(exported.points.length, 19);
  assert.equal(exported.dataset_class, 'SIMULATED_ONLY');

  phase = 'reimport cannot restore source or media identity';
  await act('refresh', () => page.reload()); await openPro();
  await importQuick(exportPath);
  assert.equal(await review.locator('video').count(), 0);
  await importTargets();
  await page.waitForFunction(() => document.querySelector('[data-targets-error]')?.textContent.includes('input-hash-mismatch'));
  await video();
  assert.equal(await review.locator('[data-current-session-reviewable]').getAttribute('data-current-session-reviewable'), '0');
  assert.equal(await review.locator('[data-independent-media-verified]').getAttribute('data-independent-media-verified'), '0');
  assert.equal(await review.locator('[data-target-play]').count(), 0);
  const stored = await page.evaluate(() => Object.keys(localStorage).filter((k) => /quick-annotation|local-video|review-target/i.test(k)));
  assert.deepEqual(stored, []); assert.deepEqual(errors, []); assert.deepEqual(requests, []);
  assert.deepEqual(consoleErrors.filter((s) => !s.endsWith(' @ http://127.0.0.1:4174/favicon.ico')), []);
  await writeFile(reportPath, JSON.stringify({ status: 'PASS', producer_commit: '6ea97363b83940e8699fb7a2f40ef4b00a795418', canonical_input_sha256: main.canonical_input_sha256, free_ram_gib: freeGiB, source_points: 19, target_point_ids: ids, confirmed_played_ids: ids.slice(0, 2), unconfirmed_id: ids[2], denominator: 3, comparison_clip_switch_ids: ids.slice(0, 2), p006_disabled: true, comparison_export_path: compareExportPath, comparison_export_facts_separated_from_user_note: true, exported_playback_authorization_persists: false, comparison_note_cleared_on_media_replacement: true, comparison_desktop_screenshot: 'goal10-7-comparison-1366x768.png', comparison_mobile_screenshot: 'goal10-7-comparison-390.png', playback_after_revoke: 1, old_queue_stopped_on_video_replacement: true, playback_after_video_replacement: 0, insight_matched_after_video_replacement: true, no_silent_basic_fallback: true, rejected_missing_and_unknown_point_ids: true, playback_after_refresh_import: 0, independent_media_verified: 0, action_count: actions.length, elapsed_ms: Date.now() - started, page_errors: errors, forbidden_requests: requests, storage_keys: stored, console_errors: consoleErrors, action_log: actions }, null, 2) + '\n');
  console.log(`Review Targets Chrome PASS: exact p002/p004/p006; 3 records, 2 bound clips, 0 verified media; ${actions.length} actions; SHA ${main.canonical_input_sha256}.`);
} catch (error) {
  const page = browser?.contexts()[0]?.pages()[0];
  const visible = page ? await page.locator('.local-video-review').innerText().catch(() => '') : '';
  if (page) await page.screenshot({ path: path.join(qa, 'goal10-6-failure.png') }).catch(() => {});
  await writeFile(reportPath, JSON.stringify({ status: String(error).includes('BLOCKED:') ? 'BLOCKED' : 'FAIL', phase, error: String(error), visible, errors, requests, consoleErrors, actions }, null, 2) + '\n');
  throw error;
} finally { await browser?.close(); server?.kill(); }
