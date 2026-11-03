import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { canonicalJsonSha256Input, consumeGoal14FanDelivery, consumeGoal14StrictPublic, evaluateGoal14WatchRoutes } from '../src/fan-content-delivery.mjs';

const root = process.cwd();
const pin = JSON.parse(readFileSync(resolve(root, 'scripts/contracts/goal14-content-source-pin.json'), 'utf8'));
const privateRoot = resolve(root, '.alpha-qa/goal14');
const rawBase = readFileSync(resolve(privateRoot, 'fan-content-internal-review.json'));
const rawDelivery = readFileSync(resolve(privateRoot, 'fan-content-delivery-internal-review.json'));
const rawLocalization = readFileSync(resolve(privateRoot, 'fan-localization-v0.1.json'), 'utf8');
const rawPublic = readFileSync(resolve(root, 'public/data/goal14-fan-content-strict-public.json'));
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');
const base = JSON.parse(rawBase.toString('utf8'));
const delivery = JSON.parse(rawDelivery.toString('utf8'));
const localization = JSON.parse(rawLocalization);
const strictPublic = JSON.parse(rawPublic.toString('utf8'));

assert.equal(sha256(rawBase), pin.sha256.internalDatasetBytes, 'Main base dataset bytes are pinned');
assert.equal(sha256(rawDelivery), pin.sha256.deliveryProjectionBytes, 'Main delivery bytes are pinned');
assert.equal(sha256(rawPublic), pin.sha256.strictPublicBytes, 'Main strict-public bytes are pinned');
assert.equal(delivery.source_manifest.base_dataset_sha256, sha256(rawBase), 'delivery manifest binds exact base JSON bytes');
assert.equal(sha256(canonicalJsonSha256Input(localization)), pin.sha256.localizationCanonicalJson, 'localization uses Main canonical JSON hash');
assert.equal(delivery.source_manifest.localization_sha256, pin.sha256.localizationCanonicalJson);
assert.equal(base.contract_version, 'ptti.fan-content-intelligence/0.1');
assert.equal(base.view, 'INTERNAL_REVIEW');
consumeGoal14StrictPublic(strictPublic);

const accepted = consumeGoal14FanDelivery(delivery);
assert.equal(accepted.events.length, 5);
assert.equal(accepted.stars.length, 3);
assert.equal(accepted.clips.length, 20);
assert.equal(accepted.watch_sources.length, 14);
assert.equal(accepted.matches.length, 0);
assert.equal(accepted.quality_summary.exact_video_url_count, 10);
assert.equal(accepted.quality_summary.event_page_only_count, 10);
assert.equal(accepted.quality_summary.playback_pass_count, 0);
assert.equal(accepted.quality_summary.public_eligible_count, 0);
assert.equal(accepted.quality_summary.match_video_links, 0);
assert.ok(accepted.clips.every((clip) => clip.public_status === 'INTERNAL_ONLY_PENDING_RIGHTS_REVIEW'
  && clip.playback_status === 'NOT_TESTED' && clip.match_id === null && clip.match_link_status === 'UNKNOWN'
  && clip.thumbnail_url === null && clip.rights.external_viewing === 'UNKNOWN'));
assert.deepEqual(accepted.stars.map((star) => star.athlete_id), ['athlete:135977', 'athlete:121558', 'athlete:123980']);
assert.ok(accepted.relationships.some((row) => row.from_type === 'ATHLETE' && row.to_type === 'EVENT'
  && row.relationship_kind === 'LISTED_ON_EVENT_PLAYER_ROSTER'
  && row.confidence_scope === 'EVENT_ROSTER_LISTING_ONLY_NOT_CLIP_APPEARANCE'));

// Negative cases: fail closed on contract, identities, relationships, URL joins and rights.
const clone = () => structuredClone(delivery);
assert.throws(() => consumeGoal14FanDelivery({ ...clone(), contract_version: 'ptti.fan-content-delivery/9.9' }), /unsupported-delivery-version/);
assert.throws(() => consumeGoal14FanDelivery({ ...clone(), view: 'STRICT_PUBLIC' }), /internal-review-view-required/);
assert.throws(() => consumeGoal14FanDelivery({ ...clone(), matches: [{ match_id: 'guessed' }] }), /goal14-match-identity-not-established/);
{
  const value = clone(); value.clips[0].match_id = 'match:guessed';
  assert.throws(() => consumeGoal14FanDelivery(value), /guessed-match-link/);
}
{
  const value = clone(); value.clips[0].rights.external_viewing = 'ALLOWED';
  assert.throws(() => consumeGoal14FanDelivery(value), /rights-escalation/);
}
{
  const value = clone(); value.clips[0].official_video_url = 'https://www.youtube.com/watch?v=wrong';
  assert.throws(() => consumeGoal14FanDelivery(value), /video-id-url-mismatch/);
}
{
  const value = clone(); value.clips[0].event_id = 'event:unknown';
  assert.throws(() => consumeGoal14FanDelivery(value), /unknown-clip-event/);
}
{
  const value = clone(); value.clips[0].watch_source_id = 'watch:missing';
  assert.throws(() => consumeGoal14FanDelivery(value), /unknown-clip-watch-source/);
}
{
  const value = clone(); value.clips[0].thumbnail_url = 'https://example.com/cover.jpg';
  assert.throws(() => consumeGoal14FanDelivery(value), /unlicensed-thumbnail-present/);
}
{
  const value = clone(); value.quality_summary.match_video_links = 1;
  assert.throws(() => consumeGoal14FanDelivery(value), /quality-summary-mismatch:match_video_links/);
}
{
  const value = clone(); value.relationships[0].evidence_ids = ['evidence:missing'];
  assert.throws(() => consumeGoal14FanDelivery(value), /unknown-relationship-evidence/);
}
{
  const value = structuredClone(strictPublic); value.content_candidates.push({ candidate_id: 'internal-leak' });
  assert.throws(() => consumeGoal14StrictPublic(value), /strict-public-must-remain-empty/);
}

// Adapter calls all five real route modes without upgrading unknown viewing rights.
const firstSource = accepted.watch_sources.find((row) => row.provider === 'YOUTUBE');
const captured = [];
const decisions = evaluateGoal14WatchRoutes(firstSource, accepted.source_index, (candidate) => {
  captured.push(candidate);
  return { state: candidate.viewingPermission === 'UNKNOWN' ? 'BLOCKED' : 'ELIGIBLE', reason: 'VIEW_PERMISSION_UNKNOWN', playbackEvidence: candidate.playbackEvidence };
});
assert.deepEqual(captured.map((row) => row.mode), ['OFFICIAL_EMBED', 'OFFICIAL_PAGE', 'AUTHORIZED_SOURCE', 'REPLAY', 'LIVE_SCORE']);
assert.ok(captured.every((row) => row.sourceReference === 'VERIFIED' && row.viewingPermission === 'UNKNOWN'));
assert.equal(decisions.length, 5);
assert.ok(decisions.every((row) => row.decision.state === 'BLOCKED'));

console.log('PASS: Main GOAL14 delivery 0.1 consumed from the pinned local snapshot (5 events, 3 stars, 20 candidates, 14 routes).');
console.log('PASS: 10 exact video URLs, 10 event-page-only routes, 0 match-video links, 0 playback passes, 0 public admissions.');
console.log('PASS: 11 fail-closed cases and five-route unknown-permission adapter check.');
