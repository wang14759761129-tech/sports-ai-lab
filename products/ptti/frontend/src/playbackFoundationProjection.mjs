import {validateFoundationRecord} from './foundationContract.mjs';

export const LOCAL_PLAYBACK_PROGRESS_KEY = 'ptti.local-video-progress/1';
export const LOCAL_CONTINUATION_USE_CASE = 'LOCAL_PERSONAL_PLAYBACK_CONTINUATION';

const HASH_ID = /^sha256-chunks-v1:[a-f0-9]{64}$/;
const RIGHTS_TARGETS = Object.freeze({WEB: 'web_display', NATIVE: 'native_display'});
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const validDateTime = value => typeof value === 'string'
  && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)
  && Number.isFinite(Date.parse(value));

function isValidLocalAsset(asset) {
  try {
    return object(asset)
      && asset.kind === 'VideoAsset'
      && validateFoundationRecord(asset)
      && asset.asset_kind === 'USER_LOCAL'
      && asset.identity_method === 'SHA256_CHUNKED_CONTENT_V1'
      && HASH_ID.test(asset.identity_value ?? '')
      && asset.identity?.video_asset_id === `asset:${asset.identity_value}`
      && asset.identity?.source_id === null
      && asset.identity?.match_id === null
      && Number.isSafeInteger(asset.duration_ms)
      && asset.duration_ms > 0;
  } catch {
    return false;
  }
}

function exactRightsEvidence(asset, rightsEvidence, target, nowMs) {
  if (!rightsEvidence) return {record: null, status: 'MISSING', reason: 'RIGHTS_EVIDENCE_MISSING'};
  try {
    if (rightsEvidence.kind !== 'RightsEvidence' || !validateFoundationRecord(rightsEvidence)) {
      return {record: null, status: 'INVALID', reason: 'RIGHTS_EVIDENCE_INVALID'};
    }
  } catch {
    return {record: null, status: 'INVALID', reason: 'RIGHTS_EVIDENCE_INVALID'};
  }

  if (rightsEvidence.subject_kind !== 'VIDEO_ASSET'
    || rightsEvidence.subject_record_id !== asset.record_id
    || rightsEvidence.identity?.video_asset_id !== asset.identity.video_asset_id
    || rightsEvidence.identity?.source_id !== asset.identity.source_id
    || rightsEvidence.identity?.match_id !== asset.identity.match_id) {
    return {record: null, status: 'MISMATCH', reason: 'RIGHTS_SUBJECT_MISMATCH'};
  }
  if (rightsEvidence.reviewed_use_case !== LOCAL_CONTINUATION_USE_CASE) {
    return {record: null, status: 'WRONG_USE_CASE', reason: 'RIGHTS_USE_CASE_MISMATCH'};
  }
  if (['MOCK', 'SIMULATED_ONLY', 'UNKNOWN'].includes(rightsEvidence.provenance?.origin)
    || !['VERIFIED', 'USER_CONFIRMED'].includes(rightsEvidence.provenance?.verification)) {
    return {record: null, status: 'UNVERIFIED', reason: 'RIGHTS_EVIDENCE_UNVERIFIED'};
  }

  const permission = rightsEvidence.permissions?.[target];
  if (!permission || !Array.isArray(permission.evidence_refs)) {
    return {record: null, status: 'INVALID', reason: 'RIGHTS_DECISION_INVALID'};
  }
  if (permission.valid_until !== null) {
    const expiry = validDateTime(permission.valid_until) ? Date.parse(permission.valid_until) : NaN;
    if (!Number.isFinite(expiry)) return {record: null, status: 'INVALID', reason: 'RIGHTS_EXPIRY_INVALID'};
    if (nowMs >= expiry) return {record: rightsEvidence, status: 'EXPIRED', reason: 'RIGHTS_EVIDENCE_EXPIRED'};
  }
  if (permission.status === 'EXPIRED') return {record: rightsEvidence, status: 'EXPIRED', reason: 'RIGHTS_EVIDENCE_EXPIRED'};
  if (permission.status === 'REVOKED') return {record: rightsEvidence, status: 'REVOKED', reason: 'RIGHTS_EVIDENCE_REVOKED'};
  if (permission.status !== 'ALLOWED') {
    return {record: rightsEvidence, status: permission.status, reason: `RIGHTS_${permission.status}`};
  }
  if (permission.evidence_refs.length === 0) {
    return {record: null, status: 'INVALID', reason: 'RIGHTS_ALLOW_WITHOUT_EVIDENCE'};
  }
  return {record: rightsEvidence, status: 'ALLOWED', reason: null};
}

function noProjection(reason) {
  return {
    status: 'UNPROJECTABLE',
    reason,
    playbackState: null,
    rightsEvidence: null,
    savedProgress: {source_key: LOCAL_PLAYBACK_PROGRESS_KEY, status: 'UNVERIFIABLE', position_ms: null},
    continuation: {status: 'NOT_ELIGIBLE', reason},
  };
}

/**
 * Read-only projection boundary. The caller must obtain progress from
 * localPlayback.readProgress and pass the exact hashed asset identity. This
 * function never accesses storage or writes either progress store.
 */
export function projectLocalPlaybackToFoundation(input = {}) {
  const {
    recordId,
    videoAsset,
    currentAvailability = 'UNKNOWN',
    currentDurationMs,
    progressSnapshot,
    rightsEvidence = null,
    target = 'WEB',
    now = Date.now(),
  } = input;

  if (!isValidLocalAsset(videoAsset)) return noProjection('ASSET_NOT_SUPPORTED_LOCAL_HASH_IDENTITY');
  if (typeof recordId !== 'string' || !recordId.trim()) return noProjection('PLAYBACK_RECORD_ID_MISSING');
  if (!Object.hasOwn(RIGHTS_TARGETS, target)) return noProjection('PLAYBACK_TARGET_UNKNOWN');
  if (!Number.isFinite(now)) return noProjection('CURRENT_TIME_INVALID');

  const permission = exactRightsEvidence(videoAsset, rightsEvidence, RIGHTS_TARGETS[target], now);
  const rightsRecord = permission.record;
  const playbackState = {
    schema_version: 'ptti.foundation/0.1',
    record_id: recordId,
    kind: 'PlaybackState',
    identity: {...videoAsset.identity},
    timeline_anchor: null,
    provenance: {
      origin: 'USER_LOCAL',
      verification: 'NOT_INDEPENDENTLY_VERIFIED',
      evidence_refs: [],
      inference: null,
    },
    route: 'LOCAL_HTML_VIDEO',
    observation: 'NOT_TESTED',
    observed_at: null,
    provider_embeddable: null,
    // RightsEvidence for an app display surface never means provider embedding.
    embed_permission: 'UNKNOWN',
    rights_evidence_record_id: rightsRecord?.record_id ?? null,
  };
  try { validateFoundationRecord(playbackState); }
  catch { return noProjection('PLAYBACK_STATE_CONTRACT_INVALID'); }

  const result = {
    status: 'PROJECTED',
    reason: null,
    rightsTarget: target,
    rightsEvaluatedAtMs: now,
    playbackState,
    rightsEvidence: rightsRecord,
    savedProgress: {
      source_key: LOCAL_PLAYBACK_PROGRESS_KEY,
      asset_record_id: videoAsset.record_id,
      identity_method: 'SHA256_CHUNKED_CONTENT_V1',
      identity_value: videoAsset.identity_value,
      status: 'UNVERIFIABLE',
      position_ms: null,
      duration_ms: null,
    },
    continuation: {status: 'NOT_ELIGIBLE', reason: null},
  };

  if (!['AVAILABLE', 'UNAVAILABLE', 'UNKNOWN'].includes(currentAvailability)) {
    result.savedProgress.status = 'UNVERIFIABLE';
    result.continuation.reason = 'CURRENT_AVAILABILITY_INVALID';
    return result;
  }
  if (currentAvailability !== 'AVAILABLE') {
    result.savedProgress.status = currentAvailability === 'UNAVAILABLE' ? 'MEDIA_UNAVAILABLE' : 'MEDIA_AVAILABILITY_UNKNOWN';
    result.continuation.reason = currentAvailability === 'UNAVAILABLE' ? 'MEDIA_UNAVAILABLE' : 'MEDIA_AVAILABILITY_UNKNOWN';
    return result;
  }
  if (!Number.isSafeInteger(currentDurationMs) || currentDurationMs <= 0
    || Math.abs(currentDurationMs - videoAsset.duration_ms) > 500) {
    result.savedProgress.status = 'DURATION_MISMATCH';
    result.continuation.reason = 'CURRENT_DURATION_MISMATCH';
    return result;
  }

  if (!object(progressSnapshot) || progressSnapshot.source_key !== LOCAL_PLAYBACK_PROGRESS_KEY
    || progressSnapshot.identity_value !== videoAsset.identity_value) {
    result.savedProgress.status = 'IDENTITY_MISMATCH';
    result.continuation.reason = 'PROGRESS_IDENTITY_MISMATCH';
    return result;
  }
  if (progressSnapshot.status === 'UNVERIFIABLE') {
    result.savedProgress.status = 'UNVERIFIABLE';
    result.continuation.reason = 'HISTORY_UNVERIFIABLE';
    return result;
  }
  if (progressSnapshot.status === 'EMPTY') {
    result.savedProgress.status = 'EMPTY';
    result.continuation.reason = 'NO_SAVED_PROGRESS';
    return result;
  }
  if (progressSnapshot.status !== 'FOUND'
    || !Number.isFinite(progressSnapshot.position_seconds)
    || !Number.isFinite(progressSnapshot.duration_seconds)
    || progressSnapshot.duration_seconds <= 0
    || Math.abs(progressSnapshot.duration_seconds * 1000 - currentDurationMs) > 500
    || progressSnapshot.position_seconds < 0
    || progressSnapshot.position_seconds > currentDurationMs / 1000) {
    result.savedProgress.status = 'INVALID_PROGRESS';
    result.continuation.reason = 'PROGRESS_OUT_OF_RANGE';
    return result;
  }

  const positionMs = Math.round(progressSnapshot.position_seconds * 1000);
  if (!Number.isSafeInteger(positionMs)) {
    result.savedProgress.status = 'INVALID_PROGRESS';
    result.continuation.reason = 'PROGRESS_OUT_OF_RANGE';
    return result;
  }
  result.savedProgress.status = 'FOUND';
  result.savedProgress.position_ms = positionMs;
  result.savedProgress.duration_ms = currentDurationMs;

  if (permission.status !== 'ALLOWED') {
    result.continuation.reason = permission.reason;
    return result;
  }
  if (positionMs <= 0 || positionMs >= currentDurationMs) {
    result.continuation.reason = 'NO_RESUMABLE_POSITION';
    return result;
  }

  result.continuation = {status: 'ELIGIBLE', reason: null};
  return result;
}

export function isEligiblePlaybackProjection(projection, now = Date.now()) {
  if (!object(projection) || projection.status !== 'PROJECTED'
    || projection.continuation?.status !== 'ELIGIBLE'
    || projection.savedProgress?.status !== 'FOUND'
    || !Number.isSafeInteger(projection.savedProgress.position_ms)
    || !Number.isSafeInteger(projection.savedProgress.duration_ms)
    || projection.savedProgress.position_ms <= 0
    || projection.savedProgress.position_ms >= projection.savedProgress.duration_ms
    || projection.savedProgress.source_key !== LOCAL_PLAYBACK_PROGRESS_KEY
    || typeof projection.savedProgress.asset_record_id !== 'string'
    || !Number.isFinite(now)
    || !object(projection.playbackState) || projection.playbackState.kind !== 'PlaybackState'
    || projection.playbackState.observation !== 'NOT_TESTED'
    || projection.playbackState.embed_permission !== 'UNKNOWN'
    || !projection.playbackState.rights_evidence_record_id
    || !object(projection.rightsEvidence) || projection.rightsEvidence.kind !== 'RightsEvidence'
    || projection.playbackState.rights_evidence_record_id !== projection.rightsEvidence.record_id) return false;
  try {
    validateFoundationRecord(projection.playbackState);
    validateFoundationRecord(projection.rightsEvidence);
    const permissionKey = projection.rightsTarget === 'WEB' ? 'web_display'
      : projection.rightsTarget === 'NATIVE' ? 'native_display' : null;
    const decision = permissionKey && projection.rightsEvidence.permissions?.[permissionKey];
    const expiry = decision?.valid_until == null ? null : (validDateTime(decision.valid_until) ? Date.parse(decision.valid_until) : NaN);
    return Boolean(permissionKey
      && projection.rightsEvidence.subject_kind === 'VIDEO_ASSET'
      && projection.rightsEvidence.subject_record_id === projection.savedProgress.asset_record_id
      && projection.rightsEvidence.identity?.video_asset_id === projection.playbackState.identity.video_asset_id
      && projection.rightsEvidence.reviewed_use_case === LOCAL_CONTINUATION_USE_CASE
      && !['MOCK', 'SIMULATED_ONLY', 'UNKNOWN'].includes(projection.rightsEvidence.provenance?.origin)
      && ['VERIFIED', 'USER_CONFIRMED'].includes(projection.rightsEvidence.provenance?.verification)
      && decision?.status === 'ALLOWED' && Array.isArray(decision.evidence_refs) && decision.evidence_refs.length > 0
      && (expiry === null || (Number.isFinite(expiry) && now < expiry)));
  } catch {
    return false;
  }
}
