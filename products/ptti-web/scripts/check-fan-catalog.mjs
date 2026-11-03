import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { consumeFanCatalog, filterFanClips, filterFanHighlights, filterFanSources, findAdmittedFullMatch, searchFanCatalog } from '../src/fan-catalog.mjs';

const deliveredBytes = await readFile(new URL('../public/data/match-library-strict-public.json', import.meta.url));
const goal15Pin = JSON.parse(await readFile(new URL('../scripts/contracts/goal15-fan-universe-source-pin.json', import.meta.url), 'utf8'));
assert.equal(createHash('sha256').update(deliveredBytes).digest('hex'), goal15Pin.artifact_sha256, 'Main strict-public bytes changed from the reviewed Goal15 snapshot');
assert.equal(goal15Pin.main_source_commit, 'eb0a52af32eaaf26dfd39cf1ce5f321e24a1adac');
assert.equal(goal15Pin.artifact_sha256, '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930');
assert.equal(goal15Pin.projection_release, 'GOAL15_MAIN_PUBLIC_PROJECTION/0.2');
const schemaBytes = await readFile(new URL('../scripts/contracts/goal15-main-fan-universe-match-library-index-v0.1.schema.json', import.meta.url));
assert.equal(createHash('sha256').update(schemaBytes).digest('hex'), goal15Pin.schema_sha256, 'Candidate copy must remain byte-identical to Main Match Library v0.1 schema');
assert.equal(JSON.parse(schemaBytes.toString('utf8')).$id, 'https://ptti.invalid/contracts/match-library-index-v0.1.schema.json');
const delivered = JSON.parse(deliveredBytes.toString('utf8'));
const publicCatalog = consumeFanCatalog(delivered);
assert.equal(publicCatalog.contract_version, 'ptti.match-library-index/0.1');
assert.deepEqual({ matches: publicCatalog.matches.length, sources: publicCatalog.sources.length, stars: publicCatalog.stars.length }, { matches: 5, sources: 15, stars: 8 });
assert.equal(delivered.view, 'STRICT_PUBLIC');
assert.deepEqual(delivered.source_manifest, [], 'v0.2 public projection must not expose provenance paths');
assert.equal(publicCatalog.matches[0].match_id, 'pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun');
assert.equal(publicCatalog.matches[0].video_source_ids[0], 'video-source:youtube:0QgbtsBWZhk');
assert.equal(publicCatalog.matches[0].match_video_link_status, 'HUMAN_VERIFIED');
assert.deepEqual(publicCatalog.matches[0].recorded_result, { player_a_games: 4, player_b_games: 0 });
assert.equal(publicCatalog.matches[0].result_status, 'OFFICIAL_EVENT_RESULT_CROSSCHECKED');
assert.deepEqual(publicCatalog.stars.map((star) => star.athlete_id).sort(), ['athlete:119588', 'athlete:121411', 'athlete:121558', 'athlete:123980', 'athlete:131163', 'athlete:135049', 'athlete:135977', 'athlete:137237']);
assert.deepEqual(publicCatalog.stars.filter((star) => star.linked_matches.includes(publicCatalog.matches[0].match_id)).map((star) => star.athlete_id).sort(), ['athlete:121558', 'athlete:135977']);
assert.equal(publicCatalog.sources[0].url, 'https://www.youtube.com/watch?v=0QgbtsBWZhk');
assert.equal(publicCatalog.sources[0].thumbnail_display, 'NOT_ALLOWED');
assert.equal(publicCatalog.sources[0].embedding, 'UNKNOWN');
assert.equal(publicCatalog.sources[0].recorded_playback_status, 'EMBED_BLOCKED_HISTORICAL');
assert.equal(publicCatalog.sources[0].current_session_eligibility, 'NOT_EVALUATED_CURRENT_SESSION');
assert.equal(publicCatalog.sources[0].territory, 'UNKNOWN');
assert.equal(delivered.video_sources[0].completeness_status, 'UNVERIFIED');
assert.equal(delivered.video_sources[0].rights.local_analysis, 'NOT_GRANTED');
assert.equal(delivered.video_sources[0].rights.redistribution, 'NOT_GRANTED');
assert.equal(delivered.local_video_assets.length, 0);
assert.deepEqual(filterFanSources(publicCatalog, { athleteId: 'athlete:121558' }).map((source) => source.source_id), ['video-source:youtube:0QgbtsBWZhk', 'video-source:youtube:cDccQqVlMnc']);
assert.deepEqual(filterFanSources(publicCatalog, { athleteId: 'athlete:135977', contentType: 'FULL_MATCH' }).map((source) => source.source_id), ['video-source:youtube:0QgbtsBWZhk']);
assert.deepEqual(filterFanSources(publicCatalog, { athleteId: 'athlete:unknown' }), []);
assert.deepEqual(filterFanSources(publicCatalog, { contentType: 'UNKNOWN' }).map((source) => source.source_id), [
  'video-source:youtube:jv_XQ6oKaDU',
  'video-source:youtube:lb4UMbE8Pfs',
], 'unknown content type stays visible only as an explicitly unknown source, never as a short clip');
assert.deepEqual(filterFanClips(publicCatalog), [], 'a FULL_MATCH source must remain available from Cinema/Watch, not appear as a Clips item');
assert.equal(findAdmittedFullMatch(publicCatalog)?.match_id, 'pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun', 'Clips empty-state action can target only an exact-ID-linked admitted full match');
{
  const unverifiedLink = structuredClone(publicCatalog);
  unverifiedLink.matches[0].match_video_link_status = 'UNKNOWN';
  assert.notEqual(findAdmittedFullMatch(unverifiedLink)?.match_id, publicCatalog.matches[0].match_id, 'unverified match-source relation cannot power that match route');
}
{
  const mismatchedSource = structuredClone(publicCatalog);
  mismatchedSource.sources[0].canonical_match_id = 'match:other';
  assert.notEqual(findAdmittedFullMatch(mismatchedSource)?.match_id, publicCatalog.matches[0].match_id, 'mismatched source ID cannot power that match route');
}
assert.equal(publicCatalog.stars.find((star) => star.athlete_id === 'athlete:121558')?.name_zh, '王楚钦');
assert.equal(publicCatalog.stars.find((star) => star.athlete_id === 'athlete:135977')?.name_en, 'Felix LEBRUN');
assert.equal(publicCatalog.stars.find((star) => star.athlete_id === 'athlete:131163')?.name_zh, '孙颖莎');
assert.equal(publicCatalog.stars.find((star) => star.athlete_id === 'athlete:121411')?.name_zh, '王曼昱');
assert(delivered.stars.every((star) => star.public_listing === 'ALLOWED'), 'all consumed star records come from Main strict-public admission');
assert.equal(publicCatalog.sources.filter((source) => source.match_link_status === 'HUMAN_VERIFIED').length, 5);
assert.equal(publicCatalog.sources.filter((source) => source.content_type_claim === 'FULL_MATCH').length, 3);
assert.equal(filterFanHighlights(publicCatalog).length, 10);
assert(filterFanHighlights(publicCatalog).every((source) => source.match_link_status === 'UNKNOWN' && source.canonical_match_id === null && source.external_viewing === 'ALLOWED'));
assert.equal(publicCatalog.sources.filter((source) => source.content_type_claim === 'UNKNOWN').length, 2);
assert.equal(publicCatalog.sources.filter((source) => source.recorded_playback_status === 'PASS').length, 0, 'no external playback result is inferred from an official URL');
assert.equal(publicCatalog.stars.find((star) => star.athlete_id === 'athlete:121411')?.linked_matches.includes('pro:wtt:china-smash-2025:sun-yingsha-wang-manyu-ws-final'), true, 'exact athlete IDs link Sun Yingsha and Wang Manyu to their final');
assert.deepEqual(searchFanCatalog(publicCatalog, '林昀儒').matches.map((match) => match.match_id), ['pro:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final']);
assert.deepEqual(searchFanCatalog(publicCatalog, 'Wang Chuqin').stars.map((star) => star.athlete_id), ['athlete:121558']);
assert(searchFanCatalog(publicCatalog, 'Felix Lebrun').matches.some((match) => match.match_id === 'pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun'));
assert.equal(searchFanCatalog(publicCatalog, 'China Smash').matches.length, 2);
assert.equal(searchFanCatalog(publicCatalog, 'Singapore Smash').matches.length, 1);
assert(searchFanCatalog(publicCatalog, '孙颖莎').stars.some((star) => star.athlete_id === 'athlete:131163'));
assert(searchFanCatalog(publicCatalog, '王曼昱').matches.some((match) => match.match_id === 'pro:wtt:china-smash-2025:sun-yingsha-wang-manyu-ws-final'));
assert(searchFanCatalog(publicCatalog, 'Lin Yun-Ju').matches.some((match) => match.match_id === 'pro:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final'));

function permittedFixture() {
  const sourceId = 'video-source:youtube:abc123';
  return {
    contract_version: 'ptti.match-library-index/0.1', view: 'STRICT_PUBLIC', generated_at: '2026-10-18T00:00:00Z',
    source_manifest: [], local_video_assets: [], evidence_sources: [], quality_summary: { public_match_count: 1, public_video_source_count: 1, public_star_count: 1 }, notice: 'Test-only permission-path fixture.',
    analysis_compatibility: { review_targets_version: 'ptti.review-targets/0.1', review_evidence_pack_version: 'ptti.review-evidence-pack/0.1', automatic_join_by_title_or_player_name: false, join_policy: 'EXACT_MATCH_ID_AND_SOURCE_ID_WITH_EVIDENCE_ONLY', playback_eligibility: 'NOT_EVALUATED_CURRENT_SESSION' },
    matches: [{ match_id: 'match:fixture', identity_status: 'REGISTERED_WITH_SOURCE_REFERENCES', event: { name: 'Fixture event' }, round: 'Final', match_type: 'MS', participants: [{ side: 'A', athlete_id: 'athlete:fixture', name_en: 'Player One' }], recorded_result: null, result_status: 'RECORDED_NOT_REVERIFIED', reference_url: null, evidence_source_ids: ['evidence:match'], video_source_ids: [sourceId], match_video_link_status: 'HUMAN_VERIFIED', rights: { public_listing: 'ALLOWED' } }],
    video_sources: [{ catalog_record_id: 'catalog:fixture', source_id: sourceId, video_id: 'abc123', platform: 'YOUTUBE', official_url: 'https://www.youtube.com/watch?v=abc123', watch_entry: 'OPEN_OFFICIAL_PLATFORM_URL', title: 'Claimed clip', event: 'Fixture event', event_year: 2026, match_type: 'MS', round: 'Final', participants_claimed: { side_a: 'Player One' }, publisher: 'Publisher', publisher_url: null, source_verified_at: '2026-10-18T00:00:00Z', source_identity_status: 'VERIFIED', publisher_identity_status: 'VERIFIED', identity_conflicts: [], canonical_match_id: 'match:fixture', match_link_status: 'HUMAN_VERIFIED', content_type_claim: 'HIGHLIGHTS', completeness_status: 'UNVERIFIED', rights: { public_listing: 'ALLOWED', external_viewing: 'ALLOWED', thumbnail_display: 'UNKNOWN', embedding: 'UNKNOWN', local_analysis: 'NOT_GRANTED', redistribution: 'NOT_GRANTED' }, thumbnail: { url: null, source_has_thumbnail_url: false, display_status: 'NOT_DISPLAYED' }, availability: { current_session_eligibility: 'NOT_EVALUATED_CURRENT_SESSION', vision_analysis: 'NOT_TESTED', latest_recorded_playback_status: 'NOT_TESTED', territory_availability: 'UNKNOWN' }, provenance: [] }],
    stars: [{ athlete_id: 'athlete:fixture', name_en: 'Player One', name_zh: '球员一', association: 'Association', official_profile_url: 'https://example.org/profile', profile_last_verified_at: null, evidence_source_ids: ['evidence:star'], public_listing: 'ALLOWED', equipment: { status: 'UNKNOWN', items: [] }, coach_observations: {}, interviews: {}, sponsorships: {}, social_feedback: {} }],
  };
}

const testOnly = permittedFixture();
const projected = consumeFanCatalog(testOnly);
assert.deepEqual(filterFanClips(projected), [], 'event-level highlights do not enter the short Clips section');
assert.deepEqual(filterFanHighlights(projected).map((source) => source.source_id), ['video-source:youtube:abc123'], 'an admitted event highlight appears in the separate Highlights section');
assert.equal(projected.sources[0].url, 'https://www.youtube.com/watch?v=abc123');
assert.deepEqual(projected.stars[0].linked_matches, ['match:fixture']);
assert.equal(projected.matches[0].video_source_ids[0], projected.sources[0].source_id);
assert.equal(projected.sources[0].current_session_eligibility, 'NOT_EVALUATED_CURRENT_SESSION');
const unknownViewing = structuredClone(testOnly);
unknownViewing.video_sources[0].rights.external_viewing = 'UNKNOWN';
assert.equal(consumeFanCatalog(unknownViewing).sources[0].url, null, 'unknown external-viewing permission must not produce a watch link');

let rejected = 0;
for (const mutate of [
  (x) => { x.view = 'INTERNAL_REVIEW'; },
  (x) => { x.contract_version = 'ptti.match-library-index/0.2'; },
  (x) => { x.video_sources[0].rights.public_listing = 'UNKNOWN'; },
  (x) => { x.video_sources[0].official_url = 'https://untrusted.example/watch'; },
  (x) => { x.video_sources[0].thumbnail.url = 'https://example.org/image.jpg'; },
  (x) => { x.matches[0].video_source_ids = ['video-source:youtube:other']; },
  (x) => { x.video_sources[0].canonical_match_id = null; },
  (x) => { x.stars[0].public_listing = 'NOT_ALLOWED'; },
  (x) => { x.matches[0].rights.public_listing = 'UNKNOWN'; },
  (x) => { x.analysis_compatibility.automatic_join_by_title_or_player_name = true; },
  (x) => { x.local_video_assets = [{ path: 'private.mp4' }]; },
  (x) => { delete x.analysis_compatibility.review_evidence_pack_version; },
  (x) => { delete x.matches[0].identity_status; },
]) {
  const invalid = structuredClone(testOnly);
  mutate(invalid);
  assert.throws(() => consumeFanCatalog(invalid));
  rejected++;
}
assert.throws(() => consumeFanCatalog({ ...testOnly, video_sources: [testOnly.video_sources[0], structuredClone(testOnly.video_sources[0])] }), /duplicate-source-id/);
rejected++;
console.log(`Fan catalog: Goal15 Main STRICT_PUBLIC 5 matches / 15 sources / 8 stars, 5 exact match-source links and 10 event-level highlights verified; clips remain 0; ${rejected} unsafe catalog cases rejected.`);
