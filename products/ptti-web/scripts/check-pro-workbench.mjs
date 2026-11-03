import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  computeDemoStats,
  computeDemoSummary,
  applyDemoEdits,
  applyDemoEditsWithLineage,
  createDemoExport,
  DEMO_BUNDLE_URL,
  DEMO_DATASET_ID,
  DEMO_MATCH_ID,
  DEMO_STORAGE_KEY,
  loadDemoRecord,
  MATCH_INTELLIGENCE_CONTRACT,
  POINT_FIELDS,
  saveDemoRecord,
  updateDemoPoint,
  validateDemoRecord,
  validatePoint,
  verifyDemoLineage,
} from '../src/pro-demo.mjs';

const sourceText = await readFile(new URL(`../public${DEMO_BUNDLE_URL}`, import.meta.url), 'utf8');
const source = JSON.parse(sourceText);
assert.equal(MATCH_INTELLIGENCE_CONTRACT, 'ptti.match-intelligence/0.1');
assert.equal(validateDemoRecord(source).ok, true);
assert.equal(POINT_FIELDS.length, 21);
assert.equal(source.points.length, 24, 'the Web consumes MainDex\'s full 24-point deterministic fixture');
assert.deepEqual(Object.keys(source).sort(), ['contract_version', 'dataset', 'points']);
assert.deepEqual(Object.keys(source.dataset).sort(), ['dataset_class', 'dataset_id', 'match_id', 'provenance', 'source_binding', 'source_protocol']);
assert.equal(source.dataset.dataset_class, 'SIMULATED_ONLY');
assert.equal(source.dataset.match_id, DEMO_MATCH_ID);
assert.equal(source.dataset.dataset_id, DEMO_DATASET_ID);
assert.equal(source.dataset.source_binding.status, 'NOT_APPLICABLE_SIMULATED');
assert.deepEqual(source.dataset.source_binding, { status: 'NOT_APPLICABLE_SIMULATED', source_id: null, source_sha256: null, timeline_id: null, time_base: null });
for (const point of source.points) {
  assert.equal(Object.keys(point).length, 21);
  assert.deepEqual(Object.keys(point).sort(), [...POINT_FIELDS].sort());
  assert.equal(point.match_id, DEMO_MATCH_ID);
  assert.equal(validatePoint(point).ok, true);
}

const initialStats = computeDemoStats(source.points);
assert.equal(initialStats.total, 24);
assert.equal(initialStats.serveLength.observed, source.points.filter((point) => ['short', 'half_long', 'long'].includes(point.serve_length)).length);
assert.equal(initialStats.serveSpin.observed, source.points.filter((point) => ['backspin', 'sidespin', 'topspin', 'no_spin', 'mixed'].includes(point.serve_spin)).length);
const initialAttackDenominator = source.points.filter((point) => ['yes', 'no'].includes(point.third_ball_attack)).length;
assert.equal(initialStats.thirdBall.classified, initialAttackDenominator);
assert.equal(initialStats.thirdBall.yes, source.points.filter((point) => point.third_ball_attack === 'yes').length);
assert.equal(initialStats.thirdBall.no, source.points.filter((point) => point.third_ball_attack === 'no').length);
assert.equal(initialStats.thirdBall.rate, initialAttackDenominator ? initialStats.thirdBall.yes / initialAttackDenominator : null);
const noRows = computeDemoStats([]);
assert.equal(noRows.total, 0);
assert.equal(noRows.thirdBall.rate, null, 'empty data stays not estimable');
const sourceSummary = computeDemoSummary(source.points);
assert.equal(sourceSummary.point_wins.denominator, 24);
assert.deepEqual(sourceSummary.point_wins.counts, { player: 13, opponent: 11 });
assert.equal(sourceSummary.third_ball_attack_rate.numerator, 12);
assert.equal(sourceSummary.third_ball_attack_rate.denominator, 18);
assert.equal(sourceSummary.third_ball_immediate_outcome.rate.denominator, 12);
assert.equal(sourceSummary.third_ball_point_conversion.denominator, 12);
assert.equal(sourceSummary.rally_length.denominator, 22);

const protocolParity = await applyDemoEdits(source, updateDemoPoint(source, { ...source.points[0], serve_length: 'long' }));
assert.equal(protocolParity.dataset.dataset_id, 'SIMULATED_ONLY:edit-a04094cba859788df424f18a');
assert.equal(protocolParity.dataset.provenance.parent_input_sha256, '48a86acd50237d416c1544344ccbfc496ef073240f3b33dc57d122d937d83e4c');
assert.deepEqual(protocolParity.dataset.provenance.edit, {
  point_id: 'SIMULATED_ONLY%3Agoal07-match-001/g01/p001',
  field: 'serve_length', before: 'unclear', after: 'long',
}, 'deterministic edit lineage matches MainDex output');

const originalPoint = source.points[0];
const editedPoint = { ...originalPoint, serve_length: 'long', third_ball_attack: 'no', third_ball_side: 'not_applicable', third_ball_outcome: 'not_applicable' };
const desired = updateDemoPoint(source, editedPoint);
const updatedTransition = await applyDemoEditsWithLineage(source, desired, [source]);
const updated = updatedTransition.record;
const updatedHistory = updatedTransition.history;
assert.notEqual(updated, source);
assert.notEqual(updated.points, source.points);
assert.equal(source.points[0].third_ball_attack, originalPoint.third_ball_attack, 'edits never mutate the source fixture');
assert.equal(updated.points.length, 24, 'editing changes an existing point, not the shared sequence');
assert.equal(updated.dataset.provenance.method, 'SIMULATED_INTERACTIVE_EDIT');
assert.match(updated.dataset.provenance.parent_dataset_id, /^SIMULATED_ONLY:/);
assert.match(updated.dataset.provenance.parent_input_sha256, /^[0-9a-f]{64}$/);
assert.equal(updated.dataset.provenance.edit.point_id, 'SIMULATED_ONLY%3Agoal07-match-001/g01/p001');
assert.equal(updated.dataset.provenance.edit.after, 'not_applicable');
assert.match(updated.dataset.dataset_id, /^SIMULATED_ONLY:edit-[0-9a-f]{24}$/);
assert.deepEqual(updated.dataset.source_binding, source.dataset.source_binding, 'edited synthetic data stays unbound from real sources/timelines');
const updatedStats = computeDemoStats(updated.points);
assert.equal(updatedStats.serveLength.long, initialStats.serveLength.long + (originalPoint.serve_length === 'long' ? 0 : 1));
assert.equal(updatedStats.thirdBall.yes, initialStats.thirdBall.yes - (originalPoint.third_ball_attack === 'yes' ? 1 : 0));
assert.equal(updatedStats.thirdBall.no, initialStats.thirdBall.no + (originalPoint.third_ball_attack === 'no' ? 0 : 1));
assert.equal(updatedStats.total, 24);
const exported = await createDemoExport(updated, updatedHistory);
assert.deepEqual(Object.keys(exported).sort(), ['analysis', 'export_format', 'input', 'lineage']);
assert.deepEqual(Object.keys(exported.input).sort(), ['contract_version', 'dataset', 'points']);
assert.equal(exported.analysis.analysis_version, MATCH_INTELLIGENCE_CONTRACT);
assert.equal(exported.input.dataset.dataset_class, 'SIMULATED_ONLY');
assert.equal(exported.input.points.length, 24);
assert.equal(exported.input.points[0].notes, originalPoint.notes);
assert.equal(exported.lineage.snapshots.length, updatedHistory.length);
const exportedText = JSON.stringify(exported);
assert(!exportedText.includes('web-match:'));
assert(!exportedText.includes('Fan Zhendong'));
assert(!exportedText.includes('source_sha256":"[a-f0-9]'), 'no invented source hash is attached');

const reject = (bundle, label) => assert.equal(validateDemoRecord(bundle).ok, false, label);
reject({ ...source, contract_version: 'ptti.match-intelligence/0.2' }, 'unknown contract versions reject');
reject({ ...source, unexpected: true }, 'extra root properties reject');
reject({ ...source, dataset: { ...source.dataset, unexpected: true } }, 'extra dataset properties reject');
reject({ ...source, dataset: { ...source.dataset, dataset_class: 'HUMAN_ANNOTATION' } }, 'public human data cannot enter the built-in SIMULATED_ONLY demo slot');
reject({ ...source, dataset: { ...source.dataset, match_id: 'web-match:real-match' } }, 'real match IDs reject');
reject({ ...source, dataset: { ...source.dataset, provenance: { method: 'DETERMINISTIC_ORIGINAL_GENERATOR', seed: 20261013, generated_on: '2026-02-30' } } }, 'invalid provenance date rejects');
reject({ ...source, dataset: { ...source.dataset, source_binding: { ...source.dataset.source_binding, source_id: 'invented-source' } } }, 'simulated data cannot bind to any real source');
reject({ ...source, dataset: { ...source.dataset, source_protocol: { ...source.dataset.source_protocol, version: '0.4' } } }, 'unknown protocol versions reject');
const missingLineageField = structuredClone(updated);
delete missingLineageField.dataset.provenance.parent_input_sha256;
reject(missingLineageField, 'missing parent input SHA field rejects');
const incompleteEdit = structuredClone(updated);
delete incompleteEdit.dataset.provenance.edit.before;
reject(incompleteEdit, 'incomplete before/after edit record rejects');
reject({ ...source, points: [source.points[0], source.points[0]] }, 'duplicate natural point IDs reject');
reject({ ...source, points: [{ ...source.points[0], match_id: 'web-match:real-match' }, ...source.points.slice(1)] }, 'foreign point-to-match references reject');
reject({ ...source, points: [{ ...source.points[0], third_ball_attack: 'certain' }, ...source.points.slice(1)] }, 'unknown enum values reject');
reject({ ...source, points: [{ ...source.points[0], extra_field: 'conflict' }, ...source.points.slice(1)] }, 'extra point fields reject');
assert.equal(validatePoint({ ...source.points[0], match_id: 'web-match:real-match' }).ok, false);
assert.throws(() => updateDemoPoint(source, { ...editedPoint, game_number: 99 }), /does not exist/);
await assert.rejects(() => createDemoExport({ ...updated, dataset: { ...updated.dataset, match_id: 'web-match:real-match' } }, updatedHistory));
assert.throws(() => JSON.parse('{broken JSON'), SyntaxError);

const memory = new Map();
const storage = { getItem: (key) => memory.get(key) ?? null, setItem: (key, value) => memory.set(key, value) };
assert.deepEqual((await loadDemoRecord(storage, source)).record, source);
assert.equal((await loadDemoRecord(storage, source)).issue, null);
assert.equal((await saveDemoRecord(storage, updated, updatedHistory)).ok, true);
assert.deepEqual((await loadDemoRecord(storage, source)).record, updated);
assert.equal((await loadDemoRecord(storage, source)).history.length, updatedHistory.length);
assert.equal(memory.has(DEMO_STORAGE_KEY), true);
memory.set(DEMO_STORAGE_KEY, '{bad json');
assert.equal((await loadDemoRecord(storage, source)).issue, 'invalid');
assert.deepEqual((await loadDemoRecord(storage, source)).record, source, 'corrupt local state recovers from the exact source fixture');
memory.set(DEMO_STORAGE_KEY, JSON.stringify({ ...updated, contract_version: 'ptti.match-intelligence/99' }));
assert.equal((await loadDemoRecord(storage, source)).issue, 'invalid');
assert.deepEqual((await loadDemoRecord(storage, source)).record, source, 'unsupported saved version is discarded from view, not promoted');
const blocked = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
assert.equal((await loadDemoRecord(blocked, source)).issue, 'unavailable');
assert.equal((await saveDemoRecord(blocked, updated, updatedHistory)).ok, false);
assert.equal((await loadDemoRecord(null, source)).issue, 'unavailable');
assert.equal((await saveDemoRecord(null, updated, updatedHistory)).ok, false);
assert.equal((await loadDemoRecord(storage, { contract_version: MATCH_INTELLIGENCE_CONTRACT, dataset: {}, points: [] })).record, null, 'invalid source JSON never produces an empty broken UI record');

const editedChainResult = await applyDemoEditsWithLineage(updated, updateDemoPoint(updated, { ...updated.points[1], serve_spin: 'topspin' }), updatedHistory);
const editedChain = editedChainResult.record;
assert.equal(editedChain.dataset.provenance.method, 'SIMULATED_INTERACTIVE_EDIT');
assert.equal(editedChain.dataset.provenance.parent_dataset_id, updated.dataset.dataset_id, 'each edit points to the immediate prior simulated dataset');
assert.equal(editedChain.points[0].third_ball_attack, 'no');
assert.equal(editedChain.points[1].serve_spin, 'topspin');
await assert.rejects(() => applyDemoEdits(source, { ...desired, dataset: { ...desired.dataset, source_binding: { ...desired.dataset.source_binding, source_sha256: 'a'.repeat(64) } } }), /shared contract|source binding/i);
await assert.rejects(() => applyDemoEdits(source, updateDemoPoint(source, { ...source.points[0], server: 'opponent' })), /not editable/);

const badSha = structuredClone(updatedHistory);
badSha.at(-1).dataset.provenance.parent_input_sha256 = 'a'.repeat(64);
assert.equal((await verifyDemoLineage(updated, badSha)).ok, false, 'incorrect parent SHA is rejected against retained parent snapshot');
assert.equal((await verifyDemoLineage(updated, [source])).ok, false, 'missing derived lineage snapshot is rejected');
assert.equal((await verifyDemoLineage(updated, [])).ok, false, 'missing all lineage snapshots is rejected');
assert.equal((await verifyDemoLineage(updated, [...updatedHistory, structuredClone(updated)])).ok, false, 'duplicate dataset_id is rejected');
const badParent = structuredClone(updatedHistory);
badParent.at(-1).dataset.provenance.parent_dataset_id = 'SIMULATED_ONLY:missing-parent';
assert.equal((await verifyDemoLineage(updated, badParent)).ok, false, 'missing parent dataset is rejected');
const humanAnnotation = structuredClone(source);
humanAnnotation.dataset.dataset_class = 'HUMAN_ANNOTATION';
humanAnnotation.dataset.dataset_id = 'human:manual-sample';
humanAnnotation.dataset.match_id = 'manual:sample';
humanAnnotation.dataset.provenance = { method: 'HUMAN_MANUAL', annotator_ref: 'local', annotated_at: '2026-10-13T09:00:00Z', evidence_ref: 'local-review', annotation_csv_sha256: 'b'.repeat(64), review_status: 'DECLARED_NOT_INDEPENDENTLY_AUDITED' };
humanAnnotation.dataset.source_binding = { status: 'SOURCE_BYTES_HASH_MATCHED_AT_IMPORT', source_id: 'local-source', source_sha256: 'c'.repeat(64), timeline_id: null, time_base: null, timestamp_semantics: 'PROTOCOL_TEXT_ONLY_UNBOUND' };
assert.equal(validateDemoRecord(humanAnnotation).ok, false, 'human CSV annotations are not admitted to the simulated editor');
await assert.rejects(() => applyDemoEdits(humanAnnotation, humanAnnotation), /source CSV and re-import/i);
assert.throws(() => updateDemoPoint(humanAnnotation, { ...source.points[0], serve_length: 'long' }), /source CSV and re-import/i);

const analysisMetrics = sourceSummary;
const savedAfter = computeDemoSummary(updated.points);
assert.equal(savedAfter.third_ball_attack_rate.denominator, analysisMetrics.third_ball_attack_rate.denominator, 'the explicit yes/no eligibility denominator remains correct after changing yes to no');
assert.equal(savedAfter.third_ball_attack_rate.numerator, analysisMetrics.third_ball_attack_rate.numerator - 1);
assert.notEqual(savedAfter.third_ball_attack_rate.value, analysisMetrics.third_ball_attack_rate.value);
assert.deepEqual(source.points[0], originalPoint, 'the original generated dataset remains unchanged');

console.log('Pro workbench data PASS: MainDex 24-point / 21-field contract; exact denominators and descriptive metrics; edit-derived dataset ID and retained SHA-verified parent chain; source unchanged; export includes input, analysis and lineage; malformed, wrong SHA, duplicate IDs, missing parent, HUMAN_ANNOTATION, unknown versions and blocked storage rejected or recovered.');
