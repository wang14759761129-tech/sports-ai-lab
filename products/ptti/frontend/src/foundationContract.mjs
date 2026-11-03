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

// Projection from existing Moment Cards. Keep videoKey exact; match_id is only
// copied when supplied by the exact registered source, never inferred by title.
export function momentCardToFoundation(moment, {videoAssetId = moment?.videoKey, sourceId = null, matchId = null} = {}) {
  if (!moment || typeof moment.id !== 'string' || !moment.id.trim()
    || typeof moment.title !== 'string' || !moment.title.trim()
    || typeof moment.note !== 'string'
    || !Array.isArray(moment.tags) || moment.tags.some(tag => typeof tag !== 'string' || !tag.trim())
    || !Number.isSafeInteger(moment.seconds) || moment.seconds < 0) fail('MOMENT_SOURCE_INVALID');
  if (typeof videoAssetId !== 'string' || !videoAssetId) fail('MOMENT_ASSET_MISSING');
  const record = {
    schema_version: FOUNDATION_VERSION,
    record_id: `moment:${moment.id}`,
    kind: 'Moment',
    identity: {match_id: matchId, source_id: sourceId, video_asset_id: videoAssetId},
    timeline_anchor: {video_asset_id: videoAssetId, timestamp_ms: moment.seconds * 1000, end_ms: null, time_basis: 'USER_ENTERED_TIME'},
    provenance: {origin: 'USER_AUTHORED', verification: 'NOT_INDEPENDENTLY_VERIFIED', evidence_refs: [], inference: null},
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
