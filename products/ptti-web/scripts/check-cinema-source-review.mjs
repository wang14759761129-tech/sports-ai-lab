import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { consumeCinemaSourceReview } from '../src/cinema-source-review.mjs';
import { consumeMatchLibrary } from '../src/match-library.mjs';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const integrationRoot = path.resolve(process.env.PTTI_INTEGRATION_DIR ?? path.resolve(project, '../../../integration-preview-sprint-0-1/products/ptti-integration'));
const readJson = async (file) => JSON.parse(await readFile(file, 'utf8'));
const schema = await readJson(path.join(integrationRoot, 'contracts/cinema-source-review-v0.1.schema.json'));
const sourcePath = path.join(integrationRoot, 'generated/goal12-3/cinema-source-review-internal.json');
const input = await readJson(sourcePath);
const publicPath = path.join(integrationRoot, 'generated/goal11-match-library/match-library-strict-public.json');
const strictInput = await readJson(publicPath);

assert.equal(schema.$id, 'https://ptti.invalid/contracts/cinema-source-review-v0.1.schema.json');
assert.equal(schema.properties.contract_version.const, 'ptti.cinema-source-review/0.1');
assert.equal(schema.properties.source_contract_version.const, 'ptti.match-library-index/0.1');
assert.equal(schema.properties.input_contract_version.const, 'ptti.cinema-source-review-input/0.1');
assert.equal(schema.properties.audience.const, 'INTERNAL_REVIEW_ONLY');
assert.equal(schema.properties.catalog_snapshot.properties.strict_public_video_source_count.const, 0);
assert.equal(schema.properties.summary.properties.external_visual_playback_pass.const, 0);
assert.equal(schema.properties.summary.properties.canonical_match_links.const, 0);
assert.equal(schema.$defs.source.properties.watch_status.$ref, '#/$defs/watchStatus');

const result = consumeCinemaSourceReview(input);
const strict = consumeMatchLibrary(strictInput, 'STRICT_PUBLIC');
assert.equal(input.catalog_snapshot.unique_video_sources, 35);
assert.equal(input.catalog_snapshot.registered_match_records, 6);
assert.equal(input.catalog_snapshot.canonical_video_match_links, 0);
assert.equal(result.catalog_snapshot.strict_public_video_source_count, 0);
assert.deepEqual(strict, { view: 'STRICT_PUBLIC', sources: [], registered_match_count: 0, source_count: 0 });
assert.equal(result.sources.length, 3);
assert.equal(result.summary.selected_sources, 3);
assert.equal(result.summary.external_visual_playback_pass, 0);
assert.equal(result.summary.canonical_match_links, 0);

for (const [index, row] of input.featured_sources.entries()) {
  const projected = result.sources[index];
  assert.equal(projected.source_id, row.source_id);
  assert.equal(projected.video_id, row.video_id);
  assert.equal(projected.original_source_url, row.original_source_url);
  assert.equal(projected.watch_entry, 'EXTERNAL_SOURCE_LINK_ONLY');
  assert.equal(projected.audience, 'INTERNAL_REVIEW_ONLY');
  assert.equal(projected.match_link.canonical_match_id, null);
  assert.equal(projected.match_link.status, 'UNKNOWN');
  assert.equal(projected.match_claim.official_source_references_video_id, false);
  assert.equal(projected.watch_status.external_visual_video_playback, 'NOT_TESTED');
  assert.equal(projected.watch_status.in_app_entry, 'EXTERNAL_ONLY_PERMISSION_UNVERIFIED');
  assert.equal(projected.content_claim.completeness, 'UNVERIFIED');
  assert.equal(projected.thumbnail.url, null);
  assert.deepEqual(projected.rights, row.rights);
  assert.equal(Object.hasOwn(projected, 'playback_authorized'), false);
  assert.equal(Object.hasOwn(projected, 'can_play'), false);
}

const rejects = (mutate, pattern) => {
  const bad = structuredClone(input);
  mutate(bad);
  assert.throws(() => consumeCinemaSourceReview(bad), pattern);
};
rejects((bad) => { bad.contract_version = 'ptti.cinema-source-review/9'; }, /unsupported protocol version/);
rejects((bad) => { bad.audience = 'PUBLIC'; }, /not internal-review-only/);
rejects((bad) => { bad.catalog_snapshot.strict_public_video_source_count = 1; }, /public or canonical match projection/);
rejects((bad) => { bad.featured_sources[0].original_source_url = 'https://www.youtube.com/watch?v=wrong'; }, /exact YouTube video/);
rejects((bad) => { bad.featured_sources[0].match_claim.official_source_references_video_id = true; }, /cannot establish a canonical video-to-match link/);
rejects((bad) => { bad.featured_sources[0].watch_status.external_visual_video_playback = 'PLAYBACK_PASS'; }, /cannot claim visual playback/);
rejects((bad) => { bad.featured_sources[0].rights.public_listing = 'MAYBE'; }, /unsupported permission state/);
rejects((bad) => { bad.featured_sources[1] = structuredClone(bad.featured_sources[0]); }, /duplicate source_id/);
rejects((bad) => { delete bad.featured_sources[0].next_evidence_needed; }, /unsupported or missing fields/);

console.log(`Cinema source review v0.1 PASS: consumed ${result.sources.length} real internal-review records from ${sourcePath}; 35 sources/6 matches snapshot, canonical links 0, visual playback 0, strict-public sources ${strict.source_count}; 9 negative cases rejected.`);
