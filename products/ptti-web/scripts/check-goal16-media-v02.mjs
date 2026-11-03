import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import indexJson from '../src/approved-public-media.json' with { type: 'json' };
import { consumeFanCatalog } from '../src/fan-catalog.mjs';
import { createPublicMediaIndex, validatePublicMediaAsset } from '../src/fan-media.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const catalog = consumeFanCatalog(JSON.parse(readFileSync(join(root, 'public/data/match-library-strict-public.json'))));
const mainBytes = readFileSync(join(root, 'scripts/fixtures/goal16-media/main-public-media-v0.2.json'));
assert.equal(createHash('sha256').update(mainBytes).digest('hex'), 'c05491a64f59ac922d2d85d081eccf3b2853f717ece82c8bcfa3d05608f2c004');
const schemaBytes = readFileSync(join(root, 'scripts/fixtures/goal16-media/main-public-media-v0.2-schema.json'));
assert.equal(createHash('sha256').update(schemaBytes).digest('hex'), '596d298dbb33eede22b3df3f2cdd212af54437a22bd50834c2f1a9703fea5840');
const schema = JSON.parse(schemaBytes);
assert.equal(schema.properties.contract_version.const, 'ptti.public-media-manifest/0.2');
assert.equal(schema.properties.view.const, 'STRICT_PUBLIC_MEDIA');
assert.equal(schema.$defs.asset.properties.use_scope.const, 'ATHLETE_PROFILE_EDITORIAL_ONLY');
const main = JSON.parse(mainBytes);
assert.equal(main.contract_version, 'ptti.public-media-manifest/0.2');
assert.equal(main.view, 'STRICT_PUBLIC_MEDIA');
assert.equal(main.assets.length, 4);
const index = createPublicMediaIndex(indexJson, catalog);
assert.deepEqual([...index.athletes.keys()].sort(), ['athlete:119588', 'athlete:121411', 'athlete:121558', 'athlete:123980', 'athlete:131163', 'athlete:135977']);
assert.equal(index.matches.size, 0);
assert.equal(index.athletes.has('athlete:112409'), false, 'Groth has no public star detail page');
const notClearedIds = [
  'commons:2018-yog:mixed-final-098', 'commons:2018-yog:sun-yingsha-final-061',
  'commons:munich-2022:felix-lebrun-850-9499', 'commons:2018-yog:lin-yun-ju-bronze-544',
  'commons:acttc-2016:chen-xingtong-2',
];
for (const blockedId of notClearedIds) assert.equal(index.assets.some((asset) => asset.asset_id === blockedId), false);
const artSource = readFileSync(join(root, 'src/FanArtwork.tsx'), 'utf8');
const profileSource = readFileSync(join(root, 'src/FanCatalogPage.tsx'), 'utf8');
assert.equal(artSource.includes('AthletePortrait'), false, 'shared artwork cannot promote portrait to cards or hero');
assert.equal((profileSource.match(/<AthletePortrait\b/g) ?? []).length, 1, 'only athlete detail invokes real portraits');

const expectedPaths = new Set();
for (const asset of index.assets.filter((row) => main.assets.some((candidate) => candidate.asset_id === row.asset_id))) {
  const source = main.assets.find((candidate) => candidate.asset_id === asset.asset_id);
  assert(source);
  assert.equal(source.athlete_id, asset.subject_id);
  assert.equal(source.use_scope, 'ATHLETE_PROFILE_EDITORIAL_ONLY');
  assert.equal(source.promotion_use, 'NOT_CLEARED_NO_ENDORSEMENT_OR_HOMEPAGE_PROMOTION');
  assert.equal(source.match_id, null);
  assert.equal(source.share_alike_required, true);
  assert.equal(asset.photographer, source.photographer);
  assert.equal(asset.attribution, source.attribution);
  assert.equal(asset.source_page_url, source.source_page_url);
  assert.equal(asset.license, source.license);
  assert.equal(asset.license_url, source.license_url);
  assert.equal(asset.derivative_notice, source.changes_made);
  for (const rendition of asset.renditions) {
    const derivative = source.derivatives.find((item) => rendition.src.endsWith(item.path.slice('assets/'.length)));
    assert(derivative);
    assert.equal(rendition.sha256, derivative.sha256);
    assert.equal(rendition.width, derivative.width);
    assert.equal(rendition.height, derivative.height);
    assert.equal(derivative.metadata_stripped, true);
    const file = resolve(root, `public/.${rendition.src}`);
    assert(file.startsWith(join(root, 'public/media/goal16')));
    const bytes = readFileSync(file);
    assert.equal(bytes.toString('ascii', 0, 4), 'RIFF');
    assert.equal(bytes.toString('ascii', 8, 12), 'WEBP');
    assert.equal(createHash('sha256').update(bytes).digest('hex'), derivative.sha256);
    expectedPaths.add(rendition.src.slice(1));
  }
}
const goal17Bytes = readFileSync(join(root, 'public/data/goal17-athlete-photo-additions.json'));
assert.equal(createHash('sha256').update(goal17Bytes).digest('hex'), '6afb03bcc99cefaca7d8ca26005b728162fe878317e217bd705a9253fd067dc9');
const goal17 = JSON.parse(goal17Bytes);
assert.equal(goal17.contract_version, 'ptti.goal17.1-athlete-media/0.1');
assert.equal(goal17.view, 'STRICT_PUBLIC_MEDIA_DELTA');
assert.equal(goal17.base_goal16_manifest_sha256, 'c05491a64f59ac922d2d85d081eccf3b2853f717ece82c8bcfa3d05608f2c004');
assert.equal(goal17.base_goal15_library_sha256, '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930');
const goal17Schema = JSON.parse(readFileSync(join(root, 'scripts/fixtures/goal16-media/goal17-athlete-schema.json')));
assert.equal(goal17Schema.properties.contract_version.const, goal17.contract_version);
assert.equal(goal17.assets.length, 3);
for (const source of goal17.assets) {
  const asset = index.athletes.get(source.athlete_id);
  assert(asset && asset.asset_id === source.asset_id);
  assert.equal(source.use_scope, 'ATHLETE_PROFILE_EDITORIAL_ONLY');
  assert.equal(source.display_permission, 'ALLOWED_SCOPED');
  assert.equal(source.match_id, null);
  assert.equal(source.promotion_use, 'NOT_CLEARED_NO_ENDORSEMENT_OR_ADVERTISING');
  assert.equal(asset.attribution, source.attribution);
  assert.equal(asset.photographer, source.photographer);
  assert.equal(asset.source_page_url, source.source_page_url);
  assert.equal(asset.license, source.license);
  assert.equal(asset.license_url, source.license_url);
  assert.equal(asset.derivative_notice, source.changes_made);
  assert.equal(source.derivatives.length, 2);
  for (const derivative of source.derivatives) {
    const rendition = asset.renditions.find((item) => item.src.endsWith(derivative.path.slice('assets/'.length)));
    assert(rendition);
    assert.equal(derivative.metadata_stripped, true);
    assert.equal(derivative.license, source.license);
    assert.equal(derivative.sha256, rendition.sha256);
    assert.equal(derivative.width, rendition.width);
    assert.equal(derivative.height, rendition.height);
    const file = readFileSync(resolve(root, `public/.${rendition.src}`));
    assert.equal(file.toString('ascii', 0, 4), 'RIFF');
    assert.equal(file.toString('ascii', 8, 12), 'WEBP');
    assert.equal(createHash('sha256').update(file).digest('hex'), rendition.sha256);
    expectedPaths.add(rendition.src.slice(1));
  }
}
assert.equal(expectedPaths.size, 12);
assert.equal(index.athletes.has('athlete:137237'), false, 'Lin Shidong retains original artwork');
assert.equal(index.athletes.has('athlete:135049'), false, 'Kuai Man retains original artwork');
assert(index.athletes.get('athlete:135977').alt.includes('Alexis Lebrun'), 'four-player context retained');
assert(index.athletes.get('athlete:135977').renditions.every((item) => item.width > item.height), 'Félix remains full-frame');
assert(index.athletes.get('athlete:131163').renditions.every((item) => item.width <= 400), 'Sun cannot upscale');
const liang = index.athletes.get('athlete:119588');
assert(liang.renditions.every((item) => item.width * 2 === item.height * 3), 'Liang must retain full 3:2 frame');
for (const changed of [
  { ...index.assets[0], display_permission: 'NOT_CLEARED' },
  { ...index.assets[0], attribution: '' },
  { ...index.assets[0], subject_id: 'athlete:112409' },
  { ...index.assets[0], match_evidence: { match_id: catalog.matches[0].match_id } },
  { ...index.assets[0], renditions: [{ ...index.assets[0].renditions[0], sha256: '0'.repeat(64) }] },
]) {
  if (changed.renditions?.[0]?.sha256 === '0'.repeat(64)) {
    const file = readFileSync(resolve(root, `public/.${changed.renditions[0].src}`));
    assert.notEqual(createHash('sha256').update(file).digest('hex'), changed.renditions[0].sha256);
  } else assert(validatePublicMediaAsset(changed, catalog).length > 0);
}
for (let i = 0; i < 5; i++) assert(validatePublicMediaAsset({ ...index.assets[0], asset_id: `not-cleared-${i}`, display_permission: 'NOT_CLEARED' }, catalog).includes('DISPLAY_PERMISSION_NOT_CLEARED'));

const publicFiles = ['goal16', 'goal17'].flatMap((goal) => readdirSync(join(root, `public/media/${goal}`)).map((name) => `media/${goal}/${name}`));
assert.deepEqual(publicFiles.sort(), [...expectedPaths].sort(), 'only twelve approved derivative bytes may be public');
if (process.argv.includes('--built')) {
  const dist = join(root, 'dist');
  function walk(dir) { return readdirSync(dir).flatMap((name) => { const path = join(dir, name); return statSync(path).isDirectory() ? walk(path) : [path]; }); }
  const files = walk(dist);
  const raster = files.filter((path) => /\.(?:webp|avif|png|jpe?g)$/i.test(path)).map((path) => relative(dist, path).replaceAll('\\', '/'));
  assert.deepEqual(raster.sort(), [...expectedPaths].sort(), 'dist raster allowlist differs from approved derivative set');
  for (const path of raster) {
    const bytes = readFileSync(join(dist, path));
    const rendition = index.assets.flatMap((asset) => asset.renditions).find((item) => item.src.slice(1) === path);
    assert.equal(createHash('sha256').update(bytes).digest('hex'), rendition.sha256);
  }
  const emittedText = files.filter((path) => /\.(?:js|json|html|css|svg)$/i.test(path)).map((path) => readFileSync(path, 'utf8')).join('\n');
  for (const marker of ['public-media-manifest.json', 'clearance_review_sha256', 'INTERNAL_MEDIA_RIGHTS_REVIEW', 'commons:jonathan-groth-portrait', ...notClearedIds]) {
    assert.equal(emittedText.includes(marker), false, `nonpublic media metadata leaked: ${marker}`);
  }
}
console.log(`PASS: Main GOAL16 + GOAL17 SHA, six athlete IDs, twelve WebP bytes, attribution/licenses, five denial cases and ${process.argv.includes('--built') ? 'dist' : 'public'} isolation.`);
