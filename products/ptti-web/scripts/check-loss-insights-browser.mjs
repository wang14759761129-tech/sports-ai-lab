import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const qa = path.join(root, '.alpha-qa');
const base = 'http://127.0.0.1:4174/';
const fixture = path.join(root, 'scripts/fixtures/goal10-5-19-point-simulated.json');
const videoPath = path.join(qa, 'goal10-4-SYNTHETIC-TEST-PATTERN.mp4');
const exportPath = path.join(qa, 'goal10-5-insight-export.json');
const reportPath = path.join(qa, 'goal10-5-insight-browser.json');
const stage = 'END_AFTER_3_4_CONTACTS';
const { chromium } = await import(pathToFileURL(process.env.PTTI_PLAYWRIGHT_MODULE).href);
const actions = [];
const errors = [];
const consoleErrors = [];
const failedRequests = [];
const external = [];
const writes = [];
let ownedServer;
let browser;
let phase = 'setup';
const started = Date.now();
await mkdir(qa, { recursive: true });
if (!existsSync(videoPath)) {
  const result = spawnSync('ffmpeg', ['-y', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=12:duration=45', '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', videoPath], { windowsHide: true });
  assert.equal(result.status, 0);
}
try {
  let ready = false;
  try { ready = (await fetch(base)).ok; } catch {}
  if (!ready) {
    ownedServer = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--mode', 'internal-review', '--host', '127.0.0.1', '--port', '4174', '--strictPort'], { cwd: root, windowsHide: true, stdio: 'ignore' });
    for (let n = 0; n < 60; n++) {
      await new Promise((resolve) => setTimeout(resolve, 250));
      try { ready = (await fetch(base)).ok; } catch {}
      if (ready) break;
    }
  }
  assert.equal(ready, true, 'review server must be available');
  browser = await chromium.launch({ executablePath: process.env.PTTI_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, acceptDownloads: true });
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(`${message.text()} @ ${message.location().url}`); });
  page.on('requestfailed', (request) => failedRequests.push(`${request.method()} ${request.url()}: ${request.failure()?.errorText}`));
  page.on('dialog', (dialog) => dialog.accept());
  page.on('request', (request) => {
    if (!/^(http:\/\/127\.0\.0\.1:4174\/|blob:|data:)/.test(request.url())) external.push(request.url());
    if (!['GET', 'HEAD'].includes(request.method())) writes.push(request.url());
  });
  async function act(label, fn) { await fn(); actions.push(label); }
  const review = page.locator('.local-video-review');
  const row = (n) => review.locator(`.local-video-point-row[data-point-id$="/p${String(n).padStart(3, '0')}"]`);
  async function openPro() {
    await page.locator('main[data-catalog-mode="review"]').waitFor();
    await act('open Pro', () => page.locator('.primary-nav .nav-link').filter({ hasText: '专业分析' }).click());
  }
  async function selectVideo() {
    await act('select synthetic test-pattern MP4', () => review.getByLabel('选择本机 MP4 视频', { exact: true }).setInputFiles(videoPath));
    await page.getByText('视频已就绪', { exact: true }).waitFor();
    await review.locator('video').evaluate((video) => { video.muted = true; });
  }
  async function reviewPoint(n, addStage = false, confirm = false) {
    await act(`open point ${n}`, () => row(n).locator('.local-video-point').click());
    if (addStage) {
      const optional = review.locator('.local-video-optional-tactics');
      if (!(await optional.getAttribute('open') !== null)) await act('open optional observed fields', () => optional.locator('summary').click());
      await act(`observe stage on synthetic point ${n}`, () => review.locator('[data-observed-rally-stage]').selectOption(stage));
    }
    if (confirm) {
      await act(`confirm start ${n}`, () => review.locator('[data-confirm-boundary="start"]').click());
      await act(`confirm end ${n}`, () => review.locator('[data-confirm-boundary="end"]').click());
    }
    await act(`save point ${n}`, () => review.getByRole('button', { name: '保存本分', exact: true }).click());
  }
  await page.goto(base);
  await openPro();
  phase = 'import 19-point synthetic game and bind two loss clips';
  await act('import SIMULATED_ONLY 19-point 11:8 game', () => review.getByLabel('导入已有 Quick Annotation JSON 草稿', { exact: true }).setInputFiles(fixture));
  await selectVideo();
  assert.match(await review.locator('[data-insight-score]').innerText(), /已记分 19 · 得分 11 \/ 失分 8/);
  assert.match(await review.locator('[data-insight-score]').innerText(), /当前可回看失分 0/);
  await act('filter unbound 3–4-contact losses', () => review.locator(`[data-loss-filter="${stage}"]`).click());
  assert.match(await review.locator('[data-loss-empty]').innerText(), /确认起止时间/);
  assert.equal(await review.locator(`[data-loss-play="${stage}"]`).count(), 0);
  assert.match(await review.locator(`[data-loss-unavailable="${stage}"]`).innerText(), /确认起止时间/);
  await act('clear category', () => review.locator('[data-clear-loss-filter]').click());
  await reviewPoint(2, true, true);
  await reviewPoint(10, false, true);
  await reviewPoint(8, true, false); // Explicit stage, no timestamps: score still counts.
  await act('select observer B', () => review.locator('[data-loss-observer]').selectOption('PLAYER_B'));
  assert.match(await review.locator('[data-insight-score]').innerText(), /得分 8 \/ 失分 11/);
  assert.equal(await review.locator(`[data-loss-play="${stage}"]`).count(), 0);
  await act('select observer A', () => review.locator('[data-loss-observer]').selectOption('PLAYER_A'));
  await act('filter 3–4-contact losses', () => review.locator(`[data-loss-filter="${stage}"]`).click());
  assert.deepEqual(await review.locator('.local-video-point-row').evaluateAll((rows) => rows.map((row) => row.dataset.pointId.split('/').at(-1))), ['p002', 'p008', 'p010']);
  assert.match(await review.locator('[data-loss-selection]').innerText(), /已筛选失分 3 \/ 当前可回看 2/);
  assert.equal(await row(8).locator('input').isDisabled(), true);
  assert.equal(await row(8).locator('[data-replay-status="SCORE_ONLY"]').count(), 1);
  assert.equal(await row(2).locator('[data-replay-status="LOCAL_SESSION_ONLY"]').count(), 1);
  assert.match(await review.locator(`[data-loss-filter="${stage}"]`).innerText(), /失 3 分｜当前本机可回看 2 段/);
  assert.match(await review.locator('[data-insight-unknown]').innerText(), /UNKNOWN：15/);

  phase = 'category playlist, slow motion and manual seek';
  await act('select 0.5x playback', () => review.locator('[data-playback-speed]').selectOption('0.5'));
  assert.equal(await review.locator('video').evaluate((video) => video.playbackRate), 0.5);
  await act('play two legal category loss clips', () => review.locator(`[data-loss-play="${stage}"]`).click());
  await page.getByText('已完成所选回合回放', { exact: true }).waitFor({ timeout: 15000 });
  assert.equal(await review.locator('video').evaluate((video) => video.currentTime >= 20.8), true);
  await act('restart category playlist', () => review.locator(`[data-loss-play="${stage}"]`).click());
  await review.locator('[data-loss-playback-pause]').waitFor();
  await act('pause category playlist', () => review.locator('[data-loss-playback-pause]').click());
  assert.equal(await review.locator('video').evaluate((video) => video.paused), true);
  await act('resume category playlist', () => review.locator('[data-loss-playback-pause]').click());
  await act('manual keyboard seek cancels category playback', () => review.getByLabel('定位视频', { exact: true }).press('Home'));
  await page.getByText('连续回放已取消', { exact: true }).waitFor();
  assert.equal(await review.locator('video').evaluate((video) => video.currentTime < 0.3 && video.paused), true);
  await act('restart to check explicit cancel', () => review.locator(`[data-loss-play="${stage}"]`).click());
  await act('cancel from the insight panel', () => review.locator('[data-loss-playback-cancel]').click());
  await page.getByText('连续回放已取消', { exact: true }).waitFor();

  phase = 'immediate edit and revoke invalidation';
  await act('open first filtered point', () => row(2).locator('.local-video-point').click());
  await act('start category playlist for revoke', () => review.locator(`[data-loss-play="${stage}"]`).click());
  await act('revoke start without saving', () => review.locator('[data-confirm-boundary="start"]').click());
  await page.getByText('连续回放已取消', { exact: true }).waitFor();
  assert.match(await review.locator('[data-loss-selection]').innerText(), /失分 3 \/ 当前可回看 1/);
  assert.equal(await row(2).locator('input').isDisabled(), true);
  assert.equal(await row(2).locator('[data-replay-status="SCORE_ONLY"]').count(), 1);
  await act('save revoked boundary', () => review.getByRole('button', { name: '保存本分', exact: true }).click());
  await act('reconfirm revoked start', () => review.locator('[data-confirm-boundary="start"]').click());
  await act('save reconfirmed point', () => review.getByRole('button', { name: '保存本分', exact: true }).click());
  await act('correct point 2 winner to A', () => review.getByLabel('得分方', { exact: true }).selectOption('PLAYER_A'));
  assert.match(await review.locator('[data-loss-selection]').innerText(), /当前可回看 1/);
  await act('save corrected winner', () => review.getByRole('button', { name: '保存本分', exact: true }).click());
  assert.deepEqual(await review.locator('.local-video-point-row').evaluateAll((rows) => rows.map((row) => row.dataset.pointId.split('/').at(-1))), ['p008', 'p010']);
  assert.match(await review.locator('[data-insight-score]').innerText(), /得分 12 \/ 失分 7/);
  await act('clear filter to restore original synthetic score', () => review.locator('[data-clear-loss-filter]').click());
  await act('reopen point 2', () => row(2).locator('.local-video-point').click());
  await act('restore B winner', () => review.getByLabel('得分方', { exact: true }).selectOption('PLAYER_B'));
  await act('confirm restored point start', () => review.locator('[data-confirm-boundary="start"]').click());
  await act('confirm restored point end', () => review.locator('[data-confirm-boundary="end"]').click());
  await act('save restored point', () => review.getByRole('button', { name: '保存本分', exact: true }).click());
  await act('restore insight category', () => review.locator(`[data-loss-filter="${stage}"]`).click());
  assert.equal(await review.locator('[data-independent-media-verified]').getAttribute('data-independent-media-verified'), '0');

  phase = 'desktop, mobile and English';
  await review.locator('[data-loss-insights]').evaluate((panel) => panel.scrollIntoView({ block: 'start' }));
  await page.screenshot({ path: path.join(qa, 'goal10-5-insight-1366x768.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  // Wait for responsive layout and scroll anchoring before capturing the actual panel.
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await review.locator('[data-loss-insights]').evaluate((panel) => window.scrollTo(0, window.scrollY + panel.getBoundingClientRect().top - 135));
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));
  const mobilePanelTop = await review.locator('[data-loss-insights]').evaluate((panel) => panel.getBoundingClientRect().top);
  assert.equal(mobilePanelTop >= 125 && mobilePanelTop < 200, true, 'mobile screenshot shows the insight controls below navigation');
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1), true);
  const targets = await review.locator('[data-loss-observer], [data-loss-filter], [data-loss-play]').evaluateAll((elements) => elements.map((element) => element.getBoundingClientRect().height));
  assert.equal(targets.every((height) => height >= 44), true);
  await page.screenshot({ path: path.join(qa, 'goal10-5-insight-390.png') });
  await act('switch English', () => page.getByRole('button', { name: 'English', exact: true }).click());
  assert.match(await review.locator('[data-insight-score]').innerText(), /Won 11 \/ Lost 8/);
  assert.match(await review.locator('[data-loss-selection]').innerText(), /Filtered points lost 3 \/ Reviewable now 2/);
  await page.screenshot({ path: path.join(qa, 'goal10-5-insight-390-en.png') });
  await act('restore Chinese', () => page.getByRole('button', { name: '中文', exact: true }).click());
  await page.setViewportSize({ width: 1366, height: 768 });
  const download = page.waitForEvent('download');
  await act('export v0.2 draft', () => review.locator('[data-export-draft]').click());
  await (await download).saveAs(exportPath);
  const exported = JSON.parse(await readFile(exportPath, 'utf8'));
  assert.equal(exported.dataset_class, 'SIMULATED_ONLY');
  assert.equal(exported.points.length, 19);
  assert.equal(exported.points.filter((point) => point.winner === 'player').length, 11);
  assert.equal(exported.points.every((point) => point.observed_tactics.third_ball_attack === 'unknown'), true);
  assert.equal(exported.video_context.source_id, null);
  assert.equal(JSON.stringify(exported).includes('blob:'), false);

  phase = 'refresh, import and no false identity restoration';
  await act('refresh', () => page.reload());
  await openPro();
  await act('import exported draft', () => review.getByLabel('导入已有 Quick Annotation JSON 草稿', { exact: true }).setInputFiles(exportPath));
  assert.equal(await review.locator('video').count(), 0);
  await selectVideo();
  await act('filter after import', () => review.locator(`[data-loss-filter="${stage}"]`).click());
  assert.match(await review.locator('[data-loss-selection]').innerText(), /已筛选失分 3 \/ 当前可回看 0/);
  assert.equal(await review.locator(`[data-loss-play="${stage}"]`).count(), 0);
  assert.equal(await review.locator('[data-independent-media-verified]').getAttribute('data-independent-media-verified'), '0');
  const stored = await page.evaluate(() => Object.keys(localStorage).filter((key) => /quick-annotation|local-video/i.test(key)));
  assert.deepEqual(stored, []);
  assert.deepEqual(errors, []);
  assert.deepEqual(consoleErrors.filter((entry) => !entry.endsWith(' @ http://127.0.0.1:4174/favicon.ico')), []);
  assert.deepEqual(failedRequests.filter((entry) => !/^GET blob:http:\/\/127\.0\.0\.1:4174\/[^ ]+: net::ERR_ABORTED$/.test(entry)), []);
  assert.deepEqual(external, []);
  assert.deepEqual(writes, []);
  const result = { status: 'PASS', simulated_only: true, actions: actions.length, elapsed_ms: Date.now() - started, final_score: '11:8', filtered_point_numbers: [2, 8, 10], replayed_point_numbers: [2, 10], unknown_stage_count: 15, independent_media_count: 0, import_playable_count: 0, browser_errors: errors, console_errors: consoleErrors, failed_requests: failedRequests, external_requests: external, write_requests: writes, annotation_storage_keys: stored, mobile_minimum_target_px: Math.min(...targets), mobile_panel_top: mobilePanelTop, export: exportPath, action_log: actions };
  await writeFile(reportPath, JSON.stringify(result, null, 2) + '\n');
  console.log(`Insight-to-video Chrome PASS: ${actions.length} actions, ${result.elapsed_ms}ms; 3 recorded category losses, 2 played at 0.5x, 0 independently verified; export/reimport unbound.`);
} catch (error) {
  const failedPage = browser?.contexts()[0]?.pages()[0];
  const visibleState = failedPage ? await failedPage.locator('.local-video-review').innerText().catch(() => '') : '';
  if (failedPage) await failedPage.screenshot({ path: path.join(qa, 'goal10-5-insight-failure.png') }).catch(() => {});
  await writeFile(reportPath, JSON.stringify({ status: 'FAIL', phase, error: String(error), visibleState, actions, errors, consoleErrors, failedRequests, external, writes }, null, 2) + '\n');
  throw error;
} finally {
  await browser?.close();
  ownedServer?.kill();
}
