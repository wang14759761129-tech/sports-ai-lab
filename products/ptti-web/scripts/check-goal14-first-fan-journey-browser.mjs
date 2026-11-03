import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';

const base = new URL('../', import.meta.url);
const runId = new Date().toISOString().replace(/[:.]/g, '-');
const evidence = new URL(`.alpha-qa/goal14-first-fan-journey/${runId}/`, base);
await mkdir(evidence, { recursive: true });
const candidateHead = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: fileURLToPath(base), encoding: 'utf8', windowsHide: true }).trim();
const candidateStatus = execFileSync('git', ['status', '--porcelain'], { cwd: fileURLToPath(base), encoding: 'utf8', windowsHide: true }).trim();
const started = Date.now();
const actions = [];
const errors = [];
const httpFailures = [];
const externalPageErrors = [];
const externalHttpFailures = [];
const mainPageExternalRequests = [];
const popupResponses = [];
const memorySamples = [];
const screenshots = [];
let resolveRuntimeGuard;
const runtimeGuardPromise = new Promise((resolve) => { resolveRuntimeGuard = resolve; });
let status = 'NOT_TESTED';
let appStatus = 'NOT_TESTED';
let phase = 'preflight';
let browser;
let runtimeGuardTimer;
let minRamGiB = Infinity;
let health = null;
let reportError = null;
let officialWatchEvidence = {
  explicit_user_click: false,
  official_link_open: 'NOT_TESTED',
  final_url: null,
  navigation_urls: [],
  official_page_domcontentloaded: 'NOT_TESTED',
  official_page_load_result: 'NOT_TESTED',
  official_page_load_error: null,
  page_http_status: null,
  video_playback: 'NOT_TESTED',
};

function availableRamGiB() {
  const value = Number(execFileSync('powershell', ['-NoProfile', '-Command', '(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'], { encoding: 'utf8', windowsHide: true }).trim()) / 1048576;
  return Number(value.toFixed(3));
}

function sampleRam(label, minimum = 2.5) {
  const availableGiB = availableRamGiB();
  memorySamples.push({ label, at: new Date().toISOString(), availableGiB });
  minRamGiB = Math.min(minRamGiB, availableGiB);
  if (!Number.isFinite(availableGiB) || availableGiB < minimum) {
    const error = new Error(`RAM guard: ${availableGiB.toFixed(3)} GiB < ${minimum.toFixed(1)} GiB at ${label}`);
    error.code = 'RESOURCE_BLOCKED';
    throw error;
  }
  return availableGiB;
}

async function guarded(label, action) {
  phase = label;
  sampleRam(`before:${label}`);
  const result = await Promise.race([
    action(),
    runtimeGuardPromise.then((error) => { throw error; }),
  ]);
  sampleRam(`after:${label}`);
  actions.push(label);
  return result;
}

function startRuntimeRamGuard() {
  const check = () => {
    try {
      sampleRam('runtime-monitor', 2.5);
    } catch (error) {
      clearInterval(runtimeGuardTimer);
      runtimeGuardTimer = undefined;
      reportError = `BLOCKED during ${phase}: ${error.message}`;
      status = 'BLOCKED';
      resolveRuntimeGuard(error);
      if (browser) void browser.close().catch((closeError) => errors.push(`browser-close-after-ram-guard: ${closeError.message}`));
    }
  };
  check();
  if (status !== 'BLOCKED') runtimeGuardTimer = setInterval(check, 1000);
}

async function screenshot(page, name) {
  phase = `screenshot:${name}`;
  sampleRam(`before:${phase}`);
  await Promise.race([
    page.screenshot({ path: fileURLToPath(new URL(name, evidence)) }),
    runtimeGuardPromise.then((error) => { throw error; }),
  ]);
  sampleRam(`after:${phase}`);
  screenshots.push(name);
  actions.push(phase);
}

async function assertNoHorizontalOverflow(page, label) {
  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  assert(dimensions.document <= dimensions.viewport + 1 && dimensions.body <= dimensions.viewport + 1,
    `${label} overflows horizontally: ${JSON.stringify(dimensions)}`);
}

async function assertActionable(locator, label) {
  assert.equal(await locator.isVisible(), true, `${label} must be visible`);
  assert.equal(await locator.isEnabled(), true, `${label} must be enabled`);
}

async function attachNetworkDiagnostics(targetPage, scope) {
  const cdp = await targetPage.context().newCDPSession(targetPage);
  await cdp.send('Network.enable');
  const requestDiagnostics = new Map();
  cdp.on('Network.requestWillBeSent', ({ requestId, request, type, initiator }) => {
    requestDiagnostics.set(requestId, {
      url: request.url,
      resource_type: type ?? null,
      initiator_type: initiator?.type ?? null,
      initiator_stack: (initiator?.stack?.callFrames ?? []).slice(0, 5).map((frame) => ({
        url: frame.url,
        function_name: frame.functionName,
        line_number: frame.lineNumber,
        column_number: frame.columnNumber,
      })),
    });
  });
  cdp.on('Network.responseReceived', ({ requestId, response, type }) => {
    if (response.status >= 400) {
      (scope === 'ptti-app' ? httpFailures : externalHttpFailures).push({
        scope,
        ...(requestDiagnostics.get(requestId) ?? { url: response.url, initiator_type: null, initiator_stack: [] }),
        status: response.status,
        resource_type: type ?? null,
      });
    }
  });
}

async function writeReport() {
  const value = {
    status,
    elapsed_ms: Date.now() - started,
    phase,
    candidate_worktree_head: candidateHead,
    candidate_worktree_clean_at_test_start: candidateStatus.length === 0,
    goal15_strict_public_contract: 'ptti.match-library-index/0.1',
    goal15_source_commit: 'eb0a52af32eaaf26dfd39cf1ce5f321e24a1adac',
    goal15_strict_public_bytes_sha256: '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930',
    main_schema_sha256: '4d10c5cee7b2ac5c8bb533c71887ddf88431976ebc2d2b055b8e8b6e0ca05415',
    playback_routing_head: 'b54e1546b7e6c1edc69406582ed68e90988a1910',
    health,
    actions,
    app_status: appStatus,
    third_party_page_load_status: officialWatchEvidence.official_page_load_result,
    screenshots,
    errors,
    http_failures: httpFailures,
    external_page_errors: externalPageErrors,
    external_http_failures: externalHttpFailures,
    mainPageExternalRequests,
    official_watch_evidence: officialWatchEvidence,
    memorySamples,
    minimum_available_ram_gib: Number.isFinite(minRamGiB) ? minRamGiB : null,
    independent_media_playback: 'NOT_TESTED',
    real_user_test: 'NOT_TESTED',
    error: reportError,
  };
  await writeFile(new URL('browser-report.json', evidence), `${JSON.stringify(value, null, 2)}\n`, 'utf8');
  await writeFile(new URL('interaction.log', evidence), `${actions.map((item, index) => `${index + 1}. ${item}`).join('\n')}\n${reportError ? `ERROR: ${reportError}\n` : ''}`, 'utf8');
}

try {
  assert.equal(candidateStatus, '', 'The browser candidate must be a committed, clean worktree');
  for (let sample = 1; sample <= 3; sample++) {
    sampleRam(`preflight-${sample}-of-3`, 3.0);
    if (sample < 3) await new Promise((resolve) => setTimeout(resolve, 10000));
  }
  if (!process.env.PTTI_PLAYWRIGHT_MODULE) throw new Error('PTTI_PLAYWRIGHT_MODULE is not set for this process');
  const { chromium } = await import(pathToFileURL(process.env.PTTI_PLAYWRIGHT_MODULE).href);
  sampleRam('immediately-before-browser-launch', 3.0);
  browser = await chromium.launch({ executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true });
  sampleRam('after-browser-launch');
  startRuntimeRamGuard();
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, acceptDownloads: true });
  const page = await context.newPage();
  page.setDefaultTimeout(8000);
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push({
      type: 'console',
      text: message.text(),
      location: message.location(),
    });
  });
  page.on('request', (request) => {
    const url = request.url();
    if (!url.startsWith('http://127.0.0.1:4183/') && !/^(blob:|data:)/.test(url)) mainPageExternalRequests.push(url);
  });
  context.on('page', (popup) => {
    popup.on('framenavigated', (frame) => {
      if (frame === popup.mainFrame()) officialWatchEvidence.navigation_urls.push(frame.url());
    });
    popup.on('response', (response) => {
      const observed = { url: response.url(), status: response.status() };
      popupResponses.push(observed);
      if (response.status() >= 400) externalHttpFailures.push({ scope: 'official-external', ...observed });
    });
    popup.on('console', (message) => {
      if (message.type() === 'error') externalPageErrors.push({ text: message.text(), location: message.location() });
    });
    popup.on('pageerror', (error) => externalPageErrors.push({ type: 'pageerror', text: error.message }));
  });
  await attachNetworkDiagnostics(page, 'ptti-app');

  await guarded('open 4183 Fan Cinema', async () => {
    await page.goto('http://127.0.0.1:4183/', { waitUntil: 'domcontentloaded' });
    await page.locator('[data-fan-welcome]').waitFor();
    await page.locator('[data-fan-mode="cinema"] [data-fan-counts]').waitFor();
  });
  await guarded('check Chinese desktop navigation labels stay on one row', async () => {
    await assertNoHorizontalOverflow(page, 'Chinese desktop Cinema');
    const navRows = await page.locator('.primary-nav .nav-link').evaluateAll((links) => links.map((link) => ({
      top: Math.round(link.getBoundingClientRect().top),
      height: Math.round(link.getBoundingClientRect().height),
      noWrap: getComputedStyle(link).whiteSpace === 'nowrap',
    })));
    assert(navRows.every((item) => item.height <= 46 && item.noWrap));
    assert.equal(new Set(navRows.map((item) => item.top)).size, 1, 'Desktop navigation labels must remain on one row');
  });
  health = await guarded('verify candidate and Main admission health', async () => {
    const response = await page.request.get('http://127.0.0.1:4183/__ptti/goal14/health.json');
    assert.equal(response.status(), 200);
    const value = await response.json();
    assert.equal(value.san_git_head_current, candidateHead);
    assert.equal(value.mode, 'INTERNAL_REVIEW_LOCAL_ONLY');
    assert.equal(value.service_startup.goal14.public_admission_source_commit, 'e38a3ec3243f7d5e47381cdb5b77a78e5220e05b');
    assert.equal(value.service_startup.goal14.public_admission_sha256, '1e42763dadbb491b439939ee31d3473241f5efa243a1e7a2f3cc9d3f967013b2');
    assert.equal(value.service_startup.goal15_pin.main_source_commit, 'eb0a52af32eaaf26dfd39cf1ce5f321e24a1adac');
    assert.equal(value.service_startup.goal15_pin.catalog_sha256, '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930');
    assert.equal(value.current_strict_public_catalog.sha256, '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930');
    assert.equal(value.current_strict_public_catalog.consumer_validation, 'PASS');
    assert.equal(value.current_strict_public_catalog.startup_pin_match, true);
    assert.equal(value.current_strict_public_catalog.counts.matches, 5);
    assert.equal(value.current_strict_public_catalog.counts.sources, 15);
    assert.equal(value.current_strict_public_catalog.counts.stars, 8);
    assert.equal(value.current_strict_public_catalog.counts.event_highlight_claims, 10);
    assert.equal(value.current_strict_public_catalog.counts.clip_claims, 0);
    assert.equal(value.playback_core, 'b54e1546b7e6c1edc69406582ed68e90988a1910');
    return value;
  });
  const publicCatalog = await guarded('verify five matches, fifteen official sources and eight public stars', async () => {
    const response = await page.request.get('http://127.0.0.1:4183/data/match-library-strict-public.json');
    assert.equal(response.status(), 200);
    const raw = await response.body();
    assert.equal(createHash('sha256').update(raw).digest('hex'), '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930');
    const data = JSON.parse(raw.toString('utf8'));
    assert.equal(data.contract_version, 'ptti.match-library-index/0.1');
    assert.equal(data.view, 'STRICT_PUBLIC');
    assert.equal(data.matches.length, 5);
    assert.equal(data.video_sources.length, 15);
    assert.equal(data.stars.length, 8);
    assert.equal(data.video_sources.filter((source) => source.match_link_status === 'HUMAN_VERIFIED').length, 5);
    assert.equal(data.video_sources.filter((source) => source.content_type_claim === 'HIGHLIGHTS').length, 10);
    assert.equal(data.video_sources.filter((source) => source.content_type_claim === 'CLIP').length, 0);
    return data;
  });
  await guarded('confirm separate GOAL14 public fan projection remains empty', async () => {
    const data = await (await page.request.get('http://127.0.0.1:4183/data/goal14-fan-content-strict-public.json')).json();
    assert.equal(data.view, 'STRICT_PUBLIC');
    assert.deepEqual(data.events, []);
    assert.deepEqual(data.stars, []);
    assert.deepEqual(data.content_candidates, []);
  });
  await guarded('confirm raw internal review file is not served', async () => {
    assert.equal((await page.request.get('http://127.0.0.1:4183/.alpha-qa/goal14/fan-content-delivery-internal-review.json')).status(), 404);
  });

  await screenshot(page, 'cinema-zh-1366x768.png');
  await guarded('search Chinese name 王楚钦', async () => {
    await page.locator('[data-fan-mode="cinema"] .fan-search input').fill('王楚钦');
    await page.locator('[data-athlete-id="athlete:121558"]').waitFor();
    assert.equal(await page.locator('[data-public-match-id="pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"]').count(), 1);
  });
  await guarded('open Wang Chuqin exact-ID Stars profile', async () => {
    await page.locator('[data-athlete-id="athlete:121558"]').click();
    await page.locator('[data-fan-star-detail]').waitFor();
    assert.equal(await page.locator('[data-fan-star-detail]').locator('#fan-star-title').innerText(), '王楚钦');
    assert.equal(await page.locator('[data-fan-star-detail] .fan-profile-matches [data-public-match-id="pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"]').count(), 1);
    assert.match(await page.locator('[data-fan-star-detail]').innerText(), /中国大满贯|China Smash 2025/);
    await assertNoHorizontalOverflow(page, 'Chinese desktop Stars');
  });
  await screenshot(page, 'stars-zh-1366x768.png');
  await guarded('open linked China Smash 2025 final by stable IDs', async () => {
    await page.locator('[data-fan-star-detail] .fan-profile-matches [data-public-match-id="pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"] .button-outline').first().click();
    await page.locator('[data-fan-match-detail]').waitFor();
    assert.equal(await page.locator('[data-public-match-id="pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"]').count(), 1);
    assert.match(await page.locator('[data-fan-match-detail]').innerText(), /决赛|Final/);
  });
  await guarded('open Watch route for exact Main source ID', async () => {
    await page.locator('[data-fan-match-detail] [data-public-source-id="video-source:youtube:0QgbtsBWZhk"] button').filter({ hasText: '查看观看方式' }).click();
    const linkedMatch = page.locator('[data-fan-watch-detail] [data-linked-match-id="pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"]');
    await linkedMatch.waitFor();
    assert.equal(await linkedMatch.count(), 1, 'Watch view must contain the exact linked Main match ID');
    const details = page.locator('[data-fan-watch-detail]');
    assert.equal(await details.locator('a.button-primary').getAttribute('href'), 'https://www.youtube.com/watch?v=0QgbtsBWZhk');
    assert.equal(await details.locator('a.button-primary').getAttribute('target'), '_blank');
    assert.match(await details.innerText(), /尚未验证|Current playback not tested|NOT_TESTED/);
    assert.match(await details.innerText(), /中国大满贯|China Smash 2025/);
    await assertNoHorizontalOverflow(page, 'Chinese desktop Watch');
  });
  await screenshot(page, 'watch-zh-1366x768.png');
  await guarded('verify external link opens only after explicit click', async () => {
    const link = page.locator('[data-fan-watch-detail] a.button-primary');
    assert.equal(await link.getAttribute('rel'), 'noopener noreferrer');
    let external;
    try {
      const popupPromise = page.waitForEvent('popup', { timeout: 8000 });
      await link.click();
      officialWatchEvidence.explicit_user_click = true;
      external = await popupPromise;
      officialWatchEvidence.official_link_open = 'POPUP_OPENED';
      try {
        await external.waitForURL(/^https:\/\/(?:www\.)?youtube\.com\/watch\?v=0QgbtsBWZhk(?:&|$)/, { timeout: 10000, waitUntil: 'commit' });
      } catch (error) {
        officialWatchEvidence.official_link_open = 'FAIL';
        officialWatchEvidence.official_link_error = error.message;
        officialWatchEvidence.final_url = external.url();
        throw error;
      }
      officialWatchEvidence.final_url = external.url();
      officialWatchEvidence.official_link_open = 'PASS';
      try {
        await external.waitForLoadState('domcontentloaded', { timeout: 10000 });
        officialWatchEvidence.official_page_domcontentloaded = 'PASS';
        officialWatchEvidence.official_page_load_result = 'PASS';
      } catch (error) {
        // A third-party load timeout is evidence about that page only; continue the PTTI checks.
        officialWatchEvidence.official_page_domcontentloaded = 'NOT_TESTED';
        officialWatchEvidence.official_page_load_result = 'TIMEOUT';
        officialWatchEvidence.official_page_load_error = error.message;
      }
      assert.equal(officialWatchEvidence.final_url, 'https://www.youtube.com/watch?v=0QgbtsBWZhk');
      const pageResponse = popupResponses.find((response) => response.url === officialWatchEvidence.final_url)
        ?? popupResponses.find((response) => response.url.includes('youtube.com/watch'));
      officialWatchEvidence.page_http_status = pageResponse?.status ?? null;
      assert.equal(officialWatchEvidence.video_playback, 'NOT_TESTED');
    } finally {
      if (external && !external.isClosed()) {
        try {
          await external.close();
          officialWatchEvidence.test_popup_cleanup = 'PASS';
        } catch (error) {
          officialWatchEvidence.test_popup_cleanup = 'FAIL';
          officialWatchEvidence.popup_cleanup_error = error.message;
        }
      } else if (!external) {
        officialWatchEvidence.test_popup_cleanup = 'NO_TEST_POPUP_OPENED';
      }
    }
  });
  await guarded('after third-party popup cleanup, PTTI Watch context remains intact', async () => {
    assert.equal(officialWatchEvidence.test_popup_cleanup, 'PASS');
    assert.equal(await page.locator('[data-fan-watch-detail] [data-linked-match-id="pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"]').count(), 1);
    assert.equal(await page.locator('[data-fan-watch-detail] a.button-primary').getAttribute('href'), 'https://www.youtube.com/watch?v=0QgbtsBWZhk');
  });
  await guarded('return from Watch to same Stars and match context', async () => {
    await page.locator('[data-fan-watch-detail] > button').click();
    await page.locator('[data-fan-mode="stars"] [data-fan-match-detail]').waitFor();
    assert.equal(await page.locator('[data-fan-mode="stars"] [data-public-match-id="pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"]').count(), 1);
  });
  await guarded('keep full match out of Clips and show clear empty-state guidance', async () => {
    await page.locator('.primary-nav button').filter({ hasText: 'Clips' }).click();
    await page.locator('[data-fan-mode="clips"] [data-clips-empty]').waitFor();
    assert.equal(await page.locator('[data-fan-mode="clips"] [data-public-source-id]').count(), 0);
    assert.match(await page.locator('[data-fan-mode="clips"]').innerText(), /完整比赛/);
    const emptyActions = page.locator('[data-fan-mode="clips"] .fan-empty-actions button');
    assert.equal(await emptyActions.count(), 3);
    const admittedMatchAction = page.locator('[data-fan-mode="clips"] [data-fan-open-match-id="pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"]');
    await assertActionable(admittedMatchAction, 'Clips empty-state exact admitted match action');
    await assertActionable(emptyActions.nth(2), 'Clips empty-state demo action');
    await assertNoHorizontalOverflow(page, 'Chinese desktop Clips');
  });
  await screenshot(page, 'clips-zh-1366x768.png');
  await guarded('Clips empty state opens the exact admitted match and returns to Clips', async () => {
    await page.locator('[data-fan-mode="clips"] [data-fan-open-match-id="pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"]').click();
    await page.locator('[data-fan-mode="cinema"] [data-fan-match-detail][data-public-match-id="pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"]').waitFor();
    await page.locator('.primary-nav button').filter({ hasText: 'Clips' }).click();
    await page.locator('[data-fan-mode="clips"] [data-clips-empty]').waitFor();
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await guarded('check Chinese mobile width and capture', async () => {
    await assertNoHorizontalOverflow(page, 'Chinese mobile Clips');
    const navRows = await page.locator('.primary-nav .nav-link').evaluateAll((links) => links.map((link) => ({
      top: Math.round(link.getBoundingClientRect().top),
      height: Math.round(link.getBoundingClientRect().height),
      noWrap: getComputedStyle(link).whiteSpace === 'nowrap',
    })));
    assert(navRows.every((item) => item.height <= 46 && item.noWrap));
  });
  await screenshot(page, 'clips-zh-390x844.png');
  await guarded('check and capture Chinese mobile Cinema, Stars and Watch actions', async () => {
    await page.locator('.primary-nav button').filter({ hasText: '首页' }).click();
    const search = page.locator('[data-fan-mode="cinema"] .fan-search input');
    await assertActionable(search, 'Cinema search');
    await search.fill('王楚钦');
    const star = page.locator('[data-athlete-id="athlete:121558"]');
    await assertActionable(star, 'Stars profile action');
    await assertNoHorizontalOverflow(page, 'Chinese mobile Cinema');
  });
  await screenshot(page, 'cinema-zh-390x844.png');
  await page.locator('[data-athlete-id="athlete:121558"]').click();
  await page.locator('[data-fan-star-detail]').waitFor();
  await assertNoHorizontalOverflow(page, 'Chinese mobile Stars');
  await screenshot(page, 'stars-zh-390x844.png');
  await page.locator('[data-fan-star-detail] .fan-profile-matches [data-public-match-id="pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"] .button-outline').first().click();
  await page.locator('[data-fan-match-detail]').waitFor();
  await page.locator('[data-fan-match-detail] [data-public-source-id="video-source:youtube:0QgbtsBWZhk"] button').filter({ hasText: '查看观看方式' }).click();
  await page.locator('[data-fan-watch-detail]').waitFor();
  await guarded('check and capture Chinese mobile Watch action', async () => {
    await assertActionable(page.locator('[data-fan-watch-detail] a.button-primary'), 'Official source link');
    await assertNoHorizontalOverflow(page, 'Chinese mobile Watch');
  });
  await screenshot(page, 'watch-zh-390x844.png');
  await guarded('switch to English and verify same catalog', async () => {
    await page.getByRole('button', { name: 'English', exact: true }).click();
    assert.equal(await page.evaluate(() => document.documentElement.lang), 'en');
    await page.locator('.primary-nav button').filter({ hasText: 'Home' }).click();
    await page.locator('[data-fan-mode="cinema"] .fan-search input').fill('Felix');
    await page.locator('[data-athlete-id="athlete:135977"]').waitFor();
    assert.match(await page.locator('[data-fan-mode="cinema"]').innerText(), /Felix LEBRUN/);
    await assertNoHorizontalOverflow(page, 'English desktop Cinema');
  });
  await page.setViewportSize({ width: 1366, height: 768 });
  await guarded('check English desktop navigation labels stay on one row', async () => {
    const navRows = await page.locator('.primary-nav .nav-link').evaluateAll((links) => links.map((link) => ({
      top: Math.round(link.getBoundingClientRect().top),
      height: Math.round(link.getBoundingClientRect().height),
      noWrap: getComputedStyle(link).whiteSpace === 'nowrap',
    })));
    assert(navRows.every((item) => item.height <= 46 && item.noWrap));
    assert.equal(new Set(navRows.map((item) => item.top)).size, 1, 'Desktop navigation labels must remain on one row');
  });
  await screenshot(page, 'cinema-en-1366x768.png');
  await page.setViewportSize({ width: 390, height: 844 });
  await guarded('check English mobile Cinema navigation and document width', async () => {
    await assertNoHorizontalOverflow(page, 'English mobile Cinema');
    const navRows = await page.locator('.primary-nav .nav-link').evaluateAll((links) => links.map((link) => ({
      height: Math.round(link.getBoundingClientRect().height),
      noWrap: getComputedStyle(link).whiteSpace === 'nowrap',
    })));
    assert(navRows.every((item) => item.height <= 46 && item.noWrap));
  });
  await screenshot(page, 'cinema-en-390x844.png');
  await page.setViewportSize({ width: 1366, height: 768 });
  await guarded('verify the real English Clips empty state and keep full-match source out', async () => {
    await page.locator('.primary-nav button').filter({ hasText: 'Clips' }).click();
    await page.locator('[data-fan-mode="clips"] [data-clips-empty]').waitFor();
    assert.equal(await page.locator('[data-fan-mode="clips"] [data-public-source-id]').count(), 0);
    assert.match(await page.locator('[data-fan-mode="clips"]').innerText(), /No short clips/);
    assert.match(await page.locator('[data-fan-mode="clips"]').innerText(), /0 short clips/);
    const emptyActions = page.locator('[data-fan-mode="clips"] .fan-empty-actions button');
    assert.equal(await emptyActions.count(), 3);
    const admittedMatchAction = page.locator('[data-fan-mode="clips"] [data-fan-open-match-id="pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"]');
    await assertActionable(admittedMatchAction, 'English Clips empty-state exact admitted match action');
    await assertActionable(emptyActions.nth(2), 'English Clips empty-state demo action');
    await assertNoHorizontalOverflow(page, 'English desktop Clips');
  });
  await screenshot(page, 'clips-en-1366x768.png');
  await guarded('English Clips action opens the exact admitted match and returns to Clips', async () => {
    await page.locator('[data-fan-mode="clips"] [data-fan-open-match-id="pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"]').click();
    await page.locator('[data-fan-mode="cinema"] [data-fan-match-detail][data-public-match-id="pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"]').waitFor();
    await page.locator('.primary-nav button').filter({ hasText: 'Clips' }).click();
    await page.locator('[data-fan-mode="clips"] [data-clips-empty]').waitFor();
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await guarded('check English mobile Clips empty state and width', async () => {
    await assertNoHorizontalOverflow(page, 'English mobile Clips');
    assert.match(await page.locator('[data-fan-mode="clips"]').innerText(), /No short clips/);
  });
  await screenshot(page, 'clips-en-390x844.png');
  await page.setViewportSize({ width: 1366, height: 768 });
  await guarded('open the same official match in English Watch', async () => {
    await page.locator('.primary-nav button').filter({ hasText: 'Home' }).click();
    await page.locator('[data-fan-mode="cinema"] .fan-search input').fill('Felix');
    await page.locator('[data-athlete-id="athlete:135977"]').waitFor();
    await page.locator('[data-athlete-id="athlete:135977"]').click();
    await page.locator('[data-fan-star-detail]').waitFor();
    await page.locator('[data-fan-star-detail] .fan-profile-matches [data-public-match-id="pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"] .button-outline').first().click();
    await page.locator('[data-fan-match-detail]').waitFor();
    await page.locator('[data-fan-match-detail] [data-public-source-id="video-source:youtube:0QgbtsBWZhk"] button').filter({ hasText: 'View watch options' }).click();
    await page.locator('[data-fan-watch-detail]').waitFor();
    assert.equal(await page.locator('[data-fan-watch-detail] a.button-primary').getAttribute('href'), publicCatalog.video_sources[0].official_url);
    await assertNoHorizontalOverflow(page, 'English desktop Watch');
  });
  await screenshot(page, 'watch-en-1366x768.png');
  await page.setViewportSize({ width: 390, height: 844 });
  await guarded('check English mobile layout and capture', async () => {
    await assertNoHorizontalOverflow(page, 'English mobile Watch');
    await assertActionable(page.locator('[data-fan-watch-detail] a.button-primary'), 'English official source link');
    const navRows = await page.locator('.primary-nav .nav-link').evaluateAll((links) => links.map((link) => ({
      height: Math.round(link.getBoundingClientRect().height),
      noWrap: getComputedStyle(link).whiteSpace === 'nowrap',
    })));
    assert(navRows.every((item) => item.height <= 46 && item.noWrap));
  });
  await screenshot(page, 'watch-en-390x844.png');
  for (const language of ['中文', 'English']) {
    await guarded(`Gold editorial pages in ${language}`, async () => {
      await page.getByRole('button', { name: language, exact: true }).click();
      for (const width of [1366, 390]) {
        await page.setViewportSize({ width, height: width === 390 ? 844 : 768 });
        await page.locator('.primary-nav button').nth(0).click();
        await page.locator('[data-fan-welcome]').waitFor();
        await assertNoHorizontalOverflow(page, `Gold Cinema ${language} ${width}`);
        await screenshot(page, `gold-cinema-${language === '中文' ? 'zh' : 'en'}-${width}.png`);
        await page.locator('.primary-nav button').nth(2).click();
        assert.equal(await page.locator('[data-fan-mode="stars"] [data-athlete-id]').count(), 8);
        await assertNoHorizontalOverflow(page, `Gold Stars ${language} ${width}`);
        await screenshot(page, `gold-stars-${language === '中文' ? 'zh' : 'en'}-${width}.png`);
        await page.locator('.footer-universe-links button').filter({ hasText: language === '中文' ? '赛事高光' : 'Event highlights' }).click();
        assert.equal(await page.locator('[data-official-highlights-page] [data-public-source-id]').count(), 10);
        await assertNoHorizontalOverflow(page, `Gold Highlights ${language} ${width}`);
        await screenshot(page, `gold-highlights-${language === '中文' ? 'zh' : 'en'}-${width}.png`);
      }
    });
  }
  await page.setViewportSize({ width: 1366, height: 768 });
  await guarded('Gold save, follow, My Corner and removal use exact public IDs', async () => {
    await page.locator('.primary-nav button').nth(0).click();
    const save = page.locator('.fan-hero-actions .button-quiet');
    await save.click();
    assert.equal(await save.getAttribute('aria-pressed'), 'true');
    await page.locator('.primary-nav button').nth(2).click();
    const star = page.locator('.fan-star-card-wrap').filter({ has: page.locator('[data-athlete-id="athlete:121558"]') });
    await star.locator('.fan-follow-control').click();
    await page.locator('.header-corner').click();
    const saved = page.locator('[data-saved-match-id="pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"]');
    await saved.waitFor();
    assert.equal(await saved.locator('.fan-artwork').count(), 1);
    assert.equal(await page.locator('[data-followed-athlete-id="athlete:121558"]').count(), 1);
    await screenshot(page, 'gold-my-corner-en-1366.png');
    await saved.getByRole('button', { name: 'Remove saved match', exact: true }).click();
    await page.locator('[data-followed-athlete-id="athlete:121558"]').getByRole('button', { name: 'Unfollow', exact: true }).click();
    assert.equal(await page.locator('[data-saved-match-id]').count(), 0);
    assert.equal(await page.locator('[data-followed-athlete-id]').count(), 0);
  });
  await guarded('Gold training note survives refresh, edits, and real JSON download', async () => {
    const openTrain = async () => page.locator('.footer-universe-links button').filter({ hasText: /^Train$/ }).click();
    await openTrain();
    let notes = page.locator('[data-note-kind="training"]');
    await notes.getByRole('button', { name: 'Add training note', exact: true }).click();
    await notes.locator('input[name="topic"]').fill('QA original observation');
    await notes.locator('textarea[name="summary"]').fill('I will observe the next rally. <script>plain text</script>');
    await notes.getByRole('button', { name: 'Save training note', exact: true }).click();
    await page.reload({ waitUntil: 'domcontentloaded' });
    await openTrain();
    notes = page.locator('[data-note-kind="training"]');
    assert.match(await notes.innerText(), /QA original observation/);
    await notes.getByRole('button', { name: 'Edit', exact: true }).click();
    await notes.locator('textarea[name="summary"]').fill('Edited personal observation; not a system diagnosis.');
    await notes.getByRole('button', { name: 'Save training note', exact: true }).click();
    const downloadPromise = page.waitForEvent('download');
    await page.locator('[data-universe-page="train"] .universe-backup').getByRole('button', { name: 'Export JSON backup', exact: true }).click();
    const download = await downloadPromise;
    const exportPath = fileURLToPath(new URL('gold-fan-local-backup.json', evidence));
    await download.saveAs(exportPath);
    const exported = JSON.parse(await readFile(exportPath, 'utf8'));
    assert.equal(exported.contract_version, 'ptti.fan-local-data/2');
    assert.equal(exported.training_notes[0].summary, 'Edited personal observation; not a system diagnosis.');
    for (const key of ['training_notes', 'match_notes', 'coach_notes', 'fan_notes']) assert(Array.isArray(exported[key]));
    await screenshot(page, 'gold-train-en-1366.png');
  });
  await guarded('confirm PTTI app has no page errors, HTTP failures or unintended external requests', async () => {
    assert.deepEqual(errors, []);
    assert.deepEqual(httpFailures, []);
    assert.deepEqual(mainPageExternalRequests, []);
  });
  sampleRam('before-pass-finalization');
  appStatus = 'PASS';
  status = 'PASS';
} catch (error) {
  reportError = `${error?.code === 'RESOURCE_BLOCKED' ? 'BLOCKED' : 'FAIL'} at ${phase}: ${error?.stack ?? error}`;
  status = error?.code === 'RESOURCE_BLOCKED' ? 'BLOCKED' : 'FAIL';
  appStatus = status;
} finally {
  clearInterval(runtimeGuardTimer);
  if (browser) {
    try { await browser.close(); } catch (error) { errors.push(`browser-close: ${error.message}`); }
  }
  await writeReport();
}

const summary = JSON.parse(await readFile(new URL('browser-report.json', evidence), 'utf8'));
console.log(`GOAL14 Fan journey Chrome ${summary.status}: ${summary.actions.length} actions, ${summary.elapsed_ms}ms; min RAM ${summary.minimum_available_ram_gib ?? 'NOT_SAMPLED'} GiB; evidence ${fileURLToPath(evidence)}`);
if (summary.error) { console.error(summary.error); process.exitCode = summary.status === 'BLOCKED' ? 2 : 1; }
