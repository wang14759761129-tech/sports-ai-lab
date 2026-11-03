import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { TRAINING_REVIEW_VERSION } from '../src/training-review.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const fixturePath = process.env.PTTI_TRAINING_REVIEW_FIXTURE;
const modulePath = process.env.PTTI_PLAYWRIGHT_MODULE;
const chromePath = process.env.PTTI_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
if (!fixturePath || !existsSync(fixturePath)) throw new Error('Set PTTI_TRAINING_REVIEW_FIXTURE to the real MainDex report JSON');
if (!modulePath) throw new Error('Set PTTI_PLAYWRIGHT_MODULE to the installed Playwright index.mjs path');
if (!existsSync(chromePath)) throw new Error(`Chrome executable not found: ${chromePath}`);
const { chromium } = await import(pathToFileURL(modulePath).href);
const base = 'http://127.0.0.1:4174/';
const pageUrl = `${base}?match=${encodeURIComponent('web-match:doha-2023-ms-sf-fan-lin')}`;
const errors = [];
const externalRequests = [];
const artifactDirectory = path.join(root, '.alpha-qa');
await mkdir(artifactDirectory, { recursive: true });
const invalidFixture = path.join(artifactDirectory, 'goal081-invalid-report.json');
await writeFile(invalidFixture, '{bad json', 'utf8');
let browser;
let child;

async function ensureServer() {
  try { const response = await fetch(base); if (response.ok) return; } catch {}
  child = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--mode', 'internal-review', '--host', '127.0.0.1', '--port', '4174', '--strictPort'], { cwd: root, stdio: 'ignore', windowsHide: true, env: process.env });
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`Review server exited: ${child.exitCode}`);
    try { const response = await fetch(base); if (response.ok) return; } catch {}
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error('Review server did not start at 127.0.0.1:4174');
}

await ensureServer();
try {
  browser = await chromium.launch({ headless: true, executablePath: chromePath });
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 1100 } });
  const page = await context.newPage();
  await page.addInitScript(() => {
    const originalSetItem = Storage.prototype.setItem;
    window.__pttiStorageWrites = [];
    Storage.prototype.setItem = function (key, value) {
      window.__pttiStorageWrites.push(String(key));
      return originalSetItem.call(this, key, value);
    };
  });
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('request', (request) => {
    const url = request.url();
    if (!url.startsWith('http://127.0.0.1:') && !url.startsWith('blob:') && !url.startsWith('data:')) externalRequests.push(url);
  });
  await page.goto(pageUrl);
  await page.locator('main[data-catalog-mode="review"]').waitFor();
  await page.locator('.match-center-tabs button').nth(1).click();
  await page.getByRole('heading', { name: '导入训练比赛复盘报告' }).waitFor();
  await page.locator('[data-training-report-import] input[type=file]').setInputFiles(invalidFixture);
  await page.getByRole('alert').filter({ hasText: '报告无法载入' }).waitFor();
  await page.getByRole('heading', { name: '导入训练比赛复盘报告' }).waitFor();
  await page.locator('[data-training-report-import] input[type=file]').setInputFiles(fixturePath);
  const report = page.locator(`[data-training-report-version="${TRAINING_REVIEW_VERSION}"]`);
  await report.waitFor();
  assert.equal(await report.getAttribute('data-report-dataset-class'), 'SIMULATED_ONLY');
  await page.getByText('原创模拟数据 · SIMULATED_ONLY', { exact: true }).waitFor();
  await page.getByText('无法独立核验原始 CSV 或来源证据', { exact: true }).waitFor();
  assert.deepEqual(await page.evaluate(() => window.__pttiStorageWrites.filter((key) => key.toLowerCase().includes('training-review'))), [], 'imported private reports are not persisted in browser storage');
  assert.equal(await report.locator('input:not([type=file]), textarea, select').count(), 0, 'imported report annotation fields remain read-only');
  assert.equal(await page.locator('.training-report-table tbody tr').count(), 24, 'report opens with all source point records visible');
  const attackCard = page.locator('[data-report-metric="third_ball_attack_rate"]');
  await attackCard.click();
  assert.equal(await page.locator('.training-report-table tbody tr').count(), 18, 'third-ball filter displays the metric denominator rows');
  await attackCard.getByText('66.7%').waitFor();
  await attackCard.getByText('12/18', { exact: false }).waitFor();
  await attackCard.getByText('有效样本 20 · 缺失 2', { exact: false }).waitFor();
  const firstPointRow = page.locator('.training-report-table tbody tr').first();
  const firstPointId = await firstPointRow.getAttribute('data-report-point-id');
  await firstPointRow.getByRole('button', { name: '查看逐分字段' }).click();
  assert.equal(await page.locator('[data-selected-report-point]').getAttribute('data-selected-report-point'), firstPointId);
  await page.locator('.training-report-point-detail').getByText('CSV 记录序号', { exact: true }).waitFor();
  await page.getByText('SIMULATED_ONLY', { exact: true }).last().waitFor();
  await page.locator('[data-report-metric="key_point_player_win_rate"]').click();
  assert.equal(await page.locator('.training-report-table tbody tr').count(), 10, 'key-point rate drills to its reported candidate rows');
  await page.locator('.training-report-distributions summary').click();
  await page.locator('[data-report-metric="serve_length"]').click();
  assert.equal(await page.locator('.training-report-table tbody tr').count(), 12, 'serve distribution drills to observed serve-length rows');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载已导入报告副本' }).click();
  const download = await downloadPromise;
  assert.equal(download.suggestedFilename(), 'ptti-training-review-report-copy.json');
  const copyPath = path.join(artifactDirectory, 'goal081-imported-report-copy.json');
  await download.saveAs(copyPath);
  const original = await readFile(fixturePath, 'utf8');
  const exported = await readFile(copyPath, 'utf8');
  assert.equal(exported, original, 'downloaded local report copy preserves the selected report bytes');
  const exportedJson = JSON.parse(exported);
  assert.equal(exportedJson.report_version, TRAINING_REVIEW_VERSION);
  assert.equal(exportedJson.metrics.third_ball_attack_rate.denominator, 18);

  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    if (width !== 1440) {
      await page.getByRole('button', { name: 'English', exact: true }).click();
      await page.getByRole('heading', { name: 'Import a training review report' }).waitFor();
      await page.getByText('Third-ball attack rate', { exact: true }).waitFor();
      const englishMetrics = await page.locator('[data-report-metric="third_ball_attack_rate"]').innerText();
      assert.match(englishMetrics, /66\.7%/);
      await page.getByRole('button', { name: '中文', exact: true }).click();
      await page.getByRole('heading', { name: '导入训练比赛复盘报告' }).waitFor();
      await page.getByText('第三板进攻率', { exact: true }).waitFor();
    }
    const layout = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      page: document.documentElement.scrollWidth,
      report: document.querySelector('[data-training-report-import]')?.getBoundingClientRect().width,
      controls: [...document.querySelectorAll('[data-training-report-import] button')].map((item) => Math.round(item.getBoundingClientRect().height)),
      tableInside: document.querySelector('.training-report-table-scroll').scrollWidth >= document.querySelector('.training-report-table-scroll').clientWidth,
      overflowing: [...document.querySelectorAll('body *')].map((item) => ({ tag: item.tagName, className: typeof item.className === 'string' ? item.className : '', right: Math.round(item.getBoundingClientRect().right), width: Math.round(item.getBoundingClientRect().width) })).filter((item) => item.right > innerWidth + 1).slice(0, 8),
    }));
    assert(layout.page <= layout.viewport + 1, `page overflow at ${width}px: ${JSON.stringify(layout)}`);
    assert(layout.report <= width + 1, `report overflow at ${width}px: ${JSON.stringify(layout)}`);
    assert(layout.controls.every((height) => height >= 44), `small touch control at ${width}px: ${JSON.stringify(layout)}`);
    assert(layout.tableInside, `point table should scroll within its region at ${width}px`);
    const screenshotPath = path.join(artifactDirectory, `goal081-training-review-${width}.png`);
    await page.locator('#training-report-title').scrollIntoViewIfNeeded();
    await page.screenshot({ path: screenshotPath, animations: 'disabled' });
  }
  await page.locator('.training-report-table tbody tr').first().getByRole('button', { name: '查看逐分字段' }).click();
  await page.locator('.training-report-point-detail').screenshot({ path: path.join(artifactDirectory, 'goal081-training-review-point-trace.png'), animations: 'disabled' });
  await page.getByRole('button', { name: '清除此页报告' }).click();
  await page.getByText(/选择 ptti\.training-review\/0\.1 报告或 ptti\.training-handoff\/0\.1/).waitFor();
  assert.deepEqual(externalRequests, [], `unexpected external request: ${externalRequests.join(', ')}`);
  assert.deepEqual(errors, [], `browser errors: ${errors.join('; ')}`);
  await context.close();
  console.log('Training review Chrome PASS: imported the real MainDex JSON from a local file; reviewed metrics and denominators; drilled to point_id/CSV record/evidence and read-only 21 fields; downloaded and byte-compared a report copy; Chinese/English; 390/768/1440; 44px controls; no page overflow or external requests. Screenshots saved under .alpha-qa/goal081-training-review-*.png.');
} finally {
  await browser?.close();
  child?.kill();
}
