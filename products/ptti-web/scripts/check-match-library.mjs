import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { consumeMatchLibrary } from '../src/match-library.mjs';
import { consumeFanCatalog } from '../src/fan-catalog.mjs';

const publicDoc = JSON.parse(await readFile(new URL('../public/data/match-library-strict-public.json', import.meta.url), 'utf8'));
const publicCatalog = consumeFanCatalog(publicDoc);
assert.deepEqual([publicCatalog.matches.length, publicCatalog.sources.length, publicCatalog.stars.length], [5, 15, 8]);
assert.equal(publicCatalog.sources.filter((source) => source.match_link_status === 'HUMAN_VERIFIED').length, 5);
assert.equal(publicCatalog.sources.filter((source) => source.content_type_claim === 'HIGHLIGHTS').length, 10);
assert.equal(publicCatalog.sources.filter((source) => source.content_type_claim === 'CLIP').length, 0);
assert.deepEqual(publicDoc.source_manifest, [], 'strict-public projection must not contain internal source paths');
assert.equal(publicCatalog.sources.filter((source) => source.content_type_claim === 'UNKNOWN').length, 2);
assert.equal(publicCatalog.matches[0].match_id, 'pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun');
assert.deepEqual(publicCatalog.matches[0].video_source_ids, ['video-source:youtube:0QgbtsBWZhk']);
assert.equal(publicCatalog.sources[0].url, 'https://www.youtube.com/watch?v=0QgbtsBWZhk');
assert.equal(publicCatalog.sources[0].thumbnail_display, 'NOT_ALLOWED');
assert.equal(publicCatalog.sources[0].embedding, 'UNKNOWN');
assert.equal(publicCatalog.sources[0].territory, 'UNKNOWN');
assert.equal(publicCatalog.sources[0].recorded_playback_status, 'EMBED_BLOCKED_HISTORICAL');
assert.equal(publicCatalog.sources[0].current_session_eligibility, 'NOT_EVALUATED_CURRENT_SESSION');
assert.throws(() => consumeFanCatalog({ ...publicDoc, view: 'INTERNAL_REVIEW' }), /strict-public-view-required/);

let internalReviewStatus = 'NOT_TESTED: internal review QA fixture is absent';
let internalNegativeCases = 0;
try {
  const raw = await readFile(new URL('../.alpha-qa/match-library/internal-review.json', import.meta.url));
  const internal = JSON.parse(raw);
  const receipt = JSON.parse(await readFile(new URL('../.alpha-qa/match-library/import-receipt.json', import.meta.url), 'utf8'));
  assert.equal(createHash('sha256').update(raw).digest('hex'), receipt.artifacts['internal-review'].sha256);
  const projection = consumeMatchLibrary(internal, 'INTERNAL_REVIEW');
  assert.equal(projection.source_count, 35);
  assert.equal(projection.registered_match_count, 6);
  assert.equal(new Set(projection.sources.map(source => source.source_id)).size, 35);
  assert(projection.sources.every(source => source.match_link_status === 'UNKNOWN' && source.current_session_eligibility === 'NOT_EVALUATED_CURRENT_SESSION'));
  assert(projection.sources.every(source => !Object.hasOwn(source, 'thumbnail')));
  assert.throws(() => consumeMatchLibrary(internal, 'STRICT_PUBLIC'), /view-mismatch/);
  for (const mutate of [
    d => { d.contract_version = 'ptti.match-library-index/9'; },
    d => { d.local_video_assets = [{}]; },
    d => { d.video_sources.push(structuredClone(d.video_sources[0])); },
    d => { d.video_sources[0].official_url = 'javascript:alert(1)'; },
    d => { d.video_sources[0].official_url = 'https://untrusted.example/video'; },
    d => { d.video_sources[0].thumbnail.url = 'https://example.com/unlicensed.jpg'; },
    d => { d.video_sources[0].canonical_match_id = d.matches[0].match_id; },
    d => { d.matches[0].video_source_ids = [d.video_sources[0].source_id]; },
    d => { d.video_sources[0].rights.public_listing = 'FAKE_ALLOWED'; },
    d => { d.video_sources[0].availability.current_session_eligibility = 'PASS'; },
    d => { d.analysis_compatibility.automatic_join_by_title_or_player_name = true; },
    d => { delete d.video_sources[0].source_identity_status; },
  ]) {
    const value = structuredClone(internal);
    mutate(value);
    assert.throws(() => consumeMatchLibrary(value, 'INTERNAL_REVIEW'));
    internalNegativeCases++;
  }
  const forgedPublic = structuredClone(internal);
  forgedPublic.view = 'STRICT_PUBLIC';
  assert.throws(() => consumeMatchLibrary(forgedPublic, 'STRICT_PUBLIC'), /public-grant/);
  internalNegativeCases++;
  internalReviewStatus = `PASS: 35 internal source records remain separately rejected from strict public; ${internalNegativeCases} negative cases`;
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}

console.log(`GOAL15 public Match Library PASS: 5 matches, 15 sources, 8 stars, 5 exact match-source edges; media permissions and NOT_TESTED playback retained.`);
console.log(`Internal review isolation: ${internalReviewStatus}.`);
