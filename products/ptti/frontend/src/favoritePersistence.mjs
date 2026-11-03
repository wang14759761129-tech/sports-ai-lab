function readFavorites(body) {
  if (!Array.isArray(body?.favorites ?? body?.feed_favorites)) throw Error('收藏状态暂不可用，请重试');
  const rows = body.favorites ?? body.feed_favorites;
  if (!rows.every(key => typeof key === 'string')) throw Error('收藏状态暂不可用，请重试');
  return [...new Set(rows)];
}

// Only server-confirmed snapshots are returned. A failed write may have reached
// SQLite, so reconcile once without re-running the mutation or hiding its error.
export async function persistFavoriteKeys(keys, saved, initial, request = fetch) {
  let favorites = [...initial];
  try {
    for (const key of new Set(keys)) {
      if (favorites.includes(key) === saved) continue;
      const response = await request('/api/video-evidence/library/feed/favorite', {
        method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key, saved}),
      });
      if (!response.ok) throw Error('收藏未保存，请重试');
      favorites = readFavorites(await response.json());
    }
    return {favorites, error: ''};
  } catch {
    try {
      const response = await request('/api/video-evidence/library');
      if (!response.ok) throw Error('read failed');
      favorites = readFavorites(await response.json());
      return {favorites, error: '收藏操作未确认成功，已重新读取服务器状态，请重试。'};
    } catch {
      return {favorites, error: '收藏操作未确认成功，服务器状态暂不可用，请刷新后重试。'};
    }
  }
}
