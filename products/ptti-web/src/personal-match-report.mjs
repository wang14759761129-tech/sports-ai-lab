import { calculateOneGame, createOneGameExport } from './my-match-one-game.mjs';

export const PERSONAL_MATCH_REPORT_VERSION = 'ptti.personal-match-report/0.1';
const SIDES = ['PLAYER_A', 'PLAYER_B'];
const safeId = (value, prefix) => typeof value === 'string' && value.startsWith(prefix)
  && /^[A-Za-z0-9_-]{1,128}$/.test(value.slice(prefix.length));

/** Presentation and observation only; scores, rotation and evidence validation stay in One Game. */
export function createPersonalMatchReport(session, points, gameContext) {
  const evidence = createOneGameExport(session, points, gameContext);
  if (!evidence.ok) return evidence;
  if (!safeId(session.session_id, 'local-session:') || !safeId(session.match_id, 'LOCAL_QUICK_MATCH:')
    || !safeId(session.dataset_id, 'HUMAN_QUICK_DRAFT:')) return { ok: false, issue: 'unsafe-local-identity' };
  const summary = calculateOneGame(points, gameContext.first_server);
  if (!summary.ok) return summary;
  return projectReport(session, summary, gameContext, evidence.value);
}

// Shared presentation projection; the personal path above still requires real media evidence.
function projectReport(session, summary, gameContext, evidence) {
  // Each checkpoint's interval ends with the point reaching the next checkpoint.
  // The next interval starts with the following point, so no point is counted twice.
  const keyStages = summary.key_score_stages.map((stage, index, stages) => {
    if (stage.status === 'NOT_REACHED') return {
      id: stage.id, status: 'NOT_REACHED', reached_after_point: null,
      first_point: null, last_point: null, sample_count: null, outcomes: null,
    };
    const next = stages.slice(index + 1).find((row) => row.status === 'REACHED');
    const last = next?.reached_after_point ?? summary.annotated_point_count;
    const rows = summary.score_progression.filter((row) => row.point_number > stage.reached_after_point && row.point_number <= last);
    const aWon = rows.filter((row) => row.winner === 'PLAYER_A').length;
    return { id: stage.id, status: 'REACHED', reached_after_point: stage.reached_after_point,
      first_point: rows[0]?.point_number ?? null, last_point: rows.at(-1)?.point_number ?? null,
      sample_count: rows.length,
      outcomes: { PLAYER_A: { won: aWon, lost: rows.length - aWon }, PLAYER_B: { won: rows.length - aWon, lost: aWon } },
    };
  });
  const runs = [];
  for (const point of summary.score_progression) {
    const prior = runs.at(-1);
    if (prior?.side === point.winner) { prior.last_point = point.point_number; prior.length++; }
    else runs.push({ side: point.winner, first_point: point.point_number, last_point: point.point_number, length: 1 });
  }
  const longestRuns = SIDES.flatMap((side) => {
    const rows = runs.filter((row) => row.side === side && row.length >= 2);
    const length = Math.max(0, ...rows.map((row) => row.length));
    const earliest = rows.find((row) => row.length === length);
    return earliest ? [earliest] : [];
  });
  const questions = [
    ...keyStages.filter((stage) => stage.status === 'REACHED' && stage.sample_count > 0).map((stage) => ({
      question_id: `key:${stage.id}`, kind: 'KEY_SCORE_RANGE', stage_id: stage.id,
      first_point: stage.first_point, last_point: stage.last_point, sample_count: stage.sample_count,
      player_a_won: stage.outcomes.PLAYER_A.won, player_b_won: stage.outcomes.PLAYER_B.won,
    })),
    ...longestRuns.map((run) => ({ question_id: `run:${run.first_point}`, kind: 'SCORING_RUN', ...run, sample_count: run.length })),
    ...(summary.serve_receive.status === 'AVAILABLE' ? [{ question_id: 'serve:observe', kind: 'SERVE_RECEIVE', sample_count: summary.annotated_point_count }] : []),
    { question_id: 'evidence:observe', kind: 'MISSING_TECHNICAL_EVIDENCE', sample_count: summary.annotated_point_count },
  ];
  return { ok: true, value: {
    schema: PERSONAL_MATCH_REPORT_VERSION,
    report_scope: 'PERSONAL_TRAINING_OBSERVATION_NOT_FORMAL_TRAINING_REPORT',
    evidence_identity: { session_id: session.session_id, dataset_id: session.dataset_id, local_match_id: session.match_id,
      public_match_id: null, public_video_source_id: null, original_evidence_schema: evidence.schema },
    source: evidence.source,
    confirmation_status: evidence.confirmation_status,
    media_scope: evidence.media_scope,
    data_facts: { recorded_point_count: summary.annotated_point_count, server_confirmed_point_count: summary.server_confirmed_point_count,
      first_server: gameContext.first_server, record_coverage: 'CONTIGUOUS_USER_RECORD_ONLY',
      actual_game_coverage_independently_verified: false,
      recorded_points: summary.score_progression.map((row) => ({ point_number: row.point_number, winner: row.winner, server: row.server })) },
    calculated_results: { final: summary.final,
      score_progression: summary.score_progression.map(({ point_id, ...row }) => {
        const stage = keyStages.find((item) => item.first_point !== null && row.point_number >= item.first_point && row.point_number <= item.last_point);
        return { ...row, phase: stage?.id === 'AFTER_10_10' ? 'DEUCE' : stage?.id ?? 'EARLY_GAME' };
      }),
      key_stage_definition: 'AFTER_FIRST_EXACT_TIED_SCORE_THROUGH_NEXT_CHECKPOINT_INCLUSIVE_NO_OVERLAP',
      key_stages: keyStages, longest_scoring_runs: longestRuns, serve_receive: summary.serve_receive },
    training_questions: questions,
    unknowns: { actual_game_coverage: 'NOT_INDEPENDENTLY_VERIFIED',
      server_information: gameContext.first_server === 'UNKNOWN' ? 'FIRST_SERVER_UNKNOWN' : summary.server_confirmed_point_count === summary.annotated_point_count ? 'USER_RECORDED_COMPLETE' : 'INCOMPLETE',
      video_time_boundaries: 'NOT_INCLUDED', spin: 'NOT_ANNOTATED', placement: 'NOT_ANNOTATED', stroke_count: 'NOT_ANNOTATED',
      technique_diagnosis: 'NOT_SUPPORTED' },
    selected_question_id: null,
  } };
}

/** Fixed synthetic fixture, no media session, user input, storage or personal evidence export. */
export function createSimulatedDemoReport() {
  const points = [...Array.from({ length: 20 }, (_, i) => i % 2 ? 'PLAYER_B' : 'PLAYER_A'), 'PLAYER_A', 'PLAYER_A']
    .map((winner, i) => ({ point_id: `demo-point-${i + 1}`, game_number: 1, point_number: i + 1,
      winner, server: Math.floor(i / 2) % 2 === 0 ? 'PLAYER_A' : 'PLAYER_B' }));
  // At deuce the service changes after every point.
  points[21].server = 'PLAYER_B';
  const summary = calculateOneGame(points, 'PLAYER_A');
  if (!summary.ok) throw new Error('invalid-fixed-demo');
  const result = projectReport({ session_id: 'simulated-demo:one-game-v1', dataset_id: 'SIMULATED_DEMO:one-game-v1', match_id: null }, summary,
    { first_server: 'PLAYER_A' }, { schema: 'ptti.simulated-demo/0.1', source: { type: 'SIMULATED_DEMO', scope: 'SYNTHETIC_ONE_GAME' },
      confirmation_status: 'SIMULATED_NOT_REAL_MATCH', media_scope: 'NO_MEDIA' });
  result.value.data_facts.record_coverage = 'SYNTHETIC_FIXTURE_ONLY';
  return result.value;
}

/** A question choice is valid only for this exact report, including session identity. */
export function resolvePersonalReportSelection(report, selection) {
  return report && selection?.key === JSON.stringify(report)
    && report.training_questions.some((row) => row.question_id === selection.questionId) ? selection.questionId : null;
}

/** Rebuild from the current validated session rather than serializing arbitrary UI state. */
export function serializePersonalMatchReport(session, points, gameContext, selectedQuestionId = null) {
  const result = createPersonalMatchReport(session, points, gameContext);
  if (!result.ok) return result;
  if (selectedQuestionId !== null && !result.value.training_questions.some((row) => row.question_id === selectedQuestionId)) {
    return { ok: false, issue: 'stale-training-question' };
  }
  return { ok: true, text: `${JSON.stringify({ ...result.value, selected_question_id: selectedQuestionId }, null, 2)}\n` };
}
