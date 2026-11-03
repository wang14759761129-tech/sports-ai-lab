import { validateTrainingReview } from './training-review.mjs';

export const TRAINING_HANDOFF_VERSION = 'ptti.training-handoff/0.1';
export const ANNOTATION_RECEIPT_VERSION = 'ptti.annotation-review-receipt/0.1';

export const TRAINING_PROTOCOL_FIELDS = [
  'match_id', 'game_number', 'point_number', 'server', 'receiver', 'server_score_before', 'receiver_score_before',
  'serve_side', 'serve_length', 'serve_location', 'serve_spin', 'receive_type', 'receive_location',
  'third_ball_attack', 'third_ball_side', 'third_ball_outcome', 'rally_length', 'point_winner', 'point_outcome',
  'video_timestamp', 'notes',
];

const rootKeys = ['package_version', 'visibility', 'protocol_fields', 'csv_utf8', 'csv_sha256', 'inputs', 'report', 'quality'];
const qualityKeys = ['audit_version', 'status', 'coverage', 'findings', 'metric_flags', 'vision_status', 'independent_identity_review', 'independent_rights_review', 'annotation_accuracy'];
const coverageFields = TRAINING_PROTOCOL_FIELDS.filter((field) => !['match_id', 'game_number', 'point_number', 'notes'].includes(field));
const numericFields = new Set(['game_number', 'point_number', 'server_score_before', 'receiver_score_before', 'rally_length']);
const hashPattern = /^[0-9a-f]{64}$/;

function reject(code) { const error = new Error(code); error.code = code; throw error; }
function isObject(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function exactKeys(value, wanted, code) {
  if (!isObject(value) || JSON.stringify(Object.keys(value).sort()) !== JSON.stringify([...wanted].sort())) reject(code);
}
function timezoneDate(value) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
}

export function stableJson(value, key = '') {
  if (Array.isArray(value)) return `[${value.map((item) => stableJson(item)).join(',')}]`;
  if (isObject(value)) return `{${Object.keys(value).sort().map((childKey) => `${JSON.stringify(childKey)}:${stableJson(value[childKey], childKey)}`).join(',')}}`;
  // Python's json.dumps keeps metric values as floats (for example 1.0); JSON.parse erases that distinction.
  if (key === 'value' && typeof value === 'number' && Number.isInteger(value)) return `${value}.0`;
  return JSON.stringify(value);
}

async function sha256(bytes) {
  if (!globalThis.crypto?.subtle) reject('HANDOFF_CRYPTO_UNAVAILABLE');
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

function parseCsvRecords(source) {
  const records = [];
  let record = [];
  let field = '';
  let quoted = false;
  let closedQuote = false;
  const finishField = () => { record.push(field); field = ''; closedQuote = false; };
  const finishRecord = () => { finishField(); records.push(record); record = []; };

  for (let index = 0; index < source.length; index += 1) {
    const char = source[index];
    if (quoted) {
      if (char === '"') {
        if (source[index + 1] === '"') { field += '"'; index += 1; }
        else { quoted = false; closedQuote = true; }
      } else field += char;
      continue;
    }
    if (closedQuote && char !== ',' && char !== '\r' && char !== '\n') reject('HANDOFF_INVALID_CSV');
    if (char === '"') {
      if (field.length !== 0 || closedQuote) reject('HANDOFF_INVALID_CSV');
      quoted = true;
    } else if (char === ',') finishField();
    else if (char === '\r' || char === '\n') {
      if (char === '\r' && source[index + 1] === '\n') index += 1;
      finishRecord();
    } else field += char;
  }
  if (quoted) reject('HANDOFF_INVALID_CSV');
  if (field.length > 0 || record.length > 0 || closedQuote) finishRecord();
  return records;
}

function decodeRows(csv) {
  if (csv.startsWith('\uFEFF')) reject('HANDOFF_CSV_BOM_FORBIDDEN');
  const rows = parseCsvRecords(csv);
  if (rows.length < 2) reject('HANDOFF_CSV_ROWS_MISSING');
  const headers = rows[0];
  if (headers.length !== TRAINING_PROTOCOL_FIELDS.length
    || new Set(headers).size !== headers.length
    || TRAINING_PROTOCOL_FIELDS.some((field) => !headers.includes(field))) reject('HANDOFF_CSV_HEADER_MISMATCH');
  return rows.slice(1).map((cells, rowIndex) => {
    if (cells.length !== headers.length || cells.some((cell) => cell === '')) reject('HANDOFF_CSV_ROW_INVALID');
    const row = {};
    headers.forEach((key, column) => {
      const value = cells[column];
      if (numericFields.has(key) && /^(?:0|[1-9][0-9]*)$/.test(value)) {
        const number = Number(value);
        if (!Number.isSafeInteger(number)) reject('HANDOFF_CSV_ROW_INVALID');
        row[key] = number;
      } else row[key] = value;
    });
    if (row.game_number < 1 || row.point_number < 1) reject('HANDOFF_CSV_ROW_INVALID');
    return { row, csvRecordNumber: rowIndex + 2 };
  });
}

function encodedPointId(matchId, gameNumber, pointNumber) {
  const encoded = encodeURIComponent(matchId).replace(/[!'()*]/g, (char) => `%${char.charCodeAt(0).toString(16).toUpperCase()}`);
  return `${encoded}/g${String(gameNumber).padStart(2, '0')}/p${String(pointNumber).padStart(3, '0')}`;
}

function validateInputDeclarations(pkg, report) {
  exactKeys(pkg.inputs, ['declaration', 'manifest', 'binding'], 'HANDOFF_INPUTS_INVALID');
  const { declaration, manifest, binding } = pkg.inputs;
  const dataset = report.dataset;
  if (dataset.dataset_class === 'SIMULATED_ONLY') {
    exactKeys(declaration, ['declaration_version', 'dataset_class', 'generator_ref', 'csv_sha256', 'parent_csv_sha256'], 'HANDOFF_SIMULATED_DECLARATION_INVALID');
    if (manifest !== null || binding !== null
      || declaration.declaration_version !== 'ptti.training-simulated-declaration/0.1'
      || declaration.dataset_class !== 'SIMULATED_ONLY'
      || declaration.generator_ref !== 'goal07-24-point-v1'
      || declaration.csv_sha256 !== pkg.csv_sha256
      || (declaration.parent_csv_sha256 !== null && !hashPattern.test(String(declaration.parent_csv_sha256)))) reject('HANDOFF_SIMULATED_DECLARATION_INVALID');
    const provenance = dataset.annotation_provenance;
    if (provenance.method === 'DETERMINISTIC_ORIGINAL_GENERATOR' && declaration.parent_csv_sha256 !== null) reject('HANDOFF_SIMULATED_LINEAGE_MISMATCH');
    if (provenance.method === 'SIMULATED_INTERACTIVE_EDIT'
      && (!declaration.parent_csv_sha256 || provenance.parent_input_sha256 !== declaration.parent_csv_sha256)) reject('HANDOFF_SIMULATED_LINEAGE_MISMATCH');
    return 'SIMULATED_ONLY';
  }

  exactKeys(manifest, ['manifest_version', 'dataset_id', 'match_id', 'source_id', 'source_sha256', 'annotator_ref', 'annotated_at', 'evidence_ref', 'timestamp_semantics'], 'HANDOFF_HUMAN_MANIFEST_INVALID');
  exactKeys(binding, ['binding_version', 'dataset_id', 'match_id', 'source_id', 'local_asset_id', 'source_sha256', 'match_link_status', 'local_analysis_permission', 'rights_basis_ref', 'reviewer_ref', 'reviewed_at', 'analysis_method'], 'HANDOFF_HUMAN_BINDING_INVALID');
  const requiredText = (obj, key) => typeof obj[key] === 'string' && obj[key].trim().length > 0;
  if (declaration !== null
    || manifest.manifest_version !== 'ptti.manual-point-annotation/0.1'
    || manifest.timestamp_semantics !== 'PROTOCOL_TEXT_ONLY_UNBOUND'
    || !['dataset_id', 'match_id', 'source_id', 'annotator_ref', 'evidence_ref'].every((key) => requiredText(manifest, key))
    || !hashPattern.test(String(manifest.source_sha256)) || !timezoneDate(manifest.annotated_at)
    || binding.binding_version !== 'ptti.training-source-binding/0.1'
    || binding.match_link_status !== 'HUMAN_REVIEWED_DECLARATION'
    || binding.local_analysis_permission !== 'DECLARED_ALLOWED'
    || binding.analysis_method !== 'HUMAN_MANUAL'
    || !['local_asset_id', 'rights_basis_ref', 'reviewer_ref'].every((key) => requiredText(binding, key))
    || !timezoneDate(binding.reviewed_at)
    || !['dataset_id', 'match_id', 'source_id', 'source_sha256'].every((key) => manifest[key] === binding[key])
    || dataset.dataset_id !== manifest.dataset_id || dataset.match_id !== manifest.match_id || dataset.source_id !== manifest.source_id
    || dataset.local_asset_id !== binding.local_asset_id || dataset.source_video_sha256 !== manifest.source_sha256
    || dataset.rights_basis_ref !== binding.rights_basis_ref
    || dataset.match_link_status !== 'HUMAN_REVIEWED_DECLARATION_NOT_AUDITED'
    || dataset.local_analysis_permission !== 'DECLARED_ALLOWED_NOT_AUDITED'
    || dataset.annotation_provenance.method !== 'HUMAN_MANUAL'
    || dataset.annotation_provenance.annotator_ref !== manifest.annotator_ref
    || dataset.annotation_provenance.annotated_at !== manifest.annotated_at
    || dataset.annotation_provenance.evidence_ref !== manifest.evidence_ref
    || dataset.annotation_provenance.annotation_csv_sha256 !== pkg.csv_sha256) reject('HANDOFF_HUMAN_BINDING_MISMATCH');
  return 'HUMAN_ANNOTATION';
}

function recomputeQuality(report) {
  const coverage = Object.fromEntries(coverageFields.map((field) => [field, { known: 0, unknown: 0, unclear: 0, not_applicable: 0 }]));
  const findings = [];
  let previous = null;
  for (let index = 0; index < report.point_records.length; index += 1) {
    const row = report.point_records[index];
    const fields = row.fields;
    const uncertain = [];
    for (const [field, counts] of Object.entries(coverage)) {
      const value = fields[field];
      const kind = ['unknown', 'unclear', 'not_applicable'].includes(value) ? value : 'known';
      counts[kind] += 1;
      if (kind === 'unknown' || kind === 'unclear') uncertain.push(field);
    }
    const ref = { point_id: row.point_id, csv_record_number: row.csv_record_number, annotation_row_sha256: row.annotation_row_sha256 };
    if (uncertain.length) findings.push({ ...ref, code: 'UNCERTAINTY_REVIEW', fields: uncertain });
    if (fields.video_timestamp !== 'unknown') findings.push({ ...ref, code: 'TIMESTAMP_UNBOUND', fields: ['video_timestamp'] });
    const trace = report.score_trace[index];
    if (previous && previous.game_number === trace.game_number && previous.score_after !== null && trace.score_before !== null
      && (previous.score_after.player !== trace.score_before.player || previous.score_after.opponent !== trace.score_before.opponent)) {
      findings.push({ ...ref, code: 'SCORE_CONTINUITY_REVIEW', fields: ['server_score_before', 'receiver_score_before'] });
    }
    previous = trace;
  }
  const metricFlags = Object.entries(report.metrics)
    .filter(([, metric]) => metric.sample_status !== 'DESCRIPTIVE_ONLY' || metric.missing_count > 0)
    .map(([key, metric]) => ({ key, denominator: metric.denominator, missing_count: metric.missing_count, sample_status: metric.sample_status }));
  return {
    audit_version: 'ptti.annotation-quality/0.1',
    status: 'STRUCTURE_CHECKED_HUMAN_REVIEW_REQUIRED',
    coverage,
    findings,
    metric_flags: metricFlags,
    vision_status: 'NOT_TESTED',
    independent_identity_review: 'NOT_TESTED',
    independent_rights_review: 'NOT_TESTED',
    annotation_accuracy: 'NOT_TESTED',
  };
}

export async function validateTrainingHandoff(value) {
  exactKeys(value, rootKeys, 'HANDOFF_ROOT_FIELDS_INVALID');
  if (value.package_version !== TRAINING_HANDOFF_VERSION) reject('HANDOFF_VERSION_UNSUPPORTED');
  if (value.visibility !== 'PRIVATE_REVIEW_ONLY') reject('HANDOFF_VISIBILITY_REJECTED');
  if (JSON.stringify(value.protocol_fields) !== JSON.stringify(TRAINING_PROTOCOL_FIELDS)) reject('HANDOFF_PROTOCOL_FIELDS_MISMATCH');
  if (typeof value.csv_utf8 !== 'string' || typeof value.csv_sha256 !== 'string' || !hashPattern.test(value.csv_sha256)) reject('HANDOFF_CSV_FIELDS_INVALID');
  if (!isObject(value.report)) reject('HANDOFF_REPORT_INVALID');
  if (!isObject(value.quality)) reject('HANDOFF_QUALITY_INVALID');
  exactKeys(value.quality, qualityKeys, 'HANDOFF_QUALITY_FIELDS_INVALID');
  const report = validateTrainingReview(value.report);
  const bytes = new TextEncoder().encode(value.csv_utf8);
  const actualCsvSha256 = await sha256(bytes);
  if (actualCsvSha256 !== value.csv_sha256 || value.report.dataset.annotation_csv_sha256 !== value.csv_sha256) reject('HANDOFF_CSV_HASH_MISMATCH');
  const dataClass = validateInputDeclarations(value, report);
  const rows = decodeRows(value.csv_utf8);
  if (rows.length !== report.point_records.length || rows.length !== report.point_refs.length || rows.length !== report.sample.point_count) reject('HANDOFF_ROW_COUNT_MISMATCH');
  for (const [index, { row, csvRecordNumber }] of rows.entries()) {
    const record = report.point_records[index];
    const ref = report.point_refs[index];
    const expectedPointId = encodedPointId(report.dataset.match_id, row.game_number, row.point_number);
    const rowHash = await sha256(new TextEncoder().encode(stableJson(row)));
    if (record.csv_record_number !== csvRecordNumber || record.point_id !== expectedPointId || record.annotation_row_sha256 !== rowHash
      || stableJson(record.fields) !== stableJson(row)
      || ref.csv_record_number !== csvRecordNumber || ref.point_id !== expectedPointId || ref.annotation_row_sha256 !== rowHash
      || ref.game_number !== row.game_number || ref.point_number !== row.point_number) reject('HANDOFF_POINT_TRACE_MISMATCH');
  }
  const expectedQuality = recomputeQuality(report);
  if (stableJson(value.quality) !== stableJson(expectedQuality)) reject('HANDOFF_QUALITY_RECOMPUTATION_MISMATCH');
  return {
    package: value,
    report,
    dataClass,
    quality: expectedQuality,
    actualCsvSha256,
    sourceIndependentlyVerified: false,
  };
}

export async function parseTrainingHandoffJson(source) {
  if (typeof source !== 'string') reject('HANDOFF_JSON_NOT_TEXT');
  let value;
  try { value = JSON.parse(source); } catch { reject('HANDOFF_JSON_INVALID'); }
  return validateTrainingHandoff(value);
}

export async function validateAnnotationReviewReceipt(receipt, verifiedHandoff) {
  const keys = ['receipt_version', 'package_content_sha256', 'dataset_class', 'review', 'status', 'vision_status', 'source_annotations_changed'];
  exactKeys(receipt, keys, 'RECEIPT_FIELDS_INVALID');
  if (receipt.receipt_version !== ANNOTATION_RECEIPT_VERSION) reject('RECEIPT_VERSION_UNSUPPORTED');
  if (!verifiedHandoff?.package || !verifiedHandoff?.report) reject('RECEIPT_PACKAGE_REQUIRED');
  const expectedPackageHash = await sha256(new TextEncoder().encode(stableJson(verifiedHandoff.package)));
  if (receipt.package_content_sha256 !== expectedPackageHash) reject('RECEIPT_PACKAGE_HASH_MISMATCH');
  const report = verifiedHandoff.report;
  if (receipt.dataset_class !== report.dataset.dataset_class) reject('RECEIPT_DATASET_CLASS_MISMATCH');
  if (receipt.status !== 'DECLARED_NOT_INDEPENDENTLY_AUDITED' || receipt.vision_status !== 'NOT_TESTED' || receipt.source_annotations_changed !== false) reject('RECEIPT_STATUS_INVALID');
  exactKeys(receipt.review, ['review_version', 'annotation_csv_sha256', 'reviewer_ref', 'reviewed_at', 'decisions'], 'RECEIPT_REVIEW_INVALID');
  const review = receipt.review;
  if (review.review_version !== 'ptti.annotation-review/0.1' || review.annotation_csv_sha256 !== verifiedHandoff.package.csv_sha256
    || typeof review.reviewer_ref !== 'string' || !review.reviewer_ref.trim() || !timezoneDate(review.reviewed_at)
    || !Array.isArray(review.decisions) || review.decisions.length === 0) reject('RECEIPT_REVIEW_INVALID');
  const rows = new Map(report.point_records.map((row) => [row.point_id, row]));
  const seen = new Set();
  for (const decision of review.decisions) {
    exactKeys(decision, ['point_id', 'annotation_row_sha256', 'field', 'disposition', 'reason'], 'RECEIPT_DECISION_INVALID');
    if (Object.values(decision).some((item) => typeof item !== 'string') || !TRAINING_PROTOCOL_FIELDS.includes(decision.field)
      || !['NEEDS_REANNOTATION', 'REVIEWED_DECLARATION', 'UNRESOLVED'].includes(decision.disposition)
      || !decision.reason.trim()) reject('RECEIPT_DECISION_INVALID');
    const row = rows.get(decision.point_id);
    if (!row || row.annotation_row_sha256 !== decision.annotation_row_sha256) reject('RECEIPT_DECISION_REFERENCE_MISMATCH');
    const decisionKey = `${decision.point_id}\u0000${decision.field}`;
    if (seen.has(decisionKey)) reject('RECEIPT_DECISION_DUPLICATE');
    seen.add(decisionKey);
  }
  return receipt;
}

export async function parseAnnotationReviewReceiptJson(source, verifiedHandoff) {
  if (typeof source !== 'string') reject('RECEIPT_JSON_NOT_TEXT');
  let value;
  try { value = JSON.parse(source); } catch { reject('RECEIPT_JSON_INVALID'); }
  return validateAnnotationReviewReceipt(value, verifiedHandoff);
}
