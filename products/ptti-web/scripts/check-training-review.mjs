import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import {
  independentSourceVerification,
  metricPointIds,
  parseTrainingReviewJson,
  TRAINING_REVIEW_VERSION,
} from '../src/training-review.mjs';

const fixturePath = process.env.PTTI_TRAINING_REVIEW_FIXTURE;
if (!fixturePath) throw new Error('Set PTTI_TRAINING_REVIEW_FIXTURE to the read-only MainDex simulated report JSON');
const raw = await readFile(fixturePath, 'utf8');
const valid = parseTrainingReviewJson(raw);
const editedPath = process.env.PTTI_TRAINING_REVIEW_EDITED_FIXTURE ?? path.join(path.dirname(fixturePath), 'simulated-report-edited.json');
const edited = parseTrainingReviewJson(await readFile(editedPath, 'utf8'));
assert.equal(valid.report_version, TRAINING_REVIEW_VERSION);
assert.equal(valid.dataset.dataset_class, 'SIMULATED_ONLY');
assert.equal(valid.sample.point_count, 24);
assert.equal(valid.point_refs.length, 24);
assert.equal(valid.point_records.length, 24);
assert.equal(valid.metrics.server_point_win_rate.numerator, 13);
assert.equal(valid.metrics.server_point_win_rate.denominator, 24);
assert.equal(valid.metrics.third_ball_attack_rate.numerator, 12);
assert.equal(valid.metrics.third_ball_attack_rate.denominator, 18);
assert.equal(valid.metrics.third_ball_attack_rate.sample_count, 20);
assert.equal(valid.metrics.third_ball_attack_rate.missing_count, 2);
assert.equal(valid.metrics.third_ball_point_conversion.numerator, 7);
assert.equal(valid.metrics.third_ball_point_conversion.denominator, 12);
assert.equal(valid.metrics.key_point_player_win_rate.numerator, 6);
assert.equal(valid.metrics.key_point_player_win_rate.denominator, 10);
assert.equal(valid.metrics.rally_length_mean.numerator, 148);
assert.equal(valid.metrics.rally_length_mean.denominator, 22);
assert.equal(edited.dataset.annotation_provenance.method, 'SIMULATED_INTERACTIVE_EDIT');
assert.equal(edited.dataset.annotation_provenance.edit.field, 'rally_length');
assert.equal(edited.dataset.annotation_provenance.edit.after, 7);
assert.equal(edited.metrics.rally_length_mean.numerator, 150);
assert.equal(metricPointIds(valid, 'server_point_win_rate').length, 24);
assert.equal(metricPointIds(valid, 'third_ball_attack_rate').length, 18);
assert.equal(metricPointIds(valid, 'key_point_player_win_rate').length, valid.metrics.key_point_player_win_rate.denominator);
assert.equal(metricPointIds(valid, 'serve_length').length, 12);
assert.deepEqual(independentSourceVerification(valid), {
  sourceAvailable: false, evidenceAvailable: false, recordedCsvHashAvailable: true, status: 'CANNOT_INDEPENDENTLY_VERIFY',
});

function rejects(label, mutate) {
  const candidate = structuredClone(valid);
  mutate(candidate);
  assert.throws(() => parseTrainingReviewJson(JSON.stringify(candidate)), undefined, label);
}

assert.throws(() => parseTrainingReviewJson('{broken json'), /Invalid JSON/, 'malformed JSON is rejected');
assert.throws(() => parseTrainingReviewJson(JSON.stringify({ report_version: 'ptti.training-review/0.2' })), /Unsupported/, 'unknown version is rejected');
rejects('missing required sample field', (report) => { delete report.sample.point_count; });
rejects('missing point record', (report) => { report.point_records.pop(); });
rejects('broken point_id reference', (report) => { report.point_refs[0].point_id = 'SIMULATED_ONLY:orphan'; });
rejects('duplicate point_id', (report) => { report.point_records[1].point_id = report.point_records[0].point_id; });
rejects('wrong field type', (report) => { report.point_records[0].fields.rally_length = '5'; });
rejects('wrong scalar type', (report) => { report.sample.point_count = '24'; });
rejects('unknown dataset evidence state', (report) => { report.dataset.evidence_status = 'PLAYBACK_PASS'; });
rejects('simulated report cannot be relabeled as human', (report) => { report.dataset.dataset_class = 'HUMAN_ANNOTATION'; });
rejects('metric value inconsistent with denominator', (report) => { report.metrics.third_ball_attack_rate.value = 0.9; });
rejects('metric counts inconsistent with the actual point annotations', (report) => { report.metrics.third_ball_attack_rate.numerator = 11; report.metrics.third_ball_attack_rate.value = 11 / 18; });
rejects('distribution inconsistent with point annotations', (report) => { report.distributions.serve_length.numerator = { short: 3, half_long: 5, long: 4 }; });
rejects('metric evidence promoted above dataset', (report) => { report.metrics.third_ball_attack_rate.evidence_status = 'DECLARED_NOT_INDEPENDENTLY_AUDITED'; });
rejects('broken score trace point reference', (report) => { report.score_trace[0].point_id = 'missing-point'; });
rejects('CSV ordinal mismatch', (report) => { report.point_records[0].csv_record_number = 99; });
rejects('row hash reference mismatch', (report) => { report.point_refs[0].annotation_row_sha256 = '0'.repeat(64); });
rejects('timestamp cannot claim bound playback', (report) => { report.point_refs[0].timestamp_binding = 'PTS_VERIFIED'; });
rejects('unsupported protocol revision', (report) => { report.dataset.protocol.version = '0.4'; });

console.log('Training review import PASS: real MainDex base and edited reports parsed; 24 point IDs and CSV ordinals cross-check; all displayed metrics and serve distributions recomputed against embedded points; simulated edit lineage retained; source/evidence explicitly not independently verified; 19 malformed, unknown-version, missing-field, broken-reference, duplicate-ID, bad-type and status-promotion cases rejected.');
