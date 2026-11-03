import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import {
  FOUNDATION_KINDS,
  mediaSourceToFoundation,
  momentCardToFoundation,
  simulatedPointToFoundation,
  validateFoundationBundle,
  validateFoundationRecord,
  videoAssetFromMediaSource,
} from '../src/foundationContract.mjs';
import {
  PERSONAL_DISCOVERY_KEY,
  buildGrowthShelf,
  emptyPersonalDiscoveryProfile,
  rankDiscoveryItems,
  readPersonalDiscovery,
  recordOpenRequest,
  saveTrustedLocalProgress,
  validatePersonalDiscoveryProfile,
  writePersonalDiscovery,
} from '../src/personalDiscovery.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const fixtures = JSON.parse(readFileSync(resolve(here, '../../contracts/foundation-v0.1.examples.json'), 'utf8'));
const clone = value => structuredClone(value);

function memoryStorage(initial = null, {failSet = false} = {}) {
  const values = new Map(initial === null ? [] : [[PERSONAL_DISCOVERY_KEY, initial]]);
  return {
    values,
    writes: 0,
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) {
      this.writes += 1;
      if (failSet) throw new Error('quota exceeded');
      values.set(key, String(value));
    },
  };
}

test('12 versioned Foundation examples validate and exact references resolve', () => {
  assert.equal(fixtures.length, 12);
  assert.deepEqual([...new Set(fixtures.map(row => row.kind))].sort(), [...FOUNDATION_KINDS].sort());
  assert.equal(validateFoundationBundle(fixtures), true);
});

test('media timeline requires exact asset identity and valid bounds', () => {
  const moment = clone(fixtures.find(row => row.kind === 'Moment'));
  moment.timeline_anchor = null;
  assert.throws(() => validateFoundationRecord(moment), /TIMELINE_REQUIRED/);
  const mismatched = clone(fixtures.find(row => row.kind === 'Rally'));
  mismatched.timeline_anchor.video_asset_id = 'other-asset';
  assert.throws(() => validateFoundationRecord(mismatched), /TIMELINE_ASSET_MISMATCH/);
  const outside = clone(fixtures.find(row => row.kind === 'Moment'));
  outside.timeline_anchor.timestamp_ms = 60001;
  assert.throws(() => validateFoundationBundle([fixtures[0], fixtures[1], fixtures[2], outside]), /TIMELINE_OUT_OF_RANGE/);
});

test('simulation events cannot be dressed up as real media events', () => {
  const point = simulatedPointToFoundation({ recordId: 'p:1', pointId: 'point:1', simulationId: 'sim:1', sequenceIndex: 0 });
  assert.equal(validateFoundationRecord(point), true);
  assert.throws(() => simulatedPointToFoundation({ recordId: 'p:2', pointId: 'point:2', simulationId: 'sim:1', sequenceIndex: -1 }), /SIMULATED_POINT_INPUT_INVALID/);
  const fake = {...point, identity: {...point.identity, match_id: 'match:real'}};
  assert.throws(() => validateFoundationRecord(fake), /SIMULATION_BOUNDARY/);
});

test('provider embeddable metadata does not grant embed permission', () => {
  const playback = clone(fixtures.find(row => row.kind === 'PlaybackState'));
  playback.provider_embeddable = true;
  playback.embed_permission = 'UNKNOWN';
  assert.equal(validateFoundationRecord(playback), true);
  assert.equal(playback.embed_permission, 'UNKNOWN');
});

test('model provenance is explicit and never attached to an official or user record', () => {
  const record = clone(fixtures.find(row => row.kind === 'MatchIdentity'));
  record.provenance.inference = clone(fixtures.find(row => row.kind === 'PoseEvidence')).provenance.inference;
  assert.throws(() => validateFoundationRecord(record), /INFERENCE_ORIGIN_MISMATCH/);
});

test('ALLOWED rights require their own evidence; duplicate IDs and broken refs fail', () => {
  const rights = clone(fixtures.find(row => row.kind === 'RightsEvidence'));
  rights.permissions.remote_display.status = 'ALLOWED';
  assert.throws(() => validateFoundationRecord(rights), /RIGHTS_ALLOW_WITHOUT_EVIDENCE/);
  const duplicate = [...clone(fixtures), clone(fixtures.find(row => row.kind === 'Prediction'))];
  assert.throws(() => validateFoundationBundle(duplicate), /DUPLICATE_RECORD_ID|DUPLICATE_ENTITY_ID/);
  const prediction = clone(fixtures.find(row => row.kind === 'Prediction'));
  prediction.target_point_event_id = 'missing-event';
  assert.throws(() => validateFoundationBundle([...fixtures.filter(row => row.kind !== 'Prediction'), prediction]), /PREDICTION_EVENT_NOT_FOUND/);
});

test('playback rights reference must identify the exact source or asset', () => {
  const records = clone(fixtures);
  const playback = records.find(row => row.kind === 'PlaybackState');
  const secondSource = clone(records.find(row => row.kind === 'MediaSource'));
  secondSource.record_id = 'fixture:source-record-2';
  secondSource.identity.source_id = 'fixture:source:second';
  records.push(secondSource);
  playback.rights_evidence_record_id = 'fixture:rights-record-1';
  assert.equal(validateFoundationBundle(records), true);
  playback.identity.source_id = 'fixture:source:second';
  assert.throws(() => validateFoundationBundle(records), /PLAYBACK_RIGHTS_IDENTITY_MISMATCH/);
});

test('Moment projection requires exact registered asset binding and never joins by title', () => {
  const media = mediaSourceToFoundation({
    source_key: 'YOUTUBE:Abcdef12345', video_id: 'Abcdef12345', provider: 'YOUTUBE_OFFICIAL',
    source_url: 'https://www.youtube.com/watch?v=Abcdef12345', match_id: 'match:exact',
    title: 'Same title', video_source: {provider: 'YOUTUBE_OFFICIAL', source_id: 'Abcdef12345'},
  }, {recordId: 'source-record:exact'});
  const asset = videoAssetFromMediaSource(media, {recordId: 'asset-record:exact'});
  const projected = momentCardToFoundation({ id: 'm:1', videoKey: 'official:Abcdef12345', seconds: 12, title: 'Same title', note: '', tags: [] }, {videoAsset: asset, mediaSource: media});
  assert.equal(projected.identity.video_asset_id, asset.identity.video_asset_id);
  assert.equal(projected.identity.source_id, media.identity.source_id);
  assert.equal(projected.identity.match_id, 'match:exact');
  assert.equal(projected.timeline_anchor.timestamp_ms, 12000);
  assert.throws(() => momentCardToFoundation({id: 'm:2', videoKey: 'official:VWxyz678901', seconds: 2, title: 'Same title', note: '', tags: []}, {videoAsset: asset, mediaSource: media}), /MOMENT_ASSET_UNASSOCIATED/);
  assert.throws(() => momentCardToFoundation({id: 'm:3', videoKey: 'official:Abcdef12345', seconds: 2, title: '', note: '', tags: []}, {videoAsset: asset, mediaSource: media}), /MOMENT_SOURCE_INVALID/);
});

test('profile reads are side-effect free, including repeated StrictMode-like reads', () => {
  const existing = emptyPersonalDiscoveryProfile();
  existing.recently_opened = [{record_kind: 'MatchIdentity', record_id: 'match:1', open_requested_at: '2026-10-28T00:00:00.000Z'}];
  const storage = memoryStorage(JSON.stringify(existing));
  const first = readPersonalDiscovery(storage);
  const second = readPersonalDiscovery(storage);
  assert.equal(storage.writes, 0);
  assert.deepEqual(first.profile, second.profile);
  assert.equal(first.profile.recently_opened[0].record_id, 'match:1');
});

test('only explicit open requests are stored; no query or path is persisted', () => {
  const storage = memoryStorage();
  assert.equal(recordOpenRequest(storage, {record_kind: 'MediaSource', record_id: 'source:exact'}, 'tomorrow').error, 'OPEN_REFERENCE_INVALID');
  const result = recordOpenRequest(storage, {record_kind: 'MediaSource', record_id: 'source:exact'}, '2026-10-28T00:00:00.000Z');
  assert.equal(result.ok, true);
  assert.equal(result.recorded, 'OPEN_REQUESTED');
  const raw = storage.values.get(PERSONAL_DISCOVERY_KEY);
  assert.equal(raw.includes('search'), false);
  assert.equal(raw.includes('C:\\'), false);
  assert.equal(JSON.parse(raw).recently_opened[0].record_id, 'source:exact');
});

test('corrupt and unsupported profiles are preserved and refuse implicit overwrite', () => {
  const bytes = '{broken user data';
  const storage = memoryStorage(bytes);
  const read = readPersonalDiscovery(storage);
  assert.equal(read.error, 'PROFILE_CORRUPT');
  assert.equal(read.preserved, true);
  assert.equal(writePersonalDiscovery(storage, emptyPersonalDiscoveryProfile()).ok, false);
  assert.equal(storage.values.get(PERSONAL_DISCOVERY_KEY), bytes);
  assert.equal(storage.writes, 0);
});

test('Playback alone owns resumable progress; legacy Discovery bytes remain preserved and read-only', () => {
  const profile = emptyPersonalDiscoveryProfile();
  profile.local_progress = [{video_asset_id:'legacy-local-asset',asset_sha256:'a'.repeat(64),position_seconds:12,duration_seconds:300,asset_kind:'USER_LOCAL',availability:'AVAILABLE',identity_method:'VERIFIED_SHA256',playback_rights:'USER_CONFIRMED',rights_evidence_id:'legacy:rights',updated_at:'2026-10-28T00:00:00.000Z'}];
  const original = JSON.stringify(profile);
  const storage = memoryStorage(original);
  const common = {videoAssetId: 'local-asset:1', assetSha256: 'a'.repeat(64), positionSeconds: 12, durationSeconds: 300, assetKind: 'USER_LOCAL', availability: 'AVAILABLE', identityMethod: 'VERIFIED_SHA256', playbackRights: 'USER_CONFIRMED', rightsEvidenceId: 'rights:local:1'};
  const rejected = saveTrustedLocalProgress(storage, common, '2026-10-28T00:00:00.000Z');
  assert.deepEqual({ok: rejected.ok, error: rejected.error}, {ok: false, error: 'PLAYBACK_PROGRESS_OWNED_BY_LOCAL_PLAYBACK'});
  assert.equal(storage.writes, 0);
  assert.equal(storage.values.get(PERSONAL_DISCOVERY_KEY), original);
  const loaded = readPersonalDiscovery(storage);
  assert.equal(loaded.profile.local_progress.length, 1);
  assert.equal(validatePersonalDiscoveryProfile(loaded.profile), true);
  const shelf = buildGrowthShelf({profile: loaded.profile});
  assert.equal(shelf.continueWatching.length, 0);
  assert.equal(shelf.legacyLocalProgress.length, 1);
  assert.equal(shelf.legacyLocalProgress[0].status, 'LEGACY_STORED_NOT_RESUMABLE');
  assert.equal(recordOpenRequest(storage, {record_kind:'MediaSource',record_id:'source:after-legacy-progress'}, '2026-10-28T00:01:00.000Z').ok, true);
  assert.equal(JSON.parse(storage.values.get(PERSONAL_DISCOVERY_KEY)).local_progress.length, 1, 'unrelated profile writes preserve legacy progress bytes');
});

test('favorites remain an external SQLite projection and exact-rule ranking explains itself', () => {
  const storage = memoryStorage();
  const profile = emptyPersonalDiscoveryProfile();
  profile.recently_opened = [{record_kind: 'MatchIdentity', record_id: 'match:1', open_requested_at: '2026-10-28T00:00:00.000Z'}];
  const favorite = {record_kind: 'MatchIdentity', record_id: 'match:2'};
  const shelf = buildGrowthShelf({profile, sqliteFavoriteRefs: [favorite]});
  assert.deepEqual(shelf.favorites, [favorite]);
  assert.equal(storage.writes, 0);
  const ranked = rankDiscoveryItems([
    {record_kind: 'MatchIdentity', record_id: 'match:3', title: 'same title'},
    {record_kind: 'MatchIdentity', record_id: 'match:1', title: 'same title'},
    {record_kind: 'MatchIdentity', record_id: 'match:2', title: 'same title'},
  ], {profile, sqliteFavoriteRefs: [favorite]});
  assert.equal(ranked[0].item.record_id, 'match:1');
  assert.deepEqual(ranked[0].reasons, ['RECENTLY_OPENED']);
  assert.equal(ranked.find(row => row.item.record_id === 'match:2').reasons.includes('FAVORITED_IN_SQLITE'), true);
  assert.equal(ranked.find(row => row.item.record_id === 'match:3').score, 0);
});

test('storage quota failure is reported rather than reported as a saved profile', () => {
  const storage = memoryStorage(null, {failSet: true});
  const result = recordOpenRequest(storage, {record_kind: 'MatchIdentity', record_id: 'match:1'}, '2026-10-28T00:00:00.000Z');
  assert.deepEqual({ok: result.ok, error: result.error}, {ok: false, error: 'WRITE_FAILED'});
});
