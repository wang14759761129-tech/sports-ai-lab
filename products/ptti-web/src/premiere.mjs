/** Uses only the validated report projection. Never infers media timing or technique. */
export function premiereMoments(report) {
  const r = report.calculated_results;
  return r.score_progression.map(row => ({
    point: row.point_number, a: row.score_after.player_a, b: row.score_after.player_b,
    events: row.events,
    checkpoint: row.score_after.player_a === row.score_after.player_b && [7,9,10].includes(row.score_after.player_a),
    runs: r.longest_scoring_runs.filter(run => run.last_point === row.point_number),
  }));
}
/** Fixed text and validated integer scores only: no identity, user text, or private media. */
export function premiereSvg(report) {
  const { player_a: a, player_b: b } = report.calculated_results.final.score;
  if (![a,b].every(n => Number.isSafeInteger(n) && n >= 0)) throw new Error('invalid-score');
  const complete = report.calculated_results.final.status === 'GAME_COMPLETE';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540" role="img" aria-labelledby="title desc"><title id="title">PTTI My Match Premiere</title><desc id="desc">Manual record. Not independently verified. ${complete ? 'Recorded game complete' : 'Record in progress'}. No media included.</desc><rect width="960" height="540" fill="#0b0c10"/><rect x="32" y="32" width="896" height="476" rx="20" fill="none" stroke="#c5a574"/><g fill="#ead6b4" font-family="sans-serif" text-anchor="middle"><text x="480" y="130" font-size="24">PTTI · MY MATCH PREMIERE</text><text x="480" y="295" font-size="100">${a} : ${b}</text><text x="480" y="365" font-size="22">${complete ? 'Recorded game complete' : 'Record in progress'}</text><text x="480" y="430" font-size="18">Manual record · Not independently verified</text><text x="480" y="465" font-size="15">Score story only · No video or technical diagnosis</text></g></svg>`;
}

/** Ephemeral allowlist projection; the existing Arena engine supports only 9:9. */
export function personalArenaContext(report, point) {
  if (report?.schema !== 'ptti.personal-match-report/0.1' || report.source?.type !== 'USER_MANUAL'
    || report.confirmation_status !== 'USER_RECORDED_NOT_INDEPENDENTLY_VERIFIED') return null;
  const row = report.calculated_results?.score_progression?.find(r => r.point_number === point);
  if (!Number.isSafeInteger(point) || point < 1 || row?.score_after?.player_a !== 9 || row.score_after.player_b !== 9) return null;
  const completeness = report.calculated_results.final.status;
  if (!['GAME_COMPLETE','IN_PROGRESS'].includes(completeness)) return null;
  return { score: { player_a:9, player_b:9 }, point_index:point, completeness, source:'USER_MANUAL', verification:'NOT_INDEPENDENTLY_VERIFIED' };
}
