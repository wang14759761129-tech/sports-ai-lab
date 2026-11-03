import { consumeReadonlyProjection } from '../src/readonly-catalog.mjs';
import { consumeFanCatalog } from '../src/fan-catalog.mjs';
import assert from 'node:assert/strict';
import { readdir, readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { DEMO_BUNDLE_URL, validateDemoRecord } from '../src/pro-demo.mjs';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const distRoot = path.join(projectRoot, 'dist');

async function collectFiles(directory, prefix = '') {
  const result = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const relative = path.posix.join(prefix, entry.name);
    if (entry.isSymbolicLink()) throw new Error(`Symlink is not allowed in preview output: ${relative}`);
    if (entry.isDirectory()) result.push(...await collectFiles(path.join(directory, entry.name), relative));
    else if (entry.isFile()) result.push(relative);
    else throw new Error(`Unexpected filesystem entry in preview output: ${relative}`);
  }
  return result;
}

const files = (await collectFiles(distRoot)).sort();
assert(files.includes('_headers'), 'Cloudflare Pages _headers is missing from dist/');
assert(files.includes('index.html'), 'Production index.html is missing from dist/');
assert(files.includes('favicon.svg'), 'The app-owned PTTI favicon referenced by index.html is missing from dist/');
assert(files.includes('data/web-strict-public.json'), 'Public match source data is missing from dist/');
assert(files.includes('data/match-library-strict-public.json'), 'Strict public library missing');
assert(files.includes('data/goal14-fan-content-strict-public.json'), 'GOAL14 strict public fan projection is missing');
assert(files.includes(DEMO_BUNDLE_URL.slice(1)), 'SIMULATED_ONLY Pro demo bundle is missing from dist/');
for (const file of files) {
  const allowed = file === '_headers'
    || file === 'index.html'
    || file === 'favicon.svg'
    || file === 'data/web-strict-public.json'
    || file === 'data/match-library-strict-public.json'
    || file === 'data/goal14-fan-content-strict-public.json'
    || file === DEMO_BUNDLE_URL.slice(1)
    || /^assets\/index-[\w-]+\.(?:js|css)$/.test(file);
  assert(allowed, `Unexpected file in public preview package: ${file}`);
  assert(!/\.(?:sqlite3?|db|mp4|m4v|mov|webm|mkv|pem|key|p12|pfx|env)$/i.test(file), `Private/binary asset is not allowed: ${file}`);
}

const contentsByFile = await Promise.all(files.map(async (file) => {
  const contents = await readFile(path.join(distRoot, file), 'utf8');
  const { size } = await stat(path.join(distRoot, file));
  assert(size < 25 * 1024 * 1024, `Cloudflare Pages file-size limit exceeded: ${file}`);
  return [file, contents];
}));
const contents = new Map(contentsByFile);
const allText = contentsByFile.map(([, value]) => value).join('\n');
for (const [label, pattern] of [
  ['private key block', /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/],
  ['OpenAI project key', /sk-proj-[A-Za-z0-9_-]{20,}/],
  ['Google API key', /AIza[0-9A-Za-z_-]{30,}/],
  ['Cloudflare API token assignment', /(?:CLOUDFLARE_API_TOKEN|CF_API_TOKEN)\s*[:=]\s*["']?[A-Za-z0-9_-]{20,}/i],
]) assert(!pattern.test(allText), `Potential ${label} found in dist/`);

const headers = contents.get('_headers');
const csp = headers.match(/^\s*Content-Security-Policy:\s*(.+)$/mi)?.[1] ?? '';
assert(csp, 'CSP header is missing from _headers');
for (const directive of ["default-src 'self'", "script-src 'self'", "style-src 'self'", "connect-src 'self'", "frame-src 'none'", "media-src 'none'"]) {
  assert(csp.includes(directive), `CSP is missing required directive: ${directive}`);
}
assert(!/\b(?:unsafe-inline|unsafe-eval)\b/.test(csp), 'CSP must not allow unsafe inline code or eval');

const html = contents.get('index.html');
assert(!/<(?:iframe|video|audio)\b/i.test(html), 'Preview HTML must not embed external media');
assert(!/\son[a-z]+\s*=/i.test(html), 'Inline event handlers are not allowed in preview HTML');
for (const [, assetUrl] of html.matchAll(/<(?:script|link)\b[^>]*(?:src|href)=["']([^"']+)["'][^>]*>/gi)) {
  assert(!/^https?:\/\//i.test(assetUrl), `Production page references a remote script/stylesheet: ${assetUrl}`);
}
assert(!/<(?:img|iframe|video|audio)\b/i.test(allText), 'Preview bundle contains an embedded image/media/frame element');

const contract = JSON.parse(contents.get('data/web-strict-public.json'));
const publicCatalog = consumeReadonlyProjection(contract);
const goal14Public = JSON.parse(contents.get('data/goal14-fan-content-strict-public.json'));
assert.equal(goal14Public.contract_version, 'ptti.fan-content-intelligence/0.1', 'GOAL14 public projection contract mismatch');
assert.equal(goal14Public.view, 'STRICT_PUBLIC', 'GOAL14 public projection must remain strict-public');
for (const collection of ['source_manifest', 'evidence_sources', 'events', 'stars', 'content_candidates', 'relationships']) {
  assert.deepEqual(goal14Public[collection], [], `GOAL14 strict-public ${collection} must remain empty until explicit admission`);
}
assert.deepEqual(goal14Public.quality_summary, {
  event_count: 0,
  star_count: 0,
  candidate_count: 0,
  exact_video_url_count: 0,
  event_page_only_count: 0,
  playback_pass_count: 0,
  public_eligible_count: 0,
  match_video_links: 0,
  status_counts: { playback_NOT_TESTED: 0, rights_UNKNOWN: 0, public_INTERNAL_ONLY: 0 },
}, 'GOAL14 strict-public summary must stay at zero');
assert.match(goal14Public.notice, /must not fall back to INTERNAL_REVIEW/i, 'GOAL14 public notice must forbid internal fallback');
const matchLibrary = JSON.parse(contents.get('data/match-library-strict-public.json'));
const fanCatalog = consumeFanCatalog(matchLibrary);
assert.deepEqual([fanCatalog.matches.length, fanCatalog.sources.length, fanCatalog.stars.length], [1, 1, 2]);
assert.equal(fanCatalog.matches[0].match_id, 'pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun');
assert.deepEqual(fanCatalog.matches[0].recorded_result, { player_a_games: 4, player_b_games: 0 });
assert.equal(fanCatalog.sources[0].url, 'https://www.youtube.com/watch?v=0QgbtsBWZhk');
assert.equal(fanCatalog.sources[0].thumbnail_display, 'NOT_ALLOWED');
assert.equal(fanCatalog.sources[0].embedding, 'UNKNOWN');
assert.equal(fanCatalog.sources[0].recorded_playback_status, 'EMBED_BLOCKED_HISTORICAL');
let internalIdScan = 'NOT_TESTED: candidate internal-review QA fixture is absent';
try {
  const internal = JSON.parse(await readFile(path.join(projectRoot, '.alpha-qa/match-library/internal-review.json'), 'utf8'));
  const admittedSourceIds = new Set(fanCatalog.sources.map((source) => source.source_id));
  for (const source of internal.video_sources) assert(!allText.includes(source.source_id) || admittedSourceIds.has(source.source_id), `Non-admitted internal source leaked into production: ${source.source_id}`);
  internalIdScan = `PASS: ${internal.video_sources.length} internal source IDs checked; only strict-public admitted IDs may overlap`;
} catch (error) { if (error.code !== 'ENOENT') throw error; }
assert.equal(publicCatalog.matches.length, contract.matches.length, 'strict package must not contain rejected matches');
assert.equal(publicCatalog.matches.reduce((n,m) => n + m.sources.length,0), contract.video_sources.length, 'strict package must not contain unauthorized sources');
assert.equal(publicCatalog.matches.length, 0, 'Legacy source feed remains empty; the separate GOAL14 Match Library is the only admitted Fan dataset');
const proDemo = JSON.parse(contents.get(DEMO_BUNDLE_URL.slice(1)));
assert.equal(validateDemoRecord(proDemo).ok, true, 'Pro package sample must match the validated MainDex contract');
assert.equal(proDemo.dataset.dataset_class, 'SIMULATED_ONLY');
assert.equal(proDemo.points.length, 24);
assert(proDemo.points.every((point) => point.match_id === proDemo.dataset.match_id), 'Pro points must stay in the synthetic identity namespace');
assert.deepEqual(proDemo.dataset.source_binding, { status: 'NOT_APPLICABLE_SIMULATED', source_id: null, source_sha256: null, timeline_id: null, time_base: null });
assert(!JSON.stringify(proDemo).includes('web-match:') && !JSON.stringify(proDemo).includes('Fan Zhendong'), 'synthetic demo must not carry real match/player identity');
assert(!allText.includes('web-match:doha-2023') && !allText.includes('web-source:doha-2023'), 'internal review records must not be bundled');
assert(!files.some(name => /internal-review|cinema.json|alpha-qa/.test(name)), 'review and legacy fixture files must be absent');
const totalBytes = contentsByFile.reduce((sum, [file]) => sum + Buffer.byteLength(contents.get(file)), 0);
console.log(`Preview package PASS: ${files.length} static files, ${(totalBytes / 1024).toFixed(1)} KiB total.`);
console.log(`Files: ${files.join(', ')}`);
console.log('Headers: _headers present; same-origin CSP and static security directives verified (HTTP response not tested).');
console.log('Privacy/content: legacy strict feed remains empty and separate; GOAL14 Match Library has 1 admitted match, 1 official external source, and 2 linked athletes. Pro static JSON remains a validated 24-point SIMULATED_ONLY bundle with null source binding; no database, video, credentials, remote script/style, embed, or unapproved cover was found.');
console.log(`Internal source-ID comparison: ${internalIdScan}.`);
