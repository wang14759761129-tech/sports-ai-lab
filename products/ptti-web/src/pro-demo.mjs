export const MATCH_INTELLIGENCE_CONTRACT = 'ptti.match-intelligence/0.1';
export const DEMO_MATCH_ID = 'SIMULATED_ONLY:goal07-match-001';
export const DEMO_DATASET_ID = 'SIMULATED_ONLY:goal07-dataset-v1';
export const DEMO_STORAGE_KEY = 'ptti-web-match-intelligence-demo-v0.1';
export const DEMO_BUNDLE_URL = '/data/pro-demo-match-intelligence.json';
export const DEMO_EXPORT_FORMAT = 'ptti.web-match-intelligence-export/0.1';
export const PROTOCOL_V03 = Object.freeze({
  id: 'serve-third-ball-analytics',
  version: '0.3',
  schema_revision: '1b30e8ea0f8a90a745fb6c30105599f0334fdf7c',
});

// Exact Protocol v0.3 point row used by MainDex match-intelligence/0.1.
export const POINT_FIELDS = Object.freeze([
  'match_id', 'game_number', 'point_number', 'server', 'receiver',
  'server_score_before', 'receiver_score_before', 'serve_side', 'serve_length',
  'serve_location', 'serve_spin', 'receive_type', 'receive_location',
  'third_ball_attack', 'third_ball_side', 'third_ball_outcome', 'rally_length',
  'point_winner', 'point_outcome', 'video_timestamp', 'notes',
]);

const fieldCodes = Object.freeze({
  server: ['player', 'opponent', 'unknown'],
  receiver: ['player', 'opponent', 'unknown'],
  serve_side: ['forehand', 'backhand', 'unknown', 'unclear', 'not_applicable'],
  serve_length: ['short', 'half_long', 'long', 'unknown', 'unclear', 'not_applicable'],
  serve_location: ['forehand', 'middle', 'backhand', 'unknown', 'unclear', 'not_applicable'],
  serve_spin: ['backspin', 'sidespin', 'topspin', 'no_spin', 'mixed', 'unknown', 'unclear', 'not_applicable'],
  receive_type: ['push', 'flick', 'chiquita', 'drive', 'loop', 'long_push', 'short_touch', 'other', 'unknown', 'unclear', 'not_applicable'],
  receive_location: ['forehand', 'middle', 'backhand', 'unknown', 'unclear', 'not_applicable'],
  third_ball_attack: ['yes', 'no', 'unknown', 'unclear', 'not_applicable'],
  third_ball_side: ['forehand', 'backhand', 'other', 'unknown', 'unclear', 'not_applicable'],
  third_ball_outcome: ['successful', 'unsuccessful', 'unknown', 'unclear', 'not_applicable'],
  point_winner: ['player', 'opponent', 'unknown'],
  point_outcome: ['win', 'loss', 'unknown'],
});
const editableFields = Object.freeze([
  'serve_side', 'serve_length', 'serve_location', 'serve_spin', 'receive_type', 'receive_location',
  'third_ball_attack', 'third_ball_side', 'third_ball_outcome', 'rally_length', 'video_timestamp', 'notes',
]);

const keysMatch = (value, keys) => value && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key));
const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

function pointReference(matchId, point) {
  const escapedId = encodeURIComponent(matchId).replaceAll(':', '%3A');
  return `${escapedId}/g${String(point.game_number).padStart(2, '0')}/p${String(point.point_number).padStart(3, '0')}`;
}

function validEditValue(field, value) {
  if (fieldCodes[field]) return fieldCodes[field].includes(value);
  if (field === 'rally_length') return (Number.isInteger(value) && value >= 1) || ['unknown', 'unclear', 'not_applicable'].includes(value);
  if (field === 'video_timestamp' || field === 'notes') return typeof value === 'string';
  return false;
}

function stableValue(value) {
  if (Array.isArray(value)) return value.map(stableValue);
  if (object(value)) return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stableValue(value[key])]));
  return value;
}

function stableStringify(value) { return JSON.stringify(stableValue(value)); }

async function sha256(value) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

export function validatePoint(point, expectedMatchId = DEMO_MATCH_ID) {
  if (!keysMatch(point, POINT_FIELDS)) return { ok: false, reason: 'Each point must contain exactly the 21 Protocol v0.3 fields' };
  if (point.match_id !== expectedMatchId || point.match_id !== DEMO_MATCH_ID) return { ok: false, reason: 'Point identity must stay in the SIMULATED_ONLY namespace' };
  if (!Number.isInteger(point.game_number) || point.game_number < 1 || !Number.isInteger(point.point_number) || point.point_number < 1) return { ok: false, reason: 'Game and point numbers must be positive integers' };
  for (const [field, allowed] of Object.entries(fieldCodes)) if (!allowed.includes(point[field])) return { ok: false, reason: `Invalid ${field}` };
  for (const field of ['server_score_before', 'receiver_score_before']) {
    const value = point[field];
    if (!(Number.isInteger(value) && value >= 0) && !['unknown', 'unclear', 'not_applicable'].includes(value)) return { ok: false, reason: `Invalid ${field}` };
  }
  const rally = point.rally_length;
  if (!(Number.isInteger(rally) && rally >= 1) && !['unknown', 'unclear', 'not_applicable'].includes(rally)) return { ok: false, reason: 'Invalid rally_length' };
  if (typeof point.video_timestamp !== 'string' || !point.video_timestamp.length || typeof point.notes !== 'string' || !point.notes.length) return { ok: false, reason: 'Timestamp and notes must be nonempty text' };
  return { ok: true, reason: '' };
}

export function validateDemoRecord(bundle) {
  if (!keysMatch(bundle, ['contract_version', 'dataset', 'points']) || bundle.contract_version !== MATCH_INTELLIGENCE_CONTRACT || !object(bundle.dataset) || !Array.isArray(bundle.points)) return { ok: false, reason: 'Expected exact ptti.match-intelligence/0.1 root fields' };
  const dataset = bundle.dataset;
  if (!keysMatch(dataset, ['dataset_id', 'dataset_class', 'match_id', 'source_protocol', 'provenance', 'source_binding'])
    || !(dataset.dataset_id === DEMO_DATASET_ID || /^SIMULATED_ONLY:edit-[0-9a-f]{24}$/.test(dataset.dataset_id))
    || dataset.dataset_class !== 'SIMULATED_ONLY' || dataset.match_id !== DEMO_MATCH_ID) return { ok: false, reason: 'Dataset must stay in the MainDex SIMULATED_ONLY demo identity space' };
  if (!keysMatch(dataset.source_protocol, ['id', 'version', 'schema_revision'])
    || dataset.source_protocol.id !== PROTOCOL_V03.id || dataset.source_protocol.version !== PROTOCOL_V03.version || dataset.source_protocol.schema_revision !== PROTOCOL_V03.schema_revision) return { ok: false, reason: 'Unsupported source protocol or revision' };
  if (dataset.provenance?.method === 'DETERMINISTIC_ORIGINAL_GENERATOR') {
    if (dataset.dataset_id !== DEMO_DATASET_ID || !keysMatch(dataset.provenance, ['method', 'seed', 'generated_on']) || !Number.isInteger(dataset.provenance.seed)
      || typeof dataset.provenance.generated_on !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(dataset.provenance.generated_on)
      || Number.isNaN(Date.parse(dataset.provenance.generated_on)) || new Date(dataset.provenance.generated_on).toISOString().slice(0, 10) !== dataset.provenance.generated_on) return { ok: false, reason: 'Invalid simulated provenance' };
  } else if (dataset.provenance?.method === 'SIMULATED_INTERACTIVE_EDIT') {
    const provenance = dataset.provenance;
    if (!/^SIMULATED_ONLY:edit-[0-9a-f]{24}$/.test(dataset.dataset_id) || !keysMatch(provenance, ['method', 'parent_dataset_id', 'parent_input_sha256', 'edit'])
      || typeof provenance.parent_dataset_id !== 'string' || !provenance.parent_dataset_id.startsWith('SIMULATED_ONLY:')
      || typeof provenance.parent_input_sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(provenance.parent_input_sha256)
      || !/^SIMULATED_ONLY:edit-[0-9a-f]{24}$/.test(dataset.dataset_id)
      || !keysMatch(provenance.edit, ['point_id', 'field', 'before', 'after'])
      || !editableFields.includes(provenance.edit.field) || !validEditValue(provenance.edit.field, provenance.edit.before)
      || !validEditValue(provenance.edit.field, provenance.edit.after)) return { ok: false, reason: 'Invalid simulated interactive edit provenance' };
    const referenced = bundle.points.find((point) => pointReference(dataset.match_id, point) === provenance.edit.point_id);
    if (!referenced || referenced[provenance.edit.field] !== provenance.edit.after) return { ok: false, reason: 'Edit provenance must reference the exact edited point and value' };
  } else return { ok: false, reason: 'Unsupported simulated provenance method' };
  if (!keysMatch(dataset.source_binding, ['status', 'source_id', 'source_sha256', 'timeline_id', 'time_base'])
    || dataset.source_binding.status !== 'NOT_APPLICABLE_SIMULATED'
    || dataset.source_binding.source_id !== null || dataset.source_binding.source_sha256 !== null
    || dataset.source_binding.timeline_id !== null || dataset.source_binding.time_base !== null) return { ok: false, reason: 'Simulated data cannot bind to a real source or timeline' };
  if (bundle.points.length < 1) return { ok: false, reason: 'At least one point is required' };
  const seen = new Set();
  for (const point of bundle.points) {
    const valid = validatePoint(point);
    if (!valid.ok) return valid;
    const key = `${point.game_number}:${point.point_number}`;
    if (seen.has(key)) return { ok: false, reason: 'Duplicate natural point key' };
    seen.add(key);
  }
  return { ok: true, reason: '' };
}

export function cloneBundle(bundle) { return structuredClone(bundle); }

function sameValue(left, right) { return stableStringify(left) === stableStringify(right); }

function rowsDiff(parent, child) {
  const differences = [];
  if (!Array.isArray(parent?.points) || !Array.isArray(child?.points) || parent.points.length !== child.points.length) return null;
  for (let index = 0; index < parent.points.length; index += 1) {
    const before = parent.points[index];
    const after = child.points[index];
    for (const field of POINT_FIELDS) {
      if (before[field] !== after[field]) differences.push({ before, after, field });
    }
  }
  return differences;
}

function editIdentity(parent, edit) {
  const point = parent.points.find((row) => pointReference(parent.dataset.match_id, row) === edit.point_id);
  if (!point) return null;
  return stableStringify({ after: edit.after, field: edit.field, game_number: point.game_number, point_number: point.point_number });
}

export async function verifyDemoLineage(record, snapshots) {
  const valid = validateDemoRecord(record);
  if (!valid.ok || !Array.isArray(snapshots) || snapshots.length < 1) return { ok: false, reason: valid.ok ? 'Lineage snapshots are required' : valid.reason };
  const byId = new Map();
  for (const snapshot of snapshots) {
    const snapshotValid = validateDemoRecord(snapshot);
    if (!snapshotValid.ok) return { ok: false, reason: `Invalid lineage snapshot: ${snapshotValid.reason}` };
    const id = snapshot.dataset.dataset_id;
    if (byId.has(id)) return { ok: false, reason: 'Duplicate dataset_id in lineage' };
    byId.set(id, snapshot);
  }
  const root = byId.get(DEMO_DATASET_ID);
  if (!root || root.dataset.provenance.method !== 'DETERMINISTIC_ORIGINAL_GENERATOR') return { ok: false, reason: 'Original simulated parent dataset is missing' };
  const visited = new Set([DEMO_DATASET_ID]);
  for (const snapshot of snapshots) {
    const provenance = snapshot.dataset.provenance;
    if (provenance.method === 'DETERMINISTIC_ORIGINAL_GENERATOR') {
      if (snapshot.dataset.dataset_id !== DEMO_DATASET_ID || !sameValue(snapshot, root)) return { ok: false, reason: 'Unexpected original simulated dataset' };
      continue;
    }
    const parent = byId.get(provenance.parent_dataset_id);
    if (!parent || !visited.has(provenance.parent_dataset_id)) return { ok: false, reason: 'Edit parent is missing or out of order' };
    const parentSha = await sha256(stableStringify(parent));
    if (parentSha !== provenance.parent_input_sha256) return { ok: false, reason: 'Parent input SHA-256 does not match the retained parent snapshot' };
    const edit = provenance.edit;
    const diff = rowsDiff(parent, snapshot);
    if (!diff || diff.length !== 1 || diff[0].field !== edit.field || diff[0].before[edit.field] !== edit.before || diff[0].after[edit.field] !== edit.after
      || pointReference(snapshot.dataset.match_id, diff[0].after) !== edit.point_id) return { ok: false, reason: 'Recorded edit does not match the one-field parent-to-child change' };
    const identity = editIdentity(parent, edit);
    const expectedDigest = await sha256(parentSha + identity);
    if (snapshot.dataset.dataset_id !== `SIMULATED_ONLY:edit-${expectedDigest.slice(0, 24)}`) return { ok: false, reason: 'Derived dataset_id does not match the parent and edit' };
    visited.add(snapshot.dataset.dataset_id);
  }
  const last = snapshots.at(-1);
  if (!sameValue(last, record)) return { ok: false, reason: 'Current record is not the final verified lineage snapshot' };
  return { ok: true, reason: '' };
}

export async function loadDemoRecord(storage, sourceBundle) {
  const sourceValid = validateDemoRecord(sourceBundle);
  if (!sourceValid.ok) return { record: null, history: [], issue: 'source-invalid' };
  const fresh = () => ({ record: cloneBundle(sourceBundle), history: [cloneBundle(sourceBundle)] });
  if (!storage) return { ...fresh(), issue: 'unavailable' };
  let raw;
  try { raw = storage.getItem(DEMO_STORAGE_KEY); } catch { return { ...fresh(), issue: 'unavailable' }; }
  if (raw === null) return { ...fresh(), issue: null };
  let parsed;
  try { parsed = JSON.parse(raw); } catch { return { ...fresh(), issue: 'invalid' }; }
  if (keysMatch(parsed, ['record', 'history']) && Array.isArray(parsed.history)) {
    const lineage = await verifyDemoLineage(parsed.record, parsed.history);
    if (lineage.ok) return { record: parsed.record, history: parsed.history, issue: null };
  }
  if (validateDemoRecord(parsed).ok && parsed.dataset.dataset_id === DEMO_DATASET_ID && sameValue(parsed, sourceBundle)) return { record: parsed, history: [cloneBundle(parsed)], issue: null };
  return { ...fresh(), issue: 'invalid' };
}

export async function saveDemoRecord(storage, bundle, history) {
  const valid = validateDemoRecord(bundle);
  if (!valid.ok || !storage) return { ok: false, reason: valid.ok ? 'storage unavailable' : valid.reason };
  const lineage = await verifyDemoLineage(bundle, history);
  if (!lineage.ok) return { ok: false, reason: lineage.reason };
  try {
    storage.setItem(DEMO_STORAGE_KEY, JSON.stringify({ record: bundle, history }));
    return { ok: true, reason: '' };
  } catch { return { ok: false, reason: 'storage unavailable' }; }
}

export function updateDemoPoint(bundle, updatedPoint) {
  if (bundle?.dataset?.dataset_class === 'HUMAN_ANNOTATION') throw new Error('Manual CSV annotations cannot be edited here; update the source CSV and re-import it to recalculate its hash');
  const valid = validatePoint(updatedPoint);
  if (!valid.ok) throw new Error(valid.reason);
  const structural = keysMatch(bundle, ['contract_version', 'dataset', 'points'])
    && bundle.contract_version === MATCH_INTELLIGENCE_CONTRACT && bundle.dataset?.dataset_class === 'SIMULATED_ONLY' && Array.isArray(bundle.points);
  if (!structural) throw new Error('The working copy does not match the simulated contract shape');
  const next = cloneBundle(bundle);
  const index = next.points.findIndex((point) => point.game_number === updatedPoint.game_number && point.point_number === updatedPoint.point_number);
  if (index < 0) throw new Error('The point does not exist in this simulated game');
  next.points[index] = structuredClone(updatedPoint);
  return next;
}

export async function applyDemoEditsWithLineage(parentBundle, desiredBundle, priorHistory = [parentBundle]) {
  if (parentBundle?.dataset?.dataset_class === 'HUMAN_ANNOTATION') throw new Error('Manual CSV annotations cannot be edited here; update the source CSV and re-import it to recalculate its hash');
  const parentValid = validateDemoRecord(parentBundle);
  if (!parentValid.ok || !keysMatch(desiredBundle, ['contract_version', 'dataset', 'points'])
    || desiredBundle.contract_version !== MATCH_INTELLIGENCE_CONTRACT || !Array.isArray(desiredBundle.points)
    || desiredBundle.points.some((point) => !validatePoint(point).ok)) throw new Error('Both parent and edited data must match the shared contract');
  if (parentBundle.dataset.dataset_class !== 'SIMULATED_ONLY') throw new Error('Only the separate SIMULATED_ONLY demo identity space can be edited here');
  const historyStatus = await verifyDemoLineage(parentBundle, priorHistory);
  if (!historyStatus.ok) throw new Error(historyStatus.reason);
  if (parentBundle.dataset.match_id !== desiredBundle.dataset.match_id || parentBundle.points.length !== desiredBundle.points.length) throw new Error('Edits cannot change simulated match identity or add/remove points');
  const parentPoints = new Map(parentBundle.points.map((point) => [`${point.game_number}:${point.point_number}`, point]));
  const desiredPoints = new Map(desiredBundle.points.map((point) => [`${point.game_number}:${point.point_number}`, point]));
  if ([...parentPoints.keys()].some((key) => !desiredPoints.has(key))) throw new Error('Edits cannot change point identity');
  if (stableStringify(parentBundle.dataset.source_protocol) !== stableStringify(desiredBundle.dataset.source_protocol)
    || stableStringify(parentBundle.dataset.source_binding) !== stableStringify(desiredBundle.dataset.source_binding)) throw new Error('Edits cannot change protocol or source binding');
  for (const [key, parentPoint] of parentPoints) {
    const desiredPoint = desiredPoints.get(key);
    for (const field of POINT_FIELDS) {
      if (!editableFields.includes(field) && parentPoint[field] !== desiredPoint[field]) throw new Error(`Field ${field} is not editable in the Web demo`);
    }
  }
  const current = cloneBundle(parentBundle);
  const history = priorHistory.map(cloneBundle);
  const created = [];
  const orderedPoints = [...current.points].sort((a, b) => a.game_number - b.game_number || a.point_number - b.point_number);
  for (const currentPoint of orderedPoints) {
    const key = `${currentPoint.game_number}:${currentPoint.point_number}`;
    const desiredPoint = desiredPoints.get(key);
    const changes = editableFields.filter((field) => currentPoint[field] !== desiredPoint[field]).sort();
    for (const field of changes) {
      const before = currentPoint[field];
      const after = desiredPoint[field];
      if (!validEditValue(field, after)) throw new Error(`Invalid edited value for ${field}`);
      const parentInputSha256 = await sha256(stableStringify(current));
      const editIdentity = stableStringify({ field, game_number: currentPoint.game_number, point_number: currentPoint.point_number, after });
      const identityHash = await sha256(parentInputSha256 + editIdentity);
      const parentDatasetId = current.dataset.dataset_id;
      const edit = {
        point_id: pointReference(current.dataset.match_id, currentPoint),
        field,
        before,
        after,
      };
      current.points.find((point) => point.game_number === currentPoint.game_number && point.point_number === currentPoint.point_number)[field] = after;
      current.dataset.dataset_id = `SIMULATED_ONLY:edit-${identityHash.slice(0, 24)}`;
      current.dataset.provenance = {
        method: 'SIMULATED_INTERACTIVE_EDIT',
        parent_dataset_id: parentDatasetId,
        parent_input_sha256: parentInputSha256,
        edit,
      };
      const validation = validateDemoRecord(current);
      if (!validation.ok) throw new Error(validation.reason);
      if (history.some((snapshot) => snapshot.dataset.dataset_id === current.dataset.dataset_id)) throw new Error('Duplicate dataset_id in lineage');
      const snapshot = cloneBundle(current);
      history.push(snapshot);
      created.push(snapshot);
    }
  }
  if (created.length === 0) return { record: current, history, created };
  const lineage = await verifyDemoLineage(current, history);
  if (!lineage.ok) throw new Error(lineage.reason);
  return { record: current, history, created };
}

export async function applyDemoEdits(parentBundle, desiredBundle) {
  return (await applyDemoEditsWithLineage(parentBundle, desiredBundle, [parentBundle])).record;
}

const UNRESOLVED = new Set(['unknown', 'unclear', 'not_applicable']);
const MIN_DISPLAY_SAMPLE = 5;
const metricStatus = (denominator) => denominator === 0 ? 'NOT_ESTIMABLE' : denominator < MIN_DISPLAY_SAMPLE ? 'INSUFFICIENT_SAMPLE' : 'DESCRIPTIVE_ONLY';
const rate = (numerator, denominator, extra = {}) => ({ numerator, denominator, value: denominator ? Number((numerator / denominator).toFixed(6)) : null, status: metricStatus(denominator), ...extra });

function counterSummary(values, eligibleCount = null) {
  const counts = Object.fromEntries([...new Set(values)].filter((key) => !UNRESOLVED.has(key)).sort().map((key) => [key, values.filter((value) => value === key).length]));
  const unknown = values.filter((value) => value === 'unknown').length;
  const unclear = values.filter((value) => value === 'unclear').length;
  const notApplicable = values.filter((value) => value === 'not_applicable').length;
  const observed = values.length - unknown - unclear - notApplicable;
  const eligible = eligibleCount === null ? values.length - notApplicable : eligibleCount;
  const shares = observed ? Object.fromEntries(Object.entries(counts).map(([key, count]) => [key, Number((count / observed).toFixed(6))])) : {};
  return {
    row_count: values.length, eligible_denominator: eligible, observed_denominator: observed,
    counts, shares_of_observed: shares, unknown_count: unknown, unclear_count: unclear,
    not_applicable_count: notApplicable, uncertainty_rate: eligible ? Number(((unknown + unclear) / eligible).toFixed(6)) : null,
    status: metricStatus(observed),
  };
}

function pointReferenceListRow(point) { return { point_id: pointReference(point.match_id, point), game_number: point.game_number, point_number: point.point_number }; }

export function computeDemoSummary(points) {
  const rows = points.filter((point) => validatePoint(point).ok);
  const serveFields = ['serve_side', 'serve_length', 'serve_location', 'serve_spin', 'receive_type', 'receive_location'];
  const serveDistributions = Object.fromEntries(serveFields.map((field) => [field, counterSummary(rows.map((point) => point[field]))]));
  const winners = rows.map((point) => point.point_winner).filter((value) => !UNRESOLVED.has(value));
  const pointWins = { player: winners.filter((value) => value === 'player').length, opponent: winners.filter((value) => value === 'opponent').length };
  const pointWinnerDenominator = winners.length;
  const serverRows = rows.filter((point) => ['player', 'opponent'].includes(point.server) && ['player', 'opponent'].includes(point.point_winner));
  const serverWins = serverRows.filter((point) => point.server === point.point_winner).length;
  const attacksClassified = rows.filter((point) => ['yes', 'no'].includes(point.third_ball_attack));
  const attacks = rows.filter((point) => point.third_ball_attack === 'yes');
  const attackSide = counterSummary(attacks.map((point) => point.third_ball_side), attacks.length);
  const attackOutcome = counterSummary(attacks.map((point) => point.third_ball_outcome), attacks.length);
  const immediate = attacks.map((point) => point.third_ball_outcome).filter((value) => ['successful', 'unsuccessful'].includes(value));
  const conversions = attacks.filter((point) => ['player', 'opponent'].includes(point.server) && ['player', 'opponent'].includes(point.point_winner));
  const conversionWins = conversions.filter((point) => point.server === point.point_winner).length;
  const attackUnknown = rows.filter((point) => point.third_ball_attack === 'unknown').length;
  const attackUnclear = rows.filter((point) => point.third_ball_attack === 'unclear').length;
  const rallyValues = rows.map((point) => point.rally_length).filter((value) => Number.isInteger(value));
  const byGame = {};
  for (const point of rows) byGame[String(point.game_number)] = (byGame[String(point.game_number)] ?? 0) + 1;
  return {
    point_count: rows.length, by_game: byGame,
    point_wins: {
      counts: pointWins, denominator: pointWinnerDenominator,
      rates: { player: rate(pointWins.player, pointWinnerDenominator), opponent: rate(pointWins.opponent, pointWinnerDenominator) },
      status: metricStatus(pointWinnerDenominator),
    },
    server_point_win_rate: rate(serverWins, serverRows.length, { excluded_rows: rows.length - serverRows.length }),
    serve_distributions: serveDistributions,
    third_ball_attack_rate: rate(attacks.length, attacksClassified.length, {
      unresolved_eligibility: attackUnknown + attackUnclear,
      not_applicable: rows.filter((point) => point.third_ball_attack === 'not_applicable').length,
      unknown: attackUnknown, unclear: attackUnclear,
    }),
    third_ball_attack_side: attackSide,
    third_ball_immediate_outcome: {
      definition: 'third_ball_outcome successful / (successful + unsuccessful), among third_ball_attack=yes',
      rate: rate(immediate.filter((value) => value === 'successful').length, immediate.length, {
        unknown: attacks.filter((point) => point.third_ball_outcome === 'unknown').length,
        unclear: attacks.filter((point) => point.third_ball_outcome === 'unclear').length,
      }),
      distribution: attackOutcome,
    },
    third_ball_point_conversion: {
      definition: 'server won the point / confirmed third_ball_attack=yes with known server and point_winner',
      ...rate(conversionWins, conversions.length), excluded_confirmed_attack_rows: attacks.length - conversions.length,
    },
    rally_length: {
      numerator_sum: rallyValues.reduce((total, value) => total + value, 0), denominator: rallyValues.length,
      mean: rallyValues.length ? Number((rallyValues.reduce((total, value) => total + value, 0) / rallyValues.length).toFixed(6)) : null,
      unknown_count: rows.filter((point) => point.rally_length === 'unknown').length,
      unclear_count: rows.filter((point) => point.rally_length === 'unclear').length,
      not_applicable_count: rows.filter((point) => point.rally_length === 'not_applicable').length,
      status: metricStatus(rallyValues.length),
    },
    display_sample_threshold: { n: MIN_DISPLAY_SAMPLE, meaning: 'product display rule only; not a research reliability threshold' },
  };
}

export async function createAnalysisResult(bundle) {
  const valid = validateDemoRecord(bundle);
  if (!valid.ok) throw new Error(valid.reason);
  return {
    analysis_version: MATCH_INTELLIGENCE_CONTRACT,
    input_sha256: await sha256(stableStringify(bundle)),
    source_protocol: cloneBundle(bundle).dataset.source_protocol,
    dataset: {
      dataset_id: bundle.dataset.dataset_id, dataset_class: bundle.dataset.dataset_class, match_id: bundle.dataset.match_id,
      source_binding: structuredClone(bundle.dataset.source_binding), provenance: structuredClone(bundle.dataset.provenance), human_review_status: 'SIMULATED_ONLY',
    },
    summary: computeDemoSummary(bundle.points),
    limitations: [
      'Descriptive summaries only; no confidence intervals, significance tests, causal claims, or machine learning.',
      'Third-ball immediate outcome is not point winner; point conversion is computed separately from server and point_winner.',
      'Protocol v0.3 video_timestamp is preserved as free text; no PTS, time_base, or source timeline mapping is inferred.',
      'SIMULATED_ONLY data is isolated from real match, athlete, VideoSource, and ptti.match-media records.',
    ],
    point_refs: bundle.points.map(pointReferenceListRow),
  };
}

const countValues = (points, field, values) => Object.fromEntries(values.map((value) => [value, points.filter((point) => point[field] === value).length]));

export function computeDemoStats(points) {
  const validPoints = points.filter((point) => validatePoint(point).ok);
  const lengths = countValues(validPoints, 'serve_length', ['short', 'half_long', 'long', 'unknown', 'unclear', 'not_applicable']);
  const spins = countValues(validPoints, 'serve_spin', ['backspin', 'sidespin', 'topspin', 'no_spin', 'mixed', 'unknown', 'unclear', 'not_applicable']);
  const attacks = validPoints.filter((point) => ['yes', 'no'].includes(point.third_ball_attack));
  const confirmedAttacks = validPoints.filter((point) => point.third_ball_attack === 'yes');
  const outcomes = countValues(confirmedAttacks, 'third_ball_outcome', ['successful', 'unsuccessful', 'unknown', 'unclear', 'not_applicable']);
  const resolvedOutcomes = outcomes.successful + outcomes.unsuccessful;
  const result = {
    total: validPoints.length,
    serveLength: { ...lengths, observed: lengths.short + lengths.half_long + lengths.long },
    serveSpin: { ...spins, observed: spins.backspin + spins.sidespin + spins.topspin + spins.no_spin + spins.mixed },
    thirdBall: {
      yes: confirmedAttacks.length,
      no: attacks.filter((point) => point.third_ball_attack === 'no').length,
      unresolved: validPoints.filter((point) => ['unknown', 'unclear'].includes(point.third_ball_attack)).length,
      notApplicable: validPoints.filter((point) => point.third_ball_attack === 'not_applicable').length,
      classified: attacks.length,
      rate: attacks.length ? confirmedAttacks.length / attacks.length : null,
      side: countValues(confirmedAttacks, 'third_ball_side', ['forehand', 'backhand', 'other', 'unknown', 'unclear', 'not_applicable']),
      outcomes: { ...outcomes, resolved: resolvedOutcomes, rate: resolvedOutcomes ? outcomes.successful / resolvedOutcomes : null },
    },
  };
  return result;
}

export async function createDemoExport(bundle, history) {
  const valid = validateDemoRecord(bundle);
  if (!valid.ok) throw new Error(valid.reason);
  const lineage = await verifyDemoLineage(bundle, history);
  if (!lineage.ok) throw new Error(lineage.reason);
  return {
    export_format: DEMO_EXPORT_FORMAT,
    input: cloneBundle(bundle),
    analysis: await createAnalysisResult(bundle),
    lineage: { snapshots: history.map(cloneBundle), sha256_semantics: 'Canonical input locator; not a signature or evidence of real-match truth.' },
  };
}
