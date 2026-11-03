import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { expectedServerForPoint } from '../src/local-video-review.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const base = 'http://127.0.0.1:4174/';
const qa = path.join(root, '.alpha-qa');
const runTag = Date.now().toString();
const videoPath = path.join(qa, 'synthetic-local-video-test.mp4');
const brokenPath = path.join(qa, 'damaged-local-video.mp4');
const invalidPath = path.join(qa, 'unsupported-local-video.webm');
const integrationRoot = process.env.PTTI_INTEGRATION_WORKTREE || 'C:\\PTTI-Worktrees\\integration-preview-sprint-0-1';
const converter = path.join(integrationRoot, 'products', 'ptti-integration', 'scripts', 'run_quick_annotation.py');
const fixtureV01 = path.join(integrationRoot, 'products', 'ptti-integration', 'fixtures', 'quick-annotation-v0.1-valid-simulated.json');
const fixtureV02 = path.join(integrationRoot, 'products', 'ptti-integration', 'fixtures', 'quick-annotation-v0.2-valid-simulated.json');
const fixtureV02Stats = path.join(integrationRoot, 'products', 'ptti-integration', 'generated', 'goal10-2-review-reliability', 'expected-stats.json');
const modulePath = process.env.PTTI_PLAYWRIGHT_MODULE;
const pythonPath = process.env.PTTI_PYTHON_PATH || 'python';
if (!modulePath) throw new Error('Set PTTI_PLAYWRIGHT_MODULE to the installed Playwright index.mjs path');
if (!existsSync(converter)) throw new Error(`MainDex Quick Annotation CLI not found: ${converter}`);
const { chromium } = await import(pathToFileURL(modulePath).href);
const chromePath = process.env.PTTI_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
if (!existsSync(chromePath)) throw new Error(`Chrome executable not found: ${chromePath}`);
const children = [];
const pageErrors = [];
const outsideRequests = [];

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd: root, windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'], ...options });
    let stderr = '';
    child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
    child.once('error', reject);
    child.once('exit', (code) => code === 0 ? resolve() : reject(new Error(`${command} exited ${code}: ${stderr}`)));
  });
}

function runConverter(inputPath, label, includeStats = false) {
  const outputJson = path.join(qa, `${label}-${runTag}-converted.json`);
  const outputCsv = path.join(qa, `${label}-${runTag}-protocol-v0.3.csv`);
  const outputStats = path.join(qa, `${label}-${runTag}-stats.json`);
  const args = [converter, '--input', inputPath, '--output-json', outputJson, '--output-csv', outputCsv];
  if (includeStats) args.push('--output-stats-json', outputStats);
  const result = spawnSync(pythonPath, args, { cwd: root, encoding: 'utf8', windowsHide: true });
  return { ...result, outputJson, outputCsv, outputStats };
}

async function ensureServer() {
  try { const response = await fetch(base); if (response.ok) return; } catch {}
  const child = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--mode', 'internal-review', '--host', '127.0.0.1', '--port', '4174', '--strictPort'], { cwd: root, stdio: 'ignore', windowsHide: true, env: process.env });
  children.push(child);
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null && child.exitCode !== undefined) throw new Error(`Vite exited with ${child.exitCode}`);
    try { const response = await fetch(base); if (response.ok) return; } catch {}
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error('Local review server did not start at 127.0.0.1:4174');
}

function saveJson(filePath, value) {
  return writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

async function seekTo(page, seconds) {
  const slider = page.getByLabel('定位视频', { exact: true });
  await slider.evaluate((element, time) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
    setter?.call(element, String(time));
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
  }, seconds);
  await page.waitForFunction((time) => Math.abs(document.querySelector('[data-local-video-player]').currentTime - time) < 0.08, seconds);
}

await mkdir(qa, { recursive: true });
await run(process.env.PTTI_FFMPEG_PATH || 'ffmpeg', [
  '-y', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=24:duration=6', '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', videoPath,
]);
await writeFile(brokenPath, 'This is intentionally not a decodable MP4 test video.\n', 'utf8');
await writeFile(invalidPath, 'This file has a deliberately unsupported extension.\n', 'utf8');
await ensureServer();

let browser;
try {
  browser = await chromium.launch({ executablePath: chromePath, headless: true });
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('request', (request) => {
    const url = request.url();
    if (!url.startsWith('http://127.0.0.1:') && !url.startsWith('blob:') && !url.startsWith('data:')) outsideRequests.push(url);
  });
  await page.goto(base);
  await page.locator('main[data-catalog-mode="review"]').waitFor();
  await page.locator('.primary-nav .nav-link').filter({ hasText: '专业分析' }).click();
  await page.getByRole('heading', { name: '视频逐分复盘' }).waitFor();
  const review = page.locator('.local-video-review');
  assert.equal(await page.locator('[data-demo-match-id]').getAttribute('data-demo-match-id'), 'SIMULATED_ONLY:goal07-match-001', 'local video draft remains isolated from the separate simulated Pro dataset');
  assert.equal(await page.locator('.local-video-actions button').count(), 0, 'there is no export before a local video and a saved point exist');
  assert.equal(await page.locator('.local-video-point').count(), 0);

  const fileInput = review.getByLabel('选择本机 MP4 视频', { exact: true });
  assert.equal(existsSync(fixtureV01), true, 'MainDex v0.1 golden input is available read-only');
  assert.equal(existsSync(fixtureV02), true, 'MainDex v0.2 golden input is available read-only');
  await fileInput.setInputFiles(invalidPath);
  await page.getByRole('alert').filter({ hasText: '请选择 MP4 文件' }).waitFor();
  assert.equal(await page.locator('[data-local-video-player]').count(), 0, 'unsupported file extension is rejected before a binding is created');

  await fileInput.setInputFiles(videoPath);
  await page.getByText('视频已就绪', { exact: true }).waitFor({ timeout: 15000 });
  const video = page.locator('[data-local-video-player]');
  assert.match(await page.locator('[data-technical-samples]').innerText(), /发球侧有效观察 UNKNOWN.*\(0\/0\).*第三板进攻有效观察 UNKNOWN.*\(0\/0\)/, 'no observed technical fields are shown as UNKNOWN with an explicit sample denominator');
  assert.equal(await page.locator('[data-independent-media-verified]').getAttribute('data-independent-media-verified'), '0', 'a local Object URL is not counted as independent source verification');
  assert.equal(await page.locator('[data-small-sample-warning]').count(), 1, 'technical fields with fewer than five observations show a caution');
  const firstUrl = await video.evaluate((element) => element.currentSrc);
  assert(firstUrl?.startsWith('blob:'), 'the selected synthetic MP4 is played by a local Object URL');
  assert.equal(await video.evaluate((element) => element.controls), true, 'native browser controls expose play, pause and seek');
  assert.equal(await review.getByLabel('新建一分时自动暂停', { exact: true }).isChecked(), true, 'automatic pause is enabled by default');
  await video.evaluate((element) => { element.muted = true; });
  await page.locator('[data-playback-toggle]').click();
  await page.waitForFunction(() => document.querySelector('[data-local-video-player]').currentTime >= 0.25, null, { timeout: 5000 });
  await seekTo(page, 1.2);
  await review.getByRole('button', { name: '新增 / 补录下一分' }).click();
  assert.equal(await video.evaluate((element) => element.paused), true, 'starting a point automatically pauses the video');
  const expectedStartMs = await video.evaluate((element) => Math.round(element.currentTime * 1000));
  assert.equal(await review.getByLabel('得分方', { exact: true }).inputValue(), 'UNKNOWN', 'winner is UNKNOWN until observed');
  assert.equal(await review.locator('.local-video-rule-settings').getAttribute('open'), null, 'game and serve setup is optional and collapsed by default');
  await review.getByLabel('得分方', { exact: true }).selectOption('PLAYER_A');
  assert.equal(await review.getByLabel('发球方', { exact: true }).count(), 0, 'pass 1 hides optional fields so score capture stays quick');
  await review.getByRole('button', { name: '保存本分' }).click();
  assert.equal(await review.locator('[data-known-winner-count]').getAttribute('data-known-winner-count'), '1', 'a winner is counted before any timestamp is confirmed');
  assert.equal(await review.locator('[data-current-session-reviewable]').getAttribute('data-current-session-reviewable'), '0', 'score-only point is not reviewable until boundaries are confirmed');
  await review.locator('.local-video-point').first().click();
  await review.getByLabel('发球方', { exact: true }).selectOption('PLAYER_B');
  await review.locator('.local-video-optional-tactics > summary').click();
  assert.equal(await review.getByLabel('发球侧', { exact: true }).inputValue(), 'unknown', 'serve side is UNKNOWN until observed');
  await review.getByLabel('发球侧', { exact: true }).selectOption('forehand');
  await review.getByLabel('发球长短', { exact: true }).selectOption('short');
  await review.getByLabel('第三板进攻', { exact: true }).selectOption('yes');
  await review.getByLabel('观察到的回合阶段（粗略）', { exact: true }).selectOption('END_AFTER_3_4_CONTACTS');
  await review.getByRole('button', { name: '设为当前时间' }).nth(0).click();
  await review.locator('[data-confirm-boundary="start"]').click();
  await review.locator('[data-suggest-six-seconds]').click();
  assert.match(await review.getByText(/PROVISIONAL · AUTO_SUGGESTED/).innerText(), /查看画面并手动确认/);
  assert.equal(await review.locator('[data-confirm-boundary="end"]').getAttribute('aria-pressed'), 'false', 'the six-second proposal does not confirm the boundary');
  await seekTo(page, 2.4);
  const expectedEndMs = await video.evaluate((element) => Math.round(element.currentTime * 1000));
  await review.getByRole('button', { name: '设为当前时间' }).nth(1).click();
  const endInput = page.getByLabel('结束时间，秒', { exact: true });
  const duration = await video.evaluate((element) => element.duration);
  await endInput.fill(String(duration + 1));
  await review.getByRole('button', { name: '保存本分' }).click();
  await page.getByRole('alert').filter({ hasText: '起止时间必须在视频时长范围内' }).waitFor();
  await endInput.fill(String(expectedEndMs / 1000));
  await review.locator('[data-confirm-boundary="start"]').click();
  await review.locator('[data-confirm-boundary="end"]').click();
  await review.getByRole('button', { name: '保存本分' }).click();

  const savedPoint = page.locator('.local-video-point').first();
  await savedPoint.waitFor();
  assert.equal(await page.locator('.local-video-point').count(), 1);
  assert.match(await savedPoint.innerText(), /第 1 局 · 第 1 分/);
  const firstPointId = await page.locator('.local-video-draft-heading code').innerText();
  assert.match(firstPointId, /^LOCAL_QUICK_MATCH%3A[0-9a-f-]+\/g01\/p001$/i, 'point ID uses the contract canonical match/game/point reference');

  await seekTo(page, 3.0);
  await review.getByRole('button', { name: '新增 / 补录下一分' }).click();
  await review.getByLabel('得分方', { exact: true }).selectOption('PLAYER_B');
  await review.getByRole('button', { name: '保存本分' }).click();
  await review.locator('.local-video-point').nth(1).click();
  await review.getByRole('button', { name: '设为当前时间' }).nth(0).click();
  await review.locator('[data-confirm-boundary="start"]').click();
  await seekTo(page, 4.1);
  await review.getByRole('button', { name: '设为当前时间' }).nth(1).click();
  await review.locator('[data-confirm-boundary="start"]').click();
  await review.locator('[data-confirm-boundary="end"]').click();
  await review.getByRole('button', { name: '保存本分' }).click();
  assert.equal(await page.locator('.local-video-point').count(), 2, 'two stable point IDs were saved for the selected video session');
  assert.equal(await review.locator('[data-current-session-reviewable]').getAttribute('data-current-session-reviewable'), '2', 'two confirmed boundary pairs are reviewable only in this current video session');
  assert.equal(await review.locator('[data-independent-media-verified]').getAttribute('data-independent-media-verified'), '0', 'session playback does not become independent media verification');
  const secondPointId = await page.locator('.local-video-draft-heading code').innerText();
  assert.match(secondPointId, /\/g01\/p002$/i, 'the second point has the next canonical point number');
  assert.equal(await page.locator('.local-video-queue-control input:enabled').count(), 2, 'only explicitly confirmed and saved ranges can enter the playback list');
  assert.equal(await page.locator('[data-review-winner="PLAYER_A"]').isEnabled(), true, 'winner stats are actionable when a known, confirmed point exists');
  await page.locator('[data-review-winner="PLAYER_A"]').click();
  await page.waitForFunction(() => Math.abs(document.querySelector('[data-local-video-player]').currentTime - 1.2) < 0.08);
  await page.locator('[data-review-winner="PLAYER_B"]').click();
  await page.waitForFunction(() => Math.abs(document.querySelector('[data-local-video-player]').currentTime - 3.0) < 0.08);
  await page.locator('[data-undo-point]').click();
  assert.equal(await page.locator('.local-video-point').count(), 1, 'undo removes the most recently added saved point');
  assert.equal(await page.locator('[data-point-id]').evaluateAll((rows) => rows.map((row) => row.dataset.pointId.includes('/p002'))).then((values) => values.some(Boolean)), false, 'undo removes the latest stable point ID without changing earlier IDs');

  await seekTo(page, 3.0);
  await review.getByRole('button', { name: '新增 / 补录下一分' }).click();
  assert.match(await page.locator('.local-video-draft-heading code').innerText(), /\/g01\/p002$/i, 'a saved point can be re-entered after undo without duplicate IDs');
  await review.getByLabel('得分方', { exact: true }).selectOption('PLAYER_B');
  await review.getByRole('button', { name: '保存本分' }).click();
  await review.locator('.local-video-point').nth(1).click();
  await review.getByRole('button', { name: '设为当前时间' }).nth(0).click();
  await review.locator('[data-confirm-boundary="start"]').click();
  await seekTo(page, 4.1);
  await review.getByRole('button', { name: '设为当前时间' }).nth(1).click();
  await review.locator('[data-confirm-boundary="start"]').click();
  await review.locator('[data-confirm-boundary="end"]').click();
  await review.getByRole('button', { name: '保存本分' }).click();

  await page.locator('.local-video-point').first().click();
  await page.waitForFunction(() => Math.abs(document.querySelector('[data-local-video-player]').currentTime - 1.2) < 0.08);
  assert.equal(await video.evaluate((element) => element.paused), true, 'selecting a confirmed point seeks through the Core without autoplay');
  await page.locator('.local-video-queue-control input:enabled').nth(0).check();
  await page.locator('.local-video-queue-control input:enabled').nth(1).check();
  await page.locator('[data-playlist-start]').click();
  await page.getByText('连续回放进行中', { exact: true }).waitFor();
  await page.locator('[data-playlist-pause]').click();
  await page.getByText('连续回放已暂停', { exact: true }).waitFor();
  await page.locator('[data-playlist-resume]').click();
  await page.getByText('已完成所选回合回放', { exact: true }).waitFor({ timeout: 10000 });
  assert.equal(await video.evaluate((element) => element.currentTime >= 4.05), true, 'the Core advanced through both confirmed rally ranges');
  await page.locator('[data-playlist-start]').click();
  await page.locator('[data-playlist-cancel]').waitFor();
  await page.locator('[data-playlist-cancel]').click();
  await page.getByText('连续回放已取消', { exact: true }).waitFor();
  assert.equal(await video.evaluate((element) => element.paused), true, 'the explicit cancel control stops an active Core playlist');

  await savedPoint.click();
  await page.waitForFunction(() => Math.abs(document.querySelector('[data-local-video-player]').currentTime - 1.2) < 0.08);
  assert.equal(await video.evaluate((element) => element.paused), true, 'selecting a point seeks to its start without autoplay');
  await review.getByLabel('得分方', { exact: true }).selectOption('PLAYER_B');
  await review.getByLabel('发球方', { exact: true }).selectOption('PLAYER_A');
  assert.equal(await page.locator('.local-video-queue-control input:checked').count(), 0, 'editing a point immediately invalidates prior playback selection');
  await review.locator('[data-confirm-boundary="start"]').click();
  await review.locator('[data-confirm-boundary="end"]').click();
  await review.getByRole('button', { name: '保存本分' }).click();
  assert.equal(await page.locator('.local-video-point').count(), 2, 'editing an existing point retains its stable ID and leaves the second point intact');
  await review.locator('.local-video-save-status').filter({ hasText: '已保存到当前页面内存' }).waitFor();

  await page.locator('[data-review-winner="PLAYER_B"]').click();
  await page.waitForFunction(() => Math.abs(document.querySelector('[data-local-video-player]').currentTime - 1.2) < 0.08);
  assert.equal(await review.getByLabel('发球方', { exact: true }).inputValue(), 'PLAYER_A', 'the serve side is editable on an existing point');
  assert.match(await review.locator('[data-local-video-time]').innerText(), /00:01/);
  await page.getByText('刷新或关闭会清空本页全部标注，请主动导出草稿。', { exact: false }).waitFor();

  for (const [winner, expectedNumber] of [['PLAYER_A', 3], ['PLAYER_B', 4], ['PLAYER_A', 5]]) {
    await review.getByRole('button', { name: '新增 / 补录下一分' }).click();
    assert.match(await review.locator('.local-video-draft-heading code').innerText(), new RegExp(`/p${String(expectedNumber).padStart(3, '0')}$`));
    await review.getByLabel('得分方', { exact: true }).selectOption(winner);
    await review.getByRole('button', { name: '保存本分' }).click();
    assert.equal(await page.locator('.local-video-point').count(), expectedNumber, `point ${expectedNumber} is recorded without a video time range`);
  }
  assert.match(await page.locator('[data-score-counts]').innerText(), /得分方已知 5\/5 条/);
  assert.equal(await page.locator('[data-known-winner-count]').getAttribute('data-known-winner-count'), '5', 'five score records are retained after three points without any confirmed times');
  assert.equal(await page.locator('[data-current-session-reviewable]').getAttribute('data-current-session-reviewable'), '2', 'score-only points do not reduce or inflate the current-session playback count');
  assert.equal(await page.locator('[data-independent-media-verified]').getAttribute('data-independent-media-verified'), '0');
  assert.match(await page.locator('[data-review-winner="PLAYER_A"]').innerText(), /球员 A.*0 分/, 'score tally includes untimed points while replay stats remain separately bound');
  assert.match(await page.locator('[data-review-winner="PLAYER_B"]').innerText(), /球员 B.*2 分/);
  assert.match(await page.locator('[data-technical-samples]').innerText(), /发球侧有效观察 1\/5 · 第三板进攻有效观察 1\/5/);

  const exportPath = path.join(qa, 'quick-annotation-from-chrome.json');
  const exportButton = review.getByRole('button', { name: '导出草稿 JSON', exact: true });
  assert.equal(await exportButton.isDisabled(), false, 'export is enabled after the point is saved');
  const downloadPromise = page.waitForEvent('download', { timeout: 10000 });
  await exportButton.click();
  let download;
  try { download = await downloadPromise; } catch (error) {
    const issue = await review.locator('.local-video-error').allTextContents();
    throw new Error(`Quick Annotation export did not start; status=${await review.locator('.local-video-save-status').innerText()}; issues=${issue.join(' | ')}; ${error.message}`);
  }
  assert.equal(download.suggestedFilename(), 'ptti-quick-annotation-draft.json');
  await download.saveAs(exportPath);
  await review.locator('.local-video-save-status').filter({ hasText: 'JSON 已生成，请查看浏览器下载记录。' }).waitFor();
  const exported = JSON.parse(await readFile(exportPath, 'utf8'));
  assert.equal(exported.contract_version, 'ptti.quick-annotation/0.2', 'new Web drafts use the MainDex v0.2 contract');
  assert.equal(exported.dataset_class, 'HUMAN_QUICK_DRAFT');
  assert.equal(exported.points[0].winner, 'opponent', 'the edited winner is reflected in exported JSON');
  assert.equal(exported.points[0].server, 'player', 'the corrected server role is reflected in exported JSON');
  assert.equal(exported.points[0].observed_tactics.serve_side, 'forehand');
  assert.equal(exported.points[0].observed_tactics.serve_length, 'short');
  assert.equal(exported.points[0].observed_tactics.third_ball_attack, 'yes');
  assert.equal(exported.points[0].observed_rally_stage, 'END_AFTER_3_4_CONTACTS', 'coarse stage is preserved as a manual v0.2 observation');
  assert.equal(exported.points[0].rally_start_ms, expectedStartMs, 'browser seconds were rounded to integer milliseconds');
  assert.equal(exported.points[0].rally_end_ms, expectedEndMs);
  assert.equal(exported.points.length, 5, 'export contains all five manually recorded points, including untimed score observations');
  assert.equal(exported.points[1].point_id, secondPointId);
  assert.equal(exported.points[1].rally_start_ms, 3000);
  assert.equal(exported.points[1].rally_end_ms, 4100);
  assert.equal(exported.points[1].server, 'unknown', 'the user can leave an unobserved server as UNKNOWN');
  assert.equal(exported.points[1].observed_tactics.serve_side, 'unknown', 'optional technical fields remain UNKNOWN when skipped');
  assert.equal(exported.points[1].observed_tactics.third_ball_attack, 'unknown', 'skipping a phase/technique field does not infer it from the winner');
  assert.equal(Object.hasOwn(exported.points[1].observed_tactics, 'rally_phase'), false, 'no unsupported generic rally-phase field is added to the MainDex contract');
  assert.equal(exported.video_context.duration_ms, Math.round(duration * 1000));
  assert.equal(exported.video_context.source_id, null, 'local file is not misrepresented as a verified source');
  assert.equal(exported.rules_context.games[0].coverage, 'PARTIAL_OR_UNKNOWN');
  assert.equal(exported.points[2].winner, 'player');
  assert.equal(exported.points[2].rally_start_ms, null, 'a recorded score without confirmed video boundaries stays untimed in the export');
  assert(!JSON.stringify(exported).includes('blob:'), 'ephemeral Object URL is not included in export');
  const storageKeys = await page.evaluate(() => Object.keys(localStorage));
  assert.equal(storageKeys.some((key) => key.includes('quick-annotation') || key.includes('local-video')), false, 'quick annotations are not written to browser storage');

  const conversion = runConverter(exportPath, 'chrome-export');
  assert.equal(conversion.status, 0, `MainDex CLI should accept the Chrome export: ${conversion.stderr}`);
  const converted = JSON.parse(await readFile(conversion.outputJson, 'utf8'));
  const convertedCsv = await readFile(conversion.outputCsv, 'utf8');
  assert.equal(converted.contract_version, 'ptti.quick-annotation/0.2');
  assert.equal(converted.points[0].observed_rally_stage, 'END_AFTER_3_4_CONTACTS');
  assert.equal(converted.draft_status, 'LIGHT_ANNOTATION_DRAFT');
  assert.equal(converted.evidence_status, 'REVIEW_REQUIRED');
  assert.equal(converted.formal_report_eligibility.eligible, false);
  assert.equal(converted.dataset.source_link_status, 'UNBOUND');
  assert.equal(converted.dataset.rights_status, 'UNKNOWN');
  assert.equal(converted.dataset.local_analysis_permission, 'UNKNOWN');
  assert.equal(converted.dataset.embed_permission, 'UNKNOWN');
  assert.equal(converted.dataset.source_video_sha256, null);
  assert.equal(converted.dataset.timeline_id, null);
  assert.equal(converted.dataset.vision_status, 'NOT_TESTED');
  assert.equal(converted.points[0].protocol_fields.point_winner, 'opponent');
  assert.equal(converted.points[0].protocol_fields.point_outcome, 'loss');
  assert.match(converted.points[0].protocol_fields.video_timestamp, new RegExp(`start_ms=${expectedStartMs};end_ms=${expectedEndMs};binding=UNBOUND`));
  assert.equal(converted.points[0].timestamp.timeline_binding, 'UNBOUND');
  assert.equal(converted.protocol.rows_parseable, true);
  assert.equal(converted.protocol.formal_bundle_validated, false);
  assert.equal(convertedCsv.split(/\r?\n/)[0].split(',').length, 21, 'CLI emitted exact Protocol v0.3 21-column CSV');

  const pythonCases = path.join(qa, 'cli-cases');
  await mkdir(pythonCases, { recursive: true });
  const duplicateInput = { ...exported, points: [...exported.points, { ...exported.points[0] }] };
  const duplicatePath = path.join(pythonCases, 'duplicate.json');
  await saveJson(duplicatePath, duplicateInput);
  assert.equal(runConverter(duplicatePath, 'duplicate').status, 2, 'MainDex rejects duplicate point_id');

  const gapInput = { ...exported, rules_context: { games: [{ game_number: 1, coverage: 'COMPLETE_FROM_GAME_START', first_server: 'player' }] }, points: [
    { ...exported.points[0], point_id: exported.points[0].point_id.replace(/p\d+$/, 'p001'), server: 'player', winner: 'player', rally_start_ms: null, rally_end_ms: null },
    { ...exported.points[0], point_id: exported.points[0].point_id.replace(/p\d+$/, 'p003'), server: 'opponent', winner: 'unknown', rally_start_ms: null, rally_end_ms: null },
  ] };
  const gapPath = path.join(pythonCases, 'gap.json');
  await saveJson(gapPath, gapInput);
  const gapRun = runConverter(gapPath, 'gap');
  assert.equal(gapRun.status, 0, gapRun.stderr);
  const gapConverted = JSON.parse(await readFile(gapRun.outputJson, 'utf8'));
  assert.equal(gapConverted.protocol.sequence_valid, false, 'a missed point remains a sequence-invalid draft');
  assert.equal(gapConverted.points[1].score_before_player_opponent, null, 'scores after a missing point are not inferred');
  assert.equal(gapConverted.formal_report_eligibility.eligible, false);

  const unknownDurationInput = { ...exported, video_context: { source_id: null, duration_ms: null, duration_status: 'UNKNOWN' }, points: exported.points.map((point) => ({ ...point, rally_start_ms: null, rally_end_ms: null })) };
  const unknownDurationPath = path.join(pythonCases, 'unknown-duration.json');
  await saveJson(unknownDurationPath, unknownDurationInput);
  const unknownDurationRun = runConverter(unknownDurationPath, 'unknown-duration');
  assert.equal(unknownDurationRun.status, 0, unknownDurationRun.stderr);
  assert.equal(JSON.parse(await readFile(unknownDurationRun.outputJson, 'utf8')).dataset.duration_evidence_status, 'UNKNOWN');
  const invalidDurationInput = { ...unknownDurationInput, points: exported.points };
  const invalidDurationPath = path.join(pythonCases, 'invalid-duration.json');
  await saveJson(invalidDurationPath, invalidDurationInput);
  assert.equal(runConverter(invalidDurationPath, 'invalid-duration').status, 2, 'numeric timestamps are rejected while duration is unknown');

  const rulePoints = Array.from({ length: 22 }, (_, index) => {
    const pointNumber = index + 1;
    return {
      point_id: `LOCAL_QUICK_MATCH%3Acli-rule-check/g01/p${String(pointNumber).padStart(3, '0')}`,
      server: expectedServerForPoint('player', pointNumber),
      winner: 'unknown',
      observed_tactics: {},
      rally_start_ms: null,
      rally_end_ms: null,
    };
  });
  const ruleInput = { ...exported, match_id: 'LOCAL_QUICK_MATCH:cli-rule-check', dataset_id: 'HUMAN_QUICK_DRAFT:cli-rule-check', video_context: { source_id: null, duration_ms: null, duration_status: 'UNKNOWN' }, rules_context: { games: [{ game_number: 1, coverage: 'COMPLETE_FROM_GAME_START', first_server: 'player' }] }, points: rulePoints };
  const rulePath = path.join(pythonCases, 'serve-rotation-10-10.json');
  await saveJson(rulePath, ruleInput);
  const ruleRun = runConverter(rulePath, 'serve-rotation-10-10');
  assert.equal(ruleRun.status, 0, ruleRun.stderr);
  const ruleConverted = JSON.parse(await readFile(ruleRun.outputJson, 'utf8'));
  assert.equal(ruleConverted.protocol.sequence_valid, true);
  assert.equal(ruleConverted.points[20].protocol_fields.server, 'player');
  assert.equal(ruleConverted.points[21].protocol_fields.server, 'opponent');
  const badRuleInput = { ...ruleInput, points: rulePoints.map((point, index) => index === 21 ? { ...point, server: 'player' } : point) };
  const badRulePath = path.join(pythonCases, 'serve-rotation-conflict.json');
  await saveJson(badRulePath, badRuleInput);
  assert.equal(runConverter(badRulePath, 'serve-rotation-conflict').status, 2, 'MainDex rejects a wrong server on point 22 after 10:10');

  const badVersionPath = path.join(pythonCases, 'bad-version.json');
  await saveJson(badVersionPath, { ...exported, contract_version: 'ptti.quick-annotation/9.9' });
  assert.equal(runConverter(badVersionPath, 'bad-version').status, 2, 'unknown contract version is rejected');

  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => {
    const form = document.querySelector('.local-video-point-form');
    const header = document.querySelector('.site-header');
    window.scrollTo({ top: form.getBoundingClientRect().top + window.scrollY - (header?.getBoundingClientRect().height ?? 0) - 8, behavior: 'instant' });
  });
  await page.waitForFunction(() => {
    const form = document.querySelector('.local-video-point-form');
    const header = document.querySelector('.site-header');
    return form && header && Math.abs(form.getBoundingClientRect().top - header.getBoundingClientRect().bottom - 8) < 3;
  });
  await page.screenshot({ path: path.join(qa, 'quick-annotation-confirmed-form-390.png'), animations: 'disabled' });

  await page.locator('.local-video-point').first().click();
  await page.locator('.local-video-queue-control input:enabled').nth(0).check();
  await page.locator('.local-video-queue-control input:enabled').nth(1).check();
  await page.locator('[data-playlist-start]').click();
  await page.locator('[data-playlist-pause]').waitFor();
  await review.locator('[data-confirm-boundary="start"]').click();
  await page.getByText('连续回放已取消', { exact: true }).waitFor();
  assert.equal(await page.locator('.local-video-queue-control input:checked').count(), 0, 'revoking a boundary confirmation cancels playback and clears the stale selected list');
  assert.equal(await page.locator('.local-video-queue-control input:enabled').count(), 1, 'revoked boundary is removed from the playable set immediately, before saving');
  assert.equal(await page.locator('[data-playlist-start]').isDisabled(), true, 'the old range cannot be replayed before saving the revocation');
  assert.equal(await review.locator('[data-known-winner-count]').getAttribute('data-known-winner-count'), '5', 'revoking video review does not erase the five recorded scores');
  assert.equal(await review.locator('[data-current-session-reviewable]').getAttribute('data-current-session-reviewable'), '1', 'the other confirmed range remains reviewable');
  assert.equal(await page.locator('.local-video-queue-control input').first().isDisabled(), true, 'the revoked point cannot rejoin the old queue');
  assert.equal(await video.evaluate((element) => element.paused), true, 'revocation stops the active Core playlist');
  await page.locator('.local-video-point-row').first().scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(qa, 'goal10-3-w3-revoked-before-save.png'), animations: 'disabled' });
  await seekTo(page, 5.0);
  await page.locator('.local-video-point').first().click();
  assert.equal(await video.evaluate((element) => Math.abs(element.currentTime - 5.0) < 0.08 && element.paused), true, 'clicking the revoked point before save neither seeks to the old range nor starts playback');
  assert.equal(await review.locator('[data-confirm-boundary="start"]').getAttribute('aria-pressed'), 'false');
  assert.equal(await review.locator('[data-confirm-boundary="end"]').getAttribute('aria-pressed'), 'false');
  await page.locator('[data-review-winner="PLAYER_B"]').click();
  assert.equal(await video.evaluate((element) => Math.abs(element.currentTime - 3.0) < 0.08 && element.paused), true, 'winner statistics seek only the remaining legally bound point, without playing the revoked old range');
  await page.locator('.local-video-point').first().click();
  await review.getByRole('button', { name: '保存本分' }).click();
  assert.equal(await page.locator('.local-video-queue-control input:enabled').count(), 1, 'a point with a revoked boundary cannot remain playable');
  await review.locator('[data-confirm-boundary="start"]').click();
  assert.equal(await page.locator('.local-video-queue-control input:enabled').count(), 1, 'reconfirming only one endpoint cannot restore playback');
  await review.locator('[data-confirm-boundary="end"]').click();
  assert.equal(await page.locator('.local-video-queue-control input:enabled').count(), 1, 'both newly confirmed draft boundaries remain outside playback until saved');
  await review.getByRole('button', { name: '保存本分' }).click();
  assert.equal(await page.locator('.local-video-queue-control input:enabled').count(), 2, 'confirming both current boundaries restores only the current-session binding');
  await page.locator('.local-video-queue-control input:enabled').nth(0).check();
  await page.locator('.local-video-queue-control input:enabled').nth(1).check();
  await page.locator('[data-playlist-start]').click();
  await page.locator('[data-playlist-pause]').waitFor();
  await review.getByLabel('起始时间，秒', { exact: true }).fill('1.21');
  await page.getByText('连续回放已取消', { exact: true }).waitFor();
  assert.equal(await page.locator('.local-video-queue-control input:checked').count(), 0, 'editing a confirmed boundary cancels playback and clears the stale selected list');
  assert.equal(await page.locator('[data-playlist-start]').isDisabled(), true, 'the invalidated list cannot be replayed');

  for (const width of [390, 768, 1024, 1366, 1440]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : width <= 1366 ? 768 : 1000 });
    await page.locator('.local-video-review').scrollIntoViewIfNeeded();
    const metrics = await page.evaluate(() => ({
      width: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      unnamedButtons: [...document.querySelectorAll('.local-video-review button:not(:disabled)')]
        .filter((button) => !button.getAttribute('aria-label') && !button.textContent.trim()).length,
      targets: [...document.querySelectorAll('.local-video-review button, .local-video-review select, .local-video-review input, .local-video-review summary')]
        .filter((element) => !element.disabled && element.type !== 'file')
        .map((element) => Math.round((element.type === 'checkbox' ? element.parentElement : element).getBoundingClientRect().height)),
    }));
    assert(metrics.scrollWidth <= metrics.width + 1, `page overflows at ${width}px: ${JSON.stringify(metrics)}`);
    assert(metrics.targets.every((height) => height >= 44), `interactive target is below 44px at ${width}px: ${JSON.stringify(metrics)}`);
    assert.equal(metrics.unnamedButtons, 0, `an active button lacks an accessible name at ${width}px`);
    if (width === 390) {
      await page.screenshot({ path: path.join(qa, 'quick-annotation-panel-390.png'), animations: 'disabled' });
      await page.evaluate(() => {
        const form = document.querySelector('.local-video-point-form');
        const header = document.querySelector('.site-header');
        window.scrollTo({ top: form.getBoundingClientRect().top + window.scrollY - (header?.getBoundingClientRect().height ?? 0) - 8, behavior: 'instant' });
      });
      await page.waitForFunction(() => {
        const form = document.querySelector('.local-video-point-form');
        const header = document.querySelector('.site-header');
        return form && header && Math.abs(form.getBoundingClientRect().top - header.getBoundingClientRect().bottom - 8) < 3;
      });
      await page.screenshot({ path: path.join(qa, 'quick-annotation-form-390.png'), animations: 'disabled' });
      await page.getByRole('button', { name: 'English', exact: true }).click();
      await page.getByRole('heading', { name: 'Video point review' }).waitFor();
      const english = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }));
      assert(english.scrollWidth <= english.width + 1, 'English page fits 390px');
      assert.equal(await review.getByLabel('Serve length', { exact: true }).inputValue(), 'short');
      await page.getByRole('button', { name: '中文', exact: true }).click();
      await page.getByRole('heading', { name: '视频逐分复盘' }).waitFor();
    }
    if (width === 768) await page.screenshot({ path: path.join(qa, 'quick-annotation-panel-768.png'), animations: 'disabled' });
    if (width === 1024) await page.screenshot({ path: path.join(qa, 'quick-annotation-panel-1024.png'), animations: 'disabled' });
    if (width === 1366) await page.screenshot({ path: path.join(qa, 'quick-annotation-panel-1366x768.png'), animations: 'disabled' });
    if (width === 1440) await page.screenshot({ path: path.join(qa, 'quick-annotation-panel-1440.png'), animations: 'disabled' });
  }

  page.once('dialog', (dialog) => dialog.accept());
  await fileInput.setInputFiles(brokenPath);
  await page.getByText('视频不可用', { exact: true }).waitFor({ timeout: 10000 });
  await page.getByRole('alert').filter({ hasText: '无法读取或解码此视频' }).waitFor({ timeout: 10000 });
  const oldObjectUrlRevoked = await page.evaluate(async (url) => {
    try { await fetch(url); return false; } catch { return true; }
  }, firstUrl);
  assert.equal(oldObjectUrlRevoked, true, 'replacing a video invalidates the old local binding/Object URL');
  await fileInput.setInputFiles(videoPath);
  await page.getByText('视频已就绪', { exact: true }).waitFor({ timeout: 15000 });
  assert.equal(await page.locator('.local-video-point').count(), 0, 'replacing a video clears annotations bound to the previous file');
  assert.notEqual(await page.locator('[data-local-video-player]').evaluate((element) => element.currentSrc), firstUrl);
  await review.getByRole('button', { name: '新增 / 补录下一分' }).click();
  await review.locator('[data-annotation-pass="review"]').click();
  await review.locator('.local-video-rule-settings > summary').click();
  await review.getByLabel('本局记录范围', { exact: true }).selectOption('COMPLETE_FROM_GAME_START');
  await review.getByLabel('首发球方', { exact: true }).selectOption('PLAYER_A');
  await review.locator('[data-use-server-suggestion]').waitFor();
  await review.locator('[data-use-server-suggestion]').click();
  assert.equal(await review.getByLabel('发球方', { exact: true }).inputValue(), 'PLAYER_A', 'the UI offers an explicit rule-derived server only after complete coverage and a known first server');

  const malformedDraftPath = path.join(qa, 'malformed-quick-draft.json');
  const unknownVersionDraftPath = path.join(qa, 'unknown-version-quick-draft.json');
  await writeFile(malformedDraftPath, '{ this is not JSON', 'utf8');
  await saveJson(unknownVersionDraftPath, { ...exported, contract_version: 'ptti.quick-annotation/9.9' });
  await page.reload();
  await page.locator('main[data-catalog-mode="review"]').waitFor();
  await page.locator('.primary-nav .nav-link').filter({ hasText: '专业分析' }).click();
  await page.getByRole('heading', { name: '视频逐分复盘' }).waitFor();
  const reloadedReview = page.locator('.local-video-review');
  const importInput = reloadedReview.getByLabel('导入已有 Quick Annotation JSON 草稿', { exact: true });
  assert.equal(await reloadedReview.locator('[data-local-video-player]').count(), 0, 'refresh clears the selected local video from page memory');
  assert.equal(await reloadedReview.locator('.local-video-point').count(), 0, 'refresh clears private annotation state from page memory');
  await importInput.setInputFiles(malformedDraftPath);
  await page.getByRole('alert').filter({ hasText: '文件不是有效 JSON' }).waitFor();
  assert.equal(await reloadedReview.locator('.local-video-point').count(), 0, 'malformed JSON leaves the current draft untouched');
  await importInput.setInputFiles(unknownVersionDraftPath);
  await page.getByRole('alert').filter({ hasText: '不支持此 Quick Annotation 版本' }).waitFor();

  await fileInput.setInputFiles(videoPath);
  await page.getByText('视频已就绪', { exact: true }).waitFor({ timeout: 15000 });
  await reloadedReview.getByRole('button', { name: '新增 / 补录下一分' }).click();
  await reloadedReview.getByLabel('得分方', { exact: true }).selectOption('PLAYER_A');
  await reloadedReview.getByRole('button', { name: '保存本分' }).click();
  assert.equal(await reloadedReview.locator('.local-video-point').count(), 1, 'an existing in-memory point is present before import overwrite confirmation');
  await importInput.setInputFiles(malformedDraftPath);
  await page.getByRole('alert').filter({ hasText: '文件不是有效 JSON' }).waitFor();
  assert.equal(await reloadedReview.locator('.local-video-point').count(), 1, 'invalid JSON cannot replace an existing saved point');
  await importInput.setInputFiles(unknownVersionDraftPath);
  await page.getByRole('alert').filter({ hasText: '不支持此 Quick Annotation 版本' }).waitFor();
  assert.equal(await reloadedReview.locator('.local-video-point').count(), 1, 'unknown contract version cannot replace an existing saved point');
  page.once('dialog', (dialog) => dialog.dismiss());
  await importInput.setInputFiles(exportPath);
  await page.waitForTimeout(100);
  assert.equal(await reloadedReview.locator('.local-video-point').count(), 1, 'dismissing replacement confirmation preserves current annotations');
  page.once('dialog', (dialog) => dialog.accept());
  await importInput.setInputFiles(exportPath);
  await reloadedReview.locator('[data-imported-draft-summary]').waitFor();
  await page.getByText('草稿已导入本页内存。旧视频身份与边界确认不会恢复；请重新选择视频。', { exact: true }).waitFor();
  assert.match(await reloadedReview.locator('[data-imported-draft-summary]').innerText(), /包含 5 条逐分记录/);
  assert.equal(await reloadedReview.locator('[data-local-video-player]').count(), 0, 'valid draft import drops the prior video session');
  assert.equal(await reloadedReview.locator('[data-export-draft]').isDisabled(), true, 'export stays disabled until a video is freshly selected');

  await fileInput.setInputFiles(videoPath);
  await page.getByText('视频已就绪', { exact: true }).waitFor({ timeout: 15000 });
  const reboundVideo = reloadedReview.locator('[data-local-video-player]');
  assert.equal(await reloadedReview.locator('.local-video-point').count(), 5, 'imported five-point draft is restored after choosing a new local file');
  assert.equal(await reloadedReview.locator('.local-video-queue-control input:enabled').count(), 0, 'import does not restore confirmations or old video identity');
  assert.equal(await reloadedReview.locator('[data-local-video-player]').evaluate((element) => element.currentTime), 0, 'new session starts without an old timeline seek');
  await reloadedReview.locator('.local-video-point').first().click();
  await page.waitForTimeout(100);
  assert.equal(await reboundVideo.evaluate((element) => element.currentTime), 0, 'clicking an imported unbound point cannot seek the newly selected video');
  assert.equal(await reloadedReview.locator('[data-playlist-start]').isDisabled(), true, 'unconfirmed imported ranges cannot be added to playback');
  for (const index of [0, 1]) {
    await reloadedReview.locator('.local-video-point').nth(index).click();
    await reloadedReview.locator('[data-confirm-boundary="start"]').click();
    await reloadedReview.locator('[data-confirm-boundary="end"]').click();
    await reloadedReview.getByRole('button', { name: '保存本分' }).click();
  }
  assert.equal(await reloadedReview.locator('.local-video-queue-control input:enabled').count(), 2, 'only ranges explicitly reconfirmed against the new page session become playable');
  assert.match(await reloadedReview.locator('.local-video-file-meta').innerText(), /未计算或核验视频 SHA-256/);
  assert.match(await reloadedReview.locator('[data-imported-draft-summary]').innerText(), /未独立核验/);
  await reloadedReview.locator('[data-review-winner="PLAYER_B"]').click();
  await page.waitForFunction(() => Math.abs(document.querySelector('[data-local-video-player]').currentTime - 1.2) < 0.08);
  await reloadedReview.locator('.local-video-queue-control input:enabled').nth(0).check();
  await reloadedReview.locator('.local-video-queue-control input:enabled').nth(1).check();
  await reloadedReview.locator('[data-playlist-start]').click();
  await page.getByText('已完成所选回合回放', { exact: true }).waitFor({ timeout: 10000 });

  const reexportPath = path.join(qa, 'quick-annotation-reimported.json');
  const reexportDownloadPromise = page.waitForEvent('download', { timeout: 10000 });
  await reloadedReview.getByRole('button', { name: '导出草稿 JSON', exact: true }).click();
  const reexportDownload = await reexportDownloadPromise;
  await reexportDownload.saveAs(reexportPath);
  const reexported = JSON.parse(await readFile(reexportPath, 'utf8'));
  assert.equal(reexported.dataset_id, exported.dataset_id, 'import preserves draft dataset identity without claiming a media identity');
  assert.equal(reexported.points.length, 5);
  const reimportConversion = runConverter(reexportPath, 'chrome-reimport-export');
  assert.equal(reimportConversion.status, 0, `reimported browser draft remains acceptable to MainDex CLI: ${reimportConversion.stderr}`);
  const reimportConverted = JSON.parse(await readFile(reimportConversion.outputJson, 'utf8'));
  assert.equal(reexported.contract_version, 'ptti.quick-annotation/0.2');
  assert.equal(reimportConverted.dataset.source_video_sha256, null);
  assert.equal(reimportConverted.dataset.rights_status, 'UNKNOWN');
  assert.equal(reimportConverted.dataset.vision_status, 'NOT_TESTED');

  const goldenV01Conversion = runConverter(fixtureV01, 'maindex-v01-golden');
  assert.equal(goldenV01Conversion.status, 0, `MainDex v0.1 golden sample remains accepted: ${goldenV01Conversion.stderr}`);
  const goldenV01Converted = JSON.parse(await readFile(goldenV01Conversion.outputJson, 'utf8'));
  assert.equal(goldenV01Converted.contract_version, 'ptti.quick-annotation/0.1');
  const goldenV02Conversion = runConverter(fixtureV02, 'maindex-v02-golden', true);
  assert.equal(goldenV02Conversion.status, 0, `MainDex v0.2 golden sample and stats convert: ${goldenV02Conversion.stderr}`);
  const actualGoldenStats = JSON.parse(await readFile(goldenV02Conversion.outputStats, 'utf8'));
  const expectedGoldenStats = JSON.parse(await readFile(fixtureV02Stats, 'utf8'));
  assert.deepEqual(actualGoldenStats, expectedGoldenStats, 'the latest MainDex v0.2 golden sample matches its committed reference stats exactly');
  assert.equal(actualGoldenStats.sample.score_known_count, 4);
  assert.equal(actualGoldenStats.metrics.time_range_coverage.numerator, 2);
  assert.equal(actualGoldenStats.metrics.timeline_bound_review_coverage.numerator, 0);
  assert.equal(actualGoldenStats.rally_stage_distribution.denominator, 3);

  await page.reload();
  await page.locator('main[data-catalog-mode="review"]').waitFor();
  await page.locator('.primary-nav .nav-link').filter({ hasText: '专业分析' }).click();
  await page.getByRole('heading', { name: '视频逐分复盘' }).waitFor();
  const goldenReview = page.locator('.local-video-review');
  const goldenImport = goldenReview.getByLabel('导入已有 Quick Annotation JSON 草稿', { exact: true });
  await goldenImport.setInputFiles(fixtureV01);
  await goldenReview.locator('[data-imported-draft-summary]').waitFor();
  assert.equal(await goldenReview.locator('[data-imported-draft-summary]').getAttribute('data-import-contract-version'), 'ptti.quick-annotation/0.1');
  assert.match(await goldenReview.locator('[data-imported-draft-summary]').innerText(), /包含 5 条逐分记录/);
  await fileInput.setInputFiles(videoPath);
  await page.getByText('视频已就绪', { exact: true }).waitFor({ timeout: 15000 });
  assert.equal(await goldenReview.locator('.local-video-point').count(), 5);
  await goldenReview.locator('.local-video-point').first().click();
  assert.equal(await goldenReview.getByLabel('观察到的回合阶段（粗略）', { exact: true }).count(), 0, 'the v0.1 editor does not expose a v0.2-only stage field');
  await page.reload();
  await page.locator('main[data-catalog-mode="review"]').waitFor();
  await page.locator('.primary-nav .nav-link').filter({ hasText: '专业分析' }).click();
  const v02Review = page.locator('.local-video-review');
  const v02Import = v02Review.getByLabel('导入已有 Quick Annotation JSON 草稿', { exact: true });
  await v02Import.setInputFiles(fixtureV02);
  await v02Review.locator('[data-imported-draft-summary]').waitFor();
  assert.equal(await v02Review.locator('[data-imported-draft-summary]').getAttribute('data-import-contract-version'), 'ptti.quick-annotation/0.2');
  assert.match(await v02Review.locator('[data-imported-draft-summary]').innerText(), /原创模拟数据/);
  await fileInput.setInputFiles(videoPath);
  await page.getByText('视频已就绪', { exact: true }).waitFor({ timeout: 15000 });
  assert.equal(await v02Review.locator('[data-score-counts]').getAttribute('data-known-winner-count'), '4');
  assert.equal(await v02Review.locator('[data-current-session-reviewable]').getAttribute('data-current-session-reviewable'), '0');
  assert.equal(await v02Review.locator('[data-independent-media-verified]').getAttribute('data-independent-media-verified'), '0');
  const v02Video = v02Review.locator('[data-local-video-player]');
  await v02Review.locator('.local-video-point').first().click();
  assert.equal(await v02Review.getByLabel('观察到的回合阶段（粗略）', { exact: true }).inputValue(), 'END_AFTER_1_2_CONTACTS');
  assert.equal(await v02Video.evaluate((element) => element.currentTime), 0, 'v0.2 imported time and stage do not silently bind to the newly selected file');
  await page.getByRole('button', { name: 'English', exact: true }).click();
  await v02Review.getByRole('button', { name: 'Pass 1 · record the winner', exact: true }).waitFor();
  await page.getByRole('button', { name: '中文', exact: true }).click();
  await v02Review.getByRole('button', { name: '第 1 遍 · 先记得分方', exact: true }).waitFor();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('.local-video-review').scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(qa, 'goal10-3-imported-v02-390.png'), animations: 'disabled' });
  await page.getByRole('button', { name: 'English', exact: true }).click();
  await page.getByRole('heading', { name: 'Video point review' }).waitFor();
  assert.equal(await reloadedReview.getByLabel('Import an existing Quick Annotation JSON draft', { exact: true }).count(), 1);
  assert.match(await reloadedReview.locator('[data-imported-draft-summary]').innerText(), /Original simulated data|Imported human quick-annotation draft/);
  const importedEnglishSize = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }));
  assert(importedEnglishSize.scrollWidth <= importedEnglishSize.width + 1, 'imported draft fits the English 390px mobile viewport');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: path.join(qa, 'goal10-3-imported-v02-english-390.png'), animations: 'disabled' });
  await page.getByRole('button', { name: '中文', exact: true }).click();
  await page.getByRole('heading', { name: '视频逐分复盘' }).waitFor();
  for (const [width, height] of [[768, 768], [1024, 768], [1366, 768], [1440, 900]]) {
    await page.setViewportSize({ width, height });
    await page.locator('.local-video-review').scrollIntoViewIfNeeded();
    const size = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }));
    assert(size.scrollWidth <= size.width + 1, `reimported draft overflows at ${width}px: ${JSON.stringify(size)}`);
    if (width === 1366) await page.screenshot({ path: path.join(qa, 'goal10-3-imported-v02-1366x768.png'), animations: 'disabled' });
  }
  const privacyStorage = await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage) }));
  assert.equal(privacyStorage.local.some((key) => /quick-annotation|local-video|draft/i.test(key)), false, 'private drafts never enter localStorage');
  assert.equal(privacyStorage.session.some((key) => /quick-annotation|local-video|draft/i.test(key)), false, 'private drafts never enter sessionStorage');

  assert.deepEqual(pageErrors, [], `browser page errors: ${pageErrors.join('; ')}`);
  assert.deepEqual(outsideRequests, [], `unexpected external requests: ${outsideRequests.join('; ')}`);
  await context.close();
  console.log('Chrome GOAL10.3 Quick Annotation E2E PASS: score-first capture, v0.2 stage observation, provisional +6s suggestion, manual boundary confirmation, edit invalidation, undo/refill, selected and consecutive playback, v0.1/v0.2 golden imports, refresh/re-import without restoring playback binding, and versioned export. MainDex CLI accepted Web exports; v0.2 fixture statistics exactly matched the committed expected stats. No private annotation storage or external requests; zh/en and 390/768/1024/1366/1440 verified.');
  console.log(`Chrome export: ${exportPath}`);
  console.log(`Chrome reimport export: ${reexportPath}`);
  console.log(`MainDex converted draft: ${conversion.outputJson}`);
  console.log(`Browser evidence: ${path.join(qa, 'goal10-3-imported-v02-390.png')}, ${path.join(qa, 'goal10-3-imported-v02-1366x768.png')}`);
} finally {
  await browser?.close();
  for (const child of children) child.kill();
}
