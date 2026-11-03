const FAN_PAGES = new Set(['cinema', 'stars', 'clips', 'highlights', 'rivalries', 'corner']);

function optionalId(value) {
  return typeof value === 'string' && value.trim() ? value : null;
}

export function createFanStarDestination(athleteId) {
  const id = optionalId(athleteId);
  if (!id) throw new TypeError('athlete-id-required');
  return { page: 'stars', matchId: null, starId: id };
}

export function createFanWatchReturn(page, context = {}) {
  return {
    page: FAN_PAGES.has(page) ? page : 'cinema',
    matchId: optionalId(context.matchId),
    starId: optionalId(context.starId),
  };
}

export function restoreFanWatchReturn(snapshot) {
  return createFanWatchReturn(snapshot?.page, snapshot ?? {});
}
