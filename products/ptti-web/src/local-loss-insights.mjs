// Descriptive counts from validated Quick Annotation rows, never inferred tactics.
export const OBSERVED_LOSS_STAGES = ['END_AFTER_1_2_CONTACTS', 'END_AFTER_3_4_CONTACTS', 'END_AFTER_5_PLUS_CONTACTS'];

export function summarizeObservedLosses(points, gameNumber, observer, reviewableIds = []) {
  const eligible = observer === 'PLAYER_A' || observer === 'PLAYER_B';
  const game = points.filter((point) => point.game_number === gameNumber);
  const known = eligible ? game.filter((point) => point.winner === 'PLAYER_A' || point.winner === 'PLAYER_B') : [];
  const playable = new Set(reviewableIds);
  const ids = (rows) => rows.map((point) => point.point_id);
  const summarize = (rows) => ({
    wins: rows.filter((point) => point.winner === observer).length,
    losses: rows.filter((point) => point.winner !== observer).length,
    loss_point_ids: ids(rows.filter((point) => point.winner !== observer)),
    playable_loss_ids: ids(rows.filter((point) => point.winner !== observer && playable.has(point.point_id))),
  });
  return {
    total: game.length,
    recorded: known.length,
    unknown_winners: game.length - known.length,
    unknown_stages: known.filter((point) => !OBSERVED_LOSS_STAGES.includes(point.observed_rally_stage)).length,
    all: summarize(known),
    stages: Object.fromEntries(OBSERVED_LOSS_STAGES.map((stage) => [stage, summarize(known.filter((point) => point.observed_rally_stage === stage))])),
  };
}
