import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { computeDemoStats, computeDemoSummary, DEMO_BUNDLE_URL, MATCH_INTELLIGENCE_CONTRACT } from '../src/pro-demo.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const reviewBase = 'http://127.0.0.1:4174/';
const publicBase = 'http://127.0.0.1:4175/';
const matchId = 'web-match:doha-2023-ms-sf-fan-lin';
const modulePath = process.env.PTTI_PLAYWRIGHT_MODULE;
if (!modulePath) throw new Error('Set PTTI_PLAYWRIGHT_MODULE to the installed Playwright index.mjs path');
const { chromium } = await import(pathToFileURL(modulePath).href);
const chromePath = process.env.PTTI_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
if (!existsSync(chromePath)) throw new Error(`Chrome executable not found: ${chromePath}`);
const fixture = JSON.parse(await readFile(new URL(`../public${DEMO_BUNDLE_URL}`, import.meta.url), 'utf8'));
const startingStats = computeDemoStats(fixture.points);
const startingSummary = computeDemoSummary(fixture.points);
const started = [];

async function ready(url, expectedMode, child) {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    if (child?.exitCode !== null && child?.exitCode !== undefined) throw new Error(`Vite exited with ${child.exitCode}`);
    try { const response = await fetch(url); if (response.ok) return; } catch {}
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Local ${expectedMode} server did not start at ${url}`);
}

async function ensureServer(url, args, mode) {
  try { const response = await fetch(url); if (response.ok) return null; } catch {}
  const child = spawn(process.execPath, ['node_modules/vite/bin/vite.js', ...args], { cwd: root, stdio: 'ignore', windowsHide: true, env: process.env });
  started.push(child);
  await ready(url, mode, child);
  return child;
}

await ensureServer(reviewBase, ['--mode', 'internal-review', '--host', '127.0.0.1', '--port', '4174', '--strictPort'], 'review');
await ensureServer(publicBase, ['--host', '127.0.0.1', '--port', '4175', '--strictPort'], 'public');

let browser;
const outsideRequests = [];
const pageErrors = [];
try {
  browser = await chromium.launch({ headless: true, executablePath: chromePath });
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 390, height: 844 } });
  const errorPage = await context.newPage();
  errorPage.on('pageerror', (error) => pageErrors.push(error.message));
  let bundleRequests = 0;
  await errorPage.route(`**${DEMO_BUNDLE_URL}`, async (route) => {
    bundleRequests += 1;
    if (bundleRequests <= 2) await route.fulfill({ status: 200, contentType: 'application/json', body: '{broken json' });
    else await route.continue();
  });
  await errorPage.goto(publicBase);
  await errorPage.locator('main[data-catalog-mode="public"]').waitFor();
  await errorPage.locator('.primary-nav .nav-link').filter({ hasText: '专业分析' }).click();
  await errorPage.getByRole('alert').filter({ hasText: '演示 JSON 暂不可用' }).waitFor();
  assert.equal(await errorPage.locator('.match-card').count(), 0, 'bad demo JSON does not fall back to real catalog rows');
  await errorPage.getByRole('button', { name: '重试加载' }).click();
  await errorPage.locator(`[data-contract-version="${MATCH_INTELLIGENCE_CONTRACT}"]`).waitFor();
  assert.equal(bundleRequests, 3, 'retry recovers from malformed demo JSON');
  await errorPage.close();

  const page = await context.newPage();
  page.on('response', (response) => { if (response.status() >= 400) console.error(`Browser HTTP ${response.status()}: ${response.url()}`); });
  page.on('request', (request) => {
    const url = request.url();
    if (!url.startsWith('http://127.0.0.1:') && !url.startsWith('data:') && !url.startsWith('blob:')) outsideRequests.push(url);
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));
  await page.goto(`${reviewBase}?match=${encodeURIComponent(matchId)}`);
  await page.locator('main[data-catalog-mode="review"]').waitFor();
  await page.locator(`[data-match-id="${matchId}"]`).waitFor();
  assert.equal(await page.locator('.watch-source-card .match-actions a').getAttribute('href'), 'https://www.youtube.com/watch?v=qIXmFTzXcs0');
  await page.locator('.detail-evidence summary').click();
  assert((await page.locator('[data-permission]').allTextContents()).some((status) => status.trim() === 'UNKNOWN'), 'unknown Bridge rights stay unknown in Fan view');
  await page.locator('.detail-evidence summary').click();
  assert.equal(await page.locator('.match-center-tabs button').count(), 2);
  assert.equal(await page.locator('.download-match-card').count(), 1, 'Fan view retains PNG sharing');
  const pngDownloadPromise = page.waitForEvent('download');
  await page.locator('.download-match-card').click();
  const pngDownload = await pngDownloadPromise;
  assert.match(pngDownload.suggestedFilename(), /\.png$/);

  await page.locator('.match-center-tabs button').nth(1).click();
  await page.getByRole('heading', { name: '逐分分析工作台' }).waitFor();
  await page.locator(`[data-contract-version="${MATCH_INTELLIGENCE_CONTRACT}"]`).waitFor();
  assert.equal(await page.locator('[data-demo-match-id]').getAttribute('data-demo-match-id'), 'SIMULATED_ONLY:goal07-match-001');
  assert.equal(await page.locator('[data-dataset-class]').getAttribute('data-dataset-class'), 'SIMULATED_ONLY');
  assert.equal(await page.locator('.pro-points-table tbody tr').count(), 24, 'the point-by-point table renders every source row');
  assert.equal(await page.locator('[data-lineage-method]').innerText(), 'DETERMINISTIC_ORIGINAL_GENERATOR');
  assert.equal(await page.locator('.pro-source-panel').getByText('SIMULATED_ONLY', { exact: true }).count(), 1, 'evidence remains explicitly simulated');
  await page.getByText('这场真实比赛尚无逐分标注数据').waitFor();
  assert.equal(Number(await page.locator('[data-stat="third-yes"]').innerText()), startingStats.thirdBall.yes);
  assert.equal(Number(await page.locator('[data-stat="third-no"]').innerText()), startingStats.thirdBall.no);

  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    const metrics = await page.evaluate(() => ({
      width: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      targets: [...document.querySelectorAll('.match-center-tabs button, .pro-point-picker select, .pro-fields select, .pro-actions .button, .pro-row-edit')].map((element) => Math.round(element.getBoundingClientRect().height)),
      tableScrollsWithinPanel: document.querySelector('.pro-table-scroll').scrollWidth >= document.querySelector('.pro-table-scroll').clientWidth,
    }));
    assert(metrics.scrollWidth <= metrics.width + 1, `horizontal overflow at ${width}px: ${JSON.stringify(metrics)}`);
    assert(metrics.targets.every((height) => height >= 44), `undersized control at ${width}px: ${JSON.stringify(metrics)}`);
    assert(metrics.tableScrollsWithinPanel, `the row table must remain in its own responsive viewport at ${width}px`);
    await page.getByRole('button', { name: 'English', exact: true }).click();
    await page.getByRole('heading', { name: 'Point-by-point analysis workspace' }).waitFor();
    await page.getByRole('heading', { name: 'Point-by-point annotations' }).waitFor();
    assert.equal(await page.locator('[data-stat="third-yes"]').innerText(), String(startingStats.thirdBall.yes));
    await page.getByRole('button', { name: '中文', exact: true }).click();
    await page.getByRole('heading', { name: '逐分分析工作台' }).waitFor();
  }

  const pointPicker = page.getByLabel('选择要标注的分数');
  const serveDistributionBefore = await page.locator('[data-stat="serve-length-counts"]').innerText();
  await pointPicker.focus();
  await pointPicker.press('ArrowDown');
  assert.equal(await pointPicker.inputValue(), '1:2', 'point selection supports keyboard navigation');
  await pointPicker.press('Home');
  assert.equal(await pointPicker.inputValue(), '1:1');
  const serveLength = page.getByLabel('发球长度', { exact: true });
  await serveLength.selectOption('long');
  await page.getByLabel('第三板进攻', { exact: true }).selectOption('no');
  assert.equal(Number(await page.locator('[data-stat="third-yes"]').innerText()), startingStats.thirdBall.yes - 1, 'visible totals recalculate from edited source rows');
  assert.equal(Number(await page.locator('[data-stat="third-no"]').innerText()), startingStats.thirdBall.no + 1);
  assert.equal(await page.locator('[data-stat="third-rate"]').innerText(), `${(((startingStats.thirdBall.yes - 1) / startingStats.thirdBall.classified) * 100).toFixed(1)}%`);
  assert((await page.locator('.pro-baseline-note').innerText()).includes('66.7%'), 'original baseline is displayed alongside actual current calculations');
  assert.notEqual(await page.locator('[data-stat="serve-length-counts"]').innerText(), serveDistributionBefore, 'serve distribution updates from the edited source row');
  await page.getByText('有尚未保存的更改；统计已按当前页面中的记录更新。').waitFor();
  await page.locator('.match-center-tabs button').first().click();
  await page.locator('.match-center-tabs button').nth(1).click();
  assert.equal(Number(await page.locator('[data-stat="third-yes"]').innerText()), startingStats.thirdBall.yes - 1, 'Fan/Pro switching preserves current edits');
  await page.getByRole('button', { name: '保存本机演示记录' }).click();
  await page.getByText('已保存到此浏览器本机；没有上传。').waitFor();
  assert.equal(await page.locator('[data-dataset-class]').getAttribute('data-dataset-class'), 'SIMULATED_ONLY');
  assert.equal(await page.locator('[data-lineage-method]').innerText(), 'SIMULATED_INTERACTIVE_EDIT');
  assert.match(await page.locator('[data-lineage-sha]').innerText(), /^[0-9a-f]{64}$/);
  await page.locator('[data-lineage-parent]').waitFor();
  assert.equal(await page.locator('.pro-edit-history li').count(), 4, 'all changed fields, including dependent explicit resets, appear in lineage');

  const jsonDownloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '导出 JSON' }).click();
  const jsonDownload = await jsonDownloadPromise;
  assert.equal(jsonDownload.suggestedFilename(), 'ptti-match-intelligence-simulated-demo-export.json');
  const artifactDirectory = path.join(root, '.alpha-qa');
  await mkdir(artifactDirectory, { recursive: true });
  const jsonPath = path.join(artifactDirectory, 'goal072-simulated-analysis-export.json');
  await jsonDownload.saveAs(jsonPath);
  const exported = JSON.parse(await readFile(jsonPath, 'utf8'));
  assert.deepEqual(Object.keys(exported).sort(), ['analysis', 'export_format', 'input', 'lineage']);
  assert.equal(exported.export_format, 'ptti.web-match-intelligence-export/0.1');
  assert.deepEqual(Object.keys(exported.input).sort(), ['contract_version', 'dataset', 'points']);
  assert.equal(exported.input.contract_version, MATCH_INTELLIGENCE_CONTRACT);
  assert.equal(exported.input.dataset.dataset_class, 'SIMULATED_ONLY');
  assert.equal(exported.input.dataset.provenance.method, 'SIMULATED_INTERACTIVE_EDIT');
  assert.match(exported.input.dataset.provenance.parent_input_sha256, /^[0-9a-f]{64}$/);
  assert.equal(exported.input.points.length, 24);
  assert.equal(exported.input.points[0].serve_length, 'long');
  assert.equal(exported.input.points[0].third_ball_attack, 'no');
  assert.equal(exported.input.points[0].third_ball_side, 'not_applicable');
  assert.equal(exported.input.points[0].third_ball_outcome, 'not_applicable');
  assert.equal(exported.analysis.dataset.dataset_class, 'SIMULATED_ONLY');
  assert.equal(exported.analysis.summary.point_count, 24);
  assert.equal(exported.analysis.summary.third_ball_attack_rate.denominator, startingStats.thirdBall.classified);
  assert(exported.lineage.snapshots.length >= 2);
  assert(!JSON.stringify(exported).includes('web-match:'));
  assert(!JSON.stringify(exported).includes('Fan Zhendong'));

  await page.getByRole('button', { name: 'English', exact: true }).click();
  await page.getByRole('heading', { name: 'Point-by-point analysis workspace' }).waitFor();
  await page.reload();
  await page.locator('.primary-nav .nav-link').filter({ hasText: 'Pro analysis' }).click();
  await page.getByRole('heading', { name: 'Point-by-point analysis workspace' }).waitFor();
  await page.locator('[data-stat="third-yes"]').waitFor();
  assert.equal(await page.getByRole('button', { name: 'English', exact: true }).getAttribute('aria-pressed'), 'true', 'English preference survives refresh');
  assert.equal(await page.locator('[data-lineage-method]').innerText(), 'SIMULATED_INTERACTIVE_EDIT');
  assert.equal(await page.locator('.pro-point-picker select').inputValue(), '1:1');
  assert.equal(await page.locator('[data-stat="third-rate"]').innerText(), `${(((startingStats.thirdBall.yes - 1) / startingStats.thirdBall.classified) * 100).toFixed(1)}%`);
  await context.close();

  const publicContext = await browser.newContext({ acceptDownloads: true, viewport: { width: 390, height: 844 } });
  await publicContext.addInitScript(() => {
    Object.defineProperty(Storage.prototype, 'getItem', { configurable: true, value() { throw new DOMException('blocked', 'SecurityError'); } });
    Object.defineProperty(Storage.prototype, 'setItem', { configurable: true, value() { throw new DOMException('blocked', 'SecurityError'); } });
  });
  const publicPage = await publicContext.newPage();
  publicPage.on('pageerror', (error) => pageErrors.push(error.message));
  publicPage.on('request', (request) => {
    const url = request.url();
    if (!url.startsWith('http://127.0.0.1:') && !url.startsWith('data:') && !url.startsWith('blob:')) outsideRequests.push(url);
  });
  await publicPage.goto(publicBase);
  await publicPage.locator('main[data-catalog-mode="public"]').waitFor();
  assert.equal(await publicPage.locator('.match-card').count(), 0, 'strict-public catalog remains empty');
  await publicPage.locator('.primary-nav .nav-link').filter({ hasText: '专业分析' }).click();
  await publicPage.getByRole('heading', { name: '逐分分析工作台' }).waitFor();
  assert.equal(await publicPage.locator('[data-dataset-class]').getAttribute('data-dataset-class'), 'SIMULATED_ONLY');
  await publicPage.getByLabel('发球长度', { exact: true }).selectOption('short');
  assert.match(await publicPage.locator('[data-stat="serve-length-counts"]').innerText(), new RegExp(`短球 ${startingSummary.serve_distributions.serve_length.counts.short + 1} \\(`));
  await publicPage.getByRole('button', { name: '保存本机演示记录' }).click();
  await publicPage.getByText('本页已更新，但浏览器存储不可用；关闭页面后这些改动不会保留。').waitFor();
  assert.equal(await publicPage.locator('main[data-catalog-mode="public"] .match-card').count(), 0);
  await publicContext.close();

  assert.deepEqual(outsideRequests, [], `unexpected remote requests: ${outsideRequests.join(', ')}`);
  assert.deepEqual(pageErrors, [], `browser page errors: ${pageErrors.join('; ')}`);
  console.log('Pro browser PASS: Fan keeps deep-linked exact official URL and PNG share; Pro renders all 24 rows and source evidence; editing changes Python-matched metrics, saves a SHA-linked derived chain, exports input+analysis+lineage; zh/en and locale persistence; strict-public catalog remains 0; blocked storage is explicit; 390/768/1440, keyboard selection, responsive table containment and 44px controls; no page overflow, remote requests or page errors.');
} finally {
  await browser?.close();
  for (const child of started) child.kill();
}
