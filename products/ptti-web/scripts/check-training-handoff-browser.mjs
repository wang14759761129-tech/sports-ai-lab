import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { ANNOTATION_RECEIPT_VERSION, stableJson } from '../src/training-handoff.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const fixturePath = process.env.PTTI_TRAINING_HANDOFF_FIXTURE;
const reviewFixturePath = process.env.PTTI_TRAINING_REVIEW_FIXTURE;
const modulePath = process.env.PTTI_PLAYWRIGHT_MODULE;
const chromePath = process.env.PTTI_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
if (!fixturePath || !existsSync(fixturePath)) throw new Error('Set PTTI_TRAINING_HANDOFF_FIXTURE to the MainDex simulated handoff package');
if (!reviewFixturePath || !existsSync(reviewFixturePath)) throw new Error('Set PTTI_TRAINING_REVIEW_FIXTURE to the MainDex report JSON used by the same importer');
if (!modulePath || !existsSync(modulePath)) throw new Error('Set PTTI_PLAYWRIGHT_MODULE to the installed Playwright index.mjs path');
if (!existsSync(chromePath)) throw new Error(`Chrome executable not found: ${chromePath}`);
const { chromium } = await import(pathToFileURL(modulePath).href);
const base = 'http://127.0.0.1:4174/';
const pageUrl = `${base}?match=${encodeURIComponent('web-match:doha-2023-ms-sf-fan-lin')}`;
const errors = [];
const externalRequests = [];
const artifactDirectory = path.join(root, '.alpha-qa');
await mkdir(artifactDirectory, { recursive: true });
const rawPackage = await readFile(fixturePath, 'utf8');
const packageObject = JSON.parse(rawPackage);
const invalidPath = path.join(artifactDirectory, 'goal091-invalid-handoff.json');
const unknownVersionPath = path.join(artifactDirectory, 'goal091-unknown-version.json');
const receiptPath = path.join(artifactDirectory, 'goal091-qa-only-receipt.json');
await writeFile(invalidPath, '{bad json', 'utf8');
await writeFile(unknownVersionPath, JSON.stringify({ ...packageObject, package_version: 'ptti.training-handoff/9' }), 'utf8');
const first = packageObject.report.point_records[0];
const receipt = {
  receipt_version: ANNOTATION_RECEIPT_VERSION,
  package_content_sha256: createHash('sha256').update(stableJson(packageObject), 'utf8').digest('hex'),
  dataset_class: packageObject.report.dataset.dataset_class,
  review: {
    review_version: 'ptti.annotation-review/0.1',
    annotation_csv_sha256: packageObject.csv_sha256,
    reviewer_ref: 'QA_TEST_ONLY',
    reviewed_at: '2026-10-14T12:00:00+08:00',
    decisions: [{ point_id: first.point_id, annotation_row_sha256: first.annotation_row_sha256, field: 'serve_side', disposition: 'UNRESOLVED', reason: 'QA only; not a real coach review.' }],
  },
  status: 'DECLARED_NOT_INDEPENDENTLY_AUDITED',
  vision_status: 'NOT_TESTED',
  source_annotations_changed: false,
};
await writeFile(receiptPath, JSON.stringify(receipt), 'utf8');

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
    window.__pttiStoredValues = [];
    Storage.prototype.setItem = function (key, value) {
      window.__pttiStoredValues.push([String(key), String(value)]);
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
  const quality = page.locator('[data-training-quality-review]');
  const reportImport = page.locator('[data-training-report-import]');
  const packageInput = reportImport.locator('input[type=file]');
  assert.equal(await packageInput.count(), 1, 'there is one report import control before load');
  assert.equal(await reportImport.locator('.training-report-actions .button-primary').count(), 1, 'there is one report import button');
  await packageInput.setInputFiles(invalidPath);
  await page.getByRole('alert').filter({ hasText: '报告无法载入' }).waitFor();
  await packageInput.setInputFiles(unknownVersionPath);
  await page.getByRole('alert').filter({ hasText: '交接包版本不受支持' }).waitFor();
  await packageInput.setInputFiles(fixturePath);
  const loaded = page.locator(`[data-training-handoff-version="${packageObject.package_version}"]`);
  await loaded.waitFor();
  assert.equal(await loaded.getAttribute('data-quality-dataset-class'), 'SIMULATED_ONLY');
  await page.getByText('原创模拟数据 · SIMULATED_ONLY', { exact: true }).waitFor();
  await page.getByText('f5ec0fddebc5d108a89a42ce2acae0e8d8e12e6bca5fbb8d6b7df26dd9792ee0', { exact: true }).last().waitFor();
  await page.getByText('交接包内部校验通过', { exact: true }).waitFor();
  await page.getByText('无法独立核验原始视频或标注事实', { exact: true }).waitFor();
  assert.equal(await reportImport.locator('input[type=file]').count(), 2, 'one report picker plus one optional separate receipt picker after load');
  assert.equal(await page.locator('.training-handoff-finding').count(), 24, 'all 24 actual sample findings are visible');
  assert.equal(await page.locator('.training-report-table tbody tr').count(), 24, 'the existing report table is the only point index');
  assert.equal(await page.locator('.training-handoff-point-table').count(), 0, 'no duplicate point table is rendered');
  await page.locator('[data-report-metric="third_ball_attack_rate"]').waitFor();
  await page.getByText('有效分母 18 · 缺失 2', { exact: false }).waitFor();
  const firstFinding = page.locator('.training-handoff-finding').nth(1);
  const pointId = await firstFinding.locator('code').innerText();
  const selectedSourceRow = packageObject.report.point_records.find((row) => row.point_id === pointId);
  const pointBeforeClick = await page.locator('[data-selected-report-point]').getAttribute('data-selected-report-point');
  assert.notEqual(pointId, pointBeforeClick, 'test finding must navigate to a different source point');
  await firstFinding.focus();
  await page.keyboard.press('Enter');
  const detail = page.locator('[data-selected-report-point]');
  await page.waitForFunction((id) => document.querySelector('[data-selected-report-point]')?.getAttribute('data-selected-report-point') === id, pointId);
  assert.equal(await detail.getAttribute('data-selected-report-point'), pointId);
  assert.equal(await page.evaluate(() => document.activeElement?.id), 'training-report-point-detail', 'keyboard activation moves focus to the shared source detail');
  await detail.getByText('CSV 记录序号', { exact: true }).waitFor();
  assert.equal((await detail.locator('dl dd').first().innerText()).split(' · ')[0], String(selectedSourceRow.csv_record_number), 'the shared source detail shows the CSV record ordinal');
  await detail.getByText(selectedSourceRow.annotation_row_sha256, { exact: true }).waitFor();
  await detail.getByText('SIMULATED_ONLY', { exact: true }).waitFor();
  await page.getByText('交接包不含标注审计回执', { exact: false }).waitFor();
  await detail.screenshot({ path: path.join(artifactDirectory, 'goal091-shared-point-source-detail.png'), animations: 'disabled' });

  const storageContents = await page.evaluate(() => window.__pttiStoredValues);
  assert.equal(storageContents.some(([key, value]) => /training.?handoff|quality.?review/i.test(key) || value.includes('f5ec0fddebc5d108a89a42ce2acae0e8d8e12e6bca5fbb8d6b7df26dd9792ee0')), false, 'private package CSV/report must not be written to browser storage');

  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    if (width === 390) {
      await page.getByRole('button', { name: 'English', exact: true }).click();
      await page.getByRole('heading', { name: 'Manual point annotation quality review' }).waitFor();
      await page.getByText('Original simulated data · SIMULATED_ONLY', { exact: true }).waitFor();
      await page.getByRole('button', { name: '中文', exact: true }).click();
      await page.getByRole('heading', { name: '人工逐分标注质量复核' }).waitFor();
    }
    const layout = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      page: document.documentElement.scrollWidth,
      review: document.querySelector('[data-training-report-import]')?.getBoundingClientRect().width,
      buttons: [...document.querySelectorAll('[data-training-report-import] button')].filter((button) => button.getClientRects().length > 0).map((button) => Math.round(button.getBoundingClientRect().height)),
      issueScroll: document.querySelector('.training-handoff-finding-list')?.scrollHeight >= document.querySelector('.training-handoff-finding-list')?.clientHeight,
      internalTableScroll: document.querySelector('.training-handoff-table-scroll')?.scrollWidth >= document.querySelector('.training-handoff-table-scroll')?.clientWidth,
    }));
    assert(layout.page <= layout.viewport + 1, `page overflows at ${width}px: ${JSON.stringify(layout)}`);
    assert(layout.review <= width + 1, `quality review overflows at ${width}px: ${JSON.stringify(layout)}`);
    assert(layout.buttons.every((height) => height >= 44), `touch target below 44px at ${width}px: ${JSON.stringify(layout)}`);
    assert(layout.issueScroll, `review queue should remain internally scrollable at ${width}px`);
    assert(layout.internalTableScroll, `table must scroll inside its own region at ${width}px`);
    const screenshotPath = path.join(artifactDirectory, `goal091-quality-review-${width}.png`);
    await page.locator('#training-quality-title').scrollIntoViewIfNeeded();
    await page.screenshot({ path: screenshotPath, animations: 'disabled' });
  }
  await page.setViewportSize({ width: 390, height: 1000 });
  await page.locator('.training-handoff-findings').scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(artifactDirectory, 'goal091-quality-review-queue-390.png'), animations: 'disabled' });
  const receiptInput = quality.locator('input[type=file]');
  await receiptInput.setInputFiles(receiptPath);
  await page.locator(`[data-review-receipt="${ANNOTATION_RECEIPT_VERSION}"]`).waitFor();
  await page.getByText('QA_TEST_ONLY', { exact: true }).waitFor();
  await page.getByText('DECLARED_NOT_INDEPENDENTLY_AUDITED', { exact: true }).last().waitFor();
  await page.getByText('QA only; not a real coach review.').waitFor().catch(() => {});

  const handoffDownloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载已导入交接包副本' }).click();
  const handoffDownload = await handoffDownloadPromise;
  assert.equal(handoffDownload.suggestedFilename(), 'ptti-training-quality-handoff-copy.json');
  const handoffCopyPath = path.join(artifactDirectory, 'goal091-handoff-copy.json');
  await handoffDownload.saveAs(handoffCopyPath);
  assert.equal(await readFile(handoffCopyPath, 'utf8'), rawPackage, 'downloaded handoff copy preserves selected private package bytes exactly');
  await page.getByRole('button', { name: '清除此页报告' }).click();
  await page.getByText(/选择 ptti\.training-review\/0\.1 报告或 ptti\.training-handoff\/0\.1/).waitFor();
  await reportImport.locator('input[type=file]').setInputFiles(reviewFixturePath);
  await page.locator(`[data-training-report-version="${packageObject.report.report_version}"]`).waitFor();
  assert.equal(await page.locator('[data-training-quality-review]').count(), 0, 'plain reports still work in the same importer without the handoff panel');
  assert.deepEqual(externalRequests, [], `unexpected external request: ${externalRequests.join(', ')}`);
  assert.deepEqual(errors, [], `browser errors: ${errors.join('; ')}`);
  await context.close();
  console.log('Training handoff Chrome PASS: one existing report importer accepted both the read-only MainDex 24-point SIMULATED_ONLY handoff and plain report; verified CSV SHA and review findings; keyboard-located point_id/CSV record/row hash in the existing source detail; imported a clearly QA-only receipt; kept private package out of browser storage; Chinese/English; 390/768/1440; 44px controls; no duplicate point table, page overflow, or external requests. Screenshots saved under .alpha-qa/goal091-quality-review-*.png.');
} finally {
  await browser?.close();
  child?.kill();
}
