import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {videoAssetFromGexIdentity, validateFoundationRecord} from '../src/foundationContract.mjs';
import {LOCAL_CONTINUATION_USE_CASE, LOCAL_PLAYBACK_PROGRESS_KEY, projectLocalPlaybackToFoundation} from '../src/playbackFoundationProjection.mjs';

const sourcePath = process.argv[2];
if (!sourcePath) throw new Error('Usage: node scripts/test-playback-foundation-source-integration.mjs <absolute-localPlayback.mjs path>');
const playback = await import(pathToFileURL(resolve(sourcePath)).href);
assert.equal(playback.PROGRESS_KEY, LOCAL_PLAYBACK_PROGRESS_KEY, 'must use the reviewed canonical Playback storage key');

const hash = `sha256-chunks-v1:${'c'.repeat(64)}`;
const durationSeconds = 60;
const asset = videoAssetFromGexIdentity({
  kind: 'VideoAsset', id: hash, hash_method: 'SHA256_CHUNKED_CONTENT_V1', byte_length: 2048,
  duration: durationSeconds, origin: 'LOCAL_BROWSER_ONLY', media_kind: 'USER_LOCAL',
  verification: 'NOT_INDEPENDENTLY_VERIFIED',
}, {recordId: 'asset:playback-source-qa'});

const values = new Map();
let writes = 0;
const storage = {
  getItem(key) { return values.has(key) ? values.get(key) : null; },
  setItem(key, value) { writes += 1; values.set(key, String(value)); },
};
playback.writeProgress(storage, hash, 12.345, durationSeconds, 'integration-qa.mp4');
const storedSeconds = playback.readProgress(storage, hash, durationSeconds);
assert.equal(storedSeconds, 12.345);
const writeCountBeforeProjection = writes;

const rightsEvidence = {
  schema_version: 'ptti.foundation/0.1', record_id: 'rights:integration-qa', kind: 'RightsEvidence',
  identity: {...asset.identity}, timeline_anchor: null,
  provenance: {origin: 'USER_AUTHORED', verification: 'USER_CONFIRMED', evidence_refs: [], inference: null},
  rights_id: 'rights:integration-qa:id', subject_kind: 'VIDEO_ASSET', subject_record_id: asset.record_id,
  reviewed_use_case: LOCAL_CONTINUATION_USE_CASE,
  permissions: Object.fromEntries(['remote_display','web_display','native_display','package_distribution','embed','download','edit','analysis','commercial_use']
    .map(name => [name, {status: name === 'web_display' ? 'ALLOWED' : 'UNKNOWN', evidence_refs: name === 'web_display' ? [{reference_type: 'USER_STATEMENT', reference_id: 'synthetic-integration-fixture', relationship: 'test only'}] : [], valid_until: null}])),
};
assert.equal(validateFoundationRecord(rightsEvidence), true);
const projection = projectLocalPlaybackToFoundation({
  recordId: 'playback:integration-qa', videoAsset: asset, currentAvailability: 'AVAILABLE',
  currentDurationMs: durationSeconds * 1000,
  progressSnapshot: {source_key: playback.PROGRESS_KEY, identity_value: hash, status: 'FOUND', position_seconds: storedSeconds, duration_seconds: durationSeconds},
  rightsEvidence, target: 'WEB', now: Date.parse('2026-10-28T00:00:00.000Z'),
});
assert.equal(projection.savedProgress.position_ms, 12345);
assert.equal(projection.continuation.status, 'ELIGIBLE');
assert.equal(projection.playbackState.observation, 'NOT_TESTED');
assert.equal(projection.playbackState.embed_permission, 'UNKNOWN');
assert.equal(writes, writeCountBeforeProjection, 'the Foundation projection performs no writes');

const otherHash = `sha256-chunks-v1:${'d'.repeat(64)}`;
const mismatch = projectLocalPlaybackToFoundation({
  recordId: 'playback:other-video', videoAsset: asset, currentAvailability: 'AVAILABLE', currentDurationMs: 60000,
  progressSnapshot: {source_key: playback.PROGRESS_KEY, identity_value: otherHash, status: 'FOUND', position_seconds: storedSeconds, duration_seconds: durationSeconds},
  rightsEvidence, target: 'WEB', now: Date.parse('2026-10-28T00:00:00.000Z'),
});
assert.equal(mismatch.continuation.reason, 'PROGRESS_IDENTITY_MISMATCH');
assert.equal(writes, writeCountBeforeProjection);
console.log('PASS: exact Playback source module → read-only Foundation projection; storage is in-memory test-only; no user data or playback observed.');
