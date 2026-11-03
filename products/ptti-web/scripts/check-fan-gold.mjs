import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { build } from 'esbuild';
import postcss from 'postcss';
import { consumeFanCatalog } from '../src/fan-catalog.mjs';
import { ATHLETE_JOURNAL_FIELDS, emptyFanLocalData, parseFanLocalDataBackup, serializeFanLocalDataBackup } from '../src/fan-local-data.mjs';

const base = new URL('../', import.meta.url);
const out = new URL('.alpha-qa/goal15-gold-render/', base);
await mkdir(out, { recursive: true });
const routingSource = new URL('../../../playback-recovery-sprint-0-3/products/ptti/playback-core/adapters/watchRoutingContract.ts', base);
assert.equal(createHash('sha256').update(await readFile(routingSource)).digest('hex'), '1fa1e6100eb85f56cc51819d1e0cffaef500d6fa96bba616f6b281d60bb51619');
const built = await build({
  stdin: {
    contents: `import { createElement } from 'react';
      import { renderToStaticMarkup } from 'react-dom/server';
      import { FanArtwork } from './src/FanArtwork';
      import { PublicFanCatalog } from './src/PublicFanCatalog';
      import { FanCatalogPage } from './src/FanCatalogPage';
      import { TrainingPage, MyCornerPage, GearPage } from './src/FanUniversePages';
      const wrap = (child, projection) => renderToStaticMarkup(createElement(PublicFanCatalog, { initialProjection: projection }, child));
      export const art = (props) => renderToStaticMarkup(createElement(FanArtwork, props));
      export const gallery = (items) => renderToStaticMarkup(createElement('div', null, items.map((props, i) => createElement(FanArtwork, { ...props, key: i }))));
      export const corner = (locale, data, projection) => wrap(createElement(MyCornerPage, { locale, data, onChange: () => true, onReplace: () => true, onOpenMatch: () => {}, onOpenStar: () => {}, onOpenWatch: () => {}, onDiscover: () => {} }), projection);
      export const train = (locale, data, projection) => wrap(createElement(TrainingPage, { locale, data, onChange: () => true, onReplace: () => true, onGoPro: () => {}, onOpenMatch: () => {} }), projection);
      export const gear = (locale, projection) => wrap(createElement(GearPage, { locale }), projection);
      export const page = (props, projection) => wrap(createElement(FanCatalogPage, { onGoCinema: () => {}, onGoStars: () => {}, onGoInsight: () => {}, onChooseVideo: () => {}, onGoClips: () => {}, onGoHighlights: () => {}, onOpenMatch: () => {}, onOpenWatch: () => {}, onOpenStar: () => {}, onOpenRivalry: () => {}, onGoCorner: () => {}, onOpenArena: () => {}, onOpenTrain: () => {}, onOpenGear: () => {}, onOpenCommunity: () => {}, onToggleSavedMatch: () => {}, onToggleFollowedAthlete: () => {}, ...props }), projection);
      export const inspired = (props, projection, additions, inspiration) => renderToStaticMarkup(createElement(PublicFanCatalog, { initialProjection: projection, initialAdditions: additions, initialInspiration: inspiration }, createElement(FanCatalogPage, { onGoCinema: () => {}, onGoInsight: () => {}, onGoClips: () => {}, onOpenMatch: () => {}, onOpenWatch: () => {}, ...props })));
      export const inspiredGear = (locale, projection, additions, inspiration) => renderToStaticMarkup(createElement(PublicFanCatalog, { initialProjection: projection, initialAdditions: additions, initialInspiration: inspiration }, createElement(GearPage, { locale })));`,
    resolveDir: fileURLToPath(base), loader: 'tsx',
  }, bundle: true, platform: 'node', format: 'esm', packages: 'external', jsx: 'automatic', write: false,
  define: { 'import.meta.env.DEV': 'false' },
  alias: { '@ptti/watch-routing': fileURLToPath(routingSource) },
});
const kitUrl = new URL('render-kit.mjs', out);
await writeFile(kitUrl, built.outputFiles[0].contents);
const kit = await import(pathToFileURL(fileURLToPath(kitUrl)).href + `?${Date.now()}`);
const bytes = await readFile(new URL('public/data/match-library-strict-public.json', base));
assert.equal(createHash('sha256').update(bytes).digest('hex'), '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930');
const projection = JSON.parse(bytes.toString('utf8'));
const catalog = consumeFanCatalog(projection);
let cases = 1;

const matchArt = catalog.matches.map((match) => ({ locale: 'zh-CN', kind: 'match', identity: match.match_id, title: match.display_title_zh || match.participants.map((p) => p.name_en).join(' vs '), subtitle: match.event }));
const starArt = catalog.stars.map((star) => ({ locale: 'zh-CN', kind: 'star', identity: star.athlete_id, title: star.name_zh || star.name_en, subtitle: star.association }));
const highlights = catalog.sources.filter((source) => source.content_type_claim === 'HIGHLIGHTS');
assert.deepEqual([matchArt.length, starArt.length, highlights.length], [5, 8, 10]); cases++;
const matchHtml = kit.gallery(matchArt);
assert(new Set([...matchHtml.matchAll(/data-art-variant="(\d)"/g)].map((m) => m[1])).size >= 3, 'real match identities receive distinct art directions'); cases++;
const allHtml = kit.gallery([...matchArt, ...starArt, ...highlights.map((source) => ({ locale: 'en', kind: 'match', identity: source.source_id, title: source.event }))]);
const ids = [...allHtml.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]);
assert.equal(new Set(ids).size, ids.length, 'each original artwork has isolated SVG paint servers'); cases++;
assert.doesNotMatch(allHtml, /<(?:img|video|iframe|image|foreignObject)\b|https?:\/\//i, 'owned poster art never fetches licensed media or pretends to be a player portrait'); cases++;
assert.match(allHtml, /PTTI ORIGINAL ART/);
assert.match(allHtml, /非比赛画面/); cases++;
const specialText = '<script>alert("note")</script>';
const inertArt = kit.art({ locale: 'en', kind: 'star', title: specialText, identity: 'qa-only:original-art' });
assert.doesNotMatch(inertArt, /<script>/);
assert.match(inertArt, /&lt;script&gt;/); cases++;
const decorative = kit.art({ locale: 'en', kind: 'match', decorative: true, identity: catalog.matches[0].match_id });
assert.match(decorative, /aria-hidden="true"/);
assert.doesNotMatch(decorative, /role="img"/); cases++;

const data = emptyFanLocalData();
for (const key of ['training_notes', 'match_notes', 'coach_notes', 'fan_notes']) {
  data[key].push({ id: `qa-${key}`, date: '2026-10-18', topic: key, technical_question: '', summary: specialText, next_goal: '', match_id: null });
}
assert.deepEqual(parseFanLocalDataBackup(serializeFanLocalDataBackup(data)), data); cases++;
data.training_notes[0].athlete_journal = { contract_version: 'ptti.athlete-journal/0.1', author: 'SELF', ...Object.fromEntries(ATHLETE_JOURNAL_FIELDS.map((field) => [field, `Personal ${field} ${specialText}`])) };
assert.deepEqual(parseFanLocalDataBackup(serializeFanLocalDataBackup(data)), data); cases++;
for (const locale of ['zh-CN', 'en']) {
  const savedFixture = { ...data, saved_match_ids: [catalog.matches[0].match_id, 'match:synthetic-unlisted'] };
  const loungeHtml = kit.corner(locale, savedFixture, projection);
  const lounge = loungeHtml.slice(loungeHtml.indexOf('aria-labelledby="collector-title"'), loungeHtml.indexOf('PTTI · FOLLOWING'));
  assert(lounge.includes(`data-saved-match-id="${catalog.matches[0].match_id}"`));
  assert(lounge.includes(`data-collector-source-id="${catalog.sources[0].source_id}"`));
  assert(lounge.includes('match:synthetic-unlisted'));
  assert.match(lounge, /4–0/);
  assert.match(lounge, /当前公开目录|current public catalog/);
  assert.match(lounge, /不代表已验证视频播放|does not verify playback/);
  assert.doesNotMatch(lounge, /<img\b|<video\b|<iframe\b|Private synthetic|Personal training_goal|&lt;script&gt;/);
  assert.equal((lounge.match(/data-collector-source-id=/g) || []).length, 1, 'missing catalog records never gain Watch actions');
  const emptyLounge = kit.corner(locale, { ...data, saved_match_ids: [] }, projection);
  assert.match(emptyLounge, /collector-empty/);
  assert.match(emptyLounge, /第一场经典|first classic/);
  assert.doesNotMatch(emptyLounge, /data-collector-source-id=/);
  await writeFile(new URL(`collector-${locale}-server-render.html`, out), loungeHtml);
  cases += 2;
  const corner = kit.corner(locale, data, projection);
  for (const key of ['training', 'match', 'coach', 'fan']) assert.match(corner, new RegExp(`data-note-kind="${key}"`));
  assert.doesNotMatch(corner, /<script>|undefined/);
  assert.match(corner, /&lt;script&gt;/);
  assert.match(corner, /athlete-journal-summary/);
  for (const field of ATHLETE_JOURNAL_FIELDS) assert(corner.includes(`Personal ${field}`));
  assert.equal((corner.match(/<div[^>]* hidden=""/g) || []).length, 3, 'inactive note categories remain mounted, preserving their form state');
  assert.match(kit.train(locale, data, projection), /data-note-kind="training"/);
  assert.match(kit.gear(locale, projection), /data-gear-category="Racket"/);
  assert.doesNotMatch(kit.gear(locale, projection), /Buy now|Add to cart|立即购买|加入购物车/);
  const home = kit.page({ locale, mode: 'cinema', onOpenArena: () => {} }, projection);
  assert.doesNotMatch(home, /fan-cinema-hero grand-lobby|grand-lobby-stage|lobby-programme/);
  assert.match(home, /data-cinema-cover-wall/);
  assert.match(home, /data-lobby-collector/);
  assert.match(home, /data-arena-entry/);
  assert.equal((home.match(/data-cover-origin="PTTI_ORIGINAL"/g)||[]).length,catalog.matches.length);
  const collectorEntry = home.match(/<button[^>]*data-lobby-collector[^>]*>[\s\S]*?<\/button>/)?.[0] ?? '';
  assert(collectorEntry && !/\b\d+\b/.test(collectorEntry), 'the compact Collector entry does not expose a directory count');
  const unknownSourceProjection = structuredClone(projection);
  for (const source of unknownSourceProjection.video_sources) { source.rights.external_viewing = 'UNKNOWN'; source.source_identity_status = 'UNKNOWN'; }
  const unknownLobby = kit.page({ locale, mode: 'cinema' }, unknownSourceProjection);
  assert.doesNotMatch(unknownLobby, /data-featured-watch/);
  assert(unknownLobby.includes(`data-public-match-id="${catalog.matches[0].match_id}"`));
  assert.doesNotMatch(unknownLobby, /class="button button-primary"[^>]*>[^<]*Watch/);
  assert.doesNotMatch(unknownLobby, /<img\b|<iframe\b|<video\b/);
  cases += 2;
  assert.equal((home.match(/data-fan-search=/g) || []).length, 1, 'Cinema has a single search input');
  assert(home.indexOf('data-fan-search=') < home.indexOf('data-cinema-cover-wall'), 'compact search precedes the cover wall');
  assert.equal((home.match(/data-public-match-id=/g) || []).length, 5);
  assert.equal((home.match(/data-athlete-id=/g) || []).length, 8);
  assert.equal((home.match(/data-public-source-id=/g) || []).length, 10);
  assert.doesNotMatch(home, /<iframe\b|<video\b|<img\b|Schema|Strict Public|Projection|Routing|ID-BASED|undefined/);
  let previousSection = -1;
  for (const name of ['fan-home-matches', 'fan-home-stars', 'fan-home-highlights', 'fan-home-rivalries', 'fan-quick-hits', 'fan-arena-entry', 'fan-corner-invite', 'fan-ecosystem-explore']) {
    const position = home.indexOf(`class="${name}"`);
    assert(position > previousSection, `editorial home order: ${name}`);
    previousSection = position;
  }
  const highlightsPage = kit.page({ locale, mode: 'highlights' }, projection);
  assert.equal((highlightsPage.match(/data-public-source-id=/g) || []).length, 10);
  const clipsPage = kit.page({ locale, mode: 'clips' }, projection);
  assert.match(clipsPage, /data-clips-empty/);
  assert.equal((clipsPage.match(/data-public-source-id=/g) || []).length, 10, 'Clips discovers admitted event highlights while retaining the honest zero-short-clips state');
  for (const source of highlights) assert(clipsPage.includes(`data-public-source-id="${source.source_id}"`));
  for (const source of catalog.sources.filter((item) => item.content_type_claim !== 'HIGHLIGHTS')) assert(!clipsPage.includes(`data-public-source-id="${source.source_id}"`), 'full or unknown videos cannot become clips or highlights');
  for (const match of catalog.matches) {
    const source = catalog.sources.find((item) => item.source_id === match.video_source_ids[0]);
    const watch = kit.page({ locale, mode: 'watch', selectedSourceId: source.source_id }, projection);
    assert.match(watch, /fan-watch-help/);
    assert.match(watch, /fan-watch-detail private-theater/);
    assert(watch.includes(`data-theater-source-id="${source.source_id}"`));
    assert(watch.includes(`data-theater-match-id="${match.match_id}"`));
    assert.match(watch, /data-theater-focus="false"/);
    assert.match(watch, /尚无已确认许可|No confirmed permission recorded/);
    assert.match(watch, /本页不提供站内播放|no in-page playback/);
    assert.match(watch, /复制官方链接|Copy official link/);
    assert(watch.includes(`data-linked-match-id="${match.match_id}"`));
    assert(watch.includes(`href="${source.url.replaceAll('&', '&amp;')}" target="_blank" rel="noopener noreferrer"`));
    assert.doesNotMatch(watch, /<iframe\b|<video\b|undefined/);
    if (match.match_id === catalog.matches[0].match_id) await writeFile(new URL(`private-theater-${locale}-server-render.html`, out), watch);
  }
  const deniedWatchProjection = structuredClone(projection);
  deniedWatchProjection.video_sources[0].rights.external_viewing = 'UNKNOWN';
  const deniedWatch = kit.page({ locale, mode: 'watch', selectedSourceId: catalog.sources[0].source_id }, deniedWatchProjection);
  assert.match(deniedWatch, /来源记录|Source record/);
  assert.match(deniedWatch, /没有通过核验的观看入口|without a verified viewing entry/);
  assert(!deniedWatch.includes(`href="${catalog.sources[0].url}"`));
  assert.doesNotMatch(deniedWatch, /<iframe\b|<video\b/);
  const missingWatch = kit.page({ locale, mode: 'watch', selectedSourceId: 'video-source:youtube:missing-qa' }, projection);
  assert.match(missingWatch, /private-theater-empty/);
  assert.doesNotMatch(missingWatch, /data-theater-source-id=|data-linked-match-id=|<iframe\b|<video\b/);
  cases += 2;
  const defaultWatch = kit.page({ locale, mode: 'watch' }, projection);
  assert.equal((defaultWatch.match(/data-fan-watch-detail/g) || []).length, 1);
  assert.doesNotMatch(defaultWatch, /class="fan-empty"/);
  await writeFile(new URL(`cinema-${locale}-server-render.html`, out), home);
  cases++;
}
const inspiration = JSON.parse(await readFile(new URL('public/data/fan-inspiration-v0.1.json', base)));
const additions = JSON.parse(await readFile(new URL('public/data/goal17-official-match-video-additions.json', base)));
for (const locale of ['zh-CN', 'en']) {
  const lobby = kit.inspired({ locale, mode: 'cinema' }, projection, additions, inspiration);
  const programmeIds = [...lobby.matchAll(/data-public-match-id="([^"]+)"/g)].map((row) => row[1]);
  assert.equal(programmeIds.length, 7);
  assert.equal(new Set(programmeIds).size, 7);
  await writeFile(new URL(`grand-lobby-${locale}-server-render.html`, out), lobby);
  cases++;
  const clips = kit.inspired({ locale, mode: 'clips' }, projection, additions, inspiration);
  assert.equal((clips.match(/data-public-source-id=/g) || []).length, 11);
  assert(clips.includes('data-inspiration-sha="702bc12850676ae9eeda39b533ade9cc5f2da0fe8710aa8ebc82f0c2b803c5c9"'));
  const season = inspiration.clips.find(row => row.video_category === 'SEASON_HIGHLIGHTS_TITLE_CLAIM');
  const seasonWatch = kit.inspired({ locale, mode: 'watch', selectedSourceId: season.source_id }, projection, additions, inspiration);
  assert(seasonWatch.includes(season.original_url));
  assert.doesNotMatch(seasonWatch, /data-linked-match-id=/);
  assert.match(seasonWatch, /赛季级集锦|season highlights/);
  for (const id of ['athlete:121558', 'athlete:135977']) {
    const star = kit.inspired({ locale, mode: 'stars', initialStarId: id }, projection, additions, inspiration);
    assert(star.includes(inspiration.international_reactions[0].reaction_id));
    assert(star.includes(inspiration.international_reactions[0].source_url));
    assert.match(star, /仅代表这一篇报道|One article only/);
  }
  const other = kit.inspired({ locale, mode: 'stars', initialStarId: 'athlete:131163' }, projection, additions, inspiration);
  assert(!other.includes(inspiration.international_reactions[0].reaction_id));
  const gear = kit.inspiredGear(locale, projection, additions, inspiration);
  assert(gear.includes('data-gear-dossier-id="'+inspiration.gear_dossiers[0].match_id+'"'));
  assert.equal((gear.match(/data-equipment-status="UNKNOWN"/g) || []).length, 2);
  cases++;
}
const unsafeProjection = structuredClone(projection);
unsafeProjection.view = 'INTERNAL_REVIEW';
assert.throws(() => kit.page({ locale: 'en', mode: 'cinema' }, unsafeProjection), /strict-public-view-required/); cases++;
const goldCss = await readFile(new URL('src/fan-gold.css', base), 'utf8');
postcss.parse(goldCss);
assert.doesNotMatch(goldCss, /url\(\s*['"]?https?:/i);
assert(goldCss.includes('prefers-reduced-motion'));
assert(goldCss.includes('content-visibility: auto'));
assert(goldCss.includes('max-width: 680px')); cases++;
assert(goldCss.includes('.fan-home-matches .fan-match-card:focus-within .fan-content-body'), 'match titles and actions appear when keyboard users focus a card');
assert(goldCss.includes('.fan-home-highlights .fan-source-card:focus-within .fan-content-body'), 'highlight details appear on focus');
assert(goldCss.includes('@media (hover:none)'), 'touch layouts show titles without requiring hover');
assert(goldCss.includes('grid-template-areas:\'visual\' \'copy\''), 'narrow Cinema layouts put original artwork before hero copy');
cases++;

if (process.argv.includes('--built')) {
  const assets = await readdir(new URL('dist/assets/', base));
  assert(assets.some((name) => /^MatchDetail-.*\.js$/.test(name)), 'legacy match details are outside the first-load chunk');
  assert(assets.some((name) => /^FanSearchOverlay-.*\.js$/.test(name)), 'global search is loaded on demand');
  assert(assets.some((name) => /^ProWorkbench-.*\.js$/.test(name)), 'Pro remains on demand');
  cases++;
}
await writeFile(new URL('original-art-gallery.html', out), `<!doctype html><meta charset="utf-8"><title>PTTI original art render proof — not browser acceptance</title><style>body{background:#0b0d13;color:#fff;font-family:sans-serif}main{max-width:1200px;margin:auto}main>div{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px}${await readFile(new URL('src/style.css', base), 'utf8')}\n${goldCss}</style><h1>Original art render proof (not browser QA)</h1><main>${allHtml}</main>`);
await writeFile(new URL('arena.svg', out), decorative.match(/<svg[\s\S]*?<\/svg>/)[0]);
await writeFile(new URL('render-report.json', out), JSON.stringify({ status: 'PASS', cases, main_catalog_sha256: createHash('sha256').update(bytes).digest('hex'), evidence_type: 'REACT_SERVER_RENDER_AND_CONTRACT_CHECKS', browser: 'NOT_TESTED', screenshots: [] }, null, 2));
console.log(`PASS: ${cases} original-art, identity, safe-text, note preservation, bilingual render and build-boundary cases. Browser/layout acceptance remains NOT_TESTED.`);
