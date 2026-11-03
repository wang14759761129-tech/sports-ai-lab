// Fan Arena 0.1 — simulated match engine. Pure, no network, no real athletes,
// no event brands, no video, no photos, no money, no chips, no betting.
// Players are explicitly fictional / simulated. The point script is fixed so a
// short demo reliably reaches 9:9, 10:10, match point and a game win.
// A prediction is locked to one round/event ID and can never be edited after
// it resolves. History is counted once per prediction ID, by ID, not by re-adding.

export const FAN_ARENA_STORAGE_KEY = 'ptti-fan-arena-v1';

export const SIMULATED_PLAYERS = [
  { id: 'A', name: '雷霆', color: 'red', note: '模拟球员 · 非真实运动员' },
  { id: 'B', name: '磐石', color: 'blue', note: '模拟球员 · 非真实运动员' },
];

// Scripted winners, in order. Totals: after 18 points 9:9, after 20 points 10:10,
// after 21 points 11:10 (match point for A), after 22 points 12:10 (A wins).
export const SIMULATED_POINTS = [
  'A','B','A','B','A','B','B','A','B','A','A','B','A','B','B','A','A','B',
  'A','B','A','A',
];
export const SIMULATED_RALLIES = [
  '发球抢攻得分','反手变线得分','多拍相持后正手得分','接发球拧拉得分','台内控制后得分',
  '防守反击得分','发球轮转得分','正手连续进攻得分','关键分处理得分','反手快撕得分',
];

export function createMatch(now = Date.now()) {
  return {
    id: `fan-arena-${now}-${Math.random().toString(36).slice(2, 8)}`,
    players: SIMULATED_PLAYERS,
    pointIndex: 0,
    scoreA: 0,
    scoreB: 0,
    status: 'IN_PROGRESS',
    lastPoint: null,
    winner: null,
    createdAt: new Date(now).toISOString(),
  };
}

export function isGameWon(scoreA, scoreB) {
  if (scoreA >= 11 && scoreA - scoreB >= 2) return 'A';
  if (scoreB >= 11 && scoreB - scoreA >= 2) return 'B';
  return null;
}

// Game point: the next point, if won by the leader, wins this game.
// In progress that is: leader >= 10 and leader ahead (10:9, 10:8, 11:10, ...).
// A finished game (lead >= 2 and score >= 11) is never a game point.
// This demo is ONE game only: winning this game wins this simulated match,
// so a game point here is also the match point of this single-game demo.
// It is NOT a claim about a full multi-game match.
export function isGamePoint(scoreA, scoreB) {
  if (isGameWon(scoreA, scoreB)) return null;
  if (scoreA >= 10 && scoreA > scoreB) return 'A';
  if (scoreB >= 10 && scoreB > scoreA) return 'B';
  return null;
}

export function matchStatus(match) {
  if (match.status === 'FINISHED') return { kind: 'FINISHED', label: `单局结束 · ${match.winner === 'A' ? '雷霆' : '磐石'} 赢下本局（单局演示）` };
  if (match.scoreA === 9 && match.scoreB === 9) return { kind: 'NINE_NINE', label: '9:9 关键分' };
  if (match.scoreA === 10 && match.scoreB === 10) return { kind: 'DEUCE', label: '10:10 平分 · 需领先两分' };
  const gp = isGamePoint(match.scoreA, match.scoreB);
  if (gp) return { kind: 'GAME_POINT', label: `局点 · ${gp === 'A' ? '雷霆' : '磐石'}（单局演示：赢下本局即赢下本场）` };
  if (match.scoreA >= 9 && match.scoreB >= 9) return { kind: 'CRITICAL', label: '决胜时刻' };
  return { kind: 'IN_PROGRESS', label: '进行中' };
}

export function advancePoint(match) {
  if (match.status === 'FINISHED') return { match, advanced: false };
  if (match.pointIndex >= SIMULATED_POINTS.length) {
    return { match: { ...match, status: 'FINISHED', winner: match.scoreA > match.scoreB ? 'A' : 'B' }, advanced: false };
  }
  const winner = SIMULATED_POINTS[match.pointIndex];
  const scoreA = match.scoreA + (winner === 'A' ? 1 : 0);
  const scoreB = match.scoreB + (winner === 'B' ? 1 : 0);
  const gameWinner = isGameWon(scoreA, scoreB);
  const next = {
    ...match,
    pointIndex: match.pointIndex + 1,
    scoreA, scoreB,
    lastPoint: { index: match.pointIndex, winner, rally: SIMULATED_RALLIES[match.pointIndex % SIMULATED_RALLIES.length] },
    status: gameWinner ? 'FINISHED' : 'IN_PROGRESS',
    winner: gameWinner,
  };
  return { match: next, advanced: true };
}

const CRITICAL_KINDS = new Set(['NINE_NINE', 'DEUCE', 'GAME_POINT']);
export function isCriticalKind(kind) { return CRITICAL_KINDS.has(kind); }

// Legacy advance: advances at least one point, then stops at the next critical
// state (9:9, 10:10, game point) or at the finish. It does NOT settle predictions;
// use advanceToCriticalResolved for that (P0-2).
export function advanceToCritical(match) {
  let current = match;
  let steps = 0;
  while (current.status === 'IN_PROGRESS' && steps < 50) {
    const r = advancePoint(current);
    if (!r.advanced) break;
    current = r.match;
    steps += 1;
    if (current.status === 'FINISHED' || isCriticalKind(matchStatus(current).kind)) break;
  }
  return current;
}

// P0-2: fast-forward as a per-point reduction. Every intermediate point is
// resolved in order, so a NEXT_POINT prediction locked before the fast-forward
// is settled by the point it targeted, not lost. Resolved predictions are
// returned once, in order, and are never re-counted by a second call.
export function advanceToCriticalResolved(match, predictions) {
  let current = match;
  let preds = predictions;
  const resolved = [];
  let steps = 0;
  while (current.status === 'IN_PROGRESS' && steps < 50) {
    const r = advancePoint(current);
    if (!r.advanced) break;
    const out = resolvePredictions(preds, r.match, current);
    const newly = out.predictions.filter((np) => np.status === 'RESOLVED' && !preds.some((op) => op.id === np.id && op.status === 'RESOLVED'));
    resolved.push(...newly);
    preds = out.predictions;
    current = r.match;
    steps += 1;
    if (current.status === 'FINISHED' || isCriticalKind(matchStatus(current).kind)) break;
  }
  return { match: current, predictions: preds, resolved };
}

// Prediction types (canonical, PATCH-08):
// NEXT_POINT — resolves on the very next point.
// FIRST_TO_GAME_POINT — resolves when a player first reaches a game point
//   (leader >= 10 and ahead). Renamed from FIRST_TO_MATCH_POINT: in this
//   single-game demo the old name and its 11:10 trigger were wrong, because
//   10:9 is already a game point. Legacy records are migrated on load.
// GAME_WINNER — resolves at game end (single-game demo: game win = match win).
export const PREDICTION_TYPES = ['NEXT_POINT', 'FIRST_TO_GAME_POINT', 'GAME_WINNER'];
export function normalizePredictionType(type) {
  if (type === 'FIRST_TO_MATCH_POINT') return 'FIRST_TO_GAME_POINT';
  return type;
}
export function predictionTarget(match, type) {
  const t = normalizePredictionType(type);
  if (t === 'NEXT_POINT') return `point-${match.pointIndex}`;
  if (t === 'FIRST_TO_GAME_POINT') return 'first-game-point';
  if (t === 'GAME_WINNER') return 'game-winner';
  return null;
}

export function createPrediction(predictions, match, type, choice) {
  const errors = [];
  type = normalizePredictionType(type);
  if (!PREDICTION_TYPES.includes(type)) errors.push('预测类型无效');
  if (!['A', 'B'].includes(choice)) errors.push('请选择雷霆或磐石');
  if (match.status === 'FINISHED') errors.push('比赛已结束，不能再预测');
  if(type==='FIRST_TO_GAME_POINT'&&match.pointIndex>=19)errors.push('首次局点已揭晓，不能事后预测');
  const target = predictionTarget(match, type);
  if (!target) errors.push('预测类型无效');
  const id = `${match.id}:${type}:${target}`;
  if (predictions.some((p) => p.id === id)) errors.push('这项预测已锁定，不能重复预测');
  if (errors.length) return { errors, predictions };
  const prediction = {
    id, matchId: match.id, type, target, choice,
    scoreAtPrediction: `${match.scoreA}:${match.scoreB}`,
    status: 'LOCKED', correct: null, resolvedAt: null, createdAt: new Date().toISOString(),
  };
  return { errors: [], predictions: [...predictions, prediction], prediction };
}

// Resolve predictions against a (possibly advanced) match. Idempotent:
// a prediction with status RESOLVED is never counted or changed again.
export function resolvePredictions(predictions, match, previousMatch) {
  let changed = false;
  const next = predictions.map((p) => {
    if (p.status === 'RESOLVED' || p.matchId !== match.id) return p;
    let outcome = null;
    if (p.type === 'NEXT_POINT') {
      // Resolves when the point it targeted has been played.
      const played = match.lastPoint && match.lastPoint.index === Number(p.target.replace('point-', ''));
      if (played) outcome = match.lastPoint.winner === p.choice;
    } else if (p.type === 'FIRST_TO_GAME_POINT' || p.type === 'FIRST_TO_MATCH_POINT') {
      const nowGp = isGamePoint(match.scoreA, match.scoreB);
      const wasGp = previousMatch ? isGamePoint(previousMatch.scoreA, previousMatch.scoreB) : null;
      if (nowGp && !wasGp) {
        outcome = nowGp === p.choice;
      } else if (match.status === 'FINISHED') {
        // Game ended without a distinct game-point step in this path:
        // the winner is the player who first reached the winning margin.
        outcome = match.winner === p.choice;
      }
    } else if (p.type === 'GAME_WINNER') {
      if (match.status === 'FINISHED') outcome = match.winner === p.choice;
    }
    if (outcome === null) return p;
    changed = true;
    return { ...p, status: 'RESOLVED', correct: outcome, resolvedAt: new Date().toISOString() };
  });
  return { predictions: next, changed };
}

export function scoreHistory(predictions) {
  const resolved = uniquePredictions(predictions).filter((p) => p.status === 'RESOLVED');
  const correct = resolved.filter((p) => p.correct).length;
  const total = resolved.length;
  let streak = 0;
  for (let i = resolved.length - 1; i >= 0; i -= 1) {
    if (resolved[i].correct) streak += 1; else break;
  }
  return { total, correct, accuracy: total ? Math.round((correct / total) * 100) : 0, streak };
}

// P0-4: validate and sanitise stored data. Never throws, never crashes the
// caller on corrupt / missing / stale records. A valid pointIndex is repaired
// by recomputing scores from the fixed script; an invalid match falls back to
// null (caller creates a fresh match) while valid resolved history is kept.
// Legacy FIRST_TO_MATCH_POINT records are migrated to FIRST_TO_GAME_POINT.
export function recomputeScores(pointIndex) {
  let a = 0, b = 0;
  for (let i = 0; i < pointIndex; i += 1) {
    if (SIMULATED_POINTS[i] === 'A') a += 1; else b += 1;
  }
  return [a, b];
}
export function validateMatch(match) {
  if (!match || typeof match !== 'object') return null;
  if (typeof match.id !== 'string' || !match.id) return null;
  if (!Number.isInteger(match.pointIndex) || match.pointIndex < 0 || match.pointIndex > SIMULATED_POINTS.length) return null;
  const [a, b] = recomputeScores(match.pointIndex);
  const winner = isGameWon(a, b);
  const status = winner ? 'FINISHED' : 'IN_PROGRESS';
  let lastPoint = null;
  if (match.pointIndex > 0) {
    const idx = match.pointIndex - 1;
    lastPoint = { index: idx, winner: SIMULATED_POINTS[idx], rally: SIMULATED_RALLIES[idx % SIMULATED_RALLIES.length] };
  }
  return {id:match.id,players:SIMULATED_PLAYERS,pointIndex:match.pointIndex,scoreA:a,scoreB:b,status,winner,lastPoint,createdAt:typeof match.createdAt==='string'?match.createdAt:null};
}
export function validatePrediction(p) {
  if (!p || typeof p !== 'object') return null;
  if (typeof p.id !== 'string' || !p.id) return null;
  if (typeof p.matchId !== 'string' || !p.matchId) return null;
  const type = normalizePredictionType(p.type);
  if (!PREDICTION_TYPES.includes(type)) return null;
  if (p.choice !== 'A' && p.choice !== 'B') return null;
  if (p.status !== 'LOCKED' && p.status !== 'RESOLVED') return null;
  if (p.status === 'RESOLVED' && typeof p.correct !== 'boolean') return null;
  if (p.status === 'LOCKED' && p.correct !== null && p.correct !== undefined) return null;
  let target = type === 'FIRST_TO_GAME_POINT' ? 'first-game-point' : p.target;
  if(type==='NEXT_POINT'&&(!/^point-\d+$/.test(target)||Number(target.slice(6))>=SIMULATED_POINTS.length))return null;
  if(type==='NEXT_POINT')target=`point-${Number(target.slice(6))}`;
  if(type==='GAME_WINNER'&&target!=='game-winner')return null;
  return {id:`${p.matchId}:${type}:${target}`,matchId:p.matchId,type,target,choice:p.choice,status:p.status,
    scoreAtPrediction:typeof p.scoreAtPrediction==='string'?p.scoreAtPrediction:null,
    correct:p.status==='RESOLVED'?p.correct:null,createdAt:typeof p.createdAt==='string'?p.createdAt:null,
    resolvedAt:p.status==='RESOLVED'&&typeof p.resolvedAt==='string'?p.resolvedAt:null};
}
function uniquePredictions(list){
  const records=new Map(),conflicts=new Set();
  for(const value of list){
    const p=validatePrediction(value);if(!p||conflicts.has(p.id))continue;
    const old=records.get(p.id);
    if(old&&(old.choice!==p.choice||(old.status==='RESOLVED'&&p.status==='RESOLVED'&&old.correct!==p.correct))){records.delete(p.id);conflicts.add(p.id);continue;}
    if(!old||p.status==='RESOLVED')records.set(p.id,p);
  }
  return [...records.values()];
}
export function sanitizeArenaState(parsed) {
  if (!parsed || typeof parsed !== 'object') return null;
  const match = validateMatch(parsed.match);
  const predictions=uniquePredictions(Array.isArray(parsed.predictions)?parsed.predictions:[]);
  const history=uniquePredictions(Array.isArray(parsed.history)?parsed.history:[]).filter(x=>x.status==='RESOLVED');
  const histories=new Map(history.map(x=>[x.id,x]));
  const conflicts=new Set(predictions.filter(p=>histories.has(p.id)&&histories.get(p.id).choice!==p.choice).map(p=>p.id));
  return {match,predictions:match?predictions.filter(x=>x.matchId===match.id&&!conflicts.has(x.id)).map(x=>histories.get(x.id)||x):[],history:history.filter(x=>!conflicts.has(x.id))};
}
export function loadArenaState(storage) {
  try {
    const raw = storage?.getItem(FAN_ARENA_STORAGE_KEY);
    if (!raw) return null;
    return sanitizeArenaState(JSON.parse(raw));
  } catch {
    return null;
  }
}

export function saveArenaState(storage, state) {
  try {
    if(typeof storage?.setItem!=='function')return false;
    const clean=sanitizeArenaState(state);if(!clean?.match)return false;
    storage.setItem(FAN_ARENA_STORAGE_KEY, JSON.stringify(clean));
    return true;
  } catch {
    return false;
  }
}

// Read once per component state initializer; never write on mount or silently
// replace damaged/unreadable archives. Saving is an explicit user action.
export function readArenaSnapshot(storage){
  const fresh=()=>({match:createMatch(),predictions:[],history:[]});
  try{
    if(typeof storage?.getItem!=='function'||typeof storage?.setItem!=='function')throw Error('unavailable');
    const raw=storage.getItem(FAN_ARENA_STORAGE_KEY);
    if(raw===null)return {...fresh(),writable:true,error:''};
    const parsed=JSON.parse(raw),state=sanitizeArenaState(parsed);
    if(!state?.match||!Array.isArray(parsed.predictions)||!Array.isArray(parsed.history))return {...fresh(),writable:false,error:'Arena 存档损坏；已保留原始记录，暂不覆盖。'};
    const normalized=[...parsed.predictions,...parsed.history].map(validatePrediction),seen=new Map();
    let invalid=normalized.some(p=>!p)||parsed.history.some(p=>p.status!=='RESOLVED');
    for(const p of normalized.filter(Boolean)){
      const old=seen.get(p.id);
      if(old&&(old.choice!==p.choice||(old.status==='RESOLVED'&&p.status==='RESOLVED'&&old.correct!==p.correct)))invalid=true;
      if(!old||p.status==='RESOLVED')seen.set(p.id,p);
    }
    if(invalid)return {...fresh(),writable:false,error:'Arena 存档含无效或冲突记录；已保留原始存档，暂不覆盖。'};
    return {...state,writable:true,error:''};
  }catch{return {...fresh(),writable:false,error:'无法读取 Arena 本机存档；已有记录未改变。'};}
}
