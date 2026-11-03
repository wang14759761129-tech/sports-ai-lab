// Shared cross-space contract guards. Feature stores remain the system of
// record; this module validates projections and never persists or grants rights.
export const FOUNDATION_VERSION = 'ptti.foundation/0.1';
export const FOUNDATION_KINDS = Object.freeze([
  'MatchIdentity', 'MediaSource', 'VideoAsset', 'PlaybackState', 'Moment', 'Rally',
  'PointEvent', 'Prediction', 'PoseEvidence', 'CoachAnnotation', 'UserCollection', 'RightsEvidence',
]);

const TIMELINE_KINDS = new Set(['Moment', 'Rally', 'PoseEvidence']);
const ORIGINS = new Set(['OFFICIAL_PROVIDER', 'OFFICIAL_API_RESPONSE', 'USER_LOCAL', 'USER_AUTHORED', 'MODEL_INFERENCE', 'SIMULATED_ONLY', 'MOCK', 'UNKNOWN']);
const VERIFICATIONS = new Set(['VERIFIED', 'PAGE_VERIFIED', 'USER_CONFIRMED', 'NOT_INDEPENDENTLY_VERIFIED', 'REVIEW_REQUIRED', 'UNKNOWN', 'SYNTHETIC_ONLY']);
const TIME_BASES = new Set(['PLAYER_TIME', 'USER_MARKED_PLAYHEAD', 'USER_ENTERED_TIME', 'SOURCE_PTS', 'SOURCE_FRAME_ESTIMATE']);

function fail(code) { throw new TypeError(`FOUNDATION_CONTRACT:${code}`); }
function isObject(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function optionalId(value) { return value === null || (typeof value === 'string' && value.trim().length > 0); }

function recordBase(recordId, kind, identity, origin, verification, evidenceRefs = []) {
  if (typeof recordId !== 'string' || !recordId.trim() || recordId.length > 256) fail('RECORD_ID');
  return {
    schema_version: FOUNDATION_VERSION,
    record_id: recordId,
    kind,
    identity,
    timeline_anchor: null,
    provenance: {origin, verification, evidence_refs: evidenceRefs, inference: null},
  };
}

function providerFamily(provider) {
  if (provider === 'YOUTUBE' || provider === 'YOUTUBE_OFFICIAL') return 'YOUTUBE';
  if (provider === 'BILIBILI' || provider === 'BILIBILI_OFFICIAL') return 'BILIBILI';
  return null;
}

function validOfficialSourceUrl(provider, videoId, sourceUrl) {
  try {
    const url = new URL(sourceUrl);
    if (url.protocol !== 'https:' || url.username || url.password || url.hash || url.port) return false;
    if (provider === 'YOUTUBE_OFFICIAL') {
      if (!/^[A-Za-z0-9_-]{11}$/.test(videoId)) return false;
      if (['www.youtube.com', 'youtube.com', 'm.youtube.com'].includes(url.hostname)) {
        return url.pathname === '/watch' && url.searchParams.getAll('v').length === 1 && url.searchParams.get('v') === videoId;
      }
      return url.hostname === 'youtu.be' && url.pathname === `/${videoId}` && !url.search;
    }
    if (provider === 'BILIBILI_OFFICIAL') {
      return /^BV[A-Za-z0-9]{10}$/.test(videoId)
        && ['www.bilibili.com', 'bilibili.com'].includes(url.hostname)
        && (url.pathname === `/video/${videoId}` || url.pathname === `/video/${videoId}/`)
        && !url.search;
    }
  } catch {}
  return false;
}

function officialSourceUrlError(provider, videoId, sourceUrl) {
  try {
    const url = new URL(sourceUrl);
    if (url.protocol !== 'https:' || url.username || url.password || url.hash || url.port) return 'SOURCE_URL_INVALID';
    if (provider === 'YOUTUBE_OFFICIAL' && ['www.youtube.com', 'youtube.com', 'm.youtube.com'].includes(url.hostname)
      && url.pathname === '/watch' && url.searchParams.getAll('v').length === 1 && url.searchParams.get('v') !== videoId) return 'SOURCE_URL_ID_MISMATCH';
    if (provider === 'YOUTUBE_OFFICIAL' && url.hostname === 'youtu.be' && url.pathname !== `/${videoId}`) return 'SOURCE_URL_ID_MISMATCH';
    if (provider === 'BILIBILI_OFFICIAL' && ['www.bilibili.com', 'bilibili.com'].includes(url.hostname)
      && url.pathname.startsWith('/video/') && !url.pathname.startsWith(`/video/${videoId}`)) return 'SOURCE_URL_ID_MISMATCH';
  } catch {}
  return 'SOURCE_URL_INVALID';
}

// Maps a registered source row by its stored IDs and URL only. Titles are
// deliberately ignored; a publisher display name is not a publisher ID.
export function mediaSourceToFoundation(source, {recordId, sourceId: explicitSourceId = undefined, sourceIdEvidence = null, matchId = undefined, publisherId = undefined} = {}) {
  if (!isObject(source)) fail('MEDIA_SOURCE_REQUIRED');
  const family = providerFamily(source.provider);
  const videoId = source.video_id;
  const provider = family === 'YOUTUBE' ? 'YOUTUBE_OFFICIAL' : family === 'BILIBILI' ? 'BILIBILI_OFFICIAL' : null;
  if (!provider || typeof videoId !== 'string' || !videoId.trim()) fail('SOURCE_IDENTITY_INVALID');
  const nested = source.video_source;
  if (nested && providerFamily(nested.provider) && providerFamily(nested.provider) !== family) fail('SOURCE_PROVIDER_MISMATCH');
  if (nested?.source_id != null && nested.source_id !== videoId) fail('SOURCE_VIDEO_ID_MISMATCH');
  const sourceId = explicitSourceId !== undefined && explicitSourceId !== null
    ? explicitSourceId
    : source.source_key !== undefined && source.source_key !== null ? source.source_key : nested?.source_id ?? null;
  if (sourceId !== null && (typeof sourceId !== 'string' || sourceId !== sourceId.trim())) fail('SOURCE_ID_INVALID');
  if (!sourceId) fail('SOURCE_ID_MISSING');
  if (explicitSourceId && source.source_key != null && source.source_key !== explicitSourceId) fail('SOURCE_ID_CONFLICT');
  if (explicitSourceId && nested?.source_id != null && nested.source_id !== explicitSourceId && nested.source_id !== videoId) fail('SOURCE_ID_CONFLICT');
  const hasExactStoredSourceId = source.source_key === sourceId || nested?.source_id === sourceId;
  if (explicitSourceId && !hasExactStoredSourceId) {
    if (!isObject(sourceIdEvidence) || !['RECORD', 'URL', 'HASH', 'API_RESPONSE', 'USER_STATEMENT', 'MODEL_ARTIFACT'].includes(sourceIdEvidence.reference_type)
      || typeof sourceIdEvidence.reference_id !== 'string' || !sourceIdEvidence.reference_id.trim() || sourceIdEvidence.reference_id.length > 2048
      || typeof sourceIdEvidence.relationship !== 'string' || !sourceIdEvidence.relationship.trim() || sourceIdEvidence.relationship.length > 120
      || (sourceIdEvidence.observed_at != null && (typeof sourceIdEvidence.observed_at !== 'string' || !Number.isFinite(Date.parse(sourceIdEvidence.observed_at))))) {
      fail('SOURCE_ID_EVIDENCE_MISSING');
    }
  }
  const providerPrefixedSourceId = /^(YOUTUBE(?:_OFFICIAL)?|BILIBILI(?:_OFFICIAL)?):(.*)$/.exec(sourceId);
  if (providerPrefixedSourceId && (providerFamily(providerPrefixedSourceId[1]) !== family || providerPrefixedSourceId[2] !== videoId)) fail('SOURCE_ID_VIDEO_ID_MISMATCH');
  if (typeof source.source_url !== 'string' || source.source_url.length > 2048 || !validOfficialSourceUrl(provider, videoId, source.source_url)) {
    fail(typeof source.source_url === 'string' ? officialSourceUrlError(provider, videoId, source.source_url) : 'SOURCE_URL_INVALID');
  }
  if (source.match_id != null && (typeof source.match_id !== 'string' || !source.match_id.trim() || source.match_id !== source.match_id.trim())) fail('SOURCE_MATCH_ID_INVALID');
  const recordedMatchId = source.match_id ?? null;
  if (matchId !== undefined && matchId !== null && recordedMatchId !== null && matchId !== recordedMatchId) fail('SOURCE_MATCH_ID_CONFLICT');
  const exactMatchId = matchId === undefined ? recordedMatchId : matchId;
  if (!optionalId(exactMatchId) || (typeof exactMatchId === 'string' && exactMatchId !== exactMatchId.trim())) fail('SOURCE_MATCH_ID_INVALID');
  const recordedPublisherId = publisherId === undefined
    ? (source.publisher_id ?? source.channel_id ?? nested?.channel_id ?? source.official_embed_review?.channel_id ?? null)
    : publisherId;
  if (!optionalId(recordedPublisherId)) fail('SOURCE_PUBLISHER_ID_INVALID');
  const evidenceRefs = [
    {reference_type: 'URL', reference_id: source.source_url, relationship: 'registered source URL; identity projection only', observed_at: null},
  ];
  if (explicitSourceId && !hasExactStoredSourceId) evidenceRefs.push({
    reference_type: sourceIdEvidence.reference_type,
    reference_id: sourceIdEvidence.reference_id,
    relationship: sourceIdEvidence.relationship,
    observed_at: sourceIdEvidence.observed_at ?? null,
  });
  const record = {
    ...recordBase(recordId, 'MediaSource', {match_id: exactMatchId, source_id: sourceId, video_asset_id: null}, 'OFFICIAL_PROVIDER', 'UNKNOWN', evidenceRefs),
    provider,
    source_status: 'REGISTERED',
    source_url: source.source_url,
    provider_video_id: videoId,
    publisher_id: recordedPublisherId,
  };
  validateFoundationRecord(record);
  return record;
}

export function videoAssetFromMediaSource(mediaSource, {recordId, durationMs = null} = {}) {
  if (!isObject(mediaSource) || mediaSource.kind !== 'MediaSource') fail('MEDIA_SOURCE_REQUIRED');
  validateFoundationRecord(mediaSource);
  if (!['YOUTUBE_OFFICIAL', 'BILIBILI_OFFICIAL'].includes(mediaSource.provider)
    || typeof mediaSource.provider_video_id !== 'string' || !mediaSource.provider_video_id
    || !mediaSource.identity.source_id) fail('MEDIA_SOURCE_IDENTITY_INCOMPLETE');
  if (typeof mediaSource.source_url !== 'string'
    || !validOfficialSourceUrl(mediaSource.provider, mediaSource.provider_video_id, mediaSource.source_url)) fail('MEDIA_SOURCE_URL_ID_MISMATCH');
  if (durationMs !== null && (!Number.isSafeInteger(durationMs) || durationMs < 0)) fail('ASSET_DURATION_INVALID');
  const assetId = `asset:provider:${mediaSource.provider}:${mediaSource.provider_video_id}`;
  const record = {
    ...recordBase(recordId, 'VideoAsset', {
      match_id: mediaSource.identity.match_id,
      source_id: mediaSource.identity.source_id,
      video_asset_id: assetId,
    }, 'OFFICIAL_PROVIDER', 'UNKNOWN', [
      {reference_type: 'RECORD', reference_id: mediaSource.record_id, relationship: 'exact registered MediaSource identity', observed_at: null},
    ]),
    asset_kind: 'OFFICIAL_REMOTE',
    identity_method: 'PROVIDER_VIDEO_ID',
    identity_value: `${mediaSource.provider}:${mediaSource.provider_video_id}`,
    duration_ms: durationMs,
    availability: 'NOT_TESTED',
  };
  validateFoundationRecord(record);
  return record;
}

function normalizedProLabIdentity(identity) {
  if (!isObject(identity) || identity.version !== 1 || typeof identity.name !== 'string'
    || !identity.name.trim() || identity.name.length > 255 || identity.name !== identity.name.split(/[\\/]/).filter(Boolean).at(-1)
    || !Number.isSafeInteger(identity.size) || identity.size < 0
    || !Number.isSafeInteger(identity.lastModified) || identity.lastModified < 0
    || typeof identity.type !== 'string' || identity.type.length > 128
    || identity.type !== identity.type.trim().toLowerCase()) return null;
  const key = `local-file:v1:${encodeURIComponent(JSON.stringify([identity.name, identity.size, identity.lastModified, identity.type]))}`;
  if (identity.key !== key || key.length > 512) return null;
  return key;
}

// FILE_METADATA_V1 is a Pro Lab selection key, not a digest of file bytes.
export function videoAssetFromProLabIdentity(identity, {recordId, durationMs = null} = {}) {
  const key = normalizedProLabIdentity(identity);
  if (!key) fail('PROLAB_IDENTITY_INVALID');
  if (durationMs !== null && (!Number.isSafeInteger(durationMs) || durationMs < 0)) fail('ASSET_DURATION_INVALID');
  const record = {
    ...recordBase(recordId, 'VideoAsset', {match_id: null, source_id: null, video_asset_id: `asset:file-metadata-v1:${key}`}, 'USER_LOCAL', 'NOT_INDEPENDENTLY_VERIFIED'),
    asset_kind: 'USER_LOCAL',
    identity_method: 'FILE_METADATA_V1',
    identity_value: key,
    duration_ms: durationMs,
    availability: 'UNKNOWN',
  };
  validateFoundationRecord(record);
  return record;
}

// GEX SHA256_CHUNKED_CONTENT_V1 is kept distinct from whole-file SHA-256 and
// from Pro Lab's metadata tuple. No file bytes are read by this projection.
export function videoAssetFromGexIdentity(asset, {recordId} = {}) {
  if (!isObject(asset) || asset.kind !== 'VideoAsset'
    || !/^sha256-chunks-v1:[a-f0-9]{64}$/.test(asset.id ?? '')
    || asset.hash_method !== 'SHA256_CHUNKED_CONTENT_V1'
    || !Number.isSafeInteger(asset.byte_length) || asset.byte_length <= 0
    || !Number.isFinite(asset.duration) || asset.duration <= 0
    || asset.origin !== 'LOCAL_BROWSER_ONLY' || !['USER_LOCAL', 'SYNTHETIC_DEMO'].includes(asset.media_kind)
    || asset.verification !== 'NOT_INDEPENDENTLY_VERIFIED') fail('GEX_ASSET_INVALID');
  const durationMs = Math.round(asset.duration * 1000);
  if (!Number.isSafeInteger(durationMs) || durationMs <= 0) fail('ASSET_DURATION_INVALID');
  const record = {
    ...recordBase(recordId, 'VideoAsset', {match_id: null, source_id: null, video_asset_id: `asset:${asset.id}`},
      asset.media_kind === 'SYNTHETIC_DEMO' ? 'SIMULATED_ONLY' : 'USER_LOCAL',
      asset.media_kind === 'SYNTHETIC_DEMO' ? 'SYNTHETIC_ONLY' : 'NOT_INDEPENDENTLY_VERIFIED', [
      {reference_type: 'HASH', reference_id: asset.id, relationship: 'GEX SHA256_CHUNKED_CONTENT_V1 identity; not a whole-file SHA-256', observed_at: null},
    ]),
    asset_kind: asset.media_kind === 'SYNTHETIC_DEMO' ? 'SYNTHETIC_DEMO' : 'USER_LOCAL',
    identity_method: 'SHA256_CHUNKED_CONTENT_V1',
    identity_value: asset.id,
    duration_ms: durationMs,
    availability: 'UNKNOWN',
  };
  validateFoundationRecord(record);
  return record;
}

function validAssetRecord(asset) {
  try { return isObject(asset) && asset.kind === 'VideoAsset' && validateFoundationRecord(asset); }
  catch { return false; }
}

// This compares identity evidence only. It never joins on title or grants media rights.
export function compareVideoAssetIdentity(left, right) {
  if (!validAssetRecord(left) || !validAssetRecord(right)) return {status: 'UNCONFIRMED', reason: 'ASSET_IDENTITY_MISSING'};
  const leftMethod = left.identity_method;
  const rightMethod = right.identity_method;
  if (leftMethod === 'UNKNOWN' || rightMethod === 'UNKNOWN') return {status: 'UNCONFIRMED', reason: 'IDENTITY_METHOD_UNKNOWN'};
  if (leftMethod !== rightMethod) return {status: 'UNCONFIRMED', reason: 'IDENTITY_METHOD_OR_SCOPE_MISMATCH'};
  if (leftMethod === 'FILE_METADATA_V1') {
    return {
      status: 'UNCONFIRMED',
      reason: left.identity_value === right.identity_value ? 'IDENTICAL_METADATA_NOT_CONTENT_PROOF' : 'METADATA_TUPLE_MISMATCH',
    };
  }
  if (leftMethod === 'PROVIDER_VIDEO_ID') {
    if (left.identity_value !== right.identity_value || left.identity.video_asset_id !== right.identity.video_asset_id
      || left.identity.source_id !== right.identity.source_id || left.identity.match_id !== right.identity.match_id) {
      return {status: 'UNCONFIRMED', reason: 'PROVIDER_OR_SOURCE_IDENTITY_MISMATCH'};
    }
    return {status: 'SAME_PROVIDER_VIDEO_IDENTITY', reason: ''};
  }
  if (leftMethod === 'SHA256_CHUNKED_CONTENT_V1') {
    if (!/^sha256-chunks-v1:[a-f0-9]{64}$/.test(left.identity_value ?? '')
      || !/^sha256-chunks-v1:[a-f0-9]{64}$/.test(right.identity_value ?? '')) return {status: 'UNCONFIRMED', reason: 'HASH_SCOPE_MISSING'};
  } else if (leftMethod === 'VERIFIED_SHA256') {
    if (!/^sha256:[a-z0-9][a-z0-9._-]*:[a-f0-9]{64}$/.test(left.identity_value ?? '')
      || !/^sha256:[a-z0-9][a-z0-9._-]*:[a-f0-9]{64}$/.test(right.identity_value ?? '')) return {status: 'UNCONFIRMED', reason: 'HASH_SCOPE_MISSING'};
  } else return {status: 'UNCONFIRMED', reason: 'IDENTITY_METHOD_UNSUPPORTED'};
  if (left.identity_value !== right.identity_value) return {status: 'UNCONFIRMED', reason: 'HASH_VALUE_OR_SCOPE_MISMATCH'};
  return {status: 'SAME_SCOPED_HASH_IDENTITY', reason: ''};
}

export function secondsToMilliseconds(seconds) {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 0 || seconds >= 86400) return null;
  const milliseconds = Math.round(seconds * 1000); // Non-negative Math.round is round-half-up.
  return Number.isSafeInteger(milliseconds) && milliseconds < 86400000 ? milliseconds : null;
}

export function resolveMomentAssetBinding(moment, videoAsset, {mediaSource = null, associationEvidence = null} = {}) {
  if (!moment || typeof moment.videoKey !== 'string' || !moment.videoKey.trim()) return {status: 'UNASSOCIATED', reason: 'MOMENT_VIDEO_KEY_MISSING'};
  if (!validAssetRecord(videoAsset)) return {status: 'UNASSOCIATED', reason: 'ASSET_MISSING'};
  if (videoAsset.identity_method === 'PROVIDER_VIDEO_ID') {
    const match = /^(YOUTUBE_OFFICIAL|BILIBILI_OFFICIAL):(.+)$/.exec(videoAsset.identity_value ?? '');
    const videoIdValid = match && (match[1] === 'YOUTUBE_OFFICIAL'
      ? /^[A-Za-z0-9_-]{11}$/.test(match[2])
      : /^BV[A-Za-z0-9]{10}$/.test(match[2]));
    const expectedAssetId = match ? `asset:provider:${match[1]}:${match[2]}` : null;
    if (!videoIdValid || videoAsset.asset_kind !== 'OFFICIAL_REMOTE'
      || videoAsset.identity.video_asset_id !== expectedAssetId
      || moment.videoKey !== `official:${match[2]}` || !videoAsset.identity.source_id) return {status: 'UNASSOCIATED', reason: 'PROVIDER_VIDEO_ID_MISMATCH'};
    if (!isObject(mediaSource) || mediaSource.kind !== 'MediaSource') return {status: 'UNASSOCIATED', reason: 'SOURCE_IDENTITY_MISSING'};
    try { validateFoundationRecord(mediaSource); } catch { return {status: 'UNASSOCIATED', reason: 'SOURCE_IDENTITY_INVALID'}; }
    if (mediaSource.provider !== match[1] || mediaSource.provider_video_id !== match[2]
      || mediaSource.identity.source_id !== videoAsset.identity.source_id
      || mediaSource.identity.match_id !== videoAsset.identity.match_id
      || !validOfficialSourceUrl(mediaSource.provider, mediaSource.provider_video_id, mediaSource.source_url)) {
      return {status: 'UNASSOCIATED', reason: 'SOURCE_ASSET_IDENTITY_MISMATCH'};
    }
    return {status: 'EXACT', reason: ''};
  }
  if (associationEvidence?.decision === 'USER_CONFIRMED_EXACT_BINDING'
    && associationEvidence.video_key === moment.videoKey
    && associationEvidence.video_asset_id === videoAsset.identity.video_asset_id
    && typeof associationEvidence.evidence_id === 'string' && associationEvidence.evidence_id.trim()) {
    return {status: 'EXACT_WITH_USER_EVIDENCE', reason: ''};
  }
  return {status: 'UNASSOCIATED', reason: 'LOCAL_ASSET_REQUIRES_EXPLICIT_ASSOCIATION_EVIDENCE'};
}

export function validateFoundationRecord(record) {
  if (!isObject(record) || record.schema_version !== FOUNDATION_VERSION || !FOUNDATION_KINDS.includes(record.kind)) fail('VERSION_OR_KIND');
  if (typeof record.record_id !== 'string' || !record.record_id.trim()) fail('RECORD_ID');
  if (!isObject(record.identity) || !['match_id', 'source_id', 'video_asset_id'].every(key => key in record.identity && optionalId(record.identity[key]))) fail('IDENTITY');
  const {origin, verification, inference, evidence_refs: evidenceRefs} = record.provenance ?? {};
  if (!ORIGINS.has(origin) || !VERIFICATIONS.has(verification) || !Array.isArray(evidenceRefs)) fail('PROVENANCE');
  if (origin === 'MODEL_INFERENCE') validateInference(inference);
  else if (inference !== null) fail('INFERENCE_ORIGIN_MISMATCH');
  if ((origin === 'MOCK' || origin === 'SIMULATED_ONLY') && verification !== 'SYNTHETIC_ONLY') fail('SYNTHETIC_STATUS');

  const anchor = record.timeline_anchor;
  if (TIMELINE_KINDS.has(record.kind) && !isObject(anchor)) fail('TIMELINE_REQUIRED');
  if (anchor !== null) {
    if (!isObject(anchor) || typeof anchor.video_asset_id !== 'string' || !anchor.video_asset_id.trim()
      || !Number.isSafeInteger(anchor.timestamp_ms) || anchor.timestamp_ms < 0 || !TIME_BASES.has(anchor.time_basis)) fail('TIMELINE_ANCHOR');
    if (anchor.end_ms !== undefined && anchor.end_ms !== null
      && (!Number.isSafeInteger(anchor.end_ms) || anchor.end_ms <= anchor.timestamp_ms)) fail('TIMELINE_RANGE');
    if (record.identity.video_asset_id !== anchor.video_asset_id) fail('TIMELINE_ASSET_MISMATCH');
  }

  if (record.kind === 'MatchIdentity' && record.identity_status === 'EXACT' && !record.identity.match_id) fail('MATCH_ID_REQUIRED');
  if (record.kind === 'MediaSource' && record.source_status === 'REGISTERED'
    && (!record.identity.source_id || typeof record.source_url !== 'string' || !record.source_url)) fail('REGISTERED_SOURCE_INCOMPLETE');
  if (record.kind === 'VideoAsset') {
    if (!record.identity.video_asset_id || !['OFFICIAL_REMOTE', 'USER_LOCAL', 'SYNTHETIC_DEMO', 'UNKNOWN'].includes(record.asset_kind)) fail('VIDEO_ASSET_IDENTITY');
  }
  if (record.kind === 'PointEvent') {
    if (record.event_scope === 'MEDIA_TIMELINE') {
      if (!isObject(anchor) || !record.identity.video_asset_id) fail('POINT_EVENT_TIME_REQUIRED');
    } else if (record.event_scope === 'SIMULATED_SEQUENCE') {
      if (anchor !== null || record.identity.match_id !== null || record.identity.source_id !== null || record.identity.video_asset_id !== null
        || origin !== 'SIMULATED_ONLY' || verification !== 'SYNTHETIC_ONLY'
        || typeof record.simulation_id !== 'string' || !Number.isSafeInteger(record.sequence_index) || record.sequence_index < 0) fail('SIMULATION_BOUNDARY');
    } else fail('POINT_EVENT_SCOPE');
  }
  if (record.kind === 'Prediction' && (anchor !== null || typeof record.target_point_event_id !== 'string' || !record.target_point_event_id)) fail('PREDICTION_TARGET');
  if (record.kind === 'CoachAnnotation') {
    if (record.scope === 'MEDIA_TIMELINE' && !isObject(anchor)) fail('COACH_TIMELINE_REQUIRED');
    if (record.scope === 'GENERAL' && anchor !== null) fail('GENERAL_NOTE_HAS_TIMELINE');
    if (record.scope === 'POINT_EVENT' && !record.related_point_event_id) fail('COACH_POINT_EVENT_REQUIRED');
  }
  if (record.kind === 'PoseEvidence') {
    if (!Array.isArray(record.frame_times_ms) || !record.frame_times_ms.length
      || record.frame_times_ms.some((time, index) => !Number.isSafeInteger(time) || time < anchor.timestamp_ms || (index > 0 && time <= record.frame_times_ms[index - 1]))) fail('POSE_FRAME_TIMES');
  }
  if (record.kind === 'RightsEvidence') {
    if (!isObject(record.permissions)) fail('RIGHTS_PERMISSIONS');
    for (const decision of Object.values(record.permissions)) {
      if (!isObject(decision) || !['ALLOWED', 'NOT_ALLOWED', 'NEEDS_PERMISSION', 'UNKNOWN', 'EXPIRED', 'REVOKED'].includes(decision.status)
        || !Array.isArray(decision.evidence_refs)) fail('RIGHTS_DECISION');
      if (decision.status === 'ALLOWED' && decision.evidence_refs.length === 0) fail('RIGHTS_ALLOW_WITHOUT_EVIDENCE');
    }
  }
  return true;
}

function validateInference(inference) {
  if (!isObject(inference) || typeof inference.model_id !== 'string' || !inference.model_id
    || typeof inference.model_version !== 'string' || !inference.model_version
    || !Array.isArray(inference.input_refs) || inference.input_refs.length === 0
    || !['CALIBRATED', 'UNCALIBRATED', 'UNAVAILABLE'].includes(inference.confidence_status)) fail('INFERENCE_PROVENANCE');
  if (inference.confidence === null) {
    if (inference.confidence_status === 'CALIBRATED') fail('CALIBRATED_CONFIDENCE_MISSING');
  } else if (typeof inference.confidence !== 'number' || inference.confidence < 0 || inference.confidence > 1
    || inference.confidence_status === 'UNAVAILABLE') fail('INFERENCE_CONFIDENCE');
  return true;
}

export function validateFoundationBundle(records) {
  if (!Array.isArray(records)) fail('BUNDLE_NOT_ARRAY');
  const byRecord = new Map();
  const byMatch = new Map();
  const bySource = new Map();
  const byAsset = new Map();
  const byPointEvent = new Map();
  const businessIds = new Map();
  const simulatedSequences = new Set();
  const rememberUnique = (kind, value) => {
    if (typeof value !== 'string' || !value) return;
    const key = `${kind}:${value}`;
    if (businessIds.has(key)) fail('DUPLICATE_ENTITY_ID');
    businessIds.set(key, true);
  };
  for (const record of records) {
    validateFoundationRecord(record);
    if (byRecord.has(record.record_id)) fail('DUPLICATE_RECORD_ID');
    byRecord.set(record.record_id, record);
    const entityId = {
      MatchIdentity: record.identity.match_id,
      MediaSource: record.identity.source_id,
      VideoAsset: record.identity.video_asset_id,
      Moment: record.moment_id,
      Rally: record.rally_id,
      PointEvent: record.point_id,
      Prediction: record.prediction_id,
      PoseEvidence: record.evidence_id,
      CoachAnnotation: record.annotation_id,
      UserCollection: record.collection_id,
      RightsEvidence: record.rights_id,
    }[record.kind];
    rememberUnique(record.kind, entityId);
    const key = record.kind === 'MatchIdentity' ? record.identity.match_id
      : record.kind === 'MediaSource' ? record.identity.source_id
        : record.kind === 'VideoAsset' ? record.identity.video_asset_id : null;
    const map = record.kind === 'MatchIdentity' ? byMatch : record.kind === 'MediaSource' ? bySource : record.kind === 'VideoAsset' ? byAsset : null;
    if (map && key) {
      if (map.has(key)) fail('DUPLICATE_CANONICAL_ID');
      map.set(key, record);
    }
    if (record.kind === 'PointEvent') {
      byPointEvent.set(record.record_id, record);
      if (record.event_scope === 'SIMULATED_SEQUENCE') {
        const sequenceKey = `${record.simulation_id}:${record.sequence_index}`;
        if (simulatedSequences.has(sequenceKey)) fail('DUPLICATE_SIMULATION_SEQUENCE');
        simulatedSequences.add(sequenceKey);
      }
    }
  }

  const requireExact = (map, key, code) => { if (key !== null && !map.has(key)) fail(code); };
  for (const record of records) {
    if (record.kind !== 'MatchIdentity') requireExact(byMatch, record.identity.match_id, 'UNKNOWN_MATCH_REFERENCE');
    if (record.kind !== 'MediaSource') requireExact(bySource, record.identity.source_id, 'UNKNOWN_SOURCE_REFERENCE');
    if (record.kind !== 'VideoAsset') requireExact(byAsset, record.identity.video_asset_id, 'UNKNOWN_ASSET_REFERENCE');
    if (record.timeline_anchor) {
      const asset = byAsset.get(record.timeline_anchor.video_asset_id);
      if (!asset) fail('TIMELINE_ASSET_NOT_FOUND');
      if (asset.duration_ms !== null && record.timeline_anchor.timestamp_ms > asset.duration_ms) fail('TIMELINE_OUT_OF_RANGE');
      if (record.timeline_anchor.end_ms != null && asset.duration_ms !== null && record.timeline_anchor.end_ms > asset.duration_ms) fail('TIMELINE_OUT_OF_RANGE');
      if (asset.identity.match_id && record.identity.match_id && asset.identity.match_id !== record.identity.match_id) fail('CROSS_MATCH_TIMELINE');
    }
    if (record.kind === 'Prediction') {
      const target = byPointEvent.get(record.target_point_event_id);
      if (!target) fail('PREDICTION_EVENT_NOT_FOUND');
      if (record.provenance.origin === 'SIMULATED_ONLY'
        && (target.event_scope !== 'SIMULATED_SEQUENCE' || target.simulation_id !== record.simulation_id)) fail('PREDICTION_SIMULATION_MISMATCH');
    }
    if (record.kind === 'PlaybackState' && record.rights_evidence_record_id !== null) {
      const rights = byRecord.get(record.rights_evidence_record_id);
      if (!rights || rights.kind !== 'RightsEvidence') fail('PLAYBACK_RIGHTS_REFERENCE_MISMATCH');
      const subject = byRecord.get(rights.subject_record_id);
      if (!subject) fail('PLAYBACK_RIGHTS_REFERENCE_MISMATCH');
      if (subject.kind === 'MediaSource' && subject.identity.source_id !== record.identity.source_id) fail('PLAYBACK_RIGHTS_IDENTITY_MISMATCH');
      if (subject.kind === 'VideoAsset' && subject.identity.video_asset_id !== record.identity.video_asset_id) fail('PLAYBACK_RIGHTS_IDENTITY_MISMATCH');
    }
    if (record.kind === 'CoachAnnotation' && record.related_point_event_id !== null) {
      const related = byRecord.get(record.related_point_event_id);
      if (!related || related.kind !== 'PointEvent') fail('ANNOTATION_POINT_REFERENCE_MISMATCH');
    }
    if (record.kind === 'UserCollection') {
      for (const ref of record.item_refs) {
        const target = byRecord.get(ref.record_id);
        if (!target || target.kind !== ref.record_kind) fail('COLLECTION_REFERENCE_MISMATCH');
      }
    }
    if (record.kind === 'RightsEvidence') {
      const target = byRecord.get(record.subject_record_id);
      if (!target || !['MediaSource', 'VideoAsset'].includes(target.kind)) fail('RIGHTS_SUBJECT_NOT_FOUND');
      const subjectKind = {MEDIA_SOURCE: 'MediaSource', VIDEO_ASSET: 'VideoAsset'}[record.subject_kind];
      if (target.kind !== subjectKind) fail('RIGHTS_SUBJECT_KIND_MISMATCH');
    }
  }
  return true;
}

// Projection from Moment Cards is allowed only after an exact provider ID
// binding, or an explicit user-confirmed local asset binding.
export function momentCardToFoundation(moment, {videoAsset, mediaSource = null, associationEvidence = null} = {}) {
  if (!moment || typeof moment.id !== 'string' || !moment.id.trim() || moment.id.length > 249
    || typeof moment.title !== 'string' || !moment.title.trim()
    || moment.title.length > 120 || typeof moment.note !== 'string' || moment.note.length > 2000
    || !Array.isArray(moment.tags) || moment.tags.some(tag => typeof tag !== 'string' || !tag.trim())
    || moment.tags.length > 20 || new Set(moment.tags).size !== moment.tags.length
    || moment.tags.some(tag => tag.length > 80)) fail('MOMENT_SOURCE_INVALID');
  const binding = resolveMomentAssetBinding(moment, videoAsset, {mediaSource, associationEvidence});
  if (!['EXACT', 'EXACT_WITH_USER_EVIDENCE'].includes(binding.status)) fail('MOMENT_ASSET_UNASSOCIATED');
  const timestampMs = secondsToMilliseconds(moment.seconds);
  if (timestampMs === null) fail('MOMENT_SOURCE_INVALID');
  if (videoAsset.duration_ms !== null && timestampMs > videoAsset.duration_ms) fail('MOMENT_TIME_OUT_OF_RANGE');
  const videoAssetId = videoAsset.identity.video_asset_id;
  const bindingEvidenceRefs = binding.status === 'EXACT_WITH_USER_EVIDENCE' ? [{
    reference_type: 'USER_STATEMENT',
    reference_id: associationEvidence.evidence_id,
    relationship: 'user confirmed exact Moment-to-local-video asset binding',
    observed_at: null,
  }] : [];
  const record = {
    schema_version: FOUNDATION_VERSION,
    record_id: `moment:${moment.id}`,
    kind: 'Moment',
    identity: {match_id: videoAsset.identity.match_id, source_id: videoAsset.identity.source_id, video_asset_id: videoAssetId},
    timeline_anchor: {video_asset_id: videoAssetId, timestamp_ms: timestampMs, end_ms: null, time_basis: 'USER_ENTERED_TIME'},
    provenance: {origin: 'USER_AUTHORED', verification: 'NOT_INDEPENDENTLY_VERIFIED', evidence_refs: bindingEvidenceRefs, inference: null},
    moment_id: moment.id,
    title: String(moment.title ?? ''),
    note: String(moment.note ?? ''),
    tags: Array.isArray(moment.tags) ? [...moment.tags] : [],
    author_type: 'USER',
  };
  validateFoundationRecord(record);
  return record;
}

export function simulatedPointToFoundation({recordId, pointId, simulationId, sequenceIndex, playerA = 'A', playerB = 'B', winner = null, scoreABefore = null, scoreBBefore = null}) {
  if (typeof recordId !== 'string' || !recordId.trim() || typeof pointId !== 'string' || !pointId.trim()
    || typeof simulationId !== 'string' || !simulationId.trim() || !Number.isSafeInteger(sequenceIndex) || sequenceIndex < 0
    || typeof playerA !== 'string' || !playerA.trim() || typeof playerB !== 'string' || !playerB.trim() || playerA === playerB
    || (winner !== null && winner !== playerA && winner !== playerB)
    || (scoreABefore !== null && (!Number.isSafeInteger(scoreABefore) || scoreABefore < 0))
    || (scoreBBefore !== null && (!Number.isSafeInteger(scoreBBefore) || scoreBBefore < 0))) fail('SIMULATED_POINT_INPUT_INVALID');
  const record = {
    schema_version: FOUNDATION_VERSION, record_id: recordId, kind: 'PointEvent',
    identity: {match_id: null, source_id: null, video_asset_id: null}, timeline_anchor: null,
    provenance: {origin: 'SIMULATED_ONLY', verification: 'SYNTHETIC_ONLY', evidence_refs: [], inference: null},
    point_id: pointId, event_scope: 'SIMULATED_SEQUENCE', simulation_id: simulationId, sequence_index: sequenceIndex,
    player_a_id: playerA, player_b_id: playerB, winner_id: winner, score_a_before: scoreABefore, score_b_before: scoreBBefore,
  };
  validateFoundationRecord(record);
  return record;
}
