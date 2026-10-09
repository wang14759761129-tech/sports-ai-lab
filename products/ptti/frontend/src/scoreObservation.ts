export type ScoreObservationLike = {
  point_start_ms?: number | null;
  point_end_ms?: number | null;
  score_display_ms?: number | null;
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
  return row.verification_status === 'REVIEW_REQUIRED'
    && row.point_start_ms == null
    && row.point_end_ms == null;
}
