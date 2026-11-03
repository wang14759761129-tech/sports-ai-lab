import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {
  FOUNDATION_VERSION,
  compareVideoAssetIdentity,
  mediaSourceToFoundation,
  momentCardToFoundation,
  resolveMomentAssetBinding,
  secondsToMilliseconds,
  validateFoundationBundle,
  videoAssetFromGexIdentity,
  videoAssetFromMediaSource,
  videoAssetFromProLabIdentity,
} from '../src/foundationContract.mjs';

const source = (videoId = '0QgbtsBWZhk', overrides = {}) => ({
  source_key: `YOUTUBE:${videoId}`,
  video_id: videoId,
  provider: 'YOUTUBE_OFFICIAL',
  source_url: `https://www.youtube.com/watch?v=${videoId}`,
  video_source: {provider: 'YOUTUBE_OFFICIAL', source_id: videoId},
  match_id: 'match:exact-1',
  channel: 'Display name only; not a publisher ID',
  title: 'Same title',
  ...overrides,
});

const moment = (videoKey = 'official:0QgbtsBWZhk', seconds = 12.345, overrides = {}) => ({
  id: 'moment:1', videoKey, seconds, title: 'Observed point', note: '', tags: [], ...overrides,
});

const metadataIdentity = (name, size = 100, lastModified = 10, type = 'video/mp4') => ({
  version: 1,
  name,
  size,
  lastModified,
  type,
  key: `local-file:v1:${encodeURIComponent(JSON.stringify([name, size, lastModified, type]))}`,
});

const gexIdentity = (hex, overrides = {}) => ({
  kind: 'VideoAsset', id: `sha256-chunks-v1:${hex}`,
  hash_method: 'SHA256_CHUNKED_CONTENT_V1', byte_length: 4096, duration: 20,
  origin: 'LOCAL_BROWSER_ONLY', media_kind: 'USER_LOCAL',
  verification: 'NOT_INDEPENDENTLY_VERIFIED', ...overrides,
});

const exactMatch = {
  schema_version: FOUNDATION_VERSION, record_id: 'match-record:exact-1', kind: 'MatchIdentity',
  identity: {match_id: 'match:exact-1', source_id: null, video_asset_id: null}, timeline_anchor: null,
  provenance: {origin: 'MOCK', verification: 'SYNTHETIC_ONLY', evidence_refs: [], inference: null},
  identity_status: 'UNKNOWN', official_record_url: null, event_name: 'Synthetic only', event_year: null,
  discipline: 'UNKNOWN', participant_ids: [],
};

test('exact registered YouTube source maps provider, video ID, source ID and URL without title joins', () => {
  const projected = mediaSourceToFoundation(source(), {recordId: 'source-record:0q'});
  assert.equal(projected.schema_version, FOUNDATION_VERSION);
  assert.equal(projected.identity.source_id, 'YOUTUBE:0QgbtsBWZhk');
  assert.equal(projected.provider, 'YOUTUBE_OFFICIAL');
  assert.equal(projected.provider_video_id, '0QgbtsBWZhk');
  assert.equal(projected.source_url, 'https://www.youtube.com/watch?v=0QgbtsBWZhk');
  assert.equal(projected.publisher_id, null);
  assert.equal(projected.provenance.verification, 'UNKNOWN');

  const other = mediaSourceToFoundation(source('vYsJLPTEIaI'), {recordId: 'source-record:other'});
  const firstAsset = videoAssetFromMediaSource(projected, {recordId: 'asset-record:0q'});
  const otherAsset = videoAssetFromMediaSource(other, {recordId: 'asset-record:other'});
  assert.equal(compareVideoAssetIdentity(firstAsset, otherAsset).status, 'UNCONFIRMED');
});

test('registered Bilibili source stays on its own official URL identity path', () => {
  const projected = mediaSourceToFoundation({
    source_key: 'BILIBILI:BV1nb421H7jB', video_id: 'BV1nb421H7jB', provider: 'BILIBILI',
    source_url: 'https://www.bilibili.com/video/BV1nb421H7jB/', video_source: {source_id: 'BV1nb421H7jB'},
  }, {recordId: 'source-record:bili'});
  assert.equal(projected.provider, 'BILIBILI_OFFICIAL');
  assert.equal(projected.provider_video_id, 'BV1nb421H7jB');
  assert.equal(projected.identity.source_id, 'BILIBILI:BV1nb421H7jB');
  assert.equal(projected.identity.match_id, null);
});

test('existing 0Q catalog row projects through an exact video ID crosswalk, without title matching', () => {
  const catalog = JSON.parse(readFileSync(new URL('./fixtures/f3c1-official-video-sources.json', import.meta.url), 'utf8'));
  const coverReview = JSON.parse(readFileSync(new URL('../../data/professional/cover_review/goal105-cover-review.v0.1.json', import.meta.url), 'utf8'));
  const row = catalog.videos.find(item => item.video_id === '0QgbtsBWZhk');
  const crosswalk = coverReview.records.find(item => item.video_id === row.video_id);
  assert.ok(row && crosswalk);
  assert.equal(row.match_id, crosswalk.match_id);
  const media = mediaSourceToFoundation(row, {
    recordId: 'test:media:0q',
    sourceId: crosswalk.source_id,
    sourceIdEvidence: {reference_type: 'RECORD', reference_id: 'goal105-cover-review.v0.1#matched-video-id', relationship: 'source_id crosswalk from row with the same exact video_id', debug_path: 'C:\\private\\review.json'},
  });
  const asset = videoAssetFromMediaSource(media, {recordId: 'test:asset:0q'});
  const projectedMoment = momentCardToFoundation(moment(), {videoAsset: asset, mediaSource: media});
  assert.equal(media.identity.source_id, 'video-source:youtube:0QgbtsBWZhk');
  assert.equal(media.provenance.evidence_refs[1].reference_id, 'goal105-cover-review.v0.1#matched-video-id');
  assert.equal('debug_path' in media.provenance.evidence_refs[1], false);
  assert.equal(media.publisher_id, row.official_embed_review.channel_id);
  assert.equal(asset.identity.video_asset_id, 'asset:provider:YOUTUBE_OFFICIAL:0QgbtsBWZhk');
  assert.equal(projectedMoment.identity.match_id, row.match_id);
  assert.equal(projectedMoment.timeline_anchor.video_asset_id, asset.identity.video_asset_id);
});

test('source URL, provider and nested video identity conflicts fail closed', () => {
  assert.throws(() => mediaSourceToFoundation(source('0QgbtsBWZhk', {
    source_url: 'https://www.youtube.com/watch?v=vYsJLPTEIaI',
  }), {recordId: 'source-record:wrong-url'}), /SOURCE_URL_ID_MISMATCH/);
  assert.throws(() => mediaSourceToFoundation(source('0QgbtsBWZhk', {
    video_source: {provider: 'BILIBILI', source_id: '0QgbtsBWZhk'},
  }), {recordId: 'source-record:wrong-provider'}), /SOURCE_PROVIDER_MISMATCH/);
  assert.throws(() => mediaSourceToFoundation(source('0QgbtsBWZhk', {
    video_source: {provider: 'YOUTUBE_OFFICIAL', source_id: 'vYsJLPTEIaI'},
  }), {recordId: 'source-record:wrong-id'}), /SOURCE_VIDEO_ID_MISMATCH/);
  assert.throws(() => mediaSourceToFoundation(source('0QgbtsBWZhk', {
    source_url: 'http://www.youtube.com/watch?v=0QgbtsBWZhk',
  }), {recordId: 'source-record:http'}), /SOURCE_URL_INVALID/);
  assert.throws(() => mediaSourceToFoundation(source('0QgbtsBWZhk', {
    source_key: 'YOUTUBE:vYsJLPTEIaI',
  }), {recordId: 'source-record:key-mismatch'}), /SOURCE_ID_VIDEO_ID_MISMATCH/);
  const mismatchedMedia = mediaSourceToFoundation(source(), {recordId: 'source-record:tamper-base'});
  assert.throws(() => videoAssetFromMediaSource({...mismatchedMedia, source_url: 'https://www.youtube.com/watch?v=vYsJLPTEIaI'}, {recordId: 'asset-record:tampered-source'}), /MEDIA_SOURCE_URL_ID_MISMATCH/);
});

test('official assets preserve identity only and do not turn embed review into media permission', () => {
  const blockedObservedSource = source('0QgbtsBWZhk', {
    playback_status: 'EMBED_BLOCKED', embed_permission: 'DENIED',
    official_embed_review: {decision: 'ALLOW_OFFICIAL_PLAYER_ATTEMPT', evidence_id: 'attempt-only'},
  });
  const media = mediaSourceToFoundation(blockedObservedSource, {recordId: 'source-record:0q'});
  const asset = videoAssetFromMediaSource(media, {recordId: 'asset-record:0q'});
  assert.equal(asset.identity.video_asset_id, 'asset:provider:YOUTUBE_OFFICIAL:0QgbtsBWZhk');
  assert.equal(asset.identity.source_id, media.identity.source_id);
  assert.equal(asset.identity.match_id, media.identity.match_id);
  assert.equal(asset.identity_method, 'PROVIDER_VIDEO_ID');
  assert.equal(asset.identity_value, 'YOUTUBE_OFFICIAL:0QgbtsBWZhk');
  assert.equal(asset.availability, 'NOT_TESTED');
  for (const forbidden of ['embed_permission', 'playback_rights', 'remote_display', 'package_distribution']) {
    assert.equal(forbidden in asset, false);
  }
  assert.equal(media.publisher_id, null); // Display titles are not publisher IDs.
  assert.equal('embed_permission' in media, false);
  assert.equal('rights' in media, false);
});

test('Pro Lab file metadata is not a content hash; changed tuples remain unassociated', () => {
  const first = videoAssetFromProLabIdentity(metadataIdentity('training.mp4'), {recordId: 'asset-record:file-1'});
  const changedSize = videoAssetFromProLabIdentity(metadataIdentity('training.mp4', 101), {recordId: 'asset-record:file-2'});
  const changedModified = videoAssetFromProLabIdentity(metadataIdentity('training.mp4', 100, 11), {recordId: 'asset-record:file-3'});
  assert.equal(first.identity_method, 'FILE_METADATA_V1');
  assert.equal(first.identity_value.startsWith('local-file:v1:'), true);
  assert.deepEqual(compareVideoAssetIdentity(first, first), {status: 'UNCONFIRMED', reason: 'IDENTICAL_METADATA_NOT_CONTENT_PROOF'});
  const sameTupleUnknownContent = videoAssetFromProLabIdentity(metadataIdentity('training.mp4'), {recordId: 'asset-record:unknown-content'});
  assert.equal(compareVideoAssetIdentity(first, sameTupleUnknownContent).status, 'UNCONFIRMED');
  assert.equal(compareVideoAssetIdentity(first, changedSize).status, 'UNCONFIRMED');
  assert.equal(compareVideoAssetIdentity(first, changedModified).status, 'UNCONFIRMED');
  assert.throws(() => videoAssetFromProLabIdentity(metadataIdentity('folder/training.mp4'), {recordId: 'bad'}), /PROLAB_IDENTITY_INVALID/);
});

test('GEX chunk hash is scoped separately from Pro Lab metadata and other hash methods', () => {
  const gex = videoAssetFromGexIdentity(gexIdentity('a'.repeat(64)), {recordId: 'asset-record:gex-a'});
  const sameGex = videoAssetFromGexIdentity(gexIdentity('a'.repeat(64)), {recordId: 'asset-record:gex-same'});
  const otherGex = videoAssetFromGexIdentity(gexIdentity('b'.repeat(64)), {recordId: 'asset-record:gex-b'});
  const proLab = videoAssetFromProLabIdentity(metadataIdentity('training.mp4'), {recordId: 'asset-record:metadata'});
  const wholeFile = {
    ...gex,
    record_id: 'asset-record:whole-file',
    identity: {...gex.identity, video_asset_id: 'asset:verified-sha256:whole-file:'.concat('a'.repeat(64))},
    identity_method: 'VERIFIED_SHA256',
    identity_value: `sha256:whole-file-v1:${'a'.repeat(64)}`,
  };
  const rangeHash = {
    ...wholeFile,
    record_id: 'asset-record:prefix-hash',
    identity: {...wholeFile.identity, video_asset_id: `asset:verified-sha256:prefix:${'a'.repeat(64)}`},
    identity_value: `sha256:prefix-1m-v1:${'a'.repeat(64)}`,
  };
  assert.equal(compareVideoAssetIdentity(gex, sameGex).status, 'SAME_SCOPED_HASH_IDENTITY');
  assert.equal(compareVideoAssetIdentity(gex, otherGex).status, 'UNCONFIRMED');
  assert.equal(compareVideoAssetIdentity(gex, wholeFile).status, 'UNCONFIRMED');
  assert.equal(compareVideoAssetIdentity(wholeFile, rangeHash).reason, 'HASH_VALUE_OR_SCOPE_MISMATCH');
  assert.equal(compareVideoAssetIdentity({...wholeFile, identity_value: `sha256:${'a'.repeat(64)}`}, wholeFile).reason, 'HASH_SCOPE_MISSING');
  assert.equal(compareVideoAssetIdentity(gex, proLab).status, 'UNCONFIRMED');
  assert.equal(compareVideoAssetIdentity(null, gex).reason, 'ASSET_IDENTITY_MISSING');
});

test('Moment binding requires an exact asset and exact official Feed video key', () => {
  const media = mediaSourceToFoundation(source(), {recordId: 'source-record:0q'});
  const asset = videoAssetFromMediaSource(media, {recordId: 'asset-record:0q'});
  assert.deepEqual(resolveMomentAssetBinding(moment(), asset, {mediaSource: media}), {status: 'EXACT', reason: ''});
  assert.equal(resolveMomentAssetBinding(moment(), asset).reason, 'SOURCE_IDENTITY_MISSING');
  assert.equal(resolveMomentAssetBinding(moment('official:vYsJLPTEIaI'), asset, {mediaSource: media}).status, 'UNASSOCIATED');
  assert.equal(resolveMomentAssetBinding(moment(), null).reason, 'ASSET_MISSING');
  assert.equal(resolveMomentAssetBinding(moment(), videoAssetFromProLabIdentity(metadataIdentity('training.mp4'), {recordId: 'asset-record:metadata'})).reason,
    'LOCAL_ASSET_REQUIRES_EXPLICIT_ASSOCIATION_EVIDENCE');
  assert.throws(() => momentCardToFoundation(moment('official:vYsJLPTEIaI'), {videoAsset: asset, mediaSource: media}), /MOMENT_ASSET_UNASSOCIATED/);
  const wrongSource = {...media, identity: {...media.identity, source_id: 'different-source'}};
  assert.equal(resolveMomentAssetBinding(moment(), asset, {mediaSource: wrongSource}).reason, 'SOURCE_ASSET_IDENTITY_MISMATCH');
  const projected = momentCardToFoundation(moment(), {videoAsset: asset, mediaSource: media});
  assert.equal(projected.identity.video_asset_id, asset.identity.video_asset_id);
  assert.equal(projected.identity.source_id, media.identity.source_id);
  assert.equal(projected.identity.match_id, 'match:exact-1');
});

test('Moment seconds use round-half-up milliseconds and reject invalid or out-of-range time', () => {
  assert.equal(secondsToMilliseconds(0), 0);
  assert.equal(secondsToMilliseconds(12.3454), 12345);
  assert.equal(secondsToMilliseconds(12.3455), 12346);
  assert.equal(secondsToMilliseconds(86400), null);
  for (const value of [-0.001, Number.NaN, Number.POSITIVE_INFINITY, '12.5']) {
    assert.equal(secondsToMilliseconds(value), null);
  }

  const media = mediaSourceToFoundation(source(), {recordId: 'source-record:0q'});
  const asset = videoAssetFromMediaSource(media, {recordId: 'asset-record:0q', durationMs: 12346});
  const tail = momentCardToFoundation(moment('official:0QgbtsBWZhk', 12.346), {videoAsset: asset, mediaSource: media});
  assert.equal(tail.timeline_anchor.timestamp_ms, 12346);
  assert.equal(validateFoundationBundle([exactMatch, media, asset, tail]), true);
  assert.throws(() => momentCardToFoundation(moment('official:0QgbtsBWZhk', 12.347), {videoAsset: asset, mediaSource: media}), /MOMENT_TIME_OUT_OF_RANGE/);
  assert.throws(() => momentCardToFoundation(moment('official:0QgbtsBWZhk', Number.NaN), {videoAsset: asset, mediaSource: media}), /MOMENT_SOURCE_INVALID/);
});

test('missing source IDs, assets, and link evidence never create implicit associations', () => {
  assert.throws(() => mediaSourceToFoundation(source('0QgbtsBWZhk', {
    source_key: '', video_source: {provider: 'YOUTUBE_OFFICIAL', source_id: null},
  }), {recordId: 'source-record:missing'}), /SOURCE_ID_MISSING/);
  assert.throws(() => videoAssetFromMediaSource(null, {recordId: 'asset-record:missing'}), /MEDIA_SOURCE_REQUIRED/);
  const noStoredSourceId = source('0QgbtsBWZhk', {source_key: undefined, video_source: undefined});
  assert.throws(() => mediaSourceToFoundation(noStoredSourceId, {recordId: 'source-record:unlinked', sourceId: 'source:external'}), /SOURCE_ID_EVIDENCE_MISSING/);
  const local = videoAssetFromProLabIdentity(metadataIdentity('training.mp4'), {recordId: 'asset-record:local'});
  assert.equal(resolveMomentAssetBinding(moment('local:catalog-id'), local).status, 'UNASSOCIATED');
  assert.throws(() => momentCardToFoundation(moment('local:catalog-id'), {videoAsset: local}), /MOMENT_ASSET_UNASSOCIATED/);
  const explicit = {decision: 'USER_CONFIRMED_EXACT_BINDING', video_key: 'local:catalog-id', video_asset_id: local.identity.video_asset_id, evidence_id: 'user-confirmation:1'};
  assert.equal(resolveMomentAssetBinding(moment('local:catalog-id'), local, {associationEvidence: explicit}).status, 'EXACT_WITH_USER_EVIDENCE');
  const locallyBound = momentCardToFoundation(moment('local:catalog-id'), {videoAsset: local, associationEvidence: explicit});
  assert.equal(locallyBound.identity.video_asset_id, local.identity.video_asset_id);
  assert.equal(locallyBound.provenance.evidence_refs[0].reference_id, explicit.evidence_id);
  assert.equal(resolveMomentAssetBinding(moment('local:other'), local, {associationEvidence: explicit}).status, 'UNASSOCIATED');
});
