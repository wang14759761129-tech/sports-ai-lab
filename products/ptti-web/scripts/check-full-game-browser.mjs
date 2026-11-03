import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createQuickPointId, expectedServerForPoint } from '../src/local-video-review.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const qa = path.join(root, '.alpha-qa');
const base = 'http://127.0.0.1:4174/';
const videoPath = path.join(qa, 'goal10-4-SYNTHETIC-TEST-PATTERN.mp4');
const exportPath = path.join(qa, 'goal10-4-full-game-browser-export.json');
const runPath = path.join(qa, 'goal10-4-full-game-run.json');
const integrationRoot = process.env.PTTI_INTEGRATION_WORKTREE || 'C:\\PTTI-Worktrees\\integration-preview-sprint-0-1';
const converter = path.join(integrationRoot, 'products', 'ptti-integration', 'scripts', 'run_quick_annotation.py');
const goldenPath = path.join(integrationRoot, 'products', 'ptti-integration', 'fixtures', 'quick-annotation-v0.2-cross-endpoint-golden.json');
const modulePath = process.env.PTTI_PLAYWRIGHT_MODULE;
const chromePath = process.env.PTTI_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const pythonPath = process.env.PTTI_PYTHON_PATH || 'python';
const runTag = Date.now().toString();
if (!modulePath || !existsSync(modulePath)) throw new Error('Set PTTI_PLAYWRIGHT_MODULE to the installed Playwright index.mjs path');
if (!existsSync(chromePath) || !existsSync(converter) || !existsSync(goldenPath)) throw new Error('Chrome or read-only MainDex fixture/CLI is unavailable');
const { chromium } = await import(pathToFileURL(modulePath).href);

const finalWinners = ['PLAYER_A', 'PLAYER_B', 'PLAYER_B', 'PLAYER_A', 'PLAYER_A', 'PLAYER_B', 'PLAYER_A', 'PLAYER_B', 'PLAYER_A', 'PLAYER_B', 'PLAYER_A', 'PLAYER_B', 'PLAYER_A', 'PLAYER_B', 'PLAYER_A', 'PLAYER_B', 'PLAYER_A', 'PLAYER_A', 'PLAYER_A'];
const clips = [
  { point: 2, start: 2, end: 3, stage: 'END_AFTER_1_2_CONTACTS' },
  { point: 10, start: 20, end: 21, stage: 'END_AFTER_3_4_CONTACTS' },
  { point: 17, start: 36, end: 37, stage: 'END_AFTER_5_PLUS_CONTACTS' },
];
const actions = [];
const pageErrors = [];
const consoleErrors = [];
const failedRequests = [];
const httpErrors = [];
const outsideRequests = [];
const writeRequests = [];
let browser;
let ownedServer;
let browserStartedAt = Date.now();
let phase = 'setup';

async function act(label, operation) {
  const result = await operation();
  actions.push(label);
  return result;
}

function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, encoding: 'utf8', windowsHide: true, maxBuffer: 10 * 1024 * 1024 });
  assert.equal(result.status, 0, `${command} failed: ${result.stderr || result.error?.message}`);
  return result;
}

function convertDraft(input, label) {
  const outputJson = path.join(qa, `${label}-${runTag}-converted.json`);
  const outputCsv = path.join(qa, `${label}-${runTag}-protocol-v0.3.csv`);
  const outputStats = path.join(qa, `${label}-${runTag}-stats.json`);
  run(pythonPath, [converter, '--input', input, '--output-json', outputJson, '--output-csv', outputCsv, '--output-stats-json', outputStats]);
  return { outputJson, outputCsv, outputStats };
}

async function ensureServer() {
  try { if ((await fetch(base)).ok) return; } catch {}
  ownedServer = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--mode', 'internal-review', '--host', '127.0.0.1', '--port', '4174', '--strictPort'], { cwd: root, stdio: 'ignore', windowsHide: true, env: process.env });
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    if (ownedServer.exitCode !== null) throw new Error(`Vite exited with ${ownedServer.exitCode}`);
    try { if ((await fetch(base)).ok) return; } catch {}
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error('Internal review server did not start at 127.0.0.1:4174');
}

function assertLegalCompletedGame(winners, finalA, finalB) {
  let a = 0;
  let b = 0;
  let firstTerminal = null;
  winners.forEach((winner, index) => {
    assert(['player', 'opponent'].includes(winner), `point ${index + 1} lacks a known winner`);
    if (winner === 'player') a += 1;
    else b += 1;
    if (firstTerminal === null && Math.max(a, b) >= 11 && Math.abs(a - b) >= 2) firstTerminal = index + 1;
  });
  assert.deepEqual({ a, b }, { a: finalA, b: finalB });
  assert.equal(firstTerminal, winners.length, 'the game ends exactly on the last recorded point at 11+ with a two-point lead');
  return { a, b, firstTerminal };
}

async function seekTo(page, seconds) {
  await act(`seek video to ${seconds}s`, () => page.getByLabel('定位视频', { exact: true }).evaluate((element, value) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
    setter?.call(element, String(value));
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
  }, seconds));
  await page.waitForFunction((value) => Math.abs(document.querySelector('[data-local-video-player]').currentTime - value) < 0.1, seconds);
}

await mkdir(qa, { recursive: true });
run(process.env.PTTI_FFMPEG_PATH || 'ffmpeg', ['-y', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=12:duration=45', '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', videoPath]);
await ensureServer();

try {
  browser = await chromium.launch({ executablePath: chromePath, headless: true });
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1366, height: 768 } });
  const page = await context.newPage();
  page.setDefaultTimeout(12000);
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(`${message.text()} @ ${message.location().url}`); });
  page.on('requestfailed', (request) => failedRequests.push(`${request.method()} ${request.url()}: ${request.failure()?.errorText}`));
  page.on('response', (response) => { if (response.status() >= 400) httpErrors.push(`${response.status()} ${response.url()}`); });
  page.on('request', (request) => {
    const url = request.url();
    if (!url.startsWith('http://127.0.0.1:') && !url.startsWith('blob:') && !url.startsWith('data:')) outsideRequests.push(url);
    if (!['GET', 'HEAD'].includes(request.method())) writeRequests.push(`${request.method()} ${url}`);
  });
  browserStartedAt = Date.now();
  await page.goto(base);
  await page.locator('main[data-catalog-mode="review"]').waitFor();
  await act('open Pro', () => page.locator('.primary-nav .nav-link').filter({ hasText: '专业分析' }).click());
  const review = page.locator('.local-video-review');
  await page.getByRole('heading', { name: '视频逐分复盘' }).waitFor();
  const fileChooser = review.locator('.local-video-file-control');
  const chooserBox = await fileChooser.boundingBox();
  const initialUi = {
    chooser_visible: await fileChooser.isVisible(),
    chooser_within_first_768px: Boolean(chooserBox && chooserBox.y >= 0 && chooserBox.y + chooserBox.height <= 768),
    chooser_height_px: chooserBox?.height ?? null,
    export_visible: await review.locator('[data-export-draft]').isVisible(),
  };
  await page.screenshot({ path: path.join(qa, 'goal10-4-pro-entry-1366x768.png'), animations: 'disabled' });

  phase = 'score-first recording';
  const fileInput = review.getByLabel('选择本机 MP4 视频', { exact: true });
  await act('choose synthetic local MP4', () => fileInput.setInputFiles(videoPath));
  await page.getByText('视频已就绪', { exact: true }).waitFor({ timeout: 15000 });
  const video = review.locator('[data-local-video-player]');
  await video.evaluate((element) => { element.muted = true; });
  await act('open game rules', () => review.locator('.local-video-rule-settings > summary').click());
  await act('declare complete game from 0:0', () => review.getByLabel('本局记录范围', { exact: true }).selectOption('COMPLETE_FROM_GAME_START'));
  await act('declare first server A', () => review.getByLabel('首发球方', { exact: true }).selectOption('PLAYER_A'));
  assert.equal(await review.locator('[data-annotation-pass="score"]').getAttribute('aria-pressed'), 'true');
  const newPoint = review.getByRole('button', { name: '新增 / 补录下一分' });
  const savePoint = review.getByRole('button', { name: '保存本分', exact: true });
  const winnerInput = review.getByLabel('得分方', { exact: true });
  for (let index = 0; index < finalWinners.length; index += 1) {
    await act(`create point ${index + 1}`, () => newPoint.click());
    assert.match(await review.locator('.local-video-draft-heading code').innerText(), new RegExp(`/p${String(index + 1).padStart(3, '0')}$`));
    const firstPassWinner = index === 3 ? 'PLAYER_B' : index === 7 ? 'UNKNOWN' : finalWinners[index];
    if (firstPassWinner !== 'UNKNOWN') await act(`record winner ${index + 1}`, () => winnerInput.selectOption(firstPassWinner));
    await act(`save score ${index + 1}`, () => savePoint.click());
    assert.equal(await review.locator('.local-video-point').count(), index + 1);
  }
  assert.equal(await review.locator('[data-known-winner-count]').getAttribute('data-known-winner-count'), '18');
  assert.equal(await review.locator('[data-current-session-reviewable]').getAttribute('data-current-session-reviewable'), '0');
  await act('undo omitted point 19', () => review.locator('[data-undo-point]').click());
  assert.equal(await review.locator('.local-video-point').count(), 18);
  await act('re-enter omitted point 19', () => newPoint.click());
  assert.match(await review.locator('.local-video-draft-heading code').innerText(), /\/g01\/p019$/);
  await act('record recovered winner 19', () => winnerInput.selectOption('PLAYER_A'));
  await act('save recovered point 19', () => savePoint.click());
  assert.equal(await review.locator('.local-video-point').count(), 19);

  await act('open historic point 4', () => review.locator('.local-video-point').nth(3).click());
  await act('correct point 4 winner', () => winnerInput.selectOption('PLAYER_A'));
  await act('save corrected point 4', () => savePoint.click());
  await act('open missing winner at point 8', () => review.locator('.local-video-point').nth(7).click());
  await act('fill missing point 8 winner', () => winnerInput.selectOption('PLAYER_B'));
  await act('save completed point 8', () => savePoint.click());
  assert.equal(await review.locator('[data-known-winner-count]').getAttribute('data-known-winner-count'), '19');

  phase = 'review three synthetic segments';
  await act('switch from score pass to review pass', () => review.locator('[data-annotation-pass="review"]').click());
  await act('open optional observed-stage fields', () => review.locator('.local-video-optional-tactics > summary').click());
  for (const clip of clips) {
    await act(`open point ${clip.point} for review`, () => review.locator('.local-video-point').nth(clip.point - 1).click());
    await act(`set synthetic stage for point ${clip.point}`, () => review.getByLabel('观察到的回合阶段（粗略）', { exact: true }).selectOption(clip.stage));
    await act(`set start for point ${clip.point}`, () => review.getByLabel('起始时间，秒', { exact: true }).fill(String(clip.start)));
    if (clip.point === 2) {
      await act('preview provisional six-second suggestion', () => review.locator('[data-suggest-six-seconds]').click());
      assert.match(await review.getByText(/PROVISIONAL · AUTO_SUGGESTED/).innerText(), /查看画面并手动确认/);
      assert.equal(await review.locator('[data-current-session-reviewable]').getAttribute('data-current-session-reviewable'), '0');
    }
    await act(`set end for point ${clip.point}`, () => review.getByLabel('结束时间，秒', { exact: true }).fill(String(clip.end)));
    await act(`confirm start for point ${clip.point}`, () => review.locator('[data-confirm-boundary="start"]').click());
    await act(`confirm end for point ${clip.point}`, () => review.locator('[data-confirm-boundary="end"]').click());
    await act(`save reviewed point ${clip.point}`, () => savePoint.click());
    assert.equal(await review.locator('[data-current-session-reviewable]').getAttribute('data-current-session-reviewable'), String(clips.indexOf(clip) + 1));
  }
  assert.equal(await review.locator('.local-video-queue-control input:enabled').count(), 3);
  assert.equal(await review.locator('[data-independent-media-verified]').getAttribute('data-independent-media-verified'), '0');
  await review.locator('[data-score-counts]').scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(qa, 'goal10-4-full-game-1366x768.png'), animations: 'disabled' });

  phase = 'statistics and playlist';
  await act('open losing-point statistic', () => review.locator('[data-review-winner="PLAYER_B"]').click());
  await page.waitForFunction(() => Math.abs(document.querySelector('[data-local-video-player]').currentTime - 2) < 0.1);
  assert.equal(await video.evaluate((element) => element.paused), true);
  for (const clip of clips) await act(`queue point ${clip.point}`, () => review.locator('.local-video-point-row').nth(clip.point - 1).locator('input[type="checkbox"]').check());
  await act('play three confirmed segments', () => review.locator('[data-playlist-start]').click());
  await page.getByText('已完成所选回合回放', { exact: true }).waitFor({ timeout: 20000 });
  assert.equal(await video.evaluate((element) => element.currentTime >= 36.8), true);
  await act('restart three-segment playlist', () => review.locator('[data-playlist-start]').click());
  await page.getByText('连续回放进行中', { exact: true }).waitFor();
  await seekTo(page, 42);
  await page.getByText('连续回放已取消', { exact: true }).waitFor();
  assert.equal(await video.evaluate((element) => Math.abs(element.currentTime - 42) < 0.1 && element.paused), true, 'manual seek cancels the old playlist and does not jump back');

  phase = 'edit and invalidate';
  await act('open reviewed point 17', () => review.locator('.local-video-point').nth(16).click());
  await act('temporarily correct point 17 winner', () => winnerInput.selectOption('PLAYER_B'));
  assert.equal(await review.locator('[data-current-session-reviewable]').getAttribute('data-current-session-reviewable'), '2', 'editing a point invalidates its saved review range before save');
  await act('save temporary point 17 correction', () => savePoint.click());
  await act('restore point 17 winner', () => winnerInput.selectOption('PLAYER_A'));
  await act('reconfirm point 17 start', () => review.locator('[data-confirm-boundary="start"]').click());
  await act('reconfirm point 17 end', () => review.locator('[data-confirm-boundary="end"]').click());
  await act('save restored point 17', () => savePoint.click());
  assert.equal(await review.locator('[data-current-session-reviewable]').getAttribute('data-current-session-reviewable'), '3');
  await act('open reviewed point 2', () => review.locator('.local-video-point').nth(1).click());
  for (const clip of clips) await act(`queue point ${clip.point} for revoke check`, () => review.locator('.local-video-point-row').nth(clip.point - 1).locator('input[type="checkbox"]').check());
  await act('play playlist before boundary revoke', () => review.locator('[data-playlist-start]').click());
  await page.getByText('连续回放进行中', { exact: true }).waitFor();
  await act('revoke point 2 start confirmation', () => review.locator('[data-confirm-boundary="start"]').click());
  await page.getByText('连续回放已取消', { exact: true }).waitFor();
  assert.equal(await review.locator('[data-current-session-reviewable]').getAttribute('data-current-session-reviewable'), '2');
  assert.equal(await review.locator('.local-video-point-row').nth(1).locator('input[type="checkbox"]').isDisabled(), true);
  assert.equal(await review.locator('[data-playlist-start]').isDisabled(), true);
  assert.equal(await review.locator('[data-known-winner-count]').getAttribute('data-known-winner-count'), '19');
  await act('save revoked point 2', () => savePoint.click());
  await act('reconfirm point 2 start', () => review.locator('[data-confirm-boundary="start"]').click());
  await act('save reconfirmed point 2', () => savePoint.click());
  assert.equal(await review.locator('[data-current-session-reviewable]').getAttribute('data-current-session-reviewable'), '3');

  phase = 'export and reference checks';
  await page.setViewportSize({ width: 390, height: 844 });
  await review.locator('[data-score-counts]').scrollIntoViewIfNeeded();
  const mobileUi = await page.evaluate(() => ({
    client_width: document.documentElement.clientWidth,
    scroll_width: document.documentElement.scrollWidth,
    export_height_px: document.querySelector('[data-export-draft]')?.getBoundingClientRect().height ?? null,
  }));
  assert.equal(mobileUi.scroll_width <= mobileUi.client_width + 1, true, '390px viewport has no horizontal overflow');
  await page.screenshot({ path: path.join(qa, 'goal10-4-full-game-390.png'), animations: 'disabled' });
  await page.setViewportSize({ width: 1366, height: 768 });
  const downloadPromise = page.waitForEvent('download', { timeout: 10000 });
  await act('export Quick Annotation v0.2 draft', () => review.locator('[data-export-draft]').click());
  await (await downloadPromise).saveAs(exportPath);
  const exported = JSON.parse(await readFile(exportPath, 'utf8'));
  assert.equal(exported.contract_version, 'ptti.quick-annotation/0.2');
  assert.equal(exported.points.length, 19);
  assert.equal(exported.video_context.source_id, null);
  assert.equal(exported.rules_context.games[0].coverage, 'COMPLETE_FROM_GAME_START');
  assert.equal(exported.rules_context.games[0].first_server, 'player');
  assert.equal(new Set(exported.points.map((point) => point.point_id)).size, 19);
  assert.equal(exported.points.filter((point) => point.rally_start_ms !== null && point.rally_end_ms !== null).length, 3);
  assert.equal(exported.points.filter((point) => point.rally_start_ms === null && point.rally_end_ms === null).length, 16);
  assert.equal(exported.points.filter((point) => point.observed_rally_stage !== 'UNKNOWN').length, 3);
  assert.equal(exported.points.filter((point) => point.observed_tactics.third_ball_attack === 'unknown').length >= 3, true);
  assert.equal(exported.points.some((point) => JSON.stringify(point).includes('blob:')), false);
  const finalScore = assertLegalCompletedGame(exported.points.map((point) => point.winner), 11, 8);
  const convertedFiles = convertDraft(exportPath, 'goal10-4-full-game');
  const converted = JSON.parse(await readFile(convertedFiles.outputJson, 'utf8'));
  const stats = JSON.parse(await readFile(convertedFiles.outputStats, 'utf8'));
  assert.equal(converted.formal_report_eligibility.eligible, false);
  assert.equal(converted.dataset.source_link_status, 'UNBOUND');
  assert.equal(converted.dataset.rights_status, 'UNKNOWN');
  assert.equal(converted.dataset.source_video_sha256, null);
  assert.equal(converted.dataset.vision_status, 'NOT_TESTED');
  assert.equal(stats.sample.point_count, 19);
  assert.equal(stats.sample.score_known_count, 19);
  assert.equal(stats.metrics.time_range_coverage.numerator, 3);
  assert.equal(stats.metrics.timeline_bound_review_coverage.numerator, 0);
  assert.equal(stats.rally_stage_distribution.denominator, 3);
  assert.equal(stats.metrics.tactical_fields.third_ball_attack.denominator, 0);

  phase = 'independent 10:10 synthetic rules case';
  const deuceMatchId = 'SIMULATED_ONLY:goal10-4-deuce';
  const deuceWinners = [...Array.from({ length: 20 }, (_, index) => index % 2 === 0 ? 'player' : 'opponent'), 'player', 'opponent', 'player', 'player'];
  assert.deepEqual(assertLegalCompletedGame(deuceWinners, 13, 11), { a: 13, b: 11, firstTerminal: 24 });
  const deuceInput = {
    contract_version: 'ptti.quick-annotation/0.2', dataset_id: 'SIMULATED_ONLY:goal10-4-deuce-dataset', dataset_class: 'SIMULATED_ONLY', match_id: deuceMatchId,
    video_context: { source_id: null, duration_ms: null, duration_status: 'UNKNOWN' },
    rules_context: { games: [{ game_number: 1, coverage: 'COMPLETE_FROM_GAME_START', first_server: 'player' }] },
    points: deuceWinners.map((winner, index) => ({ point_id: createQuickPointId(deuceMatchId, 1, index + 1), server: expectedServerForPoint('player', index + 1), winner, observed_tactics: {}, rally_start_ms: null, rally_end_ms: null, observed_rally_stage: 'UNKNOWN' })),
  };
  const deucePath = path.join(qa, 'goal10-4-SIMULATED-deuce.json');
  await writeFile(deucePath, `${JSON.stringify(deuceInput, null, 2)}\n`, 'utf8');
  const deuceFiles = convertDraft(deucePath, 'goal10-4-deuce');
  const deuceConverted = JSON.parse(await readFile(deuceFiles.outputJson, 'utf8'));
  assert.equal(deuceConverted.protocol.sequence_valid, true);
  assert.deepEqual(deuceConverted.points.slice(20, 24).map((point) => point.protocol_fields.server), ['player', 'opponent', 'player', 'opponent']);

  phase = 'refresh and local rebind';
  await act('refresh page', () => page.reload());
  await page.locator('main[data-catalog-mode="review"]').waitFor();
  await act('return to Pro', () => page.locator('.primary-nav .nav-link').filter({ hasText: '专业分析' }).click());
  const reloaded = page.locator('.local-video-review');
  await act('import exported local draft', () => reloaded.getByLabel('导入已有 Quick Annotation JSON 草稿', { exact: true }).setInputFiles(exportPath));
  await reloaded.locator('[data-imported-draft-summary]').waitFor();
  assert.equal(await reloaded.locator('[data-local-video-player]').count(), 0);
  assert.equal(await reloaded.locator('[data-imported-draft-summary]').getAttribute('data-import-contract-version'), 'ptti.quick-annotation/0.2');
  await act('reselect synthetic local MP4', () => reloaded.getByLabel('选择本机 MP4 视频', { exact: true }).setInputFiles(videoPath));
  await page.getByText('视频已就绪', { exact: true }).waitFor({ timeout: 15000 });
  assert.equal(await reloaded.locator('.local-video-point').count(), 19);
  assert.equal(await reloaded.locator('[data-known-winner-count]').getAttribute('data-known-winner-count'), '19');
  assert.equal(await reloaded.locator('[data-current-session-reviewable]').getAttribute('data-current-session-reviewable'), '0');
  assert.equal(await reloaded.locator('[data-independent-media-verified]').getAttribute('data-independent-media-verified'), '0');
  assert.equal(await reloaded.locator('.local-video-queue-control input:enabled').count(), 0);
  await reloaded.locator('[data-score-counts]').scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(qa, 'goal10-4-reimport-unbound-1366x768.png'), animations: 'disabled' });
  for (const clip of clips) {
    await act(`open imported point ${clip.point}`, () => reloaded.locator('.local-video-point').nth(clip.point - 1).click());
    await act(`reconfirm imported point ${clip.point} start`, () => reloaded.locator('[data-confirm-boundary="start"]').click());
    await act(`reconfirm imported point ${clip.point} end`, () => reloaded.locator('[data-confirm-boundary="end"]').click());
    await act(`save rebound point ${clip.point}`, () => reloaded.getByRole('button', { name: '保存本分', exact: true }).click());
  }
  assert.equal(await reloaded.locator('[data-current-session-reviewable]').getAttribute('data-current-session-reviewable'), '3');
  assert.equal(await reloaded.locator('[data-independent-media-verified]').getAttribute('data-independent-media-verified'), '0');
  await act('review imported losing point', () => reloaded.locator('[data-review-winner="PLAYER_B"]').click());
  await page.waitForFunction(() => Math.abs(document.querySelector('[data-local-video-player]').currentTime - 2) < 0.1);
  await reloaded.locator('[data-score-counts]').scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(qa, 'goal10-4-reconfirmed-1366x768.png'), animations: 'disabled' });

  const storedAnnotationKeys = await page.evaluate(() => Object.keys(localStorage).filter((key) => /quick-annotation|local-video/i.test(key)));
  assert.deepEqual(storedAnnotationKeys, []);
  assert.deepEqual(pageErrors, []);
  const nonFaviconConsoleErrors = consoleErrors.filter((entry) => !entry.endsWith(' @ http://127.0.0.1:4174/favicon.ico'));
  assert.deepEqual(nonFaviconConsoleErrors, []);
  const nonBlobFailedRequests = failedRequests.filter((entry) => !/^GET blob:http:\/\/127\.0\.0\.1:4174\/[^ ]+: net::ERR_ABORTED$/.test(entry));
  assert.deepEqual(nonBlobFailedRequests, []);
  assert.deepEqual(httpErrors, []);
  assert.deepEqual(outsideRequests, []);
  assert.deepEqual(writeRequests, []);
  const golden = JSON.parse(await readFile(goldenPath, 'utf8'));
  assert.equal(golden.expected.points.valid_score_count, 4);
  assert.equal(golden.expected.time_ranges.duration_checked_count, 2);
  assert.equal(golden.expected.playback.current_session_playable_count, 0);
  assert.equal(golden.expected.sources.independently_verified_source_count, 0);
  const result = {
    status: 'PASS', scenario: 'AUTOMATED_SIMULATED_TEST_PATTERN_ONLY', video_file: path.basename(videoPath),
    browser_elapsed_ms: Date.now() - browserStartedAt, interaction_count: actions.length,
    final_score: finalScore, point_count: exported.points.length, confirmed_time_ranges: 3,
    current_session_playable_before_export: 3, imported_playable_before_reconfirmation: 0,
    rebound_playable_after_reconfirmation: 3, independently_verified_media: 0,
    observed_stage_samples: 3, unknown_or_unobserved_stage: 16, untimed_score_records: 16,
    initial_ui: initialUi, mobile_ui: mobileUi,
    browser_errors: pageErrors, console_errors: consoleErrors, benign_missing_favicon_request: consoleErrors.filter((entry) => entry.endsWith(' @ http://127.0.0.1:4174/favicon.ico')).length, failed_requests: failedRequests, expected_aborted_local_blobs: failedRequests.length - nonBlobFailedRequests.length, http_errors: httpErrors,
    external_requests: outsideRequests, write_requests: writeRequests, annotation_storage_keys: storedAnnotationKeys,
    exported_json: exportPath, converted_stats: convertedFiles.outputStats,
    golden_fixture: goldenPath, golden_expectations_are_not_web_sidecar_consumption: true,
    actions,
  };
  await writeFile(runPath, `${JSON.stringify(result, null, 2)}\n`, 'utf8');
  console.log(`GOAL10.4 full-game Chrome PASS: 11:8 in 19 points; 3 local clips; 16 score-only points; 13:11 deuce fixture verified; ${actions.length} scripted actions in ${result.browser_elapsed_ms}ms; console favicon 404: ${result.benign_missing_favicon_request}.`);
  console.log(`QA record: ${runPath}`);
  console.log(`Quick draft: ${exportPath}`);
  console.log(`Screenshots: ${path.join(qa, 'goal10-4-full-game-1366x768.png')}, ${path.join(qa, 'goal10-4-full-game-390.png')}`);
} catch (error) {
  await writeFile(runPath, `${JSON.stringify({ status: 'FAIL', phase, error: error?.message ?? String(error), browser_elapsed_ms: Date.now() - browserStartedAt, interaction_count: actions.length, actions, browser_errors: pageErrors, console_errors: consoleErrors, failed_requests: failedRequests, http_errors: httpErrors, external_requests: outsideRequests, write_requests: writeRequests }, null, 2)}\n`, 'utf8');
  throw error;
} finally {
  await browser?.close();
  ownedServer?.kill();
}
