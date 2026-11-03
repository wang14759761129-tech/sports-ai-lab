import {
  createQuickAnnotationInput,
  expectedServerForPoint,
  QUICK_ANNOTATION_VERSION_V02,
} from './local-video-review.mjs';

const players = ['PLAYER_A', 'PLAYER_B'];

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
  const serviceStats = isComplete && serverConfirmed === ordered.length
    ? Object.fromEntries(players.map((server) => {
      const served = ordered.filter((point) => point.server === server);
      return [server, {
        points: served.length,
        won: served.filter((point) => point.winner === server).length,
        lost: served.filter((point) => point.winner !== server).length,
      }];
    }))
    : null;

  return {
    ok: true,
    score,
    is_complete: isComplete,
    annotated_point_count: ordered.length,
    server_confirmed_point_count: serverConfirmed,
    service_stats: serviceStats,
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
      limitations: [
        'Scores and point winners are manually recorded by the user.',
        'No automatic technique, serve/receive, or tactical diagnosis is produced.',
        'Video is not uploaded; source and viewing permission are not independently verified.',
      ],
    },
  };
}
