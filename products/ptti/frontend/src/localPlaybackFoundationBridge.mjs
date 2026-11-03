// Local-only bridge: one Playback progress store, with read-only Foundation views.
import {identify, validateEvidence} from './gex-moment/evidence.mjs';
import {PROGRESS_KEY, readProgress} from './localPlayback.mjs';
import {validateFoundationRecord, videoAssetFromGexIdentity, momentCardToFoundation} from './foundationContract.mjs';
import {LOCAL_CONTINUATION_USE_CASE, projectLocalPlaybackToFoundation} from './playbackFoundationProjection.mjs';

export async function prepareLocalSession({file, duration, storage, isCurrent = () => true}) {
  if (!(file instanceof Blob) || !Number.isFinite(duration) || duration <= 0) throw Error('LOCAL_MEDIA_INVALID');
  const id = await identify(file, () => {}, isCurrent);
  if (!isCurrent()) throw Error('LOCAL_SESSION_CANCELLED');
  const gexAsset = {kind: 'VideoAsset', id, hash_method: 'SHA256_CHUNKED_CONTENT_V1',
    byte_length: file.size, duration, origin: 'LOCAL_BROWSER_ONLY', media_kind: 'USER_LOCAL',
    verification: 'NOT_INDEPENDENTLY_VERIFIED'};
  const videoAsset = videoAssetFromGexIdentity(gexAsset, {recordId: `local-asset:${id}`});
  let progressSnapshot;
  try {
    const saved = readProgress(storage, id, duration);
    progressSnapshot = saved === null
      ? {source_key: PROGRESS_KEY, identity_value: id, status: 'EMPTY'}
      : {source_key: PROGRESS_KEY, identity_value: id, status: 'FOUND', position_seconds: saved, duration_seconds: duration};
  } catch {
    progressSnapshot = {source_key: PROGRESS_KEY, identity_value: id, status: 'UNVERIFIABLE'};
  }
  const session = {gexAsset, videoAsset, progressSnapshot};
  return {...session, projection: projectLocalSession(session)};
}

export function projectLocalSession(session, {rightsEvidence = null, target = 'WEB', now = Date.now()} = {}) {
  return projectLocalPlaybackToFoundation({recordId: `local-playback:${session.gexAsset.id}`,
    videoAsset: session.videoAsset, currentAvailability: 'AVAILABLE', currentDurationMs: session.videoAsset.duration_ms,
    progressSnapshot: session.progressSnapshot, rightsEvidence, target, now});
}

// Only an actual explicit confirmation from the selecting user may call this.
// The resulting evidence is ephemeral and grants neither embed nor distribution.
export function confirmedLocalRights(videoAsset, {confirmed, target = 'WEB', evidenceId} = {}) {
  if (confirmed !== true || !['WEB', 'NATIVE'].includes(target) || typeof evidenceId !== 'string' || !evidenceId.trim()) throw Error('LOCAL_CONFIRMATION_REQUIRED');
  try { validateFoundationRecord(videoAsset); } catch { throw Error('LOCAL_ASSET_REQUIRED'); }
  if (videoAsset.kind !== 'VideoAsset' || videoAsset.asset_kind !== 'USER_LOCAL'
    || videoAsset.identity_method !== 'SHA256_CHUNKED_CONTENT_V1'
    || !/^sha256-chunks-v1:[a-f0-9]{64}$/.test(videoAsset.identity_value ?? '')
    || videoAsset.identity.video_asset_id !== `asset:${videoAsset.identity_value}`
    || videoAsset.identity.source_id !== null || videoAsset.identity.match_id !== null) throw Error('LOCAL_ASSET_REQUIRED');
  const ref = {reference_type: 'USER_STATEMENT', reference_id: evidenceId,
    relationship: 'user confirmed local use of this selected file', observed_at: null};
  const permissions = Object.fromEntries(['remote_display','web_display','native_display','package_distribution','embed','download','edit','analysis','commercial_use']
    .map(name => [name, {status: name === (target === 'WEB' ? 'web_display' : 'native_display') ? 'ALLOWED' : 'UNKNOWN',
      evidence_refs: name === (target === 'WEB' ? 'web_display' : 'native_display') ? [ref] : [], valid_until: null}]));
  return {schema_version: 'ptti.foundation/0.1', record_id: `local-rights:${videoAsset.identity_value}`,
    kind: 'RightsEvidence', identity: {...videoAsset.identity}, timeline_anchor: null,
    provenance: {origin: 'USER_AUTHORED', verification: 'USER_CONFIRMED', evidence_refs: [ref], inference: null},
    rights_id: `local-rights:${videoAsset.identity_value}`, subject_kind: 'VIDEO_ASSET', subject_record_id: videoAsset.record_id,
    reviewed_use_case: LOCAL_CONTINUATION_USE_CASE, permissions};
}

// Confirmation is the user's explicit import action, not a title-based match.
export function projectImportedMoment(gexAsset, item, confirmationId) {
  if (typeof confirmationId !== 'string' || !confirmationId.trim()) throw Error('MOMENT_CONFIRMATION_REQUIRED');
  validateEvidence({moments: [item], rallies: [], annotations: [], reviewNotes: [], vision: null}, gexAsset);
  if (item.video_id !== gexAsset.id) throw Error('MOMENT_VIDEO_ID_MISMATCH');
  const videoAsset = videoAssetFromGexIdentity(gexAsset, {recordId: `local-asset:${gexAsset.id}`});
  return momentCardToFoundation({id: item.id, videoKey: gexAsset.id, seconds: item.time,
    title: '本机 Moment', note: item.note, tags: []}, {videoAsset,
    associationEvidence: {decision: 'USER_CONFIRMED_EXACT_BINDING', video_key: gexAsset.id,
      video_asset_id: videoAsset.identity.video_asset_id, evidence_id: confirmationId}});
}

export function seekImportedMoment(video, expectedUrl, gexAsset, item, confirmationId) {
  if (!video || typeof expectedUrl !== 'string' || !expectedUrl || video.currentSrc !== expectedUrl
    || video.readyState < 1 || !Number.isFinite(video.duration) || video.duration <= 0
    || Math.abs(video.duration - gexAsset.duration) > 0.05) throw Error('LOCAL_VIDEO_NOT_CURRENT');
  const record = projectImportedMoment(gexAsset, item, confirmationId);
  const seconds = record.timeline_anchor.timestamp_ms / 1000;
  if (seconds > video.duration) throw Error('MOMENT_OUT_OF_RANGE');
  video.currentTime = seconds;
  return record;
}
