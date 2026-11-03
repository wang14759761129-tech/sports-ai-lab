import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { buildGoal15RuntimeHealth } from '../src/runtime-health.mjs';

const bytes = await readFile(new URL('../public/data/match-library-strict-public.json', import.meta.url));
const pin = JSON.parse(await readFile(new URL('../scripts/contracts/goal15-fan-universe-source-pin.json', import.meta.url), 'utf8'));
const actualSha = createHash('sha256').update(bytes).digest('hex');
const oldStartupPin = {
  main_source_commit: 'f58605880cdbacf9502b1ca0a5cd3d5143b1f99c',
  artifact_sha256: 'ca714727ebe43fd091b7e52a2c8e31225c6deba65fde30765e9da6f360c12ee2',
  schema_sha256: pin.schema_sha256,
};

const stale = buildGoal15RuntimeHealth({
  sanHead: 'san-head-current',
  sanHeadAtConfigLoad: 'san-head-at-config-load',
  playbackCoreHead: 'playback-head-fixed',
  playbackCoreSourceSha256: 'playback-core-source-sha',
  watchRoutingSourceSha256: 'watch-routing-source-sha',
  configLoadedAt: '2026-10-18T10:00:00.000Z',
  startupPin: oldStartupPin,
  catalogBytes: bytes,
});
assert.equal(stale.san_git_head_current, 'san-head-current');
assert.equal(stale.service_startup.san_git_head_observed_at_config_load, 'san-head-at-config-load');
assert.equal(stale.service_startup.goal15_pin.main_source_commit, oldStartupPin.main_source_commit);
assert.equal(stale.service_startup.goal15_pin.catalog_sha256, oldStartupPin.artifact_sha256);
assert.equal(stale.current_strict_public_catalog.sha256, actualSha);
assert.equal(stale.current_strict_public_catalog.sha256, '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930');
assert.equal(stale.current_strict_public_catalog.consumer_validation, 'PASS');
assert.equal(stale.current_strict_public_catalog.startup_pin_match, false);
assert.equal(stale.current_strict_public_catalog.counts.matches, 5);

const matching = buildGoal15RuntimeHealth({
  sanHead: 'san-head-current',
  sanHeadAtConfigLoad: 'san-head-at-config-load',
  playbackCoreHead: 'playback-head-fixed',
  playbackCoreSourceSha256: 'playback-core-source-sha',
  watchRoutingSourceSha256: 'watch-routing-source-sha',
  configLoadedAt: '2026-10-18T10:00:00.000Z',
  startupPin: pin,
  catalogBytes: bytes,
});
assert.equal(matching.current_strict_public_catalog.startup_pin_match, true);
assert.deepEqual(matching.current_strict_public_catalog.counts, {
  matches: 5,
  sources: 15,
  stars: 8,
  human_verified_match_source_edges: 5,
  full_match_claims: 3,
  event_highlight_claims: 10,
  clip_claims: 0,
  unknown_content_claims: 2,
  playback_passes: 0,
  source_manifest_entries: 0,
});

const malformed = buildGoal15RuntimeHealth({
  sanHead: 'san-head-current',
  sanHeadAtConfigLoad: 'san-head-at-config-load',
  playbackCoreHead: 'playback-head-fixed',
  playbackCoreSourceSha256: 'playback-core-source-sha',
  watchRoutingSourceSha256: 'watch-routing-source-sha',
  configLoadedAt: '2026-10-18T10:00:00.000Z',
  startupPin: pin,
  catalogBytes: Buffer.from('{broken-json'),
});
assert.equal(malformed.current_strict_public_catalog.consumer_validation, 'FAIL');
assert.equal(malformed.current_strict_public_catalog.counts, null);
assert.equal(malformed.current_strict_public_catalog.sha256, createHash('sha256').update('{broken-json').digest('hex'));

console.log('PASS: startup pin, current catalog bytes, and current San HEAD are reported as separate identities.');
console.log('PASS: stale startup pins are exposed as mismatches without rewriting history.');
console.log('PASS: current v0.2 counts are derived from the actual catalog bytes; malformed data fails closed.');
