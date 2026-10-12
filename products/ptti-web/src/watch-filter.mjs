const playerAliases = {
  'Fan Zhendong': '樊振东',
  'Wang Chuqin': '王楚钦',
  'Lin Gaoyuan': '林高远',
  'Wang Yidi': '王艺迪',
  'Sun Yingsha': '孙颖莎',
  'Chen Xingtong': '陈幸同',
};

const aliasEntries = Object.entries(playerAliases);

function hasHttpsUrl(value) {
  return typeof value === 'string' && value.startsWith('https://');
}

/**
 * Return a destination only when its URL matches the declared route type.
 * A source-only destination can never be promoted to a watch-video route.
 * @param {import('./types').MatchRecord} match
 */
export function getMatchDestination(match) {
  if (match.routeType === 'video-page') {
    if (!hasHttpsUrl(match.videoOriginalUrl)
      || match.platformUrl !== match.videoOriginalUrl
      || !match.sourceEvidence.includes(match.videoOriginalUrl)
      || match.sourceStatus !== 'official-listing-found') return null;
    return { type: 'video-page', url: match.videoOriginalUrl };
  }

  if (match.routeType === 'event-page') {
    if (!hasHttpsUrl(match.platformUrl) || match.videoOriginalUrl || !match.sourceEvidence.includes(match.platformUrl) || match.sourceStatus !== 'official-listing-found') return null;
    return { type: 'event-page', url: match.platformUrl };
  }

  if (match.routeType === 'source-only') {
    const evidenceUrl = match.sourceEvidence[0];
    if (!hasHttpsUrl(evidenceUrl) || match.platformUrl || match.videoOriginalUrl || match.sourceStatus !== 'no-verified-route') return null;
    return { type: 'source-only', url: evidenceUrl };
  }

  return null;
}

/**
 * Strict UI gate: a playback claim needs the original official video route,
 * matching browser evidence, changed frames, and at least five seconds of
 * observed timeline advancement. Audio and territory are separate fields.
 * @param {import('./types').MatchRecord} match
 */
export function hasVerifiedVisualPlayback(match) {
  const destination = getMatchDestination(match);
  const evidence = match.playbackEvidence;
  return destination?.type === 'video-page'
    && match.playbackTested === true
    && match.playbackStatus === 'PLAYBACK_PASS'
    && evidence?.finalUrl === destination.url
    && evidence.visualFramesChanged === true
    && Number.isFinite(evidence.timeAtFirstObservationSeconds)
    && Number.isFinite(evidence.timeAtFinalObservationSeconds)
    && evidence.timeAtFinalObservationSeconds - evidence.timeAtFirstObservationSeconds >= 5
    && typeof evidence.pageTitle === 'string'
    && evidence.pageTitle.length > 0
    && typeof evidence.publisher === 'string'
    && evidence.publisher.includes('World Table Tennis')
    && evidence.loginPromptSeen === false
    && evidence.regionPromptSeen === false
    && evidence.verificationPromptSeen === false
    && typeof evidence.audibleOutputConfirmed === 'boolean'
    && typeof evidence.territory === 'string';
}

/** @param {import('./types').MatchRecord} match */
function watchPriority(match) {
  if (hasVerifiedVisualPlayback(match)) return 0;
  const destination = getMatchDestination(match);
  if (destination?.type === 'video-page') return 1;
  if (destination?.type === 'event-page') return 2;
  if (destination?.type === 'source-only') return 3;
  return 4;
}

/**
 * Filter the current sample and keep stronger watch routes near the top.
 * Aliases let both Chinese and English player names find the same records.
 * @param {import('./types').MatchRecord[]} matches
 * @param {{ query?: string, discipline?: string, event?: string, platform?: string }} [filters]
 */
export function filterMatchRecords(matches, filters = {}) {
  const query = (filters.query ?? '').trim().toLocaleLowerCase();
  const selectedDiscipline = filters.discipline ?? 'all';
  const selectedEvent = filters.event ?? 'all';
  const selectedPlatform = filters.platform ?? 'all';
  const selectedWatchFilter = filters.watchFilter ?? 'all';

  const filtered = matches.filter((match) => {
    const playerTerms = match.players.flatMap((player) => {
      const aliases = aliasEntries.find(([english, chinese]) => player === english || player === chinese);
      return aliases ? [player, ...aliases] : [player];
    });
    const event = match.event.toLocaleLowerCase();
    const eventAlias = event.includes('doha') ? '多哈'
      : event.includes('singapore') ? '新加坡'
        : event.includes('chongqing') ? '重庆' : '';
    const searchable = [match.event, eventAlias, match.eventCategory, match.round, ...playerTerms, match.discipline]
      .join(' ')
      .toLocaleLowerCase();
    const verified = hasVerifiedVisualPlayback(match);
    const destination = getMatchDestination(match);

    return (!query || searchable.includes(query))
      && (selectedDiscipline === 'all' || match.discipline === selectedDiscipline)
      && (selectedEvent === 'all' || match.eventCategory === selectedEvent)
      && (selectedPlatform === 'all' || match.platform === selectedPlatform)
      && (selectedWatchFilter === 'all'
        || (selectedWatchFilter === 'verified-video' && verified)
        || (selectedWatchFilter === 'event-page' && destination?.type === 'event-page')
        || (selectedWatchFilter === 'source-only' && destination?.type === 'source-only')
        || (selectedWatchFilter === 'unverified' && !verified));
  });

  return filtered
    .map((match, index) => ({ match, index }))
    .sort((a, b) => watchPriority(a.match) - watchPriority(b.match) || a.index - b.index)
    .map(({ match }) => match);
}

/**
 * Counts reflect current search/discipline/event/source selections, but never
 * depend on the currently selected watch-status chip.
 * @param {import('./types').MatchRecord[]} matches
 * @param {{ query?: string, discipline?: string, event?: string, platform?: string }} [filters]
 */
export function getWatchFilterCounts(matches, filters = {}) {
  const current = filterMatchRecords(matches, { ...filters, watchFilter: 'all' });
  return {
    all: current.length,
    'verified-video': current.filter(hasVerifiedVisualPlayback).length,
    'event-page': current.filter((match) => getMatchDestination(match)?.type === 'event-page').length,
    'source-only': current.filter((match) => getMatchDestination(match)?.type === 'source-only').length,
    unverified: current.filter((match) => !hasVerifiedVisualPlayback(match)).length,
  };
}
