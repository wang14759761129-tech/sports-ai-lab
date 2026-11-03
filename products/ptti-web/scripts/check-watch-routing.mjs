import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { evaluateFanWatchRoutes } from '../src/fan-watch-routing.mjs';
import { consumeFanCatalog } from '../src/fan-catalog.mjs';
import { readFile } from 'node:fs/promises';

const playbackRoot = resolve(process.cwd(), '../../../playback-recovery-sprint-0-3');
const playbackPackage = resolve(playbackRoot, 'products/ptti/playback-core');
const corePath = join(playbackPackage, 'src/index.ts');
const routingPath = join(playbackPackage, 'adapters/watchRoutingContract.ts');
const pinnedHead = 'b54e1546b7e6c1edc69406582ed68e90988a1910';
const sha256 = async (path) => createHash('sha256').update(await readFile(path)).digest('hex');
const actualHead = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: playbackRoot, encoding: 'utf8', windowsHide: true });
assert.equal(actualHead.status, 0, actualHead.stderr);
assert.equal(actualHead.stdout.trim(), pinnedHead, 'Playback worktree HEAD must match the reviewed routing handoff');
assert.equal(await sha256(corePath), 'a59df06b688d75885bfb8ed51364e73edbaedaaa2b3746b5f7fd1d1edf67caf2', 'Playback Core src must remain at the 304eb661 source bytes');
assert.equal(await sha256(routingPath), '1fa1e6100eb85f56cc51819d1e0cffaef500d6fa96bba616f6b281d60bb51619', 'Watch-routing adapter source bytes changed');

const temp = await mkdtemp(join(tmpdir(), 'ptti-watch-route-'));
try {
  const tsc = resolve(process.cwd(), 'node_modules/typescript/bin/tsc');
  const compile = spawnSync(process.execPath, [tsc, routingPath, '--target', 'ES2022', '--module', 'ES2022', '--strict', '--skipLibCheck', '--outDir', temp], { encoding: 'utf8', windowsHide: true });
  assert.equal(compile.status, 0, compile.stdout + compile.stderr);
  await writeFile(join(temp, 'package.json'), '{"type":"module"}');
  const compiledPath = join(temp, 'watchRoutingContract.js');
  const contract = await import(pathToFileURL(compiledPath));
  const actualPublic = JSON.parse(await readFile(new URL('../public/data/match-library-strict-public.json', import.meta.url), 'utf8'));
  const catalog = consumeFanCatalog(actualPublic);
  assert.deepEqual([catalog.matches.length, catalog.stars.length, catalog.sources.length], [5, 8, 15], 'Consume the pinned Goal15 Main strict-public package');
  assert.equal(catalog.sources.filter((source) => source.match_link_status === 'HUMAN_VERIFIED').length, 5, 'Only the five exact Main match-source edges are associated');
  assert.equal(catalog.matches[0].match_id, 'pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun');
  assert.deepEqual(catalog.matches[0].video_source_ids, ['video-source:youtube:0QgbtsBWZhk']);
  const admittedSource = catalog.sources[0];
  const admittedRoutes = evaluateFanWatchRoutes(admittedSource, contract.evaluateWatchRoute);
  const admittedPage = admittedRoutes.find((row) => row.mode === 'OFFICIAL_PAGE');
  assert.equal(admittedPage.decision.state, 'ELIGIBLE', 'The scoped official external URL may be offered');
  assert.equal(admittedPage.url, 'https://www.youtube.com/watch?v=0QgbtsBWZhk');
  assert.equal(admittedPage.decision.playbackEvidence, 'NOT_TESTED');
  assert.equal(admittedRoutes.find((row) => row.mode === 'OFFICIAL_EMBED').decision.state, 'BLOCKED');
  assert.equal(admittedRoutes.find((row) => row.mode === 'AUTHORIZED_SOURCE').decision.state, 'BLOCKED');
  assert.equal(admittedRoutes.find((row) => row.mode === 'REPLAY').decision.state, 'BLOCKED');
  assert.equal(admittedRoutes.find((row) => row.mode === 'LIVE_SCORE').decision.state, 'BLOCKED');
  const unverifiedAdmission = evaluateFanWatchRoutes({ ...admittedSource, source_identity_status: 'UNKNOWN' }, contract.evaluateWatchRoute);
  assert.equal(unverifiedAdmission.find((row) => row.mode === 'OFFICIAL_PAGE').decision.state, 'BLOCKED');
  assert.equal(unverifiedAdmission.find((row) => row.mode === 'OFFICIAL_PAGE').url, null);

  const eligibleFixture = {
    source_id: 'test-source-only', url: 'https://www.youtube.com/watch?v=abc123', watch_entry: 'OPEN_OFFICIAL_PLATFORM_URL',
    source_identity_status: 'VERIFIED', publisher_identity_status: 'VERIFIED', source_verified_at: '2026-10-18T00:00:00Z', external_viewing: 'ALLOWED', embedding: 'UNKNOWN',
  };
  const routes = evaluateFanWatchRoutes(eligibleFixture, contract.evaluateWatchRoute);
  assert.deepEqual(routes.map((row) => row.mode), ['OFFICIAL_EMBED', 'OFFICIAL_PAGE', 'AUTHORIZED_SOURCE', 'REPLAY', 'LIVE_SCORE']);
  const page = routes.find((row) => row.mode === 'OFFICIAL_PAGE');
  assert.equal(page.decision.state, 'ELIGIBLE');
  assert.equal(page.decision.playbackEvidence, 'NOT_TESTED', 'An eligible official page does not assert playback');
  assert.equal(page.url, eligibleFixture.url);
  assert.equal(Object.keys(page.decision).sort().join(','), 'contract,mode,playbackEvidence,reason,state', 'Decision must not contain URLs or media identity');
  assert.equal(routes.find((row) => row.mode === 'AUTHORIZED_SOURCE').decision.state, 'BLOCKED', 'No authorized stream grant exists in Match Library v0.1');
  assert.equal(routes.find((row) => row.mode === 'REPLAY').decision.state, 'BLOCKED', 'No authorized replay grant exists in Match Library v0.1');
  assert.equal(routes.find((row) => row.mode === 'LIVE_SCORE').decision.state, 'BLOCKED', 'No score route exists in Match Library v0.1');

  const unknownRights = evaluateFanWatchRoutes({ ...eligibleFixture, external_viewing: 'UNKNOWN' }, contract.evaluateWatchRoute);
  assert.equal(unknownRights.find((row) => row.mode === 'OFFICIAL_PAGE').decision.reason, 'VIEW_PERMISSION_UNKNOWN');
  assert.equal(unknownRights.find((row) => row.mode === 'OFFICIAL_PAGE').url, null, 'Unknown permission never leaks an open link');
  const unverifiedSource = evaluateFanWatchRoutes({ ...eligibleFixture, source_identity_status: 'RECORDED_NOT_REVERIFIED' }, contract.evaluateWatchRoute);
  assert.equal(unverifiedSource.find((row) => row.mode === 'OFFICIAL_PAGE').decision.reason, 'SOURCE_REFERENCE_UNVERIFIED');
  assert.equal(unverifiedSource.find((row) => row.mode === 'OFFICIAL_PAGE').url, null);
  const embedAllowed = evaluateFanWatchRoutes({ ...eligibleFixture, embedding: 'ALLOWED' }, contract.evaluateWatchRoute);
  assert.equal(embedAllowed.find((row) => row.mode === 'OFFICIAL_EMBED').decision.state, 'ELIGIBLE');
  assert.equal(embedAllowed.find((row) => row.mode === 'OFFICIAL_EMBED').url, null, 'Only official-page route is opened here; no second player is created');

  assert.equal(contract.classifyWatchFailure({ source: 'HTTP', status: 403 }).code, 'HTTP_FORBIDDEN');
  assert.notEqual(contract.classifyWatchFailure({ source: 'HTTP', status: 403 }).code, 'REGION_RESTRICTED');
  assert.equal(contract.classifyWatchFailure({ source: 'PROVIDER', condition: 'REGION_RESTRICTED' }).code, 'REGION_RESTRICTED');
  console.log('Fan watch routing: pinned Playback identities PASS; Goal15 strict-public 5/15/8 package consumed; 5 exact match-source edges preserved; official external page remains NOT_TESTED for playback; unsafe routes remain blocked.');
} finally {
  await rm(temp, { recursive: true, force: true });
}
