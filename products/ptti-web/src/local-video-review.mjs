export const QUICK_ANNOTATION_VERSION = 'ptti.quick-annotation/0.1';
export const QUICK_ANNOTATION_VERSION_V02 = 'ptti.quick-annotation/0.2';
export const QUICK_ANNOTATION_DATASET_CLASS = 'HUMAN_QUICK_DRAFT';
export const QUICK_ANNOTATION_RALLY_STAGES_V02 = Object.freeze([
  'END_AFTER_1_2_CONTACTS',
  'END_AFTER_3_4_CONTACTS',
  'END_AFTER_5_PLUS_CONTACTS',
  'UNKNOWN',
]);

export const LOCAL_PLAYER_VALUES = Object.freeze(['PLAYER_A', 'PLAYER_B', 'UNKNOWN']);
export const QUICK_TACTIC_VALUES = Object.freeze({
  serve_side: ['forehand', 'backhand', 'unknown', 'unclear', 'not_applicable'],
  serve_length: ['short', 'half_long', 'long', 'unknown', 'unclear', 'not_applicable'],
  serve_location: ['forehand', 'middle', 'backhand', 'unknown', 'unclear', 'not_applicable'],
  serve_spin: ['backspin', 'sidespin', 'topspin', 'no_spin', 'mixed', 'unknown', 'unclear', 'not_applicable'],
  receive_type: ['push', 'flick', 'chiquita', 'drive', 'loop', 'long_push', 'short_touch', 'other', 'unknown', 'unclear', 'not_applicable'],
  receive_location: ['forehand', 'middle', 'backhand', 'unknown', 'unclear', 'not_applicable'],
  third_ball_attack: ['yes', 'no', 'unknown', 'unclear', 'not_applicable'],
  third_ball_side: ['forehand', 'backhand', 'other', 'unknown', 'unclear', 'not_applicable'],
  third_ball_outcome: ['successful', 'unsuccessful', 'unknown', 'unclear', 'not_applicable'],
  rally_length: [],
});

const QUICK_TOP_LEVEL_KEYS = ['contract_version', 'dataset_id', 'dataset_class', 'match_id', 'video_context', 'rules_context', 'points'];
const POINT_KEYS_V01 = ['point_id', 'server', 'winner', 'observed_tactics', 'rally_start_ms', 'rally_end_ms'];
const GAME_KEYS = ['game_number', 'coverage', 'first_server'];

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function hasExactKeys(value, expected) {
  return isObject(value)
    && Object.keys(value).length === expected.length
    && expected.every((key) => Object.hasOwn(value, key));
}

function toProtocolSide(value) {
  if (value === 'PLAYER_A') return 'player';
  if (value === 'PLAYER_B') return 'opponent';
  return 'unknown';
}

function fromProtocolSide(value) {
  if (value === 'player') return 'PLAYER_A';
  if (value === 'opponent') return 'PLAYER_B';
  return 'UNKNOWN';
}

export function encodeQuickMatchId(matchId) {
  return encodeURIComponent(matchId).replace(/[!'()*]/g, (character) => `%${character.charCodeAt(0).toString(16).toUpperCase()}`);
}

export function createQuickPointId(matchId, gameNumber, pointNumber) {
  if (typeof matchId !== 'string' || !matchId.trim() || !Number.isInteger(gameNumber) || gameNumber < 1 || !Number.isInteger(pointNumber) || pointNumber < 1) return '';
  return `${encodeQuickMatchId(matchId)}/g${String(gameNumber).padStart(2, '0')}/p${String(pointNumber).padStart(3, '0')}`;
}

/** Explicit contract-millisecond to San/Playback-Core second conversion. */
export function quickMillisecondsToLocalSeconds(value) {
  if (value === null) return null;
  if (!Number.isSafeInteger(value) || value < 0) return null;
  return value / 1000;
}

/** Explicit San local-second to Quick Annotation integer-millisecond conversion. */
export function localSecondsToQuickMilliseconds(value) {
  if (value === null) return null;
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return null;
  const milliseconds = Math.round(value * 1000);
  return Number.isSafeInteger(milliseconds) ? milliseconds : null;
}

export function expectedServerForPoint(firstServer, pointNumber) {
  if (!['player', 'opponent'].includes(firstServer) || !Number.isInteger(pointNumber) || pointNumber < 1) return 'unknown';
  const completedPoints = pointNumber - 1;
  const serveChanges = completedPoints < 20
    ? Math.floor(completedPoints / 2)
    : 10 + (completedPoints - 20);
  return serveChanges % 2 === 0 ? firstServer : (firstServer === 'player' ? 'opponent' : 'player');
}

export function nextUnannotatedPointNumber(points, gameNumber) {
  const used = new Set((Array.isArray(points) ? points : [])
    .filter((point) => point?.game_number === gameNumber && Number.isInteger(point?.point_number) && point.point_number > 0)
    .map((point) => point.point_number));
  let pointNumber = 1;
  while (used.has(pointNumber)) pointNumber += 1;
  return pointNumber;
}

export function suggestedLocalServerForPoint(gameContext, pointNumber) {
  if (gameContext?.coverage !== 'COMPLETE_FROM_GAME_START') return 'UNKNOWN';
  const firstServer = gameContext.first_server === 'PLAYER_A' ? 'player'
    : gameContext.first_server === 'PLAYER_B' ? 'opponent' : 'unknown';
  const expected = expectedServerForPoint(firstServer, pointNumber);
  return fromProtocolSide(expected);
}

function normalizedTactics(tactics) {
  if (!isObject(tactics)) return null;
  const keys = Object.keys(tactics);
  if (keys.some((key) => !Object.hasOwn(QUICK_TACTIC_VALUES, key))) return null;
  for (const key of keys) {
    if (key === 'rally_length') {
      if (tactics[key] !== 'unknown' && (!Number.isInteger(tactics[key]) || tactics[key] < 1)) return null;
    } else if (!QUICK_TACTIC_VALUES[key].includes(tactics[key])) return null;
  }
  return Object.fromEntries(Object.entries(QUICK_TACTIC_VALUES).map(([field]) => [field, tactics[field] ?? 'unknown']));
}

export function validateQuickAnnotationPoint(point, durationMs, gameContexts, existingPoints = [], editingPointId = null, matchId = null) {
  if (!isObject(point)) return { ok: false, issue: 'invalid-point' };
  if (!['PLAYER_A', 'PLAYER_B', 'UNKNOWN'].includes(point.winner)) return { ok: false, issue: 'invalid-winner' };
  if (!['PLAYER_A', 'PLAYER_B', 'UNKNOWN'].includes(point.server)) return { ok: false, issue: 'invalid-server' };
  if (!Number.isInteger(point.game_number) || point.game_number < 1 || !Number.isInteger(point.point_number) || point.point_number < 1) return { ok: false, issue: 'invalid-point-number' };
  if (typeof matchId !== 'string' || point.point_id !== createQuickPointId(matchId, point.game_number, point.point_number)) return { ok: false, issue: 'invalid-point-id' };
  if (existingPoints.some((item) => item?.point_id === point.point_id && point.point_id !== editingPointId)) return { ok: false, issue: 'duplicate-point-id' };
  if (!normalizedTactics(point.observed_tactics)) return { ok: false, issue: 'invalid-tactics' };

  const context = gameContexts?.[point.game_number];
  const firstServer = toProtocolSide(context?.first_server);
  if (context?.coverage === 'COMPLETE_FROM_GAME_START' && ['player', 'opponent'].includes(firstServer)) {
    const expected = fromProtocolSide(expectedServerForPoint(firstServer, point.point_number));
    if (point.server !== 'UNKNOWN' && point.server !== expected) return { ok: false, issue: 'service-rotation-conflict' };
  }

  const { start_seconds: start, end_seconds: end } = point;
  if (start === null && end === null) return { ok: true };
  const hasPartialUnconfirmedRange = start === null || end === null;
  if (hasPartialUnconfirmedRange) {
    const supplied = [start, end].filter((value) => value !== null);
    if (supplied.some((value) => typeof value !== 'number' || !Number.isFinite(value) || value < 0)) return { ok: false, issue: 'invalid-time' };
    if (!Number.isInteger(durationMs) || durationMs <= 0) return { ok: false, issue: 'duration-unknown' };
    if (supplied.some((value) => value * 1000 > durationMs)) return { ok: false, issue: 'time-out-of-range' };
    if (point.start_confirmed === true && point.end_confirmed === true) return { ok: false, issue: 'incomplete-time-range' };
    return { ok: true };
  }
  if (!Number.isFinite(start) || !Number.isFinite(end)) return { ok: false, issue: 'incomplete-time-range' };
  if (start < 0 || end < 0) return { ok: false, issue: 'time-out-of-range' };
  if (!Number.isInteger(Math.round(start * 1000)) || !Number.isInteger(Math.round(end * 1000))) return { ok: false, issue: 'invalid-time' };
  if (!Number.isInteger(durationMs) || durationMs <= 0) return { ok: false, issue: 'duration-unknown' };
  const startMs = Math.round(start * 1000);
  const endMs = Math.round(end * 1000);
  if (startMs < 0 || endMs > durationMs) return { ok: false, issue: 'time-out-of-range' };
  if (startMs >= endMs) return { ok: false, issue: 'start-after-end' };

  return { ok: true };
}

export function validateQuickAnnotationPoints(session, points, gameContexts = {}) {
  if (!isObject(session) || session.binding_status !== 'LOCAL_SESSION_ONLY' || session.media_status !== 'ready') return { ok: false, issue: 'video-not-ready' };
  if (typeof session.session_id !== 'string' || !session.session_id || typeof session.match_id !== 'string' || !session.match_id || typeof session.dataset_id !== 'string' || !session.dataset_id || !isObject(session.file)) return { ok: false, issue: 'unbound-video' };
  if (typeof session.file.name !== 'string' || !session.file.name.toLowerCase().endsWith('.mp4') || !Number.isFinite(session.file.size) || session.file.size <= 0) return { ok: false, issue: 'unbound-video' };
  if (session.file.type !== '' && session.file.type !== 'video/mp4') return { ok: false, issue: 'unbound-video' };
  const durationMs = Number.isFinite(session.duration_seconds) && session.duration_seconds > 0 ? Math.round(session.duration_seconds * 1000) : null;
  if (!Array.isArray(points)) return { ok: false, issue: 'invalid-points' };
  const seen = new Set();
  for (const point of points) {
    const result = validateQuickAnnotationPoint(point, durationMs, gameContexts, [...seen].map((point_id) => ({ point_id })), null, session.match_id);
    if (!result.ok) return result;
    seen.add(point.point_id);
  }
  return { ok: true };
}

export function createQuickAnnotationInput(session, points, gameContexts = {}, requestedVersion = null) {
  const validation = validateQuickAnnotationPoints(session, points, gameContexts);
  if (!validation.ok) return validation;

  const contractVersion = requestedVersion ?? session.contract_version ?? QUICK_ANNOTATION_VERSION_V02;
  if (![QUICK_ANNOTATION_VERSION, QUICK_ANNOTATION_VERSION_V02].includes(contractVersion)) return { ok: false, issue: 'unsupported-contract-version' };

  const usedGames = new Set([...points.map((point) => point.game_number), ...Object.keys(gameContexts).map(Number)]);
  const games = [...usedGames].sort((a, b) => a - b).map((gameNumber) => {
    const context = gameContexts[gameNumber] ?? {};
    return {
      game_number: gameNumber,
      coverage: context.coverage === 'COMPLETE_FROM_GAME_START' ? 'COMPLETE_FROM_GAME_START' : 'PARTIAL_OR_UNKNOWN',
      first_server: toProtocolSide(context.first_server),
    };
  });
  const durationMs = Number.isFinite(session.duration_seconds) && session.duration_seconds > 0
    ? Math.round(session.duration_seconds * 1000)
    : null;
  const value = {
    contract_version: contractVersion,
    dataset_id: session.dataset_id,
    dataset_class: session.dataset_class ?? QUICK_ANNOTATION_DATASET_CLASS,
    match_id: session.match_id,
    video_context: {
      source_id: session.source_id ?? null,
      duration_ms: durationMs,
      duration_status: durationMs === null ? 'UNKNOWN' : 'PLAYER_METADATA_REPORTED',
    },
    rules_context: { games },
    points: points.map((point) => {
      const timesConfirmedForSession = point.start_confirmed === true
        && point.end_confirmed === true
        && point.bound_video_identity === session.session_id;
      const startMs = timesConfirmedForSession ? localSecondsToQuickMilliseconds(point.start_seconds) : null;
      const endMs = timesConfirmedForSession ? localSecondsToQuickMilliseconds(point.end_seconds) : null;
      const output = {
        point_id: point.point_id,
        server: toProtocolSide(point.server),
        winner: toProtocolSide(point.winner),
        observed_tactics: normalizedTactics(point.observed_tactics),
        // The v0.1 and v0.2 Quick Annotation schemas both use rally_*_ms.
        // Unconfirmed/provisional values are omitted as a pair.
        rally_start_ms: startMs,
        rally_end_ms: endMs,
      };
      if (contractVersion === QUICK_ANNOTATION_VERSION_V02 && point.observed_rally_stage !== undefined) {
        output.observed_rally_stage = point.observed_rally_stage;
      }
      return output;
    }),
  };
  const contractCheck = validateQuickAnnotationInput(value);
  return contractCheck.ok ? { ok: true, value } : contractCheck;
}

/**
 * Validates and maps a Quick Annotation input draft into this page's temporary
 * editor model. Imported time values remain provisional until both boundaries
 * are explicitly confirmed against a newly selected local video session.
 */
export function importQuickAnnotationDraft(payload) {
  const validation = validateQuickAnnotationInput(payload);
  if (!validation.ok) return validation;

  const gameContexts = Object.fromEntries(payload.rules_context.games.map((game) => [game.game_number, {
    game_number: game.game_number,
    coverage: game.coverage,
    first_server: fromProtocolSide(game.first_server),
  }]));
  const points = payload.points.map((point) => {
    const match = /\/g([0-9]{2,})\/p([0-9]{3,})$/.exec(point.point_id);
    if (!match) return null;
    return {
      point_id: point.point_id,
      game_number: Number(match[1]),
      point_number: Number(match[2]),
      server: fromProtocolSide(point.server),
      winner: fromProtocolSide(point.winner),
      observed_tactics: {
        serve_side: 'unknown', serve_length: 'unknown', third_ball_attack: 'unknown',
        ...point.observed_tactics,
      },
      start_seconds: quickMillisecondsToLocalSeconds(point.rally_start_ms),
      end_seconds: quickMillisecondsToLocalSeconds(point.rally_end_ms),
      ...(payload.contract_version === QUICK_ANNOTATION_VERSION_V02 && point.observed_rally_stage !== undefined
        ? { observed_rally_stage: point.observed_rally_stage }
        : {}),
      bound_video_identity: '',
      start_confirmed: false,
      end_confirmed: false,
    };
  });
  if (points.some((point) => point === null)) return { ok: false, issue: 'invalid-point-id' };

  return {
    ok: true,
    value: {
      identity: {
        dataset_id: payload.dataset_id,
        dataset_class: payload.dataset_class,
        match_id: payload.match_id,
        source_id: payload.video_context.source_id,
        contract_version: payload.contract_version,
      },
      game_contexts: gameContexts,
      points,
    },
  };
}

/** Counts recorded score observations separately from currently playable ranges. */
export function summarizeLocalQuickPoints(points, reviewablePointIds = []) {
  const reviewable = new Set(reviewablePointIds);
  const countsFor = (records) => ({
    PLAYER_A: records.filter((point) => point.winner === 'PLAYER_A').length,
    PLAYER_B: records.filter((point) => point.winner === 'PLAYER_B').length,
  });
  const knownWinnerPoints = points.filter((point) => point.winner === 'PLAYER_A' || point.winner === 'PLAYER_B');
  const playablePoints = points.filter((point) => reviewable.has(point.point_id));
  const knownServeSide = points.filter((point) => ['forehand', 'backhand'].includes(point.observed_tactics?.serve_side)).length;
  const knownThirdBallAttack = points.filter((point) => ['yes', 'no'].includes(point.observed_tactics?.third_ball_attack)).length;
  return {
    total_points: points.length,
    known_winner_points: knownWinnerPoints.length,
    score_by_winner: countsFor(knownWinnerPoints),
    reviewable_points: playablePoints.length,
    independently_verified_media_points: 0,
    reviewable_by_winner: countsFor(playablePoints.filter((point) => point.winner !== 'UNKNOWN')),
    known_serve_side: knownServeSide,
    known_third_ball_attack: knownThirdBallAttack,
  };
}

export function validateQuickAnnotationInput(payload) {
  if (!hasExactKeys(payload, QUICK_TOP_LEVEL_KEYS)) return { ok: false, issue: 'invalid-contract-fields' };
  if (![QUICK_ANNOTATION_VERSION, QUICK_ANNOTATION_VERSION_V02].includes(payload.contract_version)) return { ok: false, issue: 'unsupported-contract-version' };
  if (![QUICK_ANNOTATION_DATASET_CLASS, 'SIMULATED_ONLY'].includes(payload.dataset_class)) return { ok: false, issue: 'invalid-dataset-class' };
  if (typeof payload.dataset_id !== 'string' || !payload.dataset_id.trim() || typeof payload.match_id !== 'string' || !payload.match_id.trim()) return { ok: false, issue: 'missing-dataset-identity' };
  if (payload.dataset_class === 'SIMULATED_ONLY' && (!payload.dataset_id.startsWith('SIMULATED_ONLY:') || !payload.match_id.startsWith('SIMULATED_ONLY:'))) return { ok: false, issue: 'simulated-namespace-required' };
  if (payload.dataset_class === 'SIMULATED_ONLY' && payload.video_context?.source_id !== null
    && typeof payload.video_context?.source_id === 'string' && !payload.video_context.source_id.startsWith('SIMULATED_ONLY:')) return { ok: false, issue: 'simulated-namespace-required' };
  if (payload.dataset_class === 'HUMAN_QUICK_DRAFT' && payload.match_id.startsWith('SIMULATED_ONLY:')) return { ok: false, issue: 'simulated-cannot-be-human' };
  if (payload.dataset_class === 'HUMAN_QUICK_DRAFT' && typeof payload.video_context?.source_id === 'string'
    && payload.video_context.source_id.startsWith('SIMULATED_ONLY:')) return { ok: false, issue: 'simulated-cannot-be-human' };
  if (!hasExactKeys(payload.video_context, ['source_id', 'duration_ms', 'duration_status'])) return { ok: false, issue: 'invalid-video-context' };
  if (payload.video_context.source_id !== null && (typeof payload.video_context.source_id !== 'string' || !payload.video_context.source_id.trim())) return { ok: false, issue: 'invalid-source-id' };
  const { duration_ms: durationMs, duration_status: durationStatus } = payload.video_context;
  if (durationStatus === 'UNKNOWN' ? durationMs !== null : durationStatus !== 'PLAYER_METADATA_REPORTED' || !Number.isInteger(durationMs) || durationMs <= 0) return { ok: false, issue: 'invalid-duration-context' };
  if (!hasExactKeys(payload.rules_context, ['games']) || !Array.isArray(payload.rules_context.games)) return { ok: false, issue: 'invalid-rules-context' };
  const contexts = {};
  for (const game of payload.rules_context.games) {
    if (!hasExactKeys(game, GAME_KEYS) || !Number.isInteger(game.game_number) || game.game_number < 1 || !['COMPLETE_FROM_GAME_START', 'PARTIAL_OR_UNKNOWN'].includes(game.coverage) || !['player', 'opponent', 'unknown'].includes(game.first_server) || contexts[game.game_number]) return { ok: false, issue: 'invalid-game-context' };
    contexts[game.game_number] = game;
  }
  if (!Array.isArray(payload.points) || payload.points.length === 0) return { ok: false, issue: 'empty-points' };
  const seen = new Set();
  let previous = [0, 0];
  for (const point of payload.points) {
    const pointKeys = payload.contract_version === QUICK_ANNOTATION_VERSION
      ? POINT_KEYS_V01
      : [...POINT_KEYS_V01, ...(isObject(point) && Object.hasOwn(point, 'observed_rally_stage') ? ['observed_rally_stage'] : [])];
    if (!hasExactKeys(point, pointKeys)) return { ok: false, issue: 'invalid-contract-point-fields' };
    if (payload.contract_version === QUICK_ANNOTATION_VERSION_V02 && Object.hasOwn(point, 'observed_rally_stage')
      && !QUICK_ANNOTATION_RALLY_STAGES_V02.includes(point.observed_rally_stage)) return { ok: false, issue: 'invalid-rally-stage' };
    const matchPattern = `^${encodeQuickMatchId(payload.match_id)}/g([0-9]{2,})/p([0-9]{3,})$`;
    const found = new RegExp(matchPattern).exec(point.point_id);
    if (!found || createQuickPointId(payload.match_id, Number(found[1]), Number(found[2])) !== point.point_id) return { ok: false, issue: 'invalid-point-id' };
    if (seen.has(point.point_id)) return { ok: false, issue: 'duplicate-point-id' };
    seen.add(point.point_id);
    const gameNumber = Number(found[1]);
    const pointNumber = Number(found[2]);
    if ([gameNumber, pointNumber][0] < previous[0] || (gameNumber === previous[0] && pointNumber <= previous[1])) return { ok: false, issue: 'point-order-invalid' };
    previous = [gameNumber, pointNumber];
    if (!['player', 'opponent', 'unknown'].includes(point.server) || !['player', 'opponent', 'unknown'].includes(point.winner)) return { ok: false, issue: 'invalid-point-side' };
    const tactics = normalizedTactics(point.observed_tactics);
    if (!tactics || Object.keys(point.observed_tactics).some((field) => !Object.hasOwn(QUICK_TACTIC_VALUES, field))) return { ok: false, issue: 'invalid-tactics' };
    const start = point.rally_start_ms;
    const end = point.rally_end_ms;
    const game = contexts[gameNumber];
    if (game?.coverage === 'COMPLETE_FROM_GAME_START' && ['player', 'opponent'].includes(game.first_server)) {
      const expected = expectedServerForPoint(game.first_server, pointNumber);
      if (point.server !== 'unknown' && point.server !== expected) return { ok: false, issue: 'service-rotation-conflict' };
    }
    if (start === null && end === null) continue;
    if (!Number.isInteger(start) || !Number.isInteger(end)) return { ok: false, issue: 'incomplete-time-range' };
    if (durationStatus !== 'PLAYER_METADATA_REPORTED') return { ok: false, issue: 'duration-required-for-time-range' };
    if (start < 0 || start >= end || end > durationMs) return { ok: false, issue: 'time-out-of-range' };
  }
  return { ok: true };
}
