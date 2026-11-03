import {
  createQuickAnnotationInput,
  expectedServerForPoint,
  importQuickAnnotationDraft,
  validateQuickAnnotationInput,
  QUICK_ANNOTATION_VERSION_V02,
} from './local-video-review.mjs';

const players = ['PLAYER_A', 'PLAYER_B'];
const oneGameLimitations = [
  'Scores and point winners are manually recorded by the user.',
  'No automatic technique, serve/receive, or tactical diagnosis is produced.',
  'Video is not uploaded; source and viewing permission are not independently verified.',
];

function isObject(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function hasExactKeys(value, expected) {
  return isObject(value)
    && Object.keys(value).length === expected.length
    && expected.every((key) => Object.hasOwn(value, key));
}
function sameJson(a, b) { return JSON.stringify(a) === JSON.stringify(b); }
function sameServiceStats(actual, expected) {
  if (actual === null || expected === null) return actual === expected;
  if (!hasExactKeys(actual, players) || !hasExactKeys(expected, players)) return false;
  return players.every((player) => hasExactKeys(actual[player], ['points', 'won', 'lost'])
    && actual[player].points === expected[player].points
    && actual[player].won === expected[player].won
    && actual[player].lost === expected[player].lost);
}

export function expectedOneGameServer(firstServer, pointNumber) {
  if (!players.includes(firstServer)) return 'UNKNOWN';
  const firstProtocolSide = firstServer === 'PLAYER_A' ? 'player' : 'opponent';
  const expected = expectedServerForPoint(firstProtocolSide, pointNumber);
  return expected === 'player' ? 'PLAYER_A' : expected === 'opponent' ? 'PLAYER_B' : 'UNKNOWN';
}

function terminalScore(score) {
  return Math.max(score.player_a, score.player_b) >= 11
    && Math.abs(score.player_a - score.player_b) >= 2;
}

function scoreLeader(score) {
  if (score.player_a === score.player_b) return 'TIED';
  return score.player_a > score.player_b ? 'PLAYER_A' : 'PLAYER_B';
}

function scorePhase(score) {
  if (score.player_a >= 10 && score.player_b >= 10) return 'DEUCE';
  if (score.player_a >= 9 && score.player_b >= 9) return 'AFTER_9_9';
  if (score.player_a >= 7 && score.player_b >= 7) return 'AFTER_7_7';
  return 'EARLY_GAME';
}

function summarizeKeyScoreStage(points, target, id) {
  const reachedIndex = points.findIndex((point) =>
    point.score_after.player_a === target && point.score_after.player_b === target);
  if (reachedIndex < 0) return {
    id,
    target,
    status: 'NOT_REACHED',
    reached_after_point: null,
    after_point_count: null,
    outcomes: null,
  };

  const after = points.slice(reachedIndex + 1);
  const playerAWins = after.filter((point) => point.winner === 'PLAYER_A').length;
  const playerBWins = after.length - playerAWins;
  return {
    id,
    target,
    status: 'REACHED',
    reached_after_point: points[reachedIndex].point_number,
    after_point_count: after.length,
    outcomes: {
      PLAYER_A: { won: playerAWins, lost: playerBWins },
      PLAYER_B: { won: playerBWins, lost: playerAWins },
    },
  };
}

function summarizeServeReceive(points, firstServer, isComplete, serverConfirmedPointCount) {
  let status = 'AVAILABLE';
  if (points.length === 0) status = 'NO_POINTS';
  else if (!players.includes(firstServer)) status = 'FIRST_SERVER_UNKNOWN';
  else if (!isComplete) status = 'GAME_IN_PROGRESS';
  else if (serverConfirmedPointCount !== points.length) status = 'SERVER_DATA_INCOMPLETE';

  if (status !== 'AVAILABLE') return { status, players: null };

  const playerStats = Object.fromEntries(players.map((player) => {
    const opponent = player === 'PLAYER_A' ? 'PLAYER_B' : 'PLAYER_A';
    const servePoints = points.filter((point) => point.server === player);
    const receivePoints = points.filter((point) => point.server === opponent);
    const serveWon = servePoints.filter((point) => point.winner === player).length;
    const receiveWon = receivePoints.filter((point) => point.winner === player).length;
    return [player, {
      serve: { won: serveWon, total: servePoints.length, rate: servePoints.length ? serveWon / servePoints.length : null },
      receive: { won: receiveWon, total: receivePoints.length, rate: receivePoints.length ? receiveWon / receivePoints.length : null },
    }];
  }));
  return { status, players: playerStats };
}

export function calculateOneGame(points, firstServer = 'UNKNOWN') {
  if (!Array.isArray(points)) return { ok: false, issue: 'invalid-points' };
  if (!['PLAYER_A', 'PLAYER_B', 'UNKNOWN'].includes(firstServer)) return { ok: false, issue: 'invalid-first-server' };
  if (points.some((point) => !point || typeof point !== 'object' || Array.isArray(point))) return { ok: false, issue: 'invalid-point' };
  if (points.some((point) => point.game_number !== 1)) return { ok: false, issue: 'multiple-games-present' };
  const ordered = [...points].sort((a, b) => a.point_number - b.point_number);
  const score = { player_a: 0, player_b: 0 };
  for (let index = 0; index < ordered.length; index += 1) {
    const point = ordered[index];
    const expectedNumber = index + 1;
    if (!Number.isInteger(point.point_number) || point.point_number !== expectedNumber) return { ok: false, issue: 'point-sequence-gap' };
    if (!players.includes(point.winner)) return { ok: false, issue: 'winner-unknown' };
    if (!['PLAYER_A', 'PLAYER_B', 'UNKNOWN'].includes(point.server)) return { ok: false, issue: 'invalid-server' };
    if (players.includes(firstServer) && players.includes(point.server) && point.server !== expectedOneGameServer(firstServer, point.point_number)) {
      return { ok: false, issue: 'service-rotation-conflict' };
    }
    score[point.winner === 'PLAYER_A' ? 'player_a' : 'player_b'] += 1;
    if (terminalScore(score) && index < ordered.length - 1) return { ok: false, issue: 'points-after-game-end' };
  }

  const isComplete = ordered.length > 0 && terminalScore(score);
  const serverConfirmed = ordered.filter((point) => players.includes(point.server)).length;
  const serviceStats = players.includes(firstServer) && isComplete && serverConfirmed === ordered.length
    ? Object.fromEntries(players.map((server) => {
      const served = ordered.filter((point) => point.server === server);
      return [server, {
        points: served.length,
        won: served.filter((point) => point.winner === server).length,
        lost: served.filter((point) => point.winner !== server).length,
      }];
    }))
    : null;

  const scoreProgression = [];
  const progressionScore = { player_a: 0, player_b: 0 };
  let previousNonTiedLeader = null;
  for (const [index, point] of ordered.entries()) {
    const scoreBefore = { ...progressionScore };
    progressionScore[point.winner === 'PLAYER_A' ? 'player_a' : 'player_b'] += 1;
    const leaderBefore = scoreLeader(scoreBefore);
    const leaderAfter = scoreLeader(progressionScore);
    const events = [];
    if (leaderAfter === 'TIED') events.push('TIED');
    else if (previousNonTiedLeader === null) events.push('TAKE_LEAD');
    else if (previousNonTiedLeader !== leaderAfter) events.push('OVERTAKE');
    if (isComplete && index === ordered.length - 1) events.push('GAME_END');
    scoreProgression.push({
      point_id: point.point_id,
      point_number: point.point_number,
      winner: point.winner,
      server: point.server,
      score_before: scoreBefore,
      score_after: { ...progressionScore },
      leader_before: leaderBefore,
      leader_after: leaderAfter,
      phase: scorePhase(scoreBefore),
      events,
    });
    if (leaderAfter !== 'TIED') previousNonTiedLeader = leaderAfter;
  }

  const final = {
    score: { ...score },
    winner: isComplete ? (score.player_a > score.player_b ? 'PLAYER_A' : 'PLAYER_B') : null,
    status: isComplete ? 'GAME_COMPLETE' : 'IN_PROGRESS',
  };
  const keyScoreStages = [
    summarizeKeyScoreStage(scoreProgression, 7, 'AFTER_7_7'),
    summarizeKeyScoreStage(scoreProgression, 9, 'AFTER_9_9'),
    summarizeKeyScoreStage(scoreProgression, 10, 'AFTER_10_10'),
  ];
  const observedCloseScoreStage = [...keyScoreStages].reverse().find((stage) =>
    stage.status === 'REACHED' && stage.after_point_count > 0) ?? null;
  const trainingObservation = observedCloseScoreStage
    ? {
      status: 'DATA_BACKED',
      focus_stage: observedCloseScoreStage.id,
      reached_after_point: observedCloseScoreStage.reached_after_point,
      after_point_count: observedCloseScoreStage.after_point_count,
      outcomes: observedCloseScoreStage.outcomes,
    }
    : { status: 'NO_RECORDED_CLOSE_SCORE_STAGE', focus_stage: null, reached_after_point: null, after_point_count: 0, outcomes: null };
  const serveReceive = summarizeServeReceive(ordered, firstServer, isComplete, serverConfirmed);

  return {
    ok: true,
    score,
    is_complete: isComplete,
    annotated_point_count: ordered.length,
    server_confirmed_point_count: serverConfirmed,
    service_stats: serviceStats,
    serve_receive: serveReceive,
    final,
    score_progression: scoreProgression,
    key_score_stages: keyScoreStages,
    training_observation: trainingObservation,
    points: ordered,
  };
}

export function createOneGameExport(session, points, gameContext) {
  if (!session || session.binding_status !== 'LOCAL_SESSION_ONLY' || session.media_status !== 'ready') return { ok: false, issue: 'video-not-ready' };
  if (session.dataset_class !== 'HUMAN_QUICK_DRAFT'
    || typeof session.dataset_id !== 'string'
    || !session.dataset_id.startsWith('HUMAN_QUICK_DRAFT:')
    || typeof session.match_id !== 'string'
    || !session.match_id.startsWith('LOCAL_QUICK_MATCH:')
    || session.source_id !== null
    || typeof session.file?.name !== 'string'
    || !session.file.name.toLowerCase().endsWith('.mp4')
    || !Number.isFinite(session.file.size)
    || session.file.size <= 0) return { ok: false, issue: 'personal-local-identity-required' };
  if (!gameContext || gameContext.game_number !== 1) return { ok: false, issue: 'invalid-game-context' };
  const summary = calculateOneGame(points, gameContext.first_server);
  if (!summary.ok) return summary;
  if (summary.annotated_point_count === 0) return { ok: false, issue: 'no-points' };

  const coverage = players.includes(gameContext.first_server) ? 'COMPLETE_FROM_GAME_START' : 'PARTIAL_OR_UNKNOWN';
  const quick = createQuickAnnotationInput(session, summary.points, {
    1: { game_number: 1, coverage, first_server: gameContext.first_server },
  }, QUICK_ANNOTATION_VERSION_V02);
  if (!quick.ok) return quick;

  const videoDurationMs = Number.isFinite(session.duration_seconds) && session.duration_seconds > 0
    ? Math.round(session.duration_seconds * 1000) : null;
  return {
    ok: true,
    value: {
      schema: 'ptti.my-match-one-game/0.1',
      dataset_identity: {
        dataset_id: session.dataset_id,
        dataset_class: 'HUMAN_QUICK_DRAFT',
        match_id: session.match_id,
        contract_version: QUICK_ANNOTATION_VERSION_V02,
      },
      source: { type: 'USER_MANUAL', scope: 'ONE_LOCAL_GAME' },
      confirmation_status: 'USER_RECORDED_NOT_INDEPENDENTLY_VERIFIED',
      media_scope: 'LOCAL_SESSION_ONLY',
      video_context: {
        duration_ms: videoDurationMs,
        duration_status: videoDurationMs === null ? 'UNKNOWN' : 'PLAYER_METADATA_REPORTED',
        source_id: null,
        filename_included: false,
        local_path_included: false,
      },
      rules: {
        points_to_win: 11,
        win_by: 2,
        first_server: gameContext.first_server,
        service_rotation: 'two_points_then_one_point_each_after_10_10',
      },
      score: {
        ...summary.score,
        complete: summary.is_complete,
        status: summary.is_complete ? 'GAME_COMPLETE' : 'IN_PROGRESS',
      },
      annotated_point_count: summary.annotated_point_count,
      server_confirmed_point_count: summary.server_confirmed_point_count,
      service_stats: summary.service_stats,
      key_points: 'NOT_MARKED',
      time_boundaries: 'ONLY_EXPLICITLY_CONFIRMED_CURRENT_SESSION_BOUNDARIES',
      points: quick.value.points,
      limitations: [...oneGameLimitations],
    },
  };
}

/**
 * Adapts a validated My Matches export to the existing Pro Quick Annotation
 * draft importer. It deliberately does not create a formal Training Review
 * report or retain confirmed time boundaries across media sessions.
 */
export function importOneGameEvidenceDraft(payload) {
  const invalid = (issue = 'invalid-one-game-evidence') => ({ ok: false, issue });
  if (!isObject(payload)) return invalid();
  if (payload.schema !== 'ptti.my-match-one-game/0.1') return invalid('unsupported-one-game-version');
  if (!hasExactKeys(payload, [
    'schema', 'dataset_identity', 'source', 'confirmation_status', 'media_scope', 'video_context',
    'rules', 'score', 'annotated_point_count', 'server_confirmed_point_count', 'service_stats',
    'key_points', 'time_boundaries', 'points', 'limitations',
  ])) return invalid();

  const identity = payload.dataset_identity;
  const video = payload.video_context;
  const rules = payload.rules;
  const score = payload.score;
  if (!hasExactKeys(identity, ['dataset_id', 'dataset_class', 'match_id', 'contract_version'])
    || identity.dataset_class !== 'HUMAN_QUICK_DRAFT'
    || identity.contract_version !== QUICK_ANNOTATION_VERSION_V02
    || typeof identity.dataset_id !== 'string'
    || !/^HUMAN_QUICK_DRAFT:[A-Za-z0-9-]{1,80}$/.test(identity.dataset_id)
    || typeof identity.match_id !== 'string'
    || !/^LOCAL_QUICK_MATCH:[A-Za-z0-9-]{1,80}$/.test(identity.match_id)
    || identity.dataset_id.slice('HUMAN_QUICK_DRAFT:'.length) !== identity.match_id.slice('LOCAL_QUICK_MATCH:'.length)) return invalid();
  if (!hasExactKeys(payload.source, ['type', 'scope'])
    || payload.source.type !== 'USER_MANUAL' || payload.source.scope !== 'ONE_LOCAL_GAME'
    || payload.confirmation_status !== 'USER_RECORDED_NOT_INDEPENDENTLY_VERIFIED'
    || payload.media_scope !== 'LOCAL_SESSION_ONLY') return invalid();
  if (!hasExactKeys(video, ['duration_ms', 'duration_status', 'source_id', 'filename_included', 'local_path_included'])
    || video.source_id !== null || video.filename_included !== false || video.local_path_included !== false
    || (video.duration_status === 'UNKNOWN' ? video.duration_ms !== null
      : video.duration_status !== 'PLAYER_METADATA_REPORTED' || !Number.isSafeInteger(video.duration_ms) || video.duration_ms <= 0)) return invalid();
  if (!hasExactKeys(rules, ['points_to_win', 'win_by', 'first_server', 'service_rotation'])
    || rules.points_to_win !== 11 || rules.win_by !== 2
    || !['PLAYER_A', 'PLAYER_B', 'UNKNOWN'].includes(rules.first_server)
    || rules.service_rotation !== 'two_points_then_one_point_each_after_10_10') return invalid();
  if (!hasExactKeys(score, ['player_a', 'player_b', 'complete', 'status'])
    || !Number.isSafeInteger(score.player_a) || score.player_a < 0
    || !Number.isSafeInteger(score.player_b) || score.player_b < 0
    || typeof score.complete !== 'boolean'
    || score.status !== (score.complete ? 'GAME_COMPLETE' : 'IN_PROGRESS')
    || !Number.isSafeInteger(payload.annotated_point_count) || payload.annotated_point_count < 1
    || !Number.isSafeInteger(payload.server_confirmed_point_count) || payload.server_confirmed_point_count < 0
    || payload.key_points !== 'NOT_MARKED'
    || payload.time_boundaries !== 'ONLY_EXPLICITLY_CONFIRMED_CURRENT_SESSION_BOUNDARIES'
    || !sameJson(payload.limitations, oneGameLimitations)) return invalid();

  const firstServer = rules.first_server === 'PLAYER_A' ? 'player'
    : rules.first_server === 'PLAYER_B' ? 'opponent' : 'unknown';
  const quickInput = {
    contract_version: identity.contract_version,
    dataset_id: identity.dataset_id,
    dataset_class: identity.dataset_class,
    match_id: identity.match_id,
    video_context: {
      source_id: null,
      duration_ms: video.duration_ms,
      duration_status: video.duration_status,
    },
    rules_context: { games: [{
      game_number: 1,
      coverage: firstServer === 'unknown' ? 'PARTIAL_OR_UNKNOWN' : 'COMPLETE_FROM_GAME_START',
      first_server: firstServer,
    }] },
    points: payload.points,
  };
  const contractCheck = validateQuickAnnotationInput(quickInput);
  if (!contractCheck.ok) return invalid();
  const imported = importQuickAnnotationDraft(quickInput);
  if (!imported.ok) return invalid();

  const summary = calculateOneGame(imported.value.points, rules.first_server);
  if (!summary.ok
    || summary.annotated_point_count !== payload.annotated_point_count
    || summary.server_confirmed_point_count !== payload.server_confirmed_point_count
    || summary.score.player_a !== score.player_a || summary.score.player_b !== score.player_b
    || summary.is_complete !== score.complete
    || !sameServiceStats(summary.service_stats, payload.service_stats)) return invalid();

  return {
    ok: true,
    value: {
      ...imported.value,
      identity: {
        ...imported.value.identity,
        evidence_origin: {
          schema: payload.schema,
          source: 'USER_MANUAL',
          confirmation_status: payload.confirmation_status,
          media_scope: payload.media_scope,
        },
      },
    },
  };
}
