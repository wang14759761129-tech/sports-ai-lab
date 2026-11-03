import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  advancePoint, advanceToCritical, advanceToCriticalResolved, createMatch, createPrediction,
  isGamePoint, loadArenaState, matchStatus, resolvePredictions, saveArenaState, scoreHistory,
  sanitizeArenaState, validateMatch,
} from '../src/fanArenaEngine.mjs';

// Scripted match: 9:9, 10:10, match point, game win
let m = createMatch(1000);
for (let i = 0; i < 18; i += 1) m = advancePoint(m).match;
assert.deepEqual([m.scoreA, m.scoreB], [9, 9]);
assert.equal(matchStatus(m).kind, 'NINE_NINE');
m = advancePoint(m).match; m = advancePoint(m).match;
assert.deepEqual([m.scoreA, m.scoreB], [10, 10]);
assert.equal(matchStatus(m).kind, 'DEUCE');
assert.equal(isGamePoint(10, 9), 'A', '10:9 is already a game point');
assert.equal(isGamePoint(10, 10), null, '10:10 is deuce, not a game point');
assert.equal(isGamePoint(9, 10), 'B');
m = advancePoint(m).match;
assert.deepEqual([m.scoreA, m.scoreB], [11, 10]);
assert.equal(matchStatus(m).kind, 'GAME_POINT');
m = advancePoint(m).match;
assert.equal(m.status, 'FINISHED');
assert.equal(m.winner, 'A');
assert.deepEqual([m.scoreA, m.scoreB], [12, 10]);

// Prediction lock, reveal, scoring, idempotent resolve
let match = createMatch(2000);
let r = createPrediction([], match, 'NEXT_POINT', 'A');
assert.equal(r.errors.length, 0);
assert.equal(r.predictions[0].id, `${match.id}:NEXT_POINT:point-0`);
const dup = createPrediction(r.predictions, match, 'NEXT_POINT', 'B');
assert.ok(dup.errors.length >= 1, 'same round prediction must not be duplicated');
const prev = match;
match = advancePoint(match).match; // scripted first point: A
let resolved = resolvePredictions(r.predictions, match, prev);
assert.equal(resolved.predictions[0].status, 'RESOLVED');
assert.equal(resolved.predictions[0].correct, true);
const again = resolvePredictions(resolved.predictions, match, prev);
assert.equal(again.changed, false, 're-resolving must not recount');
assert.deepEqual(scoreHistory(resolved.predictions), { total: 1, correct: 1, accuracy: 100, streak: 1 });

// FIRST_TO_GAME_POINT and GAME_WINNER resolve at the right moments
// First game point in the script is at 19 points (10:9, A), not at 11:10.
let m19 = createMatch(3100);
for (let i = 0; i < 19; i += 1) m19 = advancePoint(m19).match;
assert.deepEqual([m19.scoreA, m19.scoreB], [10, 9]);
assert.equal(matchStatus(m19).kind, 'GAME_POINT');
let m2 = createMatch(3000);
let p2 = createPrediction([], m2, 'FIRST_TO_GAME_POINT', 'B').predictions;
let p3 = createPrediction([], m2, 'GAME_WINNER', 'A').predictions;
let all = [...p2, ...p3];
let prev2 = m2;
while (m2.status !== 'FINISHED') {
  const step = advancePoint(m2);
  if (!step.advanced) break;
  const out = resolvePredictions(all, step.match, prev2);
  all = out.predictions; prev2 = m2; m2 = step.match;
}
const firstMp = all.find((p) => p.type === 'FIRST_TO_GAME_POINT');
const winner = all.find((p) => p.type === 'GAME_WINNER');
assert.equal(firstMp.status, 'RESOLVED');
assert.equal(firstMp.correct, false, 'A reaches game point first, B prediction is wrong');
assert.equal(winner.correct, true);
assert.equal(scoreHistory(all).total, 2);

// Invalid input and finished-match prediction
assert.ok(createPrediction([], m2, 'NEXT_POINT', 'A').errors.length >= 1);
assert.ok(createPrediction([], createMatch(4000), 'NOPE', 'A').errors.length >= 1);
assert.ok(createPrediction([], createMatch(4000), 'NEXT_POINT', 'C').errors.length >= 1);

// Persistence: save / load, new match does not reuse old current predictions
const memory = new Map();
const store = { getItem: (k) => memory.get(k) ?? null, setItem: (k, v) => memory.set(k, v) };
assert.equal(saveArenaState(store, { match: m2, predictions: all, history: all }), true);
const loaded = loadArenaState(store);
assert.equal(loaded.match.id, m2.id);
assert.equal(loaded.history.length, 2);
const fresh = createMatch(5000);
assert.notEqual(fresh.id, m2.id);
assert.equal(loaded.predictions.filter((p) => p.matchId === fresh.id).length, 0, 'new match must not reuse old records');
// Failing storage must not pretend success
const failing = { getItem: () => null, setItem: () => { throw new Error('disk full'); } };
assert.equal(saveArenaState(failing, { match: m2, predictions: [], history: [] }), false);
assert.equal(loadArenaState({ getItem: () => 'not-json' }), null);

// P0-2: fast-forward must settle intermediate predictions, not lose them.
// Lock NEXT_POINT (A) at point 0, then fast-forward to 9:9: first point is A,
// so the prediction resolves correctly during the jump, exactly once.
let ff = createMatch(7000);
let ffPreds = createPrediction([], ff, 'NEXT_POINT', 'A').predictions;
let ffOut = advanceToCriticalResolved(ff, ffPreds);
assert.deepEqual([ffOut.match.scoreA, ffOut.match.scoreB], [9, 9]);
assert.equal(matchStatus(ffOut.match).kind, 'NINE_NINE');
assert.equal(ffOut.resolved.length, 1, 'fast-forward must resolve the locked next-point prediction');
assert.equal(ffOut.resolved[0].correct, true);
assert.equal(ffOut.predictions[0].status, 'RESOLVED');
const ffAgain = advanceToCriticalResolved(ffOut.match, ffOut.predictions);
assert.ok(!ffAgain.resolved.some((x) => x.id === ffOut.resolved[0].id), 'fast-forward must not re-count a resolved prediction');
// Fast-forward from 9:9 must move to the next critical state (10:9 game point), not stall.
const ff2 = advanceToCriticalResolved(ffOut.match, ffOut.predictions);
assert.deepEqual([ff2.match.scoreA, ff2.match.scoreB], [10, 9]);
assert.equal(matchStatus(ff2.match).kind, 'GAME_POINT');

// P0-4: corrupt / legacy / stale stored records are sanitised, never thrown.
const legacy = sanitizeArenaState({
  match: { id: 'old-1', pointIndex: 19, scoreA: 0, scoreB: 0, status: 'IN_PROGRESS', winner: null },
  predictions: [
    { id: 'old-1:FIRST_TO_MATCH_POINT:first-match-point', matchId: 'old-1', type: 'FIRST_TO_MATCH_POINT', target: 'first-match-point', choice: 'A', status: 'LOCKED', correct: null },
    { id: 'bad-1', matchId: 'old-1', type: 'NOPE', target: 'x', choice: 'C', status: 'LOCKED', correct: null },
    { id: 'dup-1', matchId: 'old-1', type: 'NEXT_POINT', target: 'point-19', choice: 'A', status: 'LOCKED', correct: null },
    { id: 'dup-1', matchId: 'old-1', type: 'NEXT_POINT', target: 'point-19', choice: 'A', status: 'LOCKED', correct: null },
  ],
  history: [{ id: 'h-1', matchId: 'old-1', type: 'GAME_WINNER', target: 'game-winner', choice: 'A', status: 'RESOLVED', correct: true }],
});
assert.equal(legacy.match.scoreA, 10, 'scores are recomputed from the script, not trusted from storage');
assert.equal(legacy.match.scoreB, 9);
assert.equal(legacy.predictions[0].type, 'FIRST_TO_GAME_POINT', 'legacy match-point type migrates to game-point');
assert.equal(legacy.predictions.length, 2, 'invalid and duplicate predictions are dropped');
assert.equal(legacy.history.length, 1);
assert.equal(validateMatch({ id: 'x', pointIndex: 99 }), null, 'out-of-range pointIndex is invalid');
assert.equal(sanitizeArenaState('not-an-object'), null);
assert.equal(loadArenaState({ getItem: () => '{"match":' }), null, 'broken JSON must not throw');

// Static checks: component, CSS, demo, no betting / money language in engine
const component = readFileSync(new URL('../src/FanArena.tsx', import.meta.url), 'utf8');
assert.ok(component.includes('Fan Arena'), 'component must render Fan Arena');
assert.ok(component.includes('开始新比赛'), 'component must offer a new match');
assert.ok(component.includes('initialArena'), 'component must use lazy initialisation, not load-then-overwrite');
assert.ok(component.includes('advanceToCriticalResolved'), 'component must settle fast-forward point by point');
assert.ok(component.includes('单局演示'), 'component must label the single-game demo');
const videoFeed = readFileSync(new URL('../src/VideoFeed.tsx', import.meta.url), 'utf8');
assert.ok(videoFeed.includes("lazy(()=>import('./FanArena'))"), 'Cinema must lazy-load Fan Arena');
assert.ok(videoFeed.includes('Fan Arena'), 'Cinema must have an Arena entry');
assert.ok(videoFeed.includes('<FanArena onBack={returnToWall}')&&component.includes('返回 Cinema'), 'Arena uses the existing Cinema return path and exposes its button');
const css = readFileSync(new URL('../src/fan-arena.css', import.meta.url), 'utf8');
assert.ok(css.includes('prefers-reduced-motion'), 'CSS must respect reduced motion');
const engineText = readFileSync(new URL('../src/fanArenaEngine.mjs', import.meta.url), 'utf8');
assert.ok(engineText.includes('no money, no chips, no betting'), 'engine must explicitly deny money/chips/betting');
assert.ok(!/现金奖励|筹码奖励|真钱/i.test(engineText), 'engine must not offer cash or chip rewards');
const demo = readFileSync(new URL('../../qa/fan-arena-demo/index.html', import.meta.url), 'utf8');
assert.ok(demo.includes('fanArenaEngine.mjs'), 'demo must reuse the same engine');
assert.ok(advanceToCritical(createMatch(6000)).pointIndex >= 18, 'advance to critical must reach 9:9');

console.log('Fan Arena: scripted critical moments + lock/reveal/scoring/history/persistence/reset checks passed');
