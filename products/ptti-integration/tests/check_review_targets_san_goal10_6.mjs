// Read-only cross-runtime acceptance: imports San pure functions, never starts a server/media.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const webRoot = process.argv[2];
if (!webRoot) throw new Error('Pass the read-only San products/ptti-web path');
const load = name => import(pathToFileURL(resolve(webRoot, 'src', name)).href);
const local = await load('local-video-review.mjs');
const { summarizeObservedLosses, OBSERVED_LOSS_STAGES } = await load('local-loss-insights.mjs');
const { toRallyPlaybackBinding } = await load('playback-adapter.mjs');
const { payload, review } = JSON.parse(readFileSync(0, 'utf8'));
assert.equal(review.contract_version, 'ptti.review-targets/0.1');
assert.equal(review.input_contract_version, payload.contract_version);
assert.equal(review.dataset.dataset_id, payload.dataset_id);
assert.equal(review.dataset.match_id, payload.match_id);
assert.equal(review.dataset.source_id, payload.video_context.source_id);
const imported = local.importQuickAnnotationDraft(payload);
assert.equal(imported.ok, true, JSON.stringify(imported));
assert.deepEqual(local.QUICK_ANNOTATION_RALLY_STAGES_V02, [...OBSERVED_LOSS_STAGES, 'UNKNOWN']);
const summaries = [];
for (const [role, observer] of [['player', 'PLAYER_A'], ['opponent', 'PLAYER_B']]) {
  const main = review.athletes.find(item => item.role === role);
  const san = summarizeObservedLosses(imported.value.points, 1, observer, []);
  assert.equal(san.all.wins, main.score.won_count);
  assert.equal(san.all.losses, main.score.lost_count);
  assert.deepEqual(san.all.loss_point_ids, main.score.point_ids.lost);
  assert.equal(san.recorded, main.score.denominator);
  assert.equal(san.unknown_winners, main.score.unknown_count);
  for (const stage of OBSERVED_LOSS_STAGES) {
    const group = san.stages[stage];
    const expected = main.observed_stages[stage];
    assert.equal(group.wins, expected.won_count);
    assert.equal(group.losses, expected.lost_count);
    assert.equal(group.wins + group.losses, expected.denominator);
    assert.deepEqual(group.loss_point_ids, expected.point_ids.lost);
    assert.deepEqual(group.playable_loss_ids, []);
  }
  summaries.push({ role, score: [san.all.wins, san.all.losses], unknown_stages_among_known_winners: san.unknown_stages,
    three_four_loss_ids: san.stages.END_AFTER_3_4_CONTACTS.loss_point_ids });
}
for (const raw of payload.points) {
  const mapped = imported.value.points.find(point => point.point_id === raw.point_id);
  assert.equal(mapped.winner, { player: 'PLAYER_A', opponent: 'PLAYER_B', unknown: 'UNKNOWN' }[raw.winner]);
  assert.equal(mapped.start_confirmed, false);
  assert.equal(mapped.end_confirmed, false);
  const binding = toRallyPlaybackBinding(raw, {
    current_video_identity: 'SIMULATED_ONLY:test-session', bound_video_identity: mapped.bound_video_identity,
    start_confirmed: mapped.start_confirmed, end_confirmed: mapped.end_confirmed,
    duration_seconds: payload.video_context.duration_ms / 1000,
  });
  assert.equal(binding.binding_status, 'UNBOUND');
}
for (const target of review.review_targets) {
  assert.equal(target.playback_eligibility, 'NOT_EVALUATED_CURRENT_SESSION');
  assert.equal(target.lost_count, target.point_ids.length);
}
console.log(JSON.stringify({ status: 'PASS', summaries, imported_playable_count: 0 }));
