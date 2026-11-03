export type ScoreObservationLike = {
  point_start_ms?: number | null;
  point_end_ms?: number | null;
  score_display_ms?: number | null;
  record_kind?: string | null;
  observed_score_a?: number | null;
  observed_score_b?: number | null;
  score_a_before?: number | null;
  score_b_before?: number | null;
  verification_status?: string | null;
  availability_status?: string | null;
};

export function observationAnchorMs(row: ScoreObservationLike): number | null {
  for (const value of [row.point_start_ms, row.score_display_ms, row.point_end_ms]) {
    if (typeof value === 'number' && Number.isFinite(value) && value >= 0) return value;
  }
  return null;
}

export function observationSeekMs(row: ScoreObservationLike, preRollMs = 1500): number | null {
  const anchor = observationAnchorMs(row);
  if (anchor === null) return null;
  return Math.max(0, anchor - Math.max(0, preRollMs));
}

export function canPlayConfirmedScore(row: ScoreObservationLike): boolean {
  return row.verification_status === 'CONFIRMED'
    && row.availability_status === 'AVAILABLE'
    && Number.isFinite(row.point_start_ms)
    && Number.isFinite(row.point_end_ms)
    && (row.point_start_ms as number) >= 0
    && (row.point_end_ms as number) > (row.point_start_ms as number);
}

export function isUnboundedScoreObservation(row: ScoreObservationLike): boolean {
  return row.record_kind === 'SCOREBOARD_OBSERVATION'
    || (row.verification_status === 'REVIEW_REQUIRED'
      && row.point_start_ms == null
      && row.point_end_ms == null);
}

export function scoreObservationLabel(row: ScoreObservationLike): string {
  const observed = Number.isInteger(row.observed_score_a) && Number.isInteger(row.observed_score_b)
    ? `${row.observed_score_a}:${row.observed_score_b}` : null;
  const before = Number.isInteger(row.score_a_before) && Number.isInteger(row.score_b_before)
    ? `${row.score_a_before}:${row.score_b_before}` : null;
  if (row.record_kind === 'SCOREBOARD_OBSERVATION') return observed ? `画面比分 ${observed}` : '画面比分未知';
  if (before && observed && before !== observed) return `分前比分 ${before} · 画面比分 ${observed}`;
  if (before) return `分前比分 ${before}`;
  return observed ? `画面比分 ${observed}` : '比分未知';
}

export function scoreObservationStatusLabel(row: ScoreObservationLike): string {
  return row.verification_status === 'REJECTED'
    ? '已否决的观察书签 · 不计入逐分记录'
    : '待确认观察书签 · 不计入已确认逐分记录';
}
