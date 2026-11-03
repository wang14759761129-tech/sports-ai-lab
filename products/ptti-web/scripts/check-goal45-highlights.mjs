import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { consumeFanCatalog, filterFanClips, filterFanHighlights, searchFanCatalog } from '../src/fan-catalog.mjs';
import { applyMatchExperienceDelta, mergeMatchExperienceDelta, validateMatchExperienceDelta, MATCH_EXPERIENCE_SHA, MATCH_EXPERIENCE_BASE_SHA } from '../src/match-experience-delta.mjs';
import { applyGoal17MatchAdditions } from '../src/goal17-match-additions.mjs';
import { applyFanInspiration } from '../src/fan-inspiration.mjs';
import { buildFanWatchRouteCandidates } from '../src/fan-watch-routing.mjs';
import { createCollectorCards, removeCollectorMatch } from '../src/collector-lounge.mjs';
import { emptyFanLocalData } from '../src/fan-local-data.mjs';
import { fanLocationUrl, readFanLocation } from '../src/fan-location.mjs';
import { createFanWatchReturn, restoreFanWatchReturn } from '../src/fan-navigation.mjs';

const root = new URL('../', import.meta.url);
const read = (file) => readFile(new URL(file, root));
const hash = (bytes) => createHash('sha256').update(bytes).digest('hex');
const bytes = await read('public/data/goal27-match-experience-delta-v0.1.json');
assert.equal(hash(bytes), MATCH_EXPERIENCE_SHA);
assert.equal(hash(await read('src/contracts/match-experience-delta-v0.1.schema.json')), 'd8ad35d79bbfcc61042fc2fef6b39d772cee6b3543aad1b144f120cc985ed45a');
const delta = JSON.parse(bytes);
validateMatchExperienceDelta(delta);
const baseBytes = await read('public/data/match-library-strict-public.json');
assert.equal(hash(baseBytes), MATCH_EXPERIENCE_BASE_SHA);
const base = JSON.parse(baseBytes);
const additions = JSON.parse(await read('public/data/goal17-official-match-video-additions.json'));
const inspiration = JSON.parse(await read('public/data/fan-inspiration-v0.1.json'));
const before = JSON.stringify(base);
const merged = mergeMatchExperienceDelta(base, delta, hash(baseBytes));
assert.equal(JSON.stringify(base), before, 'base projection is never overwritten');
assert.deepEqual(mergeMatchExperienceDelta(merged, delta, hash(baseBytes)), merged, 'exact repeated delta is idempotent');
const previousCatalog = applyFanInspiration(applyGoal17MatchAdditions(consumeFanCatalog(base), additions), inspiration).catalog;
const catalog = applyMatchExperienceDelta(previousCatalog, base, delta, hash(baseBytes));
assert.deepEqual(applyMatchExperienceDelta(catalog, base, delta, hash(baseBytes)), catalog);
assert.deepEqual(catalog.sources.slice(0, 18), previousCatalog.sources, 'old evidence, permissions and source order remain unchanged');
assert.deepEqual([catalog.matches.length, catalog.sources.length, catalog.stars.length], [8, 19, 8]);
assert.equal(new Set(catalog.sources.map((source) => source.source_id)).size, 19);
const matchId = 'match:ittf-doha-2025:ms:wang-chuqin-wong-chun-ting';
const sourceId = 'video-source:youtube:suwultS-Jcc';
const match = catalog.matches.find((row) => row.match_id === matchId);
const source = catalog.sources.find((row) => row.source_id === sourceId);
assert.deepEqual(match.video_source_ids, [sourceId]);
assert.deepEqual(match.participants, [
  { side: 'A', athlete_id: 'athlete:121558', name_en: 'WANG Chuqin' },
  { side: 'B', athlete_id: null, name_en: 'WONG Chun Ting' },
]);
assert.equal(source.canonical_match_id, matchId);
assert.deepEqual(source.evidence_source_ids, ['wtt-youtube-suwultS-Jcc', 'ittf-doha-day4-wang-wong-2025', 'youtube-share-link-help']);
assert.equal(source.url, 'https://www.youtube.com/watch?v=suwultS-Jcc');
assert.equal(source.content_type_claim, 'HIGHLIGHTS');
assert.equal(source.recorded_playback_status, 'NOT_TESTED');
assert.equal(source.current_session_eligibility, 'NOT_EVALUATED_CURRENT_SESSION');
assert.equal(source.embedding, 'UNKNOWN');
assert.equal(source.thumbnail_display, 'NOT_ALLOWED');
const aliasCatalog = structuredClone(previousCatalog); aliasCatalog.sources.push({ ...source, source_id: 'youtube:suwultS-Jcc' });
assert.throws(() => applyMatchExperienceDelta(aliasCatalog, base, delta, hash(baseBytes)), /source-url-identity-conflict/);
assert.equal(delta.matches[0].provider_match_id, null);
assert.equal(delta.matches[0].event.date, null);
assert.equal(match.round, 'UNKNOWN');
assert.equal(match.participants[1].athlete_id, null);
assert.equal(catalog.stars.some((row) => /Wong Chun Ting/i.test(row.name_en ?? '')), false);
assert(filterFanHighlights(catalog).some((row) => row.source_id === sourceId));
assert.equal(filterFanClips(catalog).length, 0);
assert(searchFanCatalog(catalog, 'Wong Chun Ting').matches.some((row) => row.match_id === matchId));
assert(searchFanCatalog(catalog, '王楚钦').matches.some((row) => row.match_id === matchId));
assert(catalog.stars.find((row) => row.athlete_id === 'athlete:121558').linked_matches.includes(matchId));
const routes = buildFanWatchRouteCandidates(source);
assert.equal(routes.find((row) => row.mode === 'OFFICIAL_PAGE').viewingPermission, 'PUBLIC_PLATFORM_PAGE');
assert.equal(routes.find((row) => row.mode === 'OFFICIAL_EMBED').embedPermission, 'UNKNOWN');
const personal = { ...emptyFanLocalData(), saved_match_ids: [matchId] };
const personalBefore = JSON.stringify(personal);
assert.equal(createCollectorCards(catalog, personal.saved_match_ids)[0].watch_source.source_id, sourceId);
assert.deepEqual(removeCollectorMatch(personal, matchId).saved_match_ids, []);
assert.equal(JSON.stringify(personal), personalBefore, 'synthetic saved data is not mutated');
const location = { page: 'cinema', matchId, starId: null };
assert.equal(readFanLocation(fanLocationUrl('http://127.0.0.1:4210/', location)).matchId, matchId);
assert.deepEqual(restoreFanWatchReturn(createFanWatchReturn('cinema', { matchId, starId: null })), location);

for (const mutate of [
  (x) => { x.video_sources[0].content_type_claim = 'FULL_MATCH'; },
  (x) => { x.video_sources[0].rights.embedding = 'ALLOWED'; },
  (x) => { x.video_sources[0].rights.download = 'ALLOWED'; },
  (x) => { x.video_sources[0].rights.local_analysis = 'ALLOWED'; },
  (x) => { x.video_sources[0].thumbnail.url = 'https://example.invalid/frame.jpg'; },
  (x) => { x.video_sources[0].availability.latest_recorded_playback_status = 'PASS'; },
  (x) => { x.matches[0].event.date = '2025-05-20'; },
  (x) => { x.matches[0].participants[1].athlete_id = 'athlete:guessed'; },
  (x) => { x.video_sources[0].canonical_match_id = base.matches[0].match_id; },
  (x) => { x.video_sources[0].rights.evidence_source_ids.push('evidence:invented'); },
  (x) => { x.matches[0].evidence_source_ids.push('evidence:invented'); },
  (x) => { x.matches.push(structuredClone(x.matches[0])); },
  (x) => { x.internal_review = { path: 'C:\\private\\review.json' }; },
]) {
  const invalid = structuredClone(delta); mutate(invalid);
  assert.throws(() => mergeMatchExperienceDelta(base, invalid, MATCH_EXPERIENCE_BASE_SHA));
}
assert.throws(() => mergeMatchExperienceDelta(base, delta, '0'.repeat(64)));
const conflicting = structuredClone(merged); conflicting.matches.find((row) => row.match_id === matchId).round = 'Final';
assert.throws(() => mergeMatchExperienceDelta(conflicting, delta, MATCH_EXPERIENCE_BASE_SHA), /conflict/);

if (process.argv.includes('--built')) {
  assert.equal(hash(await read('dist/data/goal27-match-experience-delta-v0.1.json')), MATCH_EXPERIENCE_SHA);
  const files = await readdir(new URL('dist/data/', root));
  assert(!files.some((name) => /review-source|internal/i.test(name)));
  console.log('PASS: GOAL45 dist contains the exact public delta, no internal review payload.');
} else {
  const output = new URL('.alpha-qa/goal45/', root); await mkdir(output, { recursive: true });
  const kit = await build({ stdin: { contents: `
    import { createElement } from 'react'; import { renderToStaticMarkup } from 'react-dom/server';
    import { PublicFanCatalog } from './src/PublicFanCatalog'; import { FanCatalogPage } from './src/FanCatalogPage';
    export function render(props, base, additions, inspiration, delta) { return renderToStaticMarkup(createElement(PublicFanCatalog,
      { initialProjection: base, initialAdditions: additions, initialInspiration: inspiration, initialMatchExperience: delta },
      createElement(FanCatalogPage, { onGoCinema() {}, onGoInsight() {}, onOpenMatch() {}, onOpenWatch() {}, onToggleSavedMatch() {}, ...props }))); }
    `, resolveDir: fileURLToPath(root), loader: 'tsx' }, bundle: true, platform: 'node', format: 'esm', packages: 'external', jsx: 'automatic', write: false,
    define: { 'import.meta.env.DEV': 'false' },
    alias: { '@ptti/watch-routing': fileURLToPath(new URL('../../../playback-recovery-sprint-0-3/products/ptti/playback-core/adapters/watchRoutingContract.ts', root)) },
  });
  const kitFile = new URL('render-kit.mjs', output); await writeFile(kitFile, kit.outputFiles[0].contents);
  const { render } = await import(kitFile.href + `?${Date.now()}`);
  for (const locale of ['zh-CN', 'en']) {
    for (const mode of ['cinema-home', 'cinema', 'highlights', 'watch']) {
      const props = { locale, mode: mode === 'cinema-home' ? 'cinema' : mode, ...(mode === 'cinema' ? { initialMatchId: matchId } : {}), ...(mode === 'watch' ? { selectedSourceId: sourceId, initialMatchId: matchId } : {}) };
      const html = render(props, base, additions, inspiration, delta);
      assert(html.includes(mode === 'cinema' ? 'data-highlights-only' : sourceId));
      assert(!html.includes('athlete:guessed'));
      assert(!/<iframe|<video|i\.ytimg\.com/.test(html));
      if (mode === 'watch') assert(html.includes('href="https://www.youtube.com/watch?v=suwultS-Jcc" target="_blank" rel="noopener noreferrer"'));
      await writeFile(new URL(`${mode}-${locale}-OFFLINE.html`, output), html);
    }
  }
  for (const locale of ['zh-CN', 'en']) {
    const missing = render({ locale, mode: 'cinema', initialMatchId: 'qa:removed-match', matchReturnPage: 'corner' }, base, additions, inspiration, delta);
    assert(missing.includes('data-missing-match'));
    assert(!missing.includes('data-fan-match-detail'));
    assert(!missing.includes('data-featured-watch'));
    assert(missing.includes(locale === 'zh-CN' ? '返回收藏馆' : 'Back to Collector'));
  }
  console.log('PASS: 8 real-component offline renders consume GOAL27 through PublicFanCatalog (home/detail/Highlights/Watch, Chinese/English); not GUI evidence.');
}
console.log('PASS: GOAL45 fixed SHA/schema, actual 8/19/8 consumption, exact links/evidence, idempotence/conflict rejection, 16 negative cases, Highlights not Clips, UNKNOWN identities, Collector and unchanged private data. External page/playback NOT_TESTED.');
