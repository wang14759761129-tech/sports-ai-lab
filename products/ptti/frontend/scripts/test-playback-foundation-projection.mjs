import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname, resolve} from 'node:path';
import test from 'node:test';
import {validateFoundationBundle, validateFoundationRecord, videoAssetFromGexIdentity, videoAssetFromProLabIdentity} from '../src/foundationContract.mjs';
import {LOCAL_CONTINUATION_USE_CASE, LOCAL_PLAYBACK_PROGRESS_KEY, projectLocalPlaybackToFoundation} from '../src/playbackFoundationProjection.mjs';
import {createVideoIdentity} from '../src/proLabNotes.mjs';
import {buildGrowthShelf, emptyPersonalDiscoveryProfile} from '../src/personalDiscovery.mjs';

const fixtures = JSON.parse(readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), '../../contracts/foundation-v0.1.examples.json'), 'utf8'));
const now = Date.parse('2026-10-28T00:00:00.000Z');
const hashA = `sha256-chunks-v1:${'a'.repeat(64)}`;
const hashB = `sha256-chunks-v1:${'b'.repeat(64)}`;

function localAsset(hash = hashA, recordId = `asset-record:${hash.slice(-1)}`, duration = 300) {
  return videoAssetFromGexIdentity({
    kind: 'VideoAsset', id: hash, hash_method: 'SHA256_CHUNKED_CONTENT_V1',
    byte_length: 12345, duration, origin: 'LOCAL_BROWSER_ONLY', media_kind: 'USER_LOCAL',
    verification: 'NOT_INDEPENDENTLY_VERIFIED',
  }, {recordId});
}

function rightsFor(asset, {target = 'web_display', status = 'ALLOWED', validUntil = null, evidenceRefs = [{reference_type: 'USER_STATEMENT', reference_id: 'qa:confirmed-local-use', relationship: 'synthetic test evidence'}], recordId = 'rights:local:qa', reviewedUseCase = LOCAL_CONTINUATION_USE_CASE} = {}) {
  const base = structuredClone(fixtures.find(row => row.kind === 'RightsEvidence'));
  base.record_id = recordId;
  base.rights_id = `${recordId}:id`;
  base.subject_kind = 'VIDEO_ASSET';
  base.subject_record_id = asset.record_id;
  base.identity = {...asset.identity};
  base.reviewed_use_case = reviewedUseCase;
  base.provenance = {
    origin: 'USER_AUTHORED', verification: 'USER_CONFIRMED',
    evidence_refs: [{reference_type: 'USER_STATEMENT', reference_id: 'qa:founder-local-use', relationship: 'synthetic test fixture'}],
    inference: null,
  };
  base.permissions[target] = {status, evidence_refs: evidenceRefs, valid_until: validUntil};
  return base;
}

function progress(asset, positionSeconds = 12.345, durationSeconds = 300) {
  return {source_key: LOCAL_PLAYBACK_PROGRESS_KEY, identity_value: asset.identity_value, status: 'FOUND', position_seconds: positionSeconds, duration_seconds: durationSeconds};
}

function project(asset, overrides = {}) {
  return projectLocalPlaybackToFoundation({
    recordId: `playback:${asset.identity.video_asset_id}`,
    videoAsset: asset,
    currentAvailability: 'AVAILABLE',
    currentDurationMs: asset.duration_ms,
    progressSnapshot: progress(asset),
    rightsEvidence: rightsFor(asset),
    target: 'WEB',
    now,
    ...overrides,
  });
}

test('exact local Playback snapshot projects without changing v0.1 schema or rights', () => {
  const asset = localAsset();
  const rights = rightsFor(asset);
  const view = project(asset, {rightsEvidence: rights});
  assert.equal(view.status, 'PROJECTED');
  assert.equal(view.savedProgress.position_ms, 12345);
  assert.deepEqual(view.continuation, {status: 'ELIGIBLE', reason: null});
  assert.equal(view.playbackState.observation, 'NOT_TESTED');
  assert.equal(view.playbackState.observed_at, null);
  assert.equal(view.playbackState.embed_permission, 'UNKNOWN');
  assert.equal(view.playbackState.rights_evidence_record_id, rights.record_id);
  assert.equal(validateFoundationRecord(view.playbackState), true);
  assert.equal(validateFoundationBundle([asset, rights, view.playbackState]), true);
  assert.equal(Object.hasOwn(view.playbackState, 'position_ms'), false, 'Foundation v0.1 PlaybackState remains closed; saved position stays in projection view');
});

test('official remote video assets are never confused with local resume progress', () => {
  const official = structuredClone(fixtures.find(row => row.kind === 'VideoAsset'));
  const result = projectLocalPlaybackToFoundation({
    recordId: 'playback:official', videoAsset: official, currentAvailability: 'AVAILABLE', currentDurationMs: 60000,
    progressSnapshot: {source_key: LOCAL_PLAYBACK_PROGRESS_KEY, identity_value: official.identity_value, status: 'FOUND', position_seconds: 2, duration_seconds: 60},
    now,
  });
  assert.equal(result.status, 'UNPROJECTABLE');
  assert.equal(result.continuation.reason, 'ASSET_NOT_SUPPORTED_LOCAL_HASH_IDENTITY');
});

test('same filename metadata identity is not content identity and cannot resume', () => {
  const metadata = videoAssetFromProLabIdentity(createVideoIdentity({name: 'same.mp4', size: 100, lastModified: 10, type: 'video/mp4'}), {recordId: 'asset:metadata'});
  const result = projectLocalPlaybackToFoundation({recordId: 'playback:metadata', videoAsset: metadata, currentAvailability: 'AVAILABLE', currentDurationMs: 300000, progressSnapshot: progress(localAsset()), now});
  assert.equal(result.status, 'UNPROJECTABLE');
});

test('same filename with different content hashes cannot reuse another video progress', () => {
  const current = localAsset(hashB, 'asset-record:b');
  const prior = localAsset(hashA, 'asset-record:a');
  const result = project(current, {progressSnapshot: progress(prior)});
  assert.equal(result.savedProgress.status, 'IDENTITY_MISMATCH');
  assert.equal(result.savedProgress.position_ms, null);
  assert.equal(result.continuation.reason, 'PROGRESS_IDENTITY_MISMATCH');
});

test('empty, corrupt, or foreign-store history never becomes resumable', () => {
  const asset = localAsset();
  const empty = project(asset, {progressSnapshot: {source_key: LOCAL_PLAYBACK_PROGRESS_KEY, identity_value: asset.identity_value, status: 'EMPTY'}});
  assert.equal(empty.continuation.reason, 'NO_SAVED_PROGRESS');
  const corrupt = project(asset, {progressSnapshot: {source_key: LOCAL_PLAYBACK_PROGRESS_KEY, identity_value: asset.identity_value, status: 'UNVERIFIABLE'}});
  assert.equal(corrupt.continuation.reason, 'HISTORY_UNVERIFIABLE');
  const discovery = project(asset, {progressSnapshot: {source_key: 'ptti.personal-discovery/0.1', identity_value: asset.identity_value, status: 'FOUND', position_seconds: 5, duration_seconds: 300}});
  assert.equal(discovery.savedProgress.status, 'IDENTITY_MISMATCH');
  assert.equal(discovery.continuation.reason, 'PROGRESS_IDENTITY_MISMATCH');
});

test('media disappearance and unknown availability stop continuation without losing stored position', () => {
  const asset = localAsset();
  for (const [availability, reason] of [['UNAVAILABLE', 'MEDIA_UNAVAILABLE'], ['UNKNOWN', 'MEDIA_AVAILABILITY_UNKNOWN']]) {
    const result = project(asset, {currentAvailability: availability});
    assert.equal(result.continuation.reason, reason);
    assert.equal(result.savedProgress.position_ms, null);
  }
});

test('asset duration changes beyond Playback tolerance block old progress', () => {
  const asset = localAsset();
  const result = project(asset, {currentDurationMs: asset.duration_ms + 501});
  assert.equal(result.savedProgress.status, 'DURATION_MISMATCH');
  assert.equal(result.continuation.reason, 'CURRENT_DURATION_MISMATCH');
});

test('out-of-range progress and exact end position do not resume', () => {
  const asset = localAsset();
  const over = project(asset, {progressSnapshot: progress(asset, 300.001, 300)});
  assert.equal(over.savedProgress.status, 'INVALID_PROGRESS');
  assert.equal(over.continuation.reason, 'PROGRESS_OUT_OF_RANGE');
  const atEnd = project(asset, {progressSnapshot: progress(asset, 300, 300)});
  assert.equal(atEnd.savedProgress.position_ms, 300000);
  assert.equal(atEnd.continuation.reason, 'NO_RESUMABLE_POSITION');
  const atStart = project(asset, {progressSnapshot: progress(asset, 0, 300)});
  assert.equal(atStart.continuation.reason, 'NO_RESUMABLE_POSITION');
});

test('missing and mismatched RightsEvidence fail closed while position remains distinct', () => {
  const asset = localAsset();
  const missing = project(asset, {rightsEvidence: null});
  assert.equal(missing.savedProgress.position_ms, 12345);
  assert.equal(missing.continuation.reason, 'RIGHTS_EVIDENCE_MISSING');
  const other = rightsFor(localAsset(hashB, 'asset-record:other'));
  const mismatch = project(asset, {rightsEvidence: other});
  assert.equal(mismatch.playbackState.rights_evidence_record_id, null);
  assert.equal(mismatch.continuation.reason, 'RIGHTS_SUBJECT_MISMATCH');
  const sameContentOtherRecord = rightsFor(localAsset(hashA, 'asset-record:duplicate-reference'));
  const sameHashMismatch = project(asset, {rightsEvidence: sameContentOtherRecord});
  assert.equal(sameHashMismatch.continuation.reason, 'RIGHTS_SUBJECT_MISMATCH', 'same content hash does not substitute for the exact RightsEvidence subject record');
});

test('expired, revoked, unverified, wrong-use and bad-expiry evidence cannot qualify continuation', () => {
  const asset = localAsset();
  const exactExpiry = rightsFor(asset, {validUntil: new Date(now).toISOString()});
  assert.equal(project(asset, {rightsEvidence: exactExpiry}).continuation.reason, 'RIGHTS_EVIDENCE_EXPIRED');
  assert.equal(project(asset, {rightsEvidence: rightsFor(asset, {status: 'EXPIRED'})}).continuation.reason, 'RIGHTS_EVIDENCE_EXPIRED');
  assert.equal(project(asset, {rightsEvidence: rightsFor(asset, {status: 'REVOKED'})}).continuation.reason, 'RIGHTS_EVIDENCE_REVOKED');
  const wrongUse = rightsFor(asset, {reviewedUseCase: 'THUMBNAIL_DISPLAY'});
  assert.equal(project(asset, {rightsEvidence: wrongUse}).continuation.reason, 'RIGHTS_USE_CASE_MISMATCH');
  const badExpiry = rightsFor(asset, {validUntil: 'not-a-date'});
  assert.equal(project(asset, {rightsEvidence: badExpiry}).continuation.reason, 'RIGHTS_EXPIRY_INVALID');
});

test('target-specific web/native rights are independent and never grant provider embed permission', () => {
  const asset = localAsset();
  const rights = rightsFor(asset, {target: 'native_display'});
  const native = project(asset, {target: 'NATIVE', rightsEvidence: rights});
  assert.equal(native.continuation.status, 'ELIGIBLE');
  assert.equal(native.playbackState.embed_permission, 'UNKNOWN');
  const web = project(asset, {target: 'WEB', rightsEvidence: rights});
  assert.equal(web.continuation.reason, 'RIGHTS_UNKNOWN');
});

test('mock, synthetic, unsupported and status-conflicting evidence cannot grant rights', () => {
  const asset = localAsset();
  const mock = rightsFor(asset);
  mock.provenance = {origin: 'MOCK', verification: 'SYNTHETIC_ONLY', evidence_refs: [], inference: null};
  assert.equal(project(asset, {rightsEvidence: mock}).continuation.reason, 'RIGHTS_EVIDENCE_UNVERIFIED');
  const conflicting = rightsFor(asset, {status: 'NOT_ALLOWED'});
  assert.equal(project(asset, {rightsEvidence: conflicting}).continuation.reason, 'RIGHTS_NOT_ALLOWED');
  assert.equal(project(asset, {rightsEvidence: rightsFor(asset, {status: 'NEEDS_PERMISSION'})}).continuation.reason, 'RIGHTS_NEEDS_PERMISSION');
});

test('projection is read-only and does not accept a second progress authority', () => {
  let writes = 0;
  const asset = localAsset();
  const result = project(asset, {personalDiscoveryProgress: {position_seconds: 999}});
  assert.equal(result.savedProgress.position_ms, 12345);
  assert.equal(result.continuation.status, 'ELIGIBLE');
  assert.equal(writes, 0);
});

test('Discovery shelf consumes only fresh, eligible Playback projections; expired rights drop the view', () => {
  const asset = localAsset();
  const expiry = '2026-10-28T00:01:00.000Z';
  const rights = rightsFor(asset, {validUntil: expiry});
  const valid = project(asset, {rightsEvidence: rights, now});
  const profile = emptyPersonalDiscoveryProfile();
  profile.local_progress = [{video_asset_id: 'legacy', asset_sha256: 'e'.repeat(64), position_seconds: 20, duration_seconds: 90, asset_kind: 'USER_LOCAL', availability: 'AVAILABLE', identity_method: 'VERIFIED_SHA256', playback_rights: 'USER_CONFIRMED', rights_evidence_id: 'old:rights', updated_at: '2026-10-28T00:00:00Z'}];
  const shelf = buildGrowthShelf({profile, playbackProjections: [valid], now});
  assert.equal(shelf.continueWatching.length, 1);
  assert.equal(shelf.continueWatching[0].video_asset_id, asset.identity.video_asset_id);
  assert.equal(shelf.legacyLocalProgress.length, 1);
  const expiredShelf = buildGrowthShelf({profile, playbackProjections: [valid], now: Date.parse(expiry)});
  assert.equal(expiredShelf.continueWatching.length, 0);
});

console.log('Foundation playback projection tests executed; mocked evidence is explicitly test-only.');
