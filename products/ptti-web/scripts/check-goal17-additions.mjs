import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { consumeFanCatalog, searchFanCatalog } from '../src/fan-catalog.mjs';
import { applyGoal17MatchAdditions } from '../src/goal17-match-additions.mjs';
import { buildFanWatchRouteCandidates } from '../src/fan-watch-routing.mjs';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
function pinned(file, expected) {
  const bytes = readFileSync(join(root, file));
  assert.equal(createHash('sha256').update(bytes).digest('hex'), expected, `${file} SHA changed`);
  return JSON.parse(bytes);
}
const base = consumeFanCatalog(pinned('public/data/match-library-strict-public.json', '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930'));
const media = pinned('public/data/goal17-athlete-photo-additions.json', '6afb03bcc99cefaca7d8ca26005b728162fe878317e217bd705a9253fd067dc9');
const delta = pinned('public/data/goal17-official-match-video-additions.json', '6f05d1fc48fb74ffc305abe20fd9152973bd96bb009fe6a183d42c031a31198a');
const photoSchemaBytes = readFileSync(join(root, 'scripts/fixtures/goal16-media/goal17-athlete-schema.json'));
const matchSchemaBytes = readFileSync(join(root, 'scripts/fixtures/goal16-media/goal17-match-schema.json'));
assert.equal(createHash('sha256').update(photoSchemaBytes).digest('hex'), '0b0eed35ee5da0ef449faa3a377d91fd9f4d476a09c73f99f384f336d294e87d');
assert.equal(createHash('sha256').update(matchSchemaBytes).digest('hex'), 'f5a9428ee949d2ab56e707d67b473a18a2e9c98fffff9a5d2c2ae223f39a18bb');
const photoSchema = JSON.parse(photoSchemaBytes);
const matchSchema = JSON.parse(matchSchemaBytes);
assert.equal(photoSchema.properties.contract_version.const, media.contract_version);
assert.equal(matchSchema.properties.contract_version.const, delta.contract_version);
assert.equal(media.base_goal15_library_sha256, delta.base_goal15_library_sha256);
const catalog = applyGoal17MatchAdditions(base, delta);
assert.deepEqual([catalog.matches.length, catalog.sources.length, catalog.stars.length], [7, 17, 8]);
assert.equal(base.matches.length, 5);
assert.equal(base.sources.length, 15);
assert.equal(catalog.stars.find((star) => star.athlete_id === 'athlete:137237').linked_matches.length,
  base.stars.find((star) => star.athlete_id === 'athlete:137237').linked_matches.length + 2);
assert.equal(searchFanCatalog(catalog, 'Lin Shidong').matches.filter((row) => row.event_id === 'wtt-event:3231').length, 2);
for (const match of catalog.matches.slice(5)) {
  assert.equal(match.match_video_link_status, 'OFFICIAL_TITLE_ASSOCIATED_VISUAL_NOT_TESTED');
  assert.equal(match.video_source_ids.length, 1);
  assert.equal(match.recorded_result, null);
  assert.equal(match.participants[1].athlete_id, null, 'do not invent stable opponent ID');
  const source = catalog.sources.find((row) => row.source_id === match.video_source_ids[0]);
  assert(source);
  assert.equal(source.canonical_match_id, match.match_id);
  assert.equal(source.content_type_claim, 'UNKNOWN', 'official title is not independent completeness proof');
  assert.equal(source.recorded_playback_status, 'NOT_TESTED');
  assert.equal(source.thumbnail_display, 'NOT_ALLOWED');
  assert.equal(source.embedding, 'UNKNOWN');
  assert.equal(source.url, `https://www.youtube.com/watch?v=${source.video_id}`);
  const candidates = buildFanWatchRouteCandidates(source);
  assert.equal(candidates.find((row) => row.mode === 'OFFICIAL_PAGE').viewingPermission, 'PUBLIC_PLATFORM_PAGE');
  assert.equal(candidates.find((row) => row.mode === 'OFFICIAL_EMBED').embedPermission, 'UNKNOWN');
  assert(candidates.filter((row) => row.mode !== 'OFFICIAL_PAGE').every((row) => row.mode === 'OFFICIAL_EMBED' || row.viewingPermission === 'UNKNOWN'));
}
for (const changed of [
  { ...delta, contract_version: 'unknown' },
  { ...delta, base_goal15_library_sha256: '0'.repeat(64) },
  { ...delta, matches: [delta.matches[0], delta.matches[0]] },
  { ...delta, video_sources: [{ ...delta.video_sources[0], embed_permission: 'ALLOWED' }, delta.video_sources[1]] },
  { ...delta, video_sources: [{ ...delta.video_sources[0], watch_url: 'https://example.com' }, delta.video_sources[1]] },
  { ...delta, video_sources: [{ ...delta.video_sources[0], match_id: 'wrong' }, delta.video_sources[1]] },
]) assert.throws(() => applyGoal17MatchAdditions(base, changed));
if (process.argv.includes('--built')) {
  const dist = join(root, 'dist');
  function walk(dir) { return readdirSync(dir).flatMap((name) => { const path = join(dir, name); return statSync(path).isDirectory() ? walk(path) : [path]; }); }
  const files = walk(dist);
  for (const [name, hash] of [
    ['goal17-athlete-photo-additions.json', '6afb03bcc99cefaca7d8ca26005b728162fe878317e217bd705a9253fd067dc9'],
    ['goal17-official-match-video-additions.json', '6f05d1fc48fb74ffc305abe20fd9152973bd96bb009fe6a183d42c031a31198a'],
  ]) assert.equal(createHash('sha256').update(readFileSync(join(dist, 'data', name))).digest('hex'), hash);
  assert.equal(files.some((file) => /(?:reviewed-originals|goal17-media-clearance|internal)[\\/]/i.test(file)), false);
  const text = files.filter((file) => /\.(?:js|json|html|css)$/i.test(file)).map((file) => readFileSync(file, 'utf8')).join('\n');
  assert.equal(text.includes('goal17-1-photo-rights-review'), false);
}
console.log('PASS: pinned GOAL17 photos and match deltas; 7/17/8, exact source links, official-page-only rights, six negative cases and no source mutation.');
