const ROUTES = new Set(['cinema', 'stars', 'watch', 'clips', 'highlights', 'corner', 'rivalries', 'train', 'gear', 'community', 'arena', 'my-matches']);

/** Fan routes carry only public catalog IDs. Legacy ?match= links keep their existing owner. */
export function readFanLocation(input) {
  const url = new URL(input);
  const parts = url.pathname.split('/').filter(Boolean);
  const route = parts[0] === 'matches' ? 'cinema' : parts[0] || 'cinema';
  if (parts.length > 2 || !ROUTES.has(route) || (parts[0] === 'matches' && parts.length !== 2)) return null;
  let id = null;
  if (parts.length === 2) {
    try { id = decodeURIComponent(parts[1]); } catch { return null; }
    if (!id || id.length > 200 || id.includes('/') || id.includes('\\')) return null;
  }
  if (id && !['cinema', 'stars', 'watch', 'rivalries'].includes(route)) return null;
  const matchId = url.searchParams.get('fanMatch');
  const starId = url.searchParams.get('fanStar');
  const returnPage = url.searchParams.get('return');
  return {
    page: route, matchId: route === 'cinema' && parts[0] === 'matches' ? id : route === 'watch' && matchId ? matchId : null,
    starId: route === 'stars' ? id : route === 'watch' && starId ? starId : null,
    sourceId: route === 'watch' ? id : null,
    rivalryId: route === 'rivalries' ? id : null,
    returnPage: route === 'watch' && ['cinema', 'stars', 'clips', 'highlights', 'rivalries', 'corner'].includes(returnPage) ? returnPage : 'cinema',
  };
}

export function fanLocationUrl(input, {page, matchId = null, starId = null, sourceId = null, rivalryId = null, returnPage = 'cinema'}) {
  const url = new URL(input);
  if (!ROUTES.has(page)) {
    url.pathname = '/';
    for (const key of ['fanMatch', 'fanStar', 'return']) url.searchParams.delete(key);
    return url.toString();
  }
  let path = page === 'cinema' ? '/' : `/${page}`;
  if (page === 'cinema' && matchId) path = `/matches/${encodeURIComponent(matchId)}`;
  if (page === 'stars' && starId) path = `/stars/${encodeURIComponent(starId)}`;
  if (page === 'watch' && sourceId) path = `/watch/${encodeURIComponent(sourceId)}`;
  if (page === 'rivalries' && rivalryId) path = `/rivalries/${encodeURIComponent(rivalryId)}`;
  url.pathname = path;
  for (const key of ['fanMatch', 'fanStar', 'return']) url.searchParams.delete(key);
  if (page === 'watch') {
    if (matchId) url.searchParams.set('fanMatch', matchId);
    if (starId) url.searchParams.set('fanStar', starId);
    if (returnPage !== 'cinema') url.searchParams.set('return', returnPage);
  }
  return url.toString();
}
