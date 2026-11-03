export const TRAINING_REVIEW_VERSION = 'ptti.training-review/0.1';
export const TRAINING_REVIEW_PROTOCOL_REVISION = '1b30e8ea0f8a90a745fb6c30105599f0334fdf7c';

const hashPattern = /^[0-9a-f]{64}$/;
const metricKeys = [
  'server_point_win_rate', 'receiver_point_win_rate', 'third_ball_attack_rate',
  'third_ball_point_conversion', 'third_ball_immediate_success',
  'key_point_player_win_rate', 'rally_length_mean',
];
const distributionKeys = ['serve_side', 'serve_length', 'serve_location', 'serve_spin', 'receive_type', 'receive_location'];
const pointFields = [
  'match_id', 'game_number', 'point_number', 'server', 'receiver', 'server_score_before', 'receiver_score_before',
  'serve_side', 'serve_length', 'serve_location', 'serve_spin', 'receive_type', 'receive_location',
  'third_ball_attack', 'third_ball_side', 'third_ball_outcome', 'rally_length', 'point_winner', 'point_outcome',
  'video_timestamp', 'notes',
];

function fail(reason) { throw new Error(reason); }
function object(value, name) { if (!value || typeof value !== 'object' || Array.isArray(value)) fail(`${name}: expected object`); return value; }
function array(value, name) { if (!Array.isArray(value)) fail(`${name}: expected array`); return value; }
function text(value, name, { allowEmpty = false } = {}) {
  if (typeof value !== 'string' || (!allowEmpty && value.trim() === '')) fail(`${name}: expected string`);
  return value;
}
function integer(value, name, { min = 0 } = {}) { if (!Number.isSafeInteger(value) || value < min) fail(`${name}: expected integer >= ${min}`); return value; }
function oneOf(value, allowed, name) { if (!allowed.includes(value)) fail(`${name}: unsupported value`); return value; }
function nullableText(value, name) { if (value !== null) text(value, name); }
function sameKeys(value, expected, name) {
  const actual = Object.keys(object(value, name)).sort();
  const wanted = [...expected].sort();
  if (JSON.stringify(actual) !== JSON.stringify(wanted)) fail(`${name}: fields do not match the ${TRAINING_REVIEW_VERSION} contract`);
}
function naturalPointId(matchId, game, point) {
  const encoded = encodeURIComponent(matchId).replace(/[!'()*]/g, (char) => `%${char.charCodeAt(0).toString(16).toUpperCase()}`);
  return `${encoded}/g${String(game).padStart(2, '0')}/p${String(point).padStart(3, '0')}`;
}

function validateProtocolPoint(point, name, datasetMatchId) {
  object(point, name);
  sameKeys(point, pointFields, `${name}.fields`);
  if (text(point.match_id, `${name}.match_id`) !== datasetMatchId) fail(`${name}: match_id does not match dataset`);
  integer(point.game_number, `${name}.game_number`, { min: 1 });
  integer(point.point_number, `${name}.point_number`, { min: 1 });
  oneOf(point.server, ['player', 'opponent', 'unknown'], `${name}.server`);
  oneOf(point.receiver, ['player', 'opponent', 'unknown'], `${name}.receiver`);
  if (point.server !== 'unknown' && point.receiver !== 'unknown' && point.server === point.receiver) fail(`${name}: server and receiver must be opposite sides`);
  for (const key of ['server_score_before', 'receiver_score_before']) {
    const value = point[key];
    if (!(Number.isSafeInteger(value) && value >= 0) && !['unknown', 'unclear'].includes(value)) fail(`${name}.${key}: invalid score`);
  }
  const uncertainty = ['unknown', 'unclear', 'not_applicable'];
  oneOf(point.serve_side, ['forehand', 'backhand', ...uncertainty], `${name}.serve_side`);
  oneOf(point.serve_length, ['short', 'half_long', 'long', ...uncertainty], `${name}.serve_length`);
  oneOf(point.serve_location, ['forehand', 'middle', 'backhand', ...uncertainty], `${name}.serve_location`);
  oneOf(point.serve_spin, ['backspin', 'sidespin', 'topspin', 'no_spin', 'mixed', ...uncertainty], `${name}.serve_spin`);
  oneOf(point.receive_type, ['push', 'flick', 'chiquita', 'drive', 'loop', 'long_push', 'short_touch', 'other', ...uncertainty], `${name}.receive_type`);
  oneOf(point.receive_location, ['forehand', 'middle', 'backhand', ...uncertainty], `${name}.receive_location`);
  oneOf(point.third_ball_attack, ['yes', 'no', ...uncertainty], `${name}.third_ball_attack`);
  oneOf(point.third_ball_side, ['forehand', 'backhand', 'other', ...uncertainty], `${name}.third_ball_side`);
  oneOf(point.third_ball_outcome, ['successful', 'unsuccessful', ...uncertainty], `${name}.third_ball_outcome`);
  const rally = point.rally_length;
  if (!(Number.isSafeInteger(rally) && rally > 0) && !['unknown', 'unclear', 'not_applicable'].includes(rally)) fail(`${name}.rally_length: invalid value`);
  oneOf(point.point_winner, ['player', 'opponent', 'unknown'], `${name}.point_winner`);
  oneOf(point.point_outcome, ['win', 'loss', 'unknown'], `${name}.point_outcome`);
  if (point.point_winner !== 'unknown' && point.point_outcome !== 'unknown'
    && point.point_outcome !== (point.point_winner === 'player' ? 'win' : 'loss')) fail(`${name}: point_outcome conflicts with point_winner`);
  text(point.video_timestamp, `${name}.video_timestamp`, { allowEmpty: true });
  text(point.notes, `${name}.notes`);
}

function validateMetric(metric, key, evidenceStatus, pointCount, distribution = false) {
  const name = `${distribution ? 'distributions' : 'metrics'}.${key}`;
  object(metric, name);
  if (metric.key !== key) fail(`${name}.key: does not match its map key`);
  integer(metric.denominator, `${name}.denominator`);
  integer(metric.sample_count, `${name}.sample_count`);
  integer(metric.missing_count, `${name}.missing_count`);
  if (metric.denominator + metric.missing_count !== metric.sample_count) fail(`${name}: denominator plus missing_count must equal sample_count`);
  if (metric.sample_count > pointCount) fail(`${name}: sample_count exceeds point_count`);
  if (typeof metric.value !== 'number' && metric.value !== null) fail(`${name}.value: expected number or null`);
  if (typeof metric.value === 'number' && !Number.isFinite(metric.value)) fail(`${name}.value: expected finite number`);
  text(metric.computation_rule, `${name}.computation_rule`);
  if (metric.evidence_status !== evidenceStatus) fail(`${name}.evidence_status: conflicts with dataset evidence status`);
  oneOf(metric.sample_status, ['NOT_ESTIMABLE', 'INSUFFICIENT_SAMPLE', 'DESCRIPTIVE_ONLY'], `${name}.sample_status`);
  const expectedStatus = metric.denominator === 0 ? 'NOT_ESTIMABLE' : metric.denominator < 5 ? 'INSUFFICIENT_SAMPLE' : 'DESCRIPTIVE_ONLY';
  if (metric.sample_status !== expectedStatus) fail(`${name}.sample_status: conflicts with its denominator`);
  if (distribution) {
    const numerator = object(metric.numerator, `${name}.numerator`);
    let total = 0;
    for (const [category, count] of Object.entries(numerator)) { text(category, `${name}.numerator category`); total += integer(count, `${name}.numerator.${category}`); }
    if (total !== metric.denominator || metric.value !== null) fail(`${name}: category counts or value conflict with denominator`);
  } else {
    const numerator = integer(metric.numerator, `${name}.numerator`);
    if (key === 'rally_length_mean') {
      if (numerator < metric.denominator) fail(`${name}: contact sum is below its positive sample count`);
    } else if (numerator > metric.denominator) fail(`${name}: numerator exceeds denominator`);
    const expectedValue = metric.denominator === 0 ? null : numerator / metric.denominator;
    if ((expectedValue === null) !== (metric.value === null)
      || (expectedValue !== null && Math.abs(expectedValue - metric.value) > 0.0000011)) fail(`${name}: value does not agree with numerator / denominator`);
  }
  for (const keyName of ['unknown_count', 'unclear_count', 'not_applicable_count', 'key_point_candidates', 'unresolved_score_or_identity']) {
    if (metric[keyName] !== undefined) integer(metric[keyName], `${name}.${keyName}`);
  }
}

function assertMetricCounts(metric, key, numerator, denominator, sampleCount, missingCount) {
  if (metric.numerator !== numerator || metric.denominator !== denominator
    || metric.sample_count !== sampleCount || metric.missing_count !== missingCount) fail(`metrics.${key}: counts do not match the embedded point records`);
}

function computedPlayerScores(point) {
  if (!['player', 'opponent'].includes(point.server) || !['player', 'opponent'].includes(point.receiver)
    || !Number.isSafeInteger(point.server_score_before) || !Number.isSafeInteger(point.receiver_score_before)) return null;
  return point.server === 'player'
    ? { player: point.server_score_before, opponent: point.receiver_score_before }
    : { player: point.receiver_score_before, opponent: point.server_score_before };
}
function scoreEquals(actual, expected) {
  if (actual === null || expected === null) return actual === expected;
  return actual?.player === expected.player && actual?.opponent === expected.opponent;
}

export function validateTrainingReview(value) {
  object(value, 'report');
  if (value.report_version !== TRAINING_REVIEW_VERSION) fail(`Unsupported training review version: ${String(value.report_version ?? 'missing')}`);
  text(value.generated_at, 'generated_at');
  if (!/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(value.generated_at) || Number.isNaN(Date.parse(value.generated_at))) fail('generated_at: expected timezone-qualified ISO timestamp');

  const dataset = object(value.dataset, 'dataset');
  text(dataset.dataset_id, 'dataset.dataset_id');
  const datasetClass = oneOf(dataset.dataset_class, ['SIMULATED_ONLY', 'HUMAN_ANNOTATION'], 'dataset.dataset_class');
  const matchId = text(dataset.match_id, 'dataset.match_id');
  nullableText(dataset.source_id, 'dataset.source_id');
  nullableText(dataset.local_asset_id, 'dataset.local_asset_id');
  for (const name of ['annotation_csv_sha256', 'annotation_bundle_sha256']) if (!hashPattern.test(text(dataset[name], `dataset.${name}`))) fail(`dataset.${name}: expected lowercase SHA-256`);
  if (dataset.source_video_sha256 !== null && !hashPattern.test(text(dataset.source_video_sha256, 'dataset.source_video_sha256'))) fail('dataset.source_video_sha256: invalid SHA-256');
  const protocol = object(dataset.protocol, 'dataset.protocol');
  if (protocol.id !== 'serve-third-ball-analytics' || protocol.version !== '0.3' || protocol.schema_revision !== TRAINING_REVIEW_PROTOCOL_REVISION) fail('dataset.protocol: unsupported protocol revision');
  const annotationProvenance = object(dataset.annotation_provenance, 'dataset.annotation_provenance');
  const expectedEvidence = datasetClass === 'SIMULATED_ONLY' ? 'SIMULATED_ONLY' : 'DECLARED_NOT_INDEPENDENTLY_AUDITED';
  if (dataset.evidence_status !== expectedEvidence) fail('dataset.evidence_status: cannot promote the declared dataset class');
  oneOf(dataset.match_link_status, ['NOT_APPLICABLE_SIMULATED', 'HUMAN_REVIEWED_DECLARATION_NOT_AUDITED'], 'dataset.match_link_status');
  oneOf(dataset.local_analysis_permission, ['NOT_APPLICABLE_SIMULATED', 'DECLARED_ALLOWED_NOT_AUDITED'], 'dataset.local_analysis_permission');
  nullableText(dataset.rights_basis_ref, 'dataset.rights_basis_ref');
  const timeline = object(dataset.video_timeline, 'dataset.video_timeline');
  if (timeline.status !== 'UNBOUND' || timeline.timeline_id !== null || timeline.pts !== null || timeline.time_base !== null) fail('dataset.video_timeline: only the unbound contract state is accepted');
  if (dataset.vision_status !== 'NOT_TESTED' || dataset.event !== null || dataset.player_identity !== null) fail('dataset: unsupported Vision, event, or athlete binding');
  if (datasetClass === 'SIMULATED_ONLY' && (!matchId.startsWith('SIMULATED_ONLY:') || dataset.source_id !== null || dataset.local_asset_id !== null
    || dataset.match_link_status !== 'NOT_APPLICABLE_SIMULATED' || dataset.local_analysis_permission !== 'NOT_APPLICABLE_SIMULATED')) fail('dataset: simulated identity cannot bind to a real source or permission declaration');
  if (datasetClass === 'HUMAN_ANNOTATION' && (matchId.startsWith('SIMULATED_ONLY:') || !dataset.source_id || !dataset.local_asset_id
    || dataset.match_link_status !== 'HUMAN_REVIEWED_DECLARATION_NOT_AUDITED' || dataset.local_analysis_permission !== 'DECLARED_ALLOWED_NOT_AUDITED'
    || !dataset.rights_basis_ref || annotationProvenance.method !== 'HUMAN_MANUAL'
    || annotationProvenance.review_status !== 'DECLARED_NOT_INDEPENDENTLY_AUDITED'
    || !hashPattern.test(String(annotationProvenance.annotation_csv_sha256 ?? ''))
    || annotationProvenance.annotation_csv_sha256 !== dataset.annotation_csv_sha256)) fail('dataset: human annotation identity or review declaration is incomplete or inconsistent');
  if (datasetClass === 'SIMULATED_ONLY' && !['DETERMINISTIC_ORIGINAL_GENERATOR', 'SIMULATED_INTERACTIVE_EDIT'].includes(annotationProvenance.method)) fail('dataset: simulated annotation provenance method is unsupported');

  const sample = object(value.sample, 'sample');
  const pointCount = integer(sample.point_count, 'sample.point_count');
  integer(sample.game_count, 'sample.game_count');
  integer(sample.known_score_count, 'sample.known_score_count');
  integer(sample.known_winner_count, 'sample.known_winner_count');
  const metrics = object(value.metrics, 'metrics');
  sameKeys(metrics, metricKeys, 'metrics');
  for (const key of metricKeys) validateMetric(metrics[key], key, expectedEvidence, pointCount);
  const distributions = object(value.distributions, 'distributions');
  sameKeys(distributions, distributionKeys, 'distributions');
  for (const key of distributionKeys) validateMetric(distributions[key], key, expectedEvidence, pointCount, true);

  const pointRefs = array(value.point_refs, 'point_refs');
  const pointRecords = array(value.point_records, 'point_records');
  if (pointRefs.length !== pointCount || pointRecords.length !== pointCount) fail('point_refs and point_records must each match sample.point_count');
  const ids = new Set();
  const rowsById = new Map();
  for (let index = 0; index < pointRecords.length; index += 1) {
    const ref = object(pointRefs[index], `point_refs[${index}]`);
    const record = object(pointRecords[index], `point_records[${index}]`);
    const fields = object(record.fields, `point_records[${index}].fields`);
    validateProtocolPoint(fields, `point_records[${index}]`, matchId);
    const expectedId = naturalPointId(matchId, fields.game_number, fields.point_number);
    if (ref.point_id !== expectedId || record.point_id !== expectedId) fail(`point_refs[${index}]: broken point_id reference`);
    if (ids.has(expectedId)) fail(`point_records[${index}]: duplicate point_id`);
    ids.add(expectedId);
    const recordNumber = integer(record.csv_record_number, `point_records[${index}].csv_record_number`, { min: 2 });
    if (ref.csv_record_number !== recordNumber || recordNumber !== index + 2) fail(`point_refs[${index}]: CSV record ordinal mismatch`);
    const rowHash = text(record.annotation_row_sha256, `point_records[${index}].annotation_row_sha256`);
    if (!hashPattern.test(rowHash) || ref.annotation_row_sha256 !== rowHash) fail(`point_refs[${index}]: annotation row hash reference mismatch`);
    if (ref.game_number !== fields.game_number || ref.point_number !== fields.point_number) fail(`point_refs[${index}]: game/point identity mismatch`);
    text(ref.video_timestamp_text, `point_refs[${index}].video_timestamp_text`, { allowEmpty: true });
    if (ref.video_timestamp_text !== fields.video_timestamp || ref.timestamp_binding !== 'UNBOUND_PROTOCOL_TEXT') fail(`point_refs[${index}]: timestamp is not contract-bound`);
    rowsById.set(expectedId, record);
  }
  if (ids.size !== pointCount) fail('point_id set is incomplete');
  const points = pointRecords.map((record) => record.fields);
  if (datasetClass === 'SIMULATED_ONLY' && annotationProvenance.method === 'DETERMINISTIC_ORIGINAL_GENERATOR') {
    integer(annotationProvenance.seed, 'dataset.annotation_provenance.seed', { min: 0 });
    text(annotationProvenance.generated_on, 'dataset.annotation_provenance.generated_on');
  }
  if (datasetClass === 'SIMULATED_ONLY' && annotationProvenance.method === 'SIMULATED_INTERACTIVE_EDIT') {
    text(annotationProvenance.parent_dataset_id, 'dataset.annotation_provenance.parent_dataset_id');
    if (!annotationProvenance.parent_dataset_id.startsWith('SIMULATED_ONLY:') || annotationProvenance.parent_dataset_id === dataset.dataset_id
      || !hashPattern.test(text(annotationProvenance.parent_input_sha256, 'dataset.annotation_provenance.parent_input_sha256'))) fail('dataset.annotation_provenance: simulated parent reference is invalid');
    const edit = object(annotationProvenance.edit, 'dataset.annotation_provenance.edit');
    sameKeys(edit, ['point_id', 'field', 'before', 'after'], 'dataset.annotation_provenance.edit');
    const allowedEditFields = ['serve_side', 'serve_length', 'serve_location', 'serve_spin', 'receive_type', 'receive_location', 'third_ball_attack', 'third_ball_side', 'third_ball_outcome', 'rally_length', 'video_timestamp', 'notes'];
    oneOf(edit.field, allowedEditFields, 'dataset.annotation_provenance.edit.field');
    text(edit.point_id, 'dataset.annotation_provenance.edit.point_id');
    if (!rowsById.has(edit.point_id)) fail('dataset.annotation_provenance.edit.point_id: references missing point_id');
    if ((typeof edit.before !== 'string' && typeof edit.before !== 'number') || (typeof edit.after !== 'string' && typeof edit.after !== 'number')) fail('dataset.annotation_provenance.edit: before/after must be string or number');
    const editedRecord = rowsById.get(edit.point_id);
    if (!editedRecord || editedRecord.fields[edit.field] !== edit.after || edit.before === edit.after) fail('dataset.annotation_provenance.edit: recorded edit does not match the current point');
  }
  const serverKnown = points.filter((point) => ['player', 'opponent'].includes(point.server) && ['player', 'opponent'].includes(point.point_winner));
  const receiverKnown = points.filter((point) => ['player', 'opponent'].includes(point.receiver) && ['player', 'opponent'].includes(point.point_winner));
  const attackClassified = points.filter((point) => ['yes', 'no'].includes(point.third_ball_attack));
  const attacks = points.filter((point) => point.third_ball_attack === 'yes');
  const attackKnownWinner = attacks.filter((point) => ['player', 'opponent'].includes(point.server) && ['player', 'opponent'].includes(point.point_winner));
  const attackKnownOutcome = attacks.filter((point) => ['successful', 'unsuccessful'].includes(point.third_ball_outcome));
  const keyPointRows = points.filter((point) => {
    const score = computedPlayerScores(point);
    return score && Math.min(score.player, score.opponent) >= 7 && Math.abs(score.player - score.opponent) <= 1;
  });
  const keyPointKnownWinner = keyPointRows.filter((point) => ['player', 'opponent'].includes(point.point_winner));
  const rallyValues = points.map((point) => point.rally_length).filter((value) => Number.isSafeInteger(value) && value > 0);
  assertMetricCounts(metrics.server_point_win_rate, 'server_point_win_rate', serverKnown.filter((point) => point.server === point.point_winner).length, serverKnown.length, pointCount, pointCount - serverKnown.length);
  assertMetricCounts(metrics.receiver_point_win_rate, 'receiver_point_win_rate', receiverKnown.filter((point) => point.receiver === point.point_winner).length, receiverKnown.length, pointCount, pointCount - receiverKnown.length);
  assertMetricCounts(metrics.third_ball_attack_rate, 'third_ball_attack_rate', attacks.length, attackClassified.length, attackClassified.length + points.filter((point) => point.third_ball_attack !== 'not_applicable' && !['yes', 'no'].includes(point.third_ball_attack)).length, attackClassified.length + points.filter((point) => point.third_ball_attack !== 'not_applicable' && !['yes', 'no'].includes(point.third_ball_attack)).length - attackClassified.length);
  assertMetricCounts(metrics.third_ball_point_conversion, 'third_ball_point_conversion', attackKnownWinner.filter((point) => point.server === point.point_winner).length, attackKnownWinner.length, attacks.length, attacks.length - attackKnownWinner.length);
  assertMetricCounts(metrics.third_ball_immediate_success, 'third_ball_immediate_success', attackKnownOutcome.filter((point) => point.third_ball_outcome === 'successful').length, attackKnownOutcome.length, attacks.length, attacks.length - attackKnownOutcome.length);
  assertMetricCounts(metrics.key_point_player_win_rate, 'key_point_player_win_rate', keyPointKnownWinner.filter((point) => point.point_winner === 'player').length, keyPointKnownWinner.length, keyPointRows.length, keyPointRows.length - keyPointKnownWinner.length);
  assertMetricCounts(metrics.rally_length_mean, 'rally_length_mean', rallyValues.reduce((total, value) => total + value, 0), rallyValues.length, pointCount, pointCount - rallyValues.length);
  if ((metrics.third_ball_attack_rate.not_applicable_count ?? 0) !== points.filter((point) => point.third_ball_attack === 'not_applicable').length) fail('metrics.third_ball_attack_rate.not_applicable_count: does not match point records');
  if ((metrics.key_point_player_win_rate.key_point_candidates ?? keyPointRows.length) !== keyPointRows.length
    || (metrics.key_point_player_win_rate.unresolved_score_or_identity ?? pointCount - keyPointRows.length) !== pointCount - keyPointRows.length) fail('metrics.key_point_player_win_rate: key-point counts do not match point records');
  for (const key of distributionKeys) {
    const values = points.map((point) => point[key]);
    const counts = {};
    for (const value of values.filter((item) => !['unknown', 'unclear', 'not_applicable'].includes(item))) counts[value] = (counts[value] ?? 0) + 1;
    const denominator = Object.values(counts).reduce((total, count) => total + count, 0);
    const missing = values.filter((item) => ['unknown', 'unclear'].includes(item)).length;
    const notApplicable = values.filter((item) => item === 'not_applicable').length;
    const metric = distributions[key];
    if (JSON.stringify(Object.fromEntries(Object.entries(metric.numerator).sort())) !== JSON.stringify(Object.fromEntries(Object.entries(counts).sort()))
      || metric.denominator !== denominator || metric.sample_count !== pointCount - notApplicable || metric.missing_count !== missing
      || (metric.unknown_count ?? 0) !== values.filter((item) => item === 'unknown').length
      || (metric.unclear_count ?? 0) !== values.filter((item) => item === 'unclear').length
      || (metric.not_applicable_count ?? 0) !== notApplicable) fail(`distributions.${key}: categories and denominators do not match point records`);
  }
  if (sample.game_count !== new Set(points.map((point) => point.game_number)).size
    || sample.known_score_count !== points.filter((point) => computedPlayerScores(point) !== null).length
    || sample.known_winner_count !== points.filter((point) => ['player', 'opponent'].includes(point.point_winner)).length) fail('sample: summary counts do not match point records');
  const requireReference = (id, name) => { text(id, name); if (!rowsById.has(id)) fail(`${name}: references missing point_id`); };

  const scoreTrace = array(value.score_trace, 'score_trace');
  if (scoreTrace.length !== pointCount) fail('score_trace must match sample.point_count');
  for (const [index, traceValue] of scoreTrace.entries()) {
    const trace = object(traceValue, `score_trace[${index}]`);
    requireReference(trace.point_id, `score_trace[${index}].point_id`);
    integer(trace.game_number, `score_trace[${index}].game_number`, { min: 1 });
    oneOf(trace.winner, ['player', 'opponent', 'unknown'], `score_trace[${index}].winner`);
    for (const key of ['score_before', 'score_after']) {
      const score = trace[key];
      if (score !== null) { object(score, `score_trace[${index}].${key}`); integer(score.player, `score_trace[${index}].${key}.player`); integer(score.opponent, `score_trace[${index}].${key}.opponent`); }
    }
    const point = points[index];
    const expectedBefore = computedPlayerScores(point);
    const expectedAfter = expectedBefore && ['player', 'opponent'].includes(point.point_winner)
      ? { player: expectedBefore.player + Number(point.point_winner === 'player'), opponent: expectedBefore.opponent + Number(point.point_winner === 'opponent') }
      : null;
    if (trace.point_id !== pointRefs[index].point_id || trace.game_number !== point.game_number || trace.winner !== point.point_winner
      || !scoreEquals(trace.score_before, expectedBefore) || !scoreEquals(trace.score_after, expectedAfter)) fail(`score_trace[${index}]: values do not match its point record`);
  }
  const keyPointList = array(value.key_points, 'key_points');
  if (keyPointList.length !== keyPointRows.length) fail('key_points: candidate list does not match observed scores');
  const seenKeyPointIds = new Set();
  for (const [index, itemValue] of keyPointList.entries()) {
    const item = object(itemValue, `key_points[${index}]`);
    requireReference(item.point_id, `key_points[${index}].point_id`);
    object(item.score_before, `key_points[${index}].score_before`);
    integer(item.score_before.player, `key_points[${index}].score_before.player`);
    integer(item.score_before.opponent, `key_points[${index}].score_before.opponent`);
    oneOf(item.winner, ['player', 'opponent', 'unknown'], `key_points[${index}].winner`);
    if (item.evidence_status !== expectedEvidence) fail(`key_points[${index}].evidence_status: conflicts with dataset`);
    const sourceIndex = pointRefs.findIndex((ref) => ref.point_id === item.point_id);
    const source = points[sourceIndex];
    const expectedScore = computedPlayerScores(source);
    if (!expectedScore || !keyPointRows.includes(source) || seenKeyPointIds.has(item.point_id)
      || item.score_before.player !== expectedScore.player || item.score_before.opponent !== expectedScore.opponent || item.winner !== source.point_winner) fail(`key_points[${index}]: values do not match its point record`);
    seenKeyPointIds.add(item.point_id);
  }
  for (const [index, itemValue] of array(value.watchlist, 'watchlist').entries()) {
    const item = object(itemValue, `watchlist[${index}]`);
    requireReference(item.point_id, `watchlist[${index}].point_id`);
    text(item.reason, `watchlist[${index}].reason`);
  }
  for (const [index, turnValue] of array(value.serve_turns, 'serve_turns').entries()) {
    const turn = object(turnValue, `serve_turns[${index}]`);
    integer(turn.game_number, `serve_turns[${index}].game_number`, { min: 1 });
    oneOf(turn.server, ['player', 'opponent'], `serve_turns[${index}].server`);
    for (const id of array(turn.point_ids, `serve_turns[${index}].point_ids`)) requireReference(id, `serve_turns[${index}].point_ids`);
    integer(turn.winner_known_count, `serve_turns[${index}].winner_known_count`);
    integer(turn.server_wins, `serve_turns[${index}].server_wins`);
    validateMetric(turn.metric, 'serve_turn_win_rate', expectedEvidence, pointCount);
  }
  for (const [index, summaryValue] of array(value.game_summaries, 'game_summaries').entries()) {
    const summary = object(summaryValue, `game_summaries[${index}]`);
    integer(summary.game_number, `game_summaries[${index}].game_number`, { min: 1 });
    integer(summary.point_count, `game_summaries[${index}].point_count`);
    integer(summary.player_wins_recorded, `game_summaries[${index}].player_wins_recorded`);
    integer(summary.opponent_wins_recorded, `game_summaries[${index}].opponent_wins_recorded`);
    oneOf(summary.score_status, ['DERIVED_FROM_KNOWN_ANNOTATIONS', 'UNKNOWN'], `game_summaries[${index}].score_status`);
    if (summary.last_observed_score_after !== null) {
      integer(summary.last_observed_score_after.player, `game_summaries[${index}].last_observed_score_after.player`);
      integer(summary.last_observed_score_after.opponent, `game_summaries[${index}].last_observed_score_after.opponent`);
    }
  }
  for (const [index, ref] of pointRefs.entries()) {
    const record = pointRecords[index];
    rowsById.set(record.point_id, record);
  }
  array(value.limitations, 'limitations').forEach((item, index) => text(item, `limitations[${index}]`));
  text(value.summary_cn, 'summary_cn');
  return value;
}

export function parseTrainingReviewJson(source) {
  if (typeof source !== 'string') fail('File content must be text');
  let parsed;
  try { parsed = JSON.parse(source); } catch { fail('Invalid JSON. Select a valid training review report.'); }
  return validateTrainingReview(parsed);
}

export function metricPointIds(report, key) {
  const rows = report.point_records;
  if (key === 'key_point_player_win_rate') return report.key_points.filter((item) => ['player', 'opponent'].includes(item.winner)).map((item) => item.point_id);
  if (Object.hasOwn(report.distributions, key)) {
    return rows.filter((row) => !['unknown', 'unclear', 'not_applicable'].includes(row.fields[key])).map((row) => row.point_id);
  }
  const predicates = {
    server_point_win_rate: (p) => ['player', 'opponent'].includes(p.server) && ['player', 'opponent'].includes(p.point_winner),
    receiver_point_win_rate: (p) => ['player', 'opponent'].includes(p.receiver) && ['player', 'opponent'].includes(p.point_winner),
    third_ball_attack_rate: (p) => ['yes', 'no'].includes(p.third_ball_attack),
    third_ball_point_conversion: (p) => p.third_ball_attack === 'yes' && ['player', 'opponent'].includes(p.server) && ['player', 'opponent'].includes(p.point_winner),
    third_ball_immediate_success: (p) => p.third_ball_attack === 'yes' && ['successful', 'unsuccessful'].includes(p.third_ball_outcome),
    rally_length_mean: (p) => Number.isSafeInteger(p.rally_length) && p.rally_length > 0,
  };
  return rows.filter((row) => predicates[key]?.(row.fields)).map((row) => row.point_id);
}

export function independentSourceVerification(report) {
  return {
    sourceAvailable: false,
    evidenceAvailable: false,
    recordedCsvHashAvailable: hashPattern.test(report.dataset.annotation_csv_sha256),
    status: 'CANNOT_INDEPENDENTLY_VERIFY',
  };
}
