import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { prepareQuickSource, validateReviewTargets, matchesQuickSource, canonicalQuickJson } from '../src/review-targets.mjs';
import { importQuickAnnotationDraft } from '../src/local-video-review.mjs';
import { summarizeObservedLosses } from '../src/local-loss-insights.mjs';
const text = await readFile(new URL('./fixtures/review-targets/quick-input.json', import.meta.url), 'utf8');
const output = JSON.parse(await readFile(new URL('./fixtures/review-targets/targets.json', import.meta.url), 'utf8'));
const source = await prepareQuickSource(text);
let cases = 0;
function test(name, operation) { operation(); cases++; }
test('MainDex canonical SHA exact', () => assert.equal(source.hash, 'ac38316ea8dd90fb82ecf9fce565e2fe9ec2e3166e90250ae535e138ca7bdad5'));
test('exact MainDex output accepted', () => assert.equal(validateReviewTargets(output, source), output));
const shuffled = Object.fromEntries(Object.entries(JSON.parse(text)).reverse());
const reordered = await prepareQuickSource(JSON.stringify(shuffled, null, 4));
test('key order and whitespace do not change canonical SHA', () => assert.equal(reordered.hash, source.hash));
test('Unicode is preserved', () => assert.equal(canonicalQuickJson({ z: '中文🏓', a: 1 }), '{"a":1,"z":"中文🏓"}'));
test('unsupported fractional numbers rejected without guessed hashes', () => assert.throws(() => canonicalQuickJson({ a: 0.5 })));
test('lone surrogate rejected', () => assert.throws(() => canonicalQuickJson('\ud800')));
test('A exact producer target IDs', () => assert.deepEqual(output.review_targets.find((t) => t.subject_role === 'player' && t.observed_rally_stage === 'END_AFTER_3_4_CONTACTS').point_ids, [2, 4, 6].map((n) => source.points[n - 1].point_id)));
test('unknown stage excluded from N', () => { const m = output.athletes[0].observed_stages.END_AFTER_3_4_CONTACTS; assert.equal(m.denominator, 3); assert.equal(m.unknown_count, 2); assert.equal(output.unknown_stage_count, 2); });
for (const [name, mutate] of Object.entries({
  version: (r) => { r.contract_version = 'ptti.review-targets/9'; },
  missing: (r) => { delete r.athletes; },
  extra: (r) => { r.made_up_permission = true; },
  hash: (r) => { r.canonical_input_sha256 = '0'.repeat(64); },
  identity: (r) => { r.dataset.dataset_id = 'another-dataset'; },
  inputVersion: (r) => { r.input_contract_version = 'ptti.quick-annotation/0.1'; },
  source: (r) => { r.dataset.source_id = 'unrelated-source'; },
  rights: (r) => { r.dataset.rights_status = 'ALLOWED'; },
  mediaHash: (r) => { r.dataset.source_video_sha256 = 'a'.repeat(64); },
  eligibility: (r) => { r.review_targets[0].playback_eligibility = 'BOUND'; },
  duplicate: (r) => { r.review_targets.push(r.review_targets[0]); },
  reference: (r) => { r.review_targets[0].point_ids[0] = 'unrelated/p001'; },
  numericType: (r) => { r.review_targets[0].lost_count = '3'; },
  denominator: (r) => { r.athletes[0].observed_stages.END_AFTER_3_4_CONTACTS.denominator = 5; },
  groupConflict: (r) => { r.athletes[0].score.point_ids.lost[0] = source.points[0].point_id; },
  omittedTarget: (r) => { r.review_targets.pop(); },
  duplicateRole: (r) => { r.athletes[1] = r.athletes[0]; },
  observations: (r) => { r.observations[0].target_id = 'unknown-target'; },
})) test(`reject ${name}`, () => { const r = structuredClone(output); mutate(r); assert.throws(() => validateReviewTargets(r, source)); });
test('reject without original Quick source', () => assert.throws(() => validateReviewTargets(output, null)));
test('bad JSON rejected', () => assert.throws(() => JSON.parse('{broken')));
const changed = JSON.parse(text); changed.points[0].winner = 'opponent';
const changedSource = await prepareQuickSource(JSON.stringify(changed));
test('same IDs with changed winner reject old report', () => assert.throws(() => validateReviewTargets(output, changedSource), /hash/));
const current = importQuickAnnotationDraft(JSON.parse(text)).value;
test('current normalized draft matches original input', () => assert.equal(matchesQuickSource(source, current.points, current.game_contexts), true));
test('confirmation and session flags do not change source identity', () => assert.equal(matchesQuickSource(source, current.points.map((p) => ({ ...p, start_confirmed: true, end_confirmed: true, bound_video_identity: 'local-session:test' })), current.game_contexts), true));
test('changed timestamp invalidates source match', () => assert.equal(matchesQuickSource(source, current.points.map((p, i) => i === 0 ? { ...p, start_seconds: 0 } : p), current.game_contexts), false));
test('changed winner invalidates source match', () => assert.equal(matchesQuickSource(source, current.points.map((p, i) => i === 0 ? { ...p, winner: 'PLAYER_B' } : p), current.game_contexts), false));
test('changed rules invalidate source match', () => assert.equal(matchesQuickSource(source, current.points, { 1: { ...current.game_contexts[1], first_server: 'PLAYER_B' } }), false));
test('UNKNOWN populations differ when p014 winner is unknown', () => {
  const rows = current.points.map((p, i) => i === 13 ? { ...p, winner: 'UNKNOWN' } : p);
  const basic = summarizeObservedLosses(rows, 1, 'PLAYER_A');
  assert.equal(rows.filter((p) => p.observed_rally_stage === 'UNKNOWN').length, 2);
  assert.equal(basic.unknown_stages, 1);
  assert.equal(basic.recorded, 18);
  assert.equal(basic.stages.END_AFTER_3_4_CONTACTS.losses, 3);
});

test('original imported input and producer output not mutated', () => { assert.equal(JSON.parse(text).points[0].winner, 'player'); assert.equal(output.dataset.rights_status, 'UNKNOWN'); });
console.log(`Review Targets PASS: ${cases} cases; producer SHA, p002/p004/p006, N=3, UNKNOWN=2, partitions, versions, stale input, types and no media promotion.`);
