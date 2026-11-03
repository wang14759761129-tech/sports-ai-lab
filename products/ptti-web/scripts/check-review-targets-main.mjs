// Offline QA only. The Web application never reads another worktree or invokes Python.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { importQuickAnnotationDraft } from '../src/local-video-review.mjs';
import { summarizeObservedLosses } from '../src/local-loss-insights.mjs';
import { prepareQuickSource, validateReviewTargets } from '../src/review-targets.mjs';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const mainRoot = process.env.PTTI_MAIN_WORKTREE || 'C:\\PTTI-Worktrees\\integration-preview-sprint-0-1';
const producer = '6ea97363b83940e8699fb7a2f40ef4b00a795418';
function run(command, args, cwd = root) {
  const result = spawnSync(command, args, { cwd, encoding: 'utf8', windowsHide: true, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
  assert.equal(result.status, 0, `${command}: ${result.stderr || result.error?.message}`);
  return result.stdout.trim();
}
const engineBlobs = {};
for (const file of ['review_targets.py', 'quick_annotation.py', 'match_intelligence.py', 'scripts/run_review_targets.py']) {
  const relative = `products/ptti-integration/${file}`;
  const expected = run('git', ['rev-parse', `${producer}:${relative}`], mainRoot);
  const actual = run('git', ['hash-object', relative], mainRoot);
  assert.equal(actual, expected, `Main ${file} differs from the delivered engine; review it before testing`);
  engineBlobs[file] = actual;
}
const qa = path.join(root, '.alpha-qa');
await mkdir(qa, { recursive: true });
const input = path.join(root, 'scripts/fixtures/review-targets/quick-input.json');
const output = path.join(qa, 'goal10-6-final-main-generated.json');
run(process.env.PTTI_PYTHON_PATH || 'python', ['-B', path.join(mainRoot, 'products/ptti-integration/scripts/run_review_targets.py'), '--input', input, '--output', output]);
const bytes = await readFile(input);
const source = await prepareQuickSource(bytes.toString('utf8'));
const generated = JSON.parse(await readFile(output, 'utf8'));
assert.deepEqual(generated, JSON.parse(await readFile(path.join(root, 'scripts/fixtures/review-targets/targets.json'), 'utf8')));
const accepted = validateReviewTargets(generated, source); // Actual production consumer, not a test-only oracle.
const target = accepted.review_targets.find((t) => t.subject_role === 'player' && t.observed_rally_stage === 'END_AFTER_3_4_CONTACTS');
assert.deepEqual(target.point_ids, [2, 4, 6].map((n) => source.points[n - 1].point_id));
assert.equal(target.denominator, 3);
assert.equal(target.playback_eligibility, 'NOT_EVALUATED_CURRENT_SESSION');
const receipt = {
  status: 'PASS', producer_commit: producer, engine_git_blobs: engineBlobs,
  san_consumer_git_blob: run('git', ['hash-object', 'src/review-targets.mjs']),
  input_file: input, generated_file: output,
  raw_input_sha256: createHash('sha256').update(bytes).digest('hex'),
  canonical_input_sha256: source.hash, raw_hash_is_not_the_contract_hash: true,
  dataset_id: accepted.dataset.dataset_id, match_id: accepted.dataset.match_id,
  target_point_ids: target.point_ids, denominator: target.denominator,
  playback_eligibility: target.playback_eligibility,
  browser_or_media_acceptance: 'NOT_TESTED_BY_THIS_CHECK',
};
await writeFile(path.join(qa, 'goal10-6-final-cross-runtime.json'), JSON.stringify(receipt, null, 2) + '\n');
console.log('Fresh Main Python -> actual San Review Targets consumer PASS: exact Golden output, canonical hash, p002/p004/p006; no media authorization.');

// Reproduce Main's explicit UNKNOWN-population distinction using its real generator.
const unknownInput = JSON.parse(bytes.toString('utf8'));
unknownInput.points[13].winner = 'unknown';
const unknownPath = path.join(qa, 'goal10-6-unknown-winner-input.json');
const unknownOutput = path.join(qa, 'goal10-6-unknown-winner-targets.json');
await writeFile(unknownPath, JSON.stringify(unknownInput));
run(process.env.PTTI_PYTHON_PATH || 'python', ['-B', path.join(mainRoot, 'products/ptti-integration/scripts/run_review_targets.py'), '--input', unknownPath, '--output', unknownOutput]);
const unknownSource = await prepareQuickSource(JSON.stringify(unknownInput));
const unknownReport = validateReviewTargets(JSON.parse(await readFile(unknownOutput, 'utf8')), unknownSource);
const imported = importQuickAnnotationDraft(unknownInput).value;
const basic = summarizeObservedLosses(imported.points, 1, 'PLAYER_A');
assert.equal(unknownReport.unknown_stage_count, 2);
assert.equal(basic.unknown_stages, 1);
assert.equal(unknownReport.sample.score_known_count, 18);
assert.equal(basic.recorded, 18);
assert.throws(() => validateReviewTargets(accepted, unknownSource), /hash/);
console.log('Fresh Main UNKNOWN population PASS: all-input unknown stages=2, basic known-winner unknown stages=1; both score N=18; stale canonical hash rejected.');
