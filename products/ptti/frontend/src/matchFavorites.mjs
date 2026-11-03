export function feedMatchId(video) {
  const source = video?.source ?? video;
  const id = source?.match_id ?? source?.video_source?.match_id;
  return typeof id === 'string' && id.length > 0 ? id : null;
}

export function matchFavoriteKey(matchId) {
  return `match:${matchId}`;
}

export function isMatchFavorite(matchId, rows, favorites) {
  if (typeof matchId !== 'string' || !matchId) return false;
  return favorites.includes(matchFavoriteKey(matchId))
    || rows.some(row => feedMatchId(row) === matchId && favorites.includes(row.key));
}

export function favoriteKeysForMatch(matchId, rows, favorites) {
  const matchKey = matchFavoriteKey(matchId);
  const savedKeys = rows
    .filter(row => feedMatchId(row) === matchId && favorites.includes(row.key))
    .map(row => row.key);
  if (favorites.includes(matchKey)) savedKeys.push(matchKey);
  return savedKeys.length ? [...new Set(savedKeys)] : [matchKey];
}

export function isFeedFavorite(video, favorites, rows = []) {
  const matchId = feedMatchId(video);
  return favorites.includes(video.key) || (matchId !== null && isMatchFavorite(matchId, rows, favorites));
}

export function uniqueFavoriteRows(rows, favorites) {
  const explicit = new Set(favorites);
  const explicitlySavedMatches = new Set(
    rows.filter(row => explicit.has(row.key)).map(feedMatchId).filter(id => id !== null),
  );
  const seenMatchOnly = new Set();
  return rows.filter(row => {
    if (explicit.has(row.key)) return true;
    const matchId = feedMatchId(row);
    if (!matchId || !explicit.has(matchFavoriteKey(matchId))
      || explicitlySavedMatches.has(matchId) || seenMatchOnly.has(matchId)) return false;
    seenMatchOnly.add(matchId);
    return true;
  });
}
