const FAN_PAGES = new Set(['cinema', 'stars', 'clips', 'highlights', 'rivalries', 'corner']);

function optionalId(value) {
  return typeof value === 'string' && value.trim() ? value : null;
}

export function getKnownMatchAthleteIds(match, knownAthleteIds) {
  if (!match || !Array.isArray(match.participants) || !Array.isArray(knownAthleteIds)) return [];
  const known = new Set(knownAthleteIds.filter((id) => optionalId(id)));
  const seen = new Set();
  const result = [];
  for (const participant of match.participants) {
    const id = optionalId(participant?.athlete_id);
    if (id && known.has(id) && !seen.has(id)) {
      seen.add(id);
      result.push(id);
    }
  }
  return result;
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
