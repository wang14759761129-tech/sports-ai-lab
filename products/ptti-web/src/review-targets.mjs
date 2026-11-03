import { importQuickAnnotationDraft } from './local-video-review.mjs';
import { OBSERVED_LOSS_STAGES } from './local-loss-insights.mjs';

function requireValue(condition, issue) { if (!condition) throw new Error(issue); }
const object = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const integer = (v) => Number.isSafeInteger(v) && v >= 0;
function keys(value, names) {
  requireValue(object(value) && Object.keys(value).sort().join('|') === [...names].sort().join('|'), 'invalid-fields');
}
function compareKeys(a, b) {
  const aa = Array.from(a, (c) => c.codePointAt(0)), bb = Array.from(b, (c) => c.codePointAt(0));
  for (let n = 0; n < Math.min(aa.length, bb.length); n++) if (aa[n] !== bb[n]) return aa[n] - bb[n];
  return aa.length - bb.length;
}
// MainDex: json.dumps(ensure_ascii=False, sort_keys=True, separators=(',', ':')).
// Quick Annotation numeric fields must be safe integers. Other numbers fail closed.
export function canonicalQuickJson(value) {
  if (value === null || typeof value === 'boolean') return JSON.stringify(value);
  if (typeof value === 'number') { requireValue(Number.isSafeInteger(value), 'unsupported-canonical-number'); return JSON.stringify(value); }
  if (typeof value === 'string') {
    requireValue(!Array.from(value).some((c) => c.codePointAt(0) >= 0xd800 && c.codePointAt(0) <= 0xdfff), 'invalid-unicode');
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalQuickJson).join(',')}]`;
  requireValue(object(value), 'invalid-json-type');
  return `{${Object.keys(value).sort(compareKeys).map((key) => `${canonicalQuickJson(key)}:${canonicalQuickJson(value[key])}`).join(',')}}`;
}
export async function prepareQuickSource(text) {
  const payload = JSON.parse(text);
  const imported = importQuickAnnotationDraft(payload);
  requireValue(imported.ok, 'invalid-quick-input');
  const canonical = canonicalQuickJson(payload);
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonical));
  const hash = Array.from(new Uint8Array(digest), (v) => v.toString(16).padStart(2, '0')).join('');
  return { payload, hash, points: imported.value.points };
}

export function matchesQuickSource(source, points, gameContexts) {
  if (!source) return false;
  const rows = (values) => values.map((p) => ({ point_id: p.point_id, game_number: p.game_number, point_number: p.point_number, winner: p.winner, server: p.server, observed_tactics: p.observed_tactics, observed_rally_stage: p.observed_rally_stage ?? null, start_ms: p.start_seconds === null ? null : Math.round(p.start_seconds * 1000), end_ms: p.end_seconds === null ? null : Math.round(p.end_seconds * 1000) }));
  try { if (canonicalQuickJson(rows(source.points)) !== canonicalQuickJson(rows(points))) return false; } catch { return false; }
  return source.payload.rules_context.games.every((game) => {
    const current = gameContexts[game.game_number];
    const server = game.first_server === 'player' ? 'PLAYER_A' : game.first_server === 'opponent' ? 'PLAYER_B' : 'UNKNOWN';
    return current && current.coverage === game.coverage && current.first_server === server;
  });
}

export function validateReviewTargets(report, source) {
  requireValue(source && Array.isArray(source.points), 'quick-source-required');
  requireValue(report?.contract_version === 'ptti.review-targets/0.1', 'unsupported-version');
  keys(report, ['contract_version', 'input_contract_version', 'statistics_contract_version', 'canonical_input_sha256', 'dataset', 'evidence_status', 'display_caution_threshold', 'threshold_is_significance_test', 'sample', 'time_range_coverage', 'unknown_stage_count', 'unknown_server_count', 'athletes', 'review_targets', 'observations', 'limitations']);
  const input = source.payload;
  requireValue(report.input_contract_version === input.contract_version && report.statistics_contract_version === 'ptti.quick-annotation-stats/0.1', 'version-mismatch');
  requireValue(typeof report.canonical_input_sha256 === 'string' && /^[a-f0-9]{64}$/.test(report.canonical_input_sha256) && report.canonical_input_sha256 === source.hash, 'input-hash-mismatch');
  keys(report.dataset, ['dataset_id', 'dataset_class', 'match_id', 'match_link_status', 'source_id', 'source_link_status', 'rights_status', 'source_video_sha256', 'timeline_id', 'pts', 'time_base', 'vision_status']);
  const d = report.dataset;
  requireValue(d.dataset_id === input.dataset_id && d.dataset_class === input.dataset_class && d.match_id === input.match_id && d.source_id === input.video_context.source_id, 'identity-mismatch');
  requireValue(d.rights_status === 'UNKNOWN' && d.source_video_sha256 === null && d.timeline_id === null && d.pts === null && d.time_base === null && d.vision_status === 'NOT_TESTED' && d.source_link_status === (d.source_id === null ? 'UNBOUND' : 'USER_SELECTED_UNVERIFIED'), 'media-authority-rejected');
  requireValue(d.match_link_status === (d.dataset_class === 'SIMULATED_ONLY' ? 'NOT_APPLICABLE_SIMULATED' : 'USER_SELECTED_UNVERIFIED'), 'invalid-fields');
  const evidence = input.dataset_class === 'SIMULATED_ONLY' ? 'SIMULATED_ONLY' : 'REVIEW_REQUIRED';
  requireValue(report.evidence_status === evidence, 'evidence-mismatch');
  const threshold = report.display_caution_threshold;
  requireValue(integer(threshold) && threshold > 0 && report.threshold_is_significance_test === false, 'invalid-threshold');
  const points = source.points, ids = points.map((p) => p.point_id), n = points.length;
  const sameIds = (a, expected) => Array.isArray(a) && a.every((id) => typeof id === 'string') && new Set(a).size === a.length && a.length === expected.length && a.every((id, i) => id === expected[i]);
  const sameMembers = (a, expected) => Array.isArray(a) && new Set(a).size === a.length && a.length === expected.length && a.every((id) => expected.includes(id));
  const status = (denominator) => denominator === 0 ? 'NOT_ESTIMABLE' : denominator < threshold ? 'INSUFFICIENT_SAMPLE' : 'DESCRIPTIVE_ONLY';
  const sideWinner = (side) => side === 'player' ? 'PLAYER_A' : 'PLAYER_B';
  function count(metric, side, expectedGroup) {
    keys(metric, ['won_count', 'lost_count', 'denominator', 'sample_count', 'unknown_count', 'excluded_count', 'point_ids', 'computation_rule', 'evidence_status', 'sample_status']);
    keys(metric.point_ids, ['valid', 'won', 'lost', 'unknown', 'excluded']);
    requireValue(['won_count', 'lost_count', 'denominator', 'sample_count', 'unknown_count', 'excluded_count'].every((key) => integer(metric[key])), 'invalid-count');
    const pids = metric.point_ids;
    for (const key of Object.keys(pids)) requireValue(Array.isArray(pids[key]) && pids[key].every((id) => ids.includes(id)) && new Set(pids[key]).size === pids[key].length, 'invalid-point-reference');
    requireValue(sameMembers([...pids.valid, ...pids.unknown, ...pids.excluded], ids) && sameMembers([...pids.won, ...pids.lost], pids.valid), 'broken-partition');
    requireValue(metric.won_count === pids.won.length && metric.lost_count === pids.lost.length && metric.denominator === pids.valid.length && metric.sample_count === n && metric.unknown_count === pids.unknown.length && metric.excluded_count === pids.excluded.length, 'count-conflict');
    requireValue(pids.won.every((id) => points.find((p) => p.point_id === id).winner === sideWinner(side)) && pids.lost.every((id) => ['PLAYER_A', 'PLAYER_B'].includes(points.find((p) => p.point_id === id).winner) && points.find((p) => p.point_id === id).winner !== sideWinner(side)), 'winner-conflict');
    requireValue(metric.evidence_status === evidence && metric.sample_status === status(metric.denominator) && typeof metric.computation_rule === 'string', 'invalid-count-status');
    // Only validate elementary row membership. Do not reproduce professional statistics.
    if (expectedGroup) {
      const expected = { valid: [], won: [], lost: [], unknown: [], excluded: [] };
      for (const p of points) {
        const group = expectedGroup(p);
        const key = group === false ? 'excluded' : group === null || p.winner === 'UNKNOWN' ? 'unknown' : 'valid';
        expected[key].push(p.point_id);
        if (key === 'valid') expected[p.winner === sideWinner(side) ? 'won' : 'lost'].push(p.point_id);
      }
      for (const key of Object.keys(expected)) requireValue(sameIds(pids[key], expected[key]), 'group-conflict');
    }
  }
  keys(report.sample, ['point_count', 'protocol_sequence_valid', 'score_known_count', 'score_unknown_count', 'score_before_trace_known_count', 'game_count', 'game_counts']);
  const known = points.filter((p) => p.winner !== 'UNKNOWN').length;
  requireValue(report.sample.point_count === n && report.sample.score_known_count === known && report.sample.score_unknown_count === n - known && report.sample.protocol_sequence_valid === true && integer(report.sample.score_before_trace_known_count) && report.sample.score_before_trace_known_count <= n, 'sample-conflict');
  const games = [...new Set(points.map((p) => p.game_number))];
  requireValue(report.sample.game_count === games.length && object(report.sample.game_counts) && sameMembers(Object.keys(report.sample.game_counts), games.map(String)), 'sample-conflict');
  for (const game of games) {
    const rows = points.filter((p) => p.game_number === game), c = report.sample.game_counts[String(game)];
    keys(c, ['point_count', 'known_winner_count', 'player_wins', 'opponent_wins']);
    requireValue(c.point_count === rows.length && c.player_wins === rows.filter((p) => p.winner === 'PLAYER_A').length && c.opponent_wins === rows.filter((p) => p.winner === 'PLAYER_B').length && c.known_winner_count === c.player_wins + c.opponent_wins, 'sample-conflict');
  }
  requireValue(report.unknown_stage_count === points.filter((p) => !OBSERVED_LOSS_STAGES.includes(p.observed_rally_stage)).length && integer(report.unknown_server_count) && report.unknown_server_count <= n, 'unknown-conflict');
  const time = report.time_range_coverage;
  requireValue(object(time) && ['numerator', 'denominator', 'sample_count', 'missing_count', 'all_range_checked_point_rows'].every((key) => integer(time[key]) && time[key] <= n) && time.numerator <= time.denominator && time.threshold_is_significance_test === false && time.display_caution_threshold === threshold && time.evidence_status === 'RANGE_CHECKED_UNBOUND' && typeof time.computation_rule === 'string' && time.sample_status === status(time.denominator) && (time.value === null || typeof time.value === 'number' && Number.isFinite(time.value) && time.value >= 0 && time.value <= 1), 'invalid-time-summary');
  requireValue(Array.isArray(report.athletes) && report.athletes.length === 2 && sameMembers(report.athletes.map((a) => a?.role), ['player', 'opponent']), 'invalid-roles');
  const expectedTargets = [];
  for (const athlete of report.athletes) {
    keys(athlete, ['role', 'identity_status', 'score', 'service', 'observed_stages']);
    requireValue(athlete.identity_status === 'INPUT_ROLE_ONLY', 'identity-mismatch');
    count(athlete.score, athlete.role, () => true);
    count(athlete.service, athlete.role); // Membership structure only; serving formulas are not displayed by this consumer.
    keys(athlete.observed_stages, OBSERVED_LOSS_STAGES);
    for (const stage of OBSERVED_LOSS_STAGES) {
      const metric = athlete.observed_stages[stage];
      count(metric, athlete.role, (p) => !OBSERVED_LOSS_STAGES.includes(p.observed_rally_stage) ? null : p.observed_rally_stage === stage);
      if (metric.lost_count) expectedTargets.push({ athlete, stage, metric });
    }
  }
  requireValue(Array.isArray(report.review_targets) && report.review_targets.length === expectedTargets.length, 'target-conflict');
  const targetIds = new Set();
  for (const target of report.review_targets) {
    keys(target, ['target_id', 'subject_role', 'observed_rally_stage', 'lost_count', 'denominator', 'unknown_count', 'point_ids', 'evidence_status', 'sample_status', 'playback_eligibility']);
    const expected = expectedTargets.find((t) => t.athlete.role === target.subject_role && t.stage === target.observed_rally_stage);
    requireValue(expected && target.target_id === `${d.dataset_id}/${target.subject_role}/${target.observed_rally_stage}` && !targetIds.has(target.target_id), 'target-conflict');
    targetIds.add(target.target_id);
    const metric = expected.metric;
    requireValue(target.lost_count === metric.lost_count && target.denominator === metric.denominator && target.unknown_count === metric.unknown_count && sameIds(target.point_ids, metric.point_ids.lost), 'target-conflict');
    requireValue(target.evidence_status === evidence && target.sample_status === metric.sample_status && target.playback_eligibility === 'NOT_EVALUATED_CURRENT_SESSION', 'media-authority-rejected');
  }
  requireValue(Array.isArray(report.observations) && report.observations.length <= 2 && Array.isArray(report.limitations) && report.limitations.every((v) => typeof v === 'string'), 'invalid-fields');
  for (const observation of report.observations) {
    keys(observation, ['target_id', 'point_ids', 'text_zh']);
    const target = report.review_targets.find((t) => t.target_id === observation.target_id);
    requireValue(target && sameIds(observation.point_ids, target.point_ids) && typeof observation.text_zh === 'string', 'invalid-point-reference');
  }
  return report;
}
