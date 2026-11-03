import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { build } from 'esbuild';
import postcss from 'postcss';
import { consumeFanCatalog } from '../src/fan-catalog.mjs';
import { emptyFanLocalData, parseFanLocalDataBackup, serializeFanLocalDataBackup } from '../src/fan-local-data.mjs';

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
      export const corner = (locale, data, projection) => wrap(createElement(MyCornerPage, { locale, data, onChange: () => true, onReplace: () => true, onOpenMatch: () => {}, onOpenStar: () => {}, onDiscover: () => {} }), projection);
      export const train = (locale, data, projection) => wrap(createElement(TrainingPage, { locale, data, onChange: () => true, onReplace: () => true, onGoPro: () => {}, onOpenMatch: () => {} }), projection);
      export const gear = (locale, projection) => wrap(createElement(GearPage, { locale }), projection);
      export const page = (props, projection) => wrap(createElement(FanCatalogPage, { onGoCinema: () => {}, onGoStars: () => {}, onGoInsight: () => {}, onChooseVideo: () => {}, onGoClips: () => {}, onGoHighlights: () => {}, onOpenMatch: () => {}, onOpenWatch: () => {}, onOpenStar: () => {}, onOpenRivalry: () => {}, onGoCorner: () => {}, onOpenTrain: () => {}, onOpenGear: () => {}, onOpenCommunity: () => {}, onToggleSavedMatch: () => {}, onToggleFollowedAthlete: () => {}, ...props }), projection);`,
    resolveDir: fileURLToPath(base), loader: 'tsx',
  }, bundle: true, platform: 'node', format: 'esm', packages: 'external', jsx: 'automatic', write: false,
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
for (const locale of ['zh-CN', 'en']) {
  const corner = kit.corner(locale, data, projection);
  for (const key of ['training', 'match', 'coach', 'fan']) assert.match(corner, new RegExp(`data-note-kind="${key}"`));
  assert.doesNotMatch(corner, /<script>|undefined/);
  assert.match(corner, /&lt;script&gt;/);
  assert.equal((corner.match(/<div[^>]* hidden=""/g) || []).length, 3, 'inactive note categories remain mounted, preserving their form state');
  assert.match(kit.train(locale, data, projection), /data-note-kind="training"/);
  assert.match(kit.gear(locale, projection), /data-gear-category="Racket"/);
  assert.doesNotMatch(kit.gear(locale, projection), /Buy now|Add to cart|立即购买|加入购物车/);
  const home = kit.page({ locale, mode: 'cinema' }, projection);
  assert.equal((home.match(/data-public-match-id=/g) || []).length, 5);
  assert.equal((home.match(/data-athlete-id=/g) || []).length, 8);
  assert.equal((home.match(/data-public-source-id=/g) || []).length, 10);
  assert.doesNotMatch(home, /<iframe\b|<video\b|<img\b|Schema|Strict Public|Projection|Routing|ID-BASED|undefined/);
  let previousSection = -1;
  for (const name of ['fan-home-matches', 'fan-home-stars', 'fan-home-highlights', 'fan-home-rivalries', 'fan-quick-hits', 'fan-corner-invite', 'fan-ecosystem-explore']) {
    const position = home.indexOf(`class="${name}"`);
    assert(position > previousSection, `editorial home order: ${name}`);
    previousSection = position;
  }
  const highlightsPage = kit.page({ locale, mode: 'highlights' }, projection);
  assert.equal((highlightsPage.match(/data-public-source-id=/g) || []).length, 10);
  const clipsPage = kit.page({ locale, mode: 'clips' }, projection);
  assert.match(clipsPage, /data-clips-empty/);
  assert.equal((clipsPage.match(/data-public-source-id=/g) || []).length, 0);
  for (const match of catalog.matches) {
    const source = catalog.sources.find((item) => item.source_id === match.video_source_ids[0]);
    const watch = kit.page({ locale, mode: 'watch', selectedSourceId: source.source_id }, projection);
    assert(watch.includes(`data-linked-match-id="${match.match_id}"`));
    assert(watch.includes(`href="${source.url.replaceAll('&', '&amp;')}" target="_blank" rel="noopener noreferrer"`));
    assert.doesNotMatch(watch, /<iframe\b|<video\b|undefined/);
  }
  const defaultWatch = kit.page({ locale, mode: 'watch' }, projection);
  assert.equal((defaultWatch.match(/data-fan-watch-detail/g) || []).length, 1);
  assert.doesNotMatch(defaultWatch, /class="fan-empty"/);
  await writeFile(new URL(`cinema-${locale}-server-render.html`, out), home);
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
