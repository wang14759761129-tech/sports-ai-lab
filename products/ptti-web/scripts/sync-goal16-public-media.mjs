import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { consumeFanCatalog } from '../src/fan-catalog.mjs';
import { createPublicMediaIndex } from '../src/fan-media.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const manifestBytes = readFileSync(join(root, 'scripts/fixtures/goal16-media/main-public-media-v0.2.json'));
assert.equal(createHash('sha256').update(manifestBytes).digest('hex'), 'c05491a64f59ac922d2d85d081eccf3b2853f717ece82c8bcfa3d05608f2c004');
const manifest = JSON.parse(manifestBytes);
assert.equal(manifest.contract_version, 'ptti.public-media-manifest/0.2');
assert.equal(manifest.view, 'STRICT_PUBLIC_MEDIA');
assert.equal(manifest.assets.length, 4);
const catalog = consumeFanCatalog(JSON.parse(readFileSync(join(root, 'public/data/match-library-strict-public.json'))));
const admitted = manifest.assets.filter((asset) => catalog.stars.some((star) => star.athlete_id === asset.athlete_id));
assert.deepEqual(admitted.map((asset) => asset.athlete_id).sort(), ['athlete:119588', 'athlete:121411', 'athlete:123980']);
const assets = admitted.map((asset) => {
  assert.equal(asset.match_id, null);
  assert.equal(asset.match_link_status, 'NOT_LINKED_NO_DIRECT_MATCH_PHOTO_EVIDENCE');
  assert.equal(asset.use_scope, 'ATHLETE_PROFILE_EDITORIAL_ONLY');
  assert.equal(asset.promotion_use, 'NOT_CLEARED_NO_ENDORSEMENT_OR_HOMEPAGE_PROMOTION');
  assert.equal(asset.share_alike_required, true);
  assert.match(asset.license, /^CC BY-SA (?:2\.0|4\.0)$/);
  assert.equal(asset.derivatives.length, 2);
  return {
    asset_id: asset.asset_id, kind: 'ATHLETE_PORTRAIT', subject_id: asset.athlete_id,
    display_permission: 'ALLOWED', source_page_url: asset.source_page_url,
    photographer: asset.photographer, attribution: asset.attribution,
    license: asset.license, license_url: asset.license_url,
    derivative_status: 'PERMITTED', derivative_license: asset.license,
    derivative_license_url: asset.license_url, derivative_notice: asset.changes_made,
    context_notice: 'Archival athlete profile image, not photography of a listed PTTI match. No endorsement implied.',
    actual_event: asset.source_title, alt: `${asset.subject_name} — archival athlete photograph; ${asset.source_title}`,
    sizes: '(max-width: 600px) 76vw, 360px', object_position: '50% 50%',
    renditions: asset.derivatives.map((derivative) => {
      assert.equal(derivative.license, asset.license);
      assert.equal(derivative.metadata_stripped, true);
      assert.equal(derivative.format, 'WEBP');
      assert.match(derivative.path, /^assets\/[a-z0-9-]+\.webp$/);
      return { src: `/media/goal16/${derivative.path.slice('assets/'.length)}`, width: derivative.width,
        height: derivative.height, mime_type: 'image/webp', sha256: derivative.sha256 };
    }),
    depicted_athlete_ids: [asset.athlete_id], match_evidence: null,
  };
});
const goal17Bytes = readFileSync(join(root, 'public/data/goal17-athlete-photo-additions.json'));
assert.equal(createHash('sha256').update(goal17Bytes).digest('hex'), '6afb03bcc99cefaca7d8ca26005b728162fe878317e217bd705a9253fd067dc9');
const goal17 = JSON.parse(goal17Bytes);
assert.equal(goal17.contract_version, 'ptti.goal17.1-athlete-media/0.1');
assert.equal(goal17.view, 'STRICT_PUBLIC_MEDIA_DELTA');
assert.equal(goal17.base_goal16_manifest_sha256, 'c05491a64f59ac922d2d85d081eccf3b2853f717ece82c8bcfa3d05608f2c004');
assert.equal(goal17.base_goal15_library_sha256, '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930');
assert.deepEqual(goal17.assets.map((asset) => asset.athlete_id).sort(), ['athlete:121558', 'athlete:131163', 'athlete:135977']);
for (const asset of goal17.assets) {
  assert(catalog.stars.some((star) => star.athlete_id === asset.athlete_id));
  assert.equal(asset.match_id, null);
  assert.equal(asset.match_link_status, 'NOT_LINKED_NO_DIRECT_MATCH_PHOTO_EVIDENCE');
  assert.equal(asset.use_scope, 'ATHLETE_PROFILE_EDITORIAL_ONLY');
  assert.equal(asset.display_permission, 'ALLOWED_SCOPED');
  assert.equal(asset.promotion_use, 'NOT_CLEARED_NO_ENDORSEMENT_OR_ADVERTISING');
  assert.equal(asset.derivatives.length, 2);
  if (asset.athlete_id === 'athlete:131163') assert.deepEqual(asset.source_dimensions, { width: 498, height: 648 });
  if (asset.athlete_id === 'athlete:135977') assert.equal(asset.photo_presentation, 'MULTI_PLAYER_EVENT_CONTEXT');
  assets.push({
    asset_id: asset.asset_id, kind: 'ATHLETE_PORTRAIT', subject_id: asset.athlete_id,
    display_permission: 'ALLOWED', source_page_url: asset.source_page_url,
    photographer: asset.photographer, attribution: asset.attribution,
    license: asset.license, license_url: asset.license_url,
    derivative_status: 'PERMITTED', derivative_license: asset.license,
    derivative_license_url: asset.license_url, derivative_notice: asset.changes_made,
    context_notice: asset.athlete_id === 'athlete:121558'
      ? `${asset.quality_limit} Archival youth image: athlete was a minor at the time; factual profile only, no promotional or endorsement use.`
      : asset.quality_limit,
    actual_event: asset.actual_event,
    alt: `${asset.depicted_athletes.join(', ')} — ${asset.actual_event}`,
    sizes: asset.athlete_id === 'athlete:131163' ? '(max-width: 600px) 64vw, 249px' : '(max-width: 600px) 76vw, 360px',
    object_position: '50% 50%',
    renditions: asset.derivatives.map((derivative) => {
      assert.equal(derivative.format, 'WEBP');
      assert.equal(derivative.license, asset.license);
      assert.equal(derivative.metadata_stripped, true);
      assert.match(derivative.path, /^assets\/[a-z0-9-]+\.webp$/);
      return { src: `/media/goal17/${derivative.path.slice('assets/'.length)}`, width: derivative.width,
        height: derivative.height, mime_type: 'image/webp', sha256: derivative.sha256 };
    }),
    depicted_athlete_ids: [asset.athlete_id], match_evidence: null,
  });
}
const index = { contract_version: 'ptti.web-public-media-index/0.1', assets };
createPublicMediaIndex(index, catalog);
const path = join(root, 'src/approved-public-media.json');
writeFileSync(path, `${JSON.stringify(index, null, 2)}\n`);
console.log(`PASS: pinned Main GOAL16 + GOAL17 projected to ${assets.length} profile-only portraits; Groth not in strict-public catalog.`);
