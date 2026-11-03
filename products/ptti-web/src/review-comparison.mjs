export function createReviewComparisonExport({ report, target, points, playbackBindings, note, sessionId }) {
  if (!report || report.contract_version !== 'ptti.review-targets/0.1' || !target || !Array.isArray(target.point_ids)) {
    throw new Error('matched-review-target-required');
  }
  const firstPoint = points.find((candidate) => candidate.point_id === target.point_ids[0]);
  if (!firstPoint) throw new Error(`target-point-missing:${target.point_ids[0]}`);
  const rows = target.point_ids.map((pointId) => {
    const point = points.find((candidate) => candidate.point_id === pointId);
    if (!point) throw new Error(`target-point-missing:${pointId}`);
    const binding = playbackBindings.get(pointId);
    const confirmed = point.start_confirmed === true && point.end_confirmed === true;
    const playable = confirmed && binding?.binding_status === 'BOUND';
    return {
      point_id: pointId,
      winner: point.winner,
      observed_rally_stage: point.observed_rally_stage ?? 'UNKNOWN',
      current_session_playback: playable ? 'LOCAL_SESSION_ONLY' : 'NOT_PLAYABLE',
      unavailable_reason: playable ? null : !confirmed ? 'BOUNDARIES_NOT_CONFIRMED' : point.start_seconds == null || point.end_seconds == null ? 'BOUNDARIES_MISSING' : 'NOT_BOUND_TO_CURRENT_SESSION',
    };
  });
  return {
    contract_version: 'ptti.review-comparison-notes/0.1',
    generated_at: new Date().toISOString(),
    system_facts: {
      analysis_identity: {
        contract_version: report.contract_version,
        input_contract_version: report.input_contract_version,
        statistics_contract_version: report.statistics_contract_version,
        canonical_input_sha256: report.canonical_input_sha256,
        dataset_id: report.dataset.dataset_id,
        match_id: report.dataset.match_id,
        source_id: report.dataset.source_id,
        game_number: firstPoint.game_number,
        evidence_status: report.evidence_status,
        source_link_status: report.dataset.source_link_status,
        rights_status: report.dataset.rights_status,
      },
      observer_role: target.subject_role,
      target: {
        target_id: target.target_id,
        observed_rally_stage: target.observed_rally_stage,
        lost_count: target.lost_count,
        denominator: target.denominator,
        unknown_count: target.unknown_count,
        evidence_status: target.evidence_status,
        point_ids: [...target.point_ids],
        sample_status: target.sample_status,
        sample_size_caution_threshold: report.display_caution_threshold,
        threshold_is_significance_test: report.threshold_is_significance_test,
      },
      current_video_session: {
        scope: 'STATE_AT_EXPORT_TIME_ONLY',
        identity_status: 'LOCAL_SESSION_ONLY',
        playback_authorization_persists_in_export: false,
        independently_verified_media_count: 0,
      },
      point_rows: rows,
      cautions: ['Small sample; descriptive only.', 'Media source is not independently verified.', 'This export contains review notes, not a MainDex statistical report.'],
    },
    user_observation: { authored_by: 'USER', source: 'USER_ENTERED_TEXT', text: note },
  };
}
