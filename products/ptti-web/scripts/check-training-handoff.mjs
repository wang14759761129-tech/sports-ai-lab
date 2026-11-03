import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import {
  ANNOTATION_RECEIPT_VERSION,
  parseAnnotationReviewReceiptJson,
  parseTrainingHandoffJson,
  stableJson,
  TRAINING_HANDOFF_VERSION,
  TRAINING_PROTOCOL_FIELDS,
  validateTrainingHandoff,
} from '../src/training-handoff.mjs';

const fixturePath = process.env.PTTI_TRAINING_HANDOFF_FIXTURE;
if (!fixturePath) throw new Error('Set PTTI_TRAINING_HANDOFF_FIXTURE to the read-only MainDex handoff JSON');
const source = await readFile(fixturePath, 'utf8');
const sourcePackage = JSON.parse(source);
const verified = await parseTrainingHandoffJson(source);
const pkg = verified.package;
const report = verified.report;
const quality = verified.quality;
assert.equal(pkg.package_version, TRAINING_HANDOFF_VERSION);
assert.equal(pkg.visibility, 'PRIVATE_REVIEW_ONLY');
assert.equal(pkg.protocol_fields.length, 21);
assert.deepEqual(pkg.protocol_fields, TRAINING_PROTOCOL_FIELDS);
assert.equal(verified.dataClass, 'SIMULATED_ONLY');
assert.equal(report.dataset.dataset_class, 'SIMULATED_ONLY');
assert.equal(report.dataset.evidence_status, 'SIMULATED_ONLY');
assert.equal(report.dataset.source_video_sha256, null);
assert.equal(report.sample.point_count, 24);
assert.equal(report.point_records.length, 24);
assert.equal(report.metrics.third_ball_attack_rate.numerator, 12);
assert.equal(report.metrics.third_ball_attack_rate.denominator, 18);
assert.equal(report.metrics.third_ball_attack_rate.missing_count, 2);
assert.equal(report.metrics.third_ball_point_conversion.denominator, 12);
assert.equal(quality.status, 'STRUCTURE_CHECKED_HUMAN_REVIEW_REQUIRED');
assert.equal(quality.findings.length, 24);
assert.deepEqual(quality.metric_flags.map((flag) => [flag.key, flag.denominator, flag.missing_count]), [
  ['third_ball_attack_rate', 18, 2], ['rally_length_mean', 22, 2],
]);
assert.deepEqual(quality.coverage.serve_side, { known: 12, unknown: 6, unclear: 6, not_applicable: 0 });
assert.equal(verified.actualCsvSha256, 'f5ec0fddebc5d108a89a42ce2acae0e8d8e12e6bca5fbb8d6b7df26dd9792ee0');
assert.equal(verified.sourceIndependentlyVerified, false);

let negativeCount = 0;
async function rejectsHandoff(label, mutate, expectedCode) {
  const candidate = structuredClone(sourcePackage);
  mutate(candidate);
  await assert.rejects(Promise.resolve().then(() => validateTrainingHandoff(candidate)), expectedCode ? new RegExp(expectedCode) : undefined, label);
  negativeCount += 1;
}

await assert.rejects(parseTrainingHandoffJson('{broken json'), /HANDOFF_JSON_INVALID/); negativeCount += 1;
await rejectsHandoff('unknown package version', (candidate) => { candidate.package_version = 'ptti.training-handoff/0.2'; }, 'HANDOFF_VERSION_UNSUPPORTED');
await rejectsHandoff('public visibility is refused', (candidate) => { candidate.visibility = 'PUBLIC'; }, 'HANDOFF_VISIBILITY_REJECTED');
await rejectsHandoff('missing root field is refused', (candidate) => { delete candidate.quality; }, 'HANDOFF_ROOT_FIELDS_INVALID');
await rejectsHandoff('unexpected root field is refused', (candidate) => { candidate.downloadable = true; }, 'HANDOFF_ROOT_FIELDS_INVALID');
await rejectsHandoff('protocol field reorder is refused', (candidate) => { candidate.protocol_fields.reverse(); }, 'HANDOFF_PROTOCOL_FIELDS_MISMATCH');
await rejectsHandoff('wrong CSV type is refused', (candidate) => { candidate.csv_utf8 = []; }, 'HANDOFF_CSV_FIELDS_INVALID');
await rejectsHandoff('stale CSV SHA is refused', (candidate) => { candidate.csv_sha256 = '0'.repeat(64); }, 'HANDOFF_CSV_HASH_MISMATCH');
await rejectsHandoff('report version mismatch is refused', (candidate) => { candidate.report.report_version = 'ptti.training-review/9'; }, 'Unsupported');
await rejectsHandoff('missing quality field is refused', (candidate) => { delete candidate.quality.coverage; }, 'HANDOFF_QUALITY_FIELDS_INVALID');
await rejectsHandoff('wrong quality type is refused', (candidate) => { candidate.quality.coverage = []; }, 'HANDOFF_QUALITY_RECOMPUTATION_MISMATCH');
await rejectsHandoff('quality status promotion is refused', (candidate) => { candidate.quality.vision_status = 'PASS'; }, 'HANDOFF_QUALITY_RECOMPUTATION_MISMATCH');
await rejectsHandoff('review queue tampering is refused', (candidate) => { candidate.quality.findings = []; }, 'HANDOFF_QUALITY_RECOMPUTATION_MISMATCH');
await rejectsHandoff('broken finding point ID is refused', (candidate) => { candidate.quality.findings[0].point_id = 'orphan'; }, 'HANDOFF_QUALITY_RECOMPUTATION_MISMATCH');
await rejectsHandoff('report point ID reference is refused', (candidate) => { candidate.report.point_refs[0].point_id = 'orphan'; }, 'point_id');
await rejectsHandoff('duplicate point ID is refused', (candidate) => { candidate.report.point_records[1].point_id = candidate.report.point_records[0].point_id; }, 'point_id');
await rejectsHandoff('CSV record ordinal mismatch is refused', (candidate) => { candidate.report.point_records[0].csv_record_number = 99; }, 'CSV');
await rejectsHandoff('row hash mismatch is refused', (candidate) => { candidate.report.point_records[0].annotation_row_sha256 = '0'.repeat(64); }, 'row');
await rejectsHandoff('wrong point field type is refused', (candidate) => { candidate.report.point_records[0].fields.rally_length = '5'; }, 'rally_length');
await rejectsHandoff('unknown evidence state cannot be promoted', (candidate) => { candidate.report.dataset.evidence_status = 'PLAYBACK_PASS'; }, 'evidence');
await rejectsHandoff('simulated data cannot be relabelled human', (candidate) => { candidate.report.dataset.dataset_class = 'HUMAN_ANNOTATION'; }, 'dataset');
await rejectsHandoff('simulated package cannot add a human manifest', (candidate) => { candidate.inputs.manifest = {}; }, 'HANDOFF_SIMULATED_DECLARATION_INVALID');
await rejectsHandoff('simulated declaration SHA mismatch is refused', (candidate) => { candidate.inputs.declaration.csv_sha256 = '0'.repeat(64); }, 'HANDOFF_SIMULATED_DECLARATION_INVALID');
await rejectsHandoff('invalid declaration object type is refused', (candidate) => { candidate.inputs.declaration = []; }, 'HANDOFF_SIMULATED_DECLARATION_INVALID');

const changedCsv = structuredClone(sourcePackage);
changedCsv.csv_utf8 = changedCsv.csv_utf8.replace('serve_side,serve_length', 'serve_side,serve_side');
const changedCsvHash = createHash('sha256').update(changedCsv.csv_utf8, 'utf8').digest('hex');
changedCsv.csv_sha256 = changedCsvHash;
changedCsv.inputs.declaration.csv_sha256 = changedCsvHash;
changedCsv.report.dataset.annotation_csv_sha256 = changedCsvHash;
await assert.rejects(Promise.resolve().then(() => validateTrainingHandoff(changedCsv)), /HANDOFF_CSV_HEADER_MISMATCH/); negativeCount += 1;

const alteredRowCsv = structuredClone(sourcePackage);
alteredRowCsv.csv_utf8 = alteredRowCsv.csv_utf8.replace(',player,opponent,0,0,', ',player,opponent,0,1,');
const alteredHash = createHash('sha256').update(alteredRowCsv.csv_utf8, 'utf8').digest('hex');
alteredRowCsv.csv_sha256 = alteredHash;
alteredRowCsv.inputs.declaration.csv_sha256 = alteredHash;
alteredRowCsv.report.dataset.annotation_csv_sha256 = alteredHash;
await assert.rejects(Promise.resolve().then(() => validateTrainingHandoff(alteredRowCsv)), /HANDOFF_POINT_TRACE_MISMATCH/); negativeCount += 1;

const receiptRow = report.point_records[0];
const receipt = {
  receipt_version: ANNOTATION_RECEIPT_VERSION,
  package_content_sha256: createHash('sha256').update(stableJson(sourcePackage), 'utf8').digest('hex'),
  dataset_class: 'SIMULATED_ONLY',
  review: {
    review_version: 'ptti.annotation-review/0.1', annotation_csv_sha256: pkg.csv_sha256,
    reviewer_ref: 'QA_TEST_ONLY', reviewed_at: '2026-10-14T12:00:00+08:00',
    decisions: [{ point_id: receiptRow.point_id, annotation_row_sha256: receiptRow.annotation_row_sha256, field: 'serve_side', disposition: 'UNRESOLVED', reason: 'QA test only; not a human audit.' }],
  },
  status: 'DECLARED_NOT_INDEPENDENTLY_AUDITED', vision_status: 'NOT_TESTED', source_annotations_changed: false,
};
const receiptCopy = structuredClone(receipt);
const acceptedReceipt = await parseAnnotationReviewReceiptJson(JSON.stringify(receipt), verified);
assert.equal(acceptedReceipt.dataset_class, 'SIMULATED_ONLY');
assert.equal(acceptedReceipt.status, 'DECLARED_NOT_INDEPENDENTLY_AUDITED');
assert.equal(acceptedReceipt.source_annotations_changed, false);
assert.deepEqual(receipt, receiptCopy, 'receipt validation never mutates the imported receipt');

async function rejectsReceipt(label, mutate, expectedCode) {
  const candidate = structuredClone(receipt);
  mutate(candidate);
  await assert.rejects(parseAnnotationReviewReceiptJson(JSON.stringify(candidate), verified), expectedCode ? new RegExp(expectedCode) : undefined, label);
  negativeCount += 1;
}

await assert.rejects(parseAnnotationReviewReceiptJson('{broken', verified), /RECEIPT_JSON_INVALID/); negativeCount += 1;
await rejectsReceipt('unknown receipt version is refused', (candidate) => { candidate.receipt_version = 'ptti.annotation-review-receipt/9'; }, 'RECEIPT_VERSION_UNSUPPORTED');
await rejectsReceipt('receipt bound to another package is refused', (candidate) => { candidate.package_content_sha256 = '0'.repeat(64); }, 'RECEIPT_PACKAGE_HASH_MISMATCH');
await rejectsReceipt('receipt CSV hash mismatch is refused', (candidate) => { candidate.review.annotation_csv_sha256 = '0'.repeat(64); }, 'RECEIPT_REVIEW_INVALID');
await rejectsReceipt('receipt with broken point row SHA is refused', (candidate) => { candidate.review.decisions[0].annotation_row_sha256 = '0'.repeat(64); }, 'RECEIPT_DECISION_REFERENCE_MISMATCH');
await rejectsReceipt('receipt with duplicate point-field decisions is refused', (candidate) => { candidate.review.decisions.push(structuredClone(candidate.review.decisions[0])); }, 'RECEIPT_DECISION_DUPLICATE');
await rejectsReceipt('receipt cannot claim changed source annotations', (candidate) => { candidate.source_annotations_changed = true; }, 'RECEIPT_STATUS_INVALID');
await rejectsReceipt('receipt cannot upgrade simulated identity', (candidate) => { candidate.dataset_class = 'HUMAN_ANNOTATION'; }, 'RECEIPT_DATASET_CLASS_MISMATCH');
await rejectsReceipt('receipt requires timezone-qualified review time', (candidate) => { candidate.review.reviewed_at = '2026-10-14T12:00:00'; }, 'RECEIPT_REVIEW_INVALID');
await rejectsReceipt('receipt requires a disposition from the contract', (candidate) => { candidate.review.decisions[0].disposition = 'PASS'; }, 'RECEIPT_DECISION_INVALID');

console.log(`Training handoff quality check PASS: MainDex ${TRAINING_HANDOFF_VERSION} sample verified (24 SIMULATED_ONLY points, 24 review findings, SHA-256 ${verified.actualCsvSha256}); report metrics and quality queue cross-checked against embedded CSV rows; no source-video truth or rights are claimed; optional receipt validation passed; ${negativeCount} malformed, tampered, unknown-version, missing-field, broken-link, bad-type, status-promotion, and stale-receipt cases rejected.`);
