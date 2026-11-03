const YOUTUBE_VIDEO_ID = /^[A-Za-z0-9_-]{11}$/;
const MAX_API_DATA_AGE_MS = 30 * 24 * 60 * 60 * 1000;
const THUMBNAIL_KEYS = ['maxres', 'standard', 'high', 'medium', 'default'];
const CLIENT_REVIEWS = new Set(['NOT_STARTED', 'CONDITIONAL_APPROVAL', 'APPROVED']);
const CLICK_TARGETS = new Set(['YOUTUBE_APP_OR_SYSTEM_BROWSER', 'OFFICIAL_IFRAME_PLAYER']);
const EMBED_PERMISSIONS = new Set(['UNKNOWN', 'ALLOWED', 'NOT_ALLOWED']);

function sourceIdFor(source) {
  if (typeof source?.source_id === 'string' && source.source_id.trim()) return source.source_id;
  const videoId = source?.video_id;
  return source?.provider === 'YOUTUBE_OFFICIAL' && typeof videoId === 'string' && YOUTUBE_VIDEO_ID.test(videoId)
    ? `video-source:youtube:${videoId}`
    : '';
}

export function youtubeThumbnailSourceId(source) {
  return sourceIdFor(source);
}

function emptyRuntime(source, clientPolicy, status, retrievedAt = null, providerVideoId = '') {
  const now = Date.parse(retrievedAt);
  const deleteOrRefreshBy = Number.isFinite(now) ? new Date(now + MAX_API_DATA_AGE_MS).toISOString() : null;
  return {
    provider: 'YOUTUBE_DATA_API',
    source_id: sourceIdFor(source),
    provider_video_id: providerVideoId,
    status,
    api_client_review: CLIENT_REVIEWS.has(clientPolicy?.api_client_review) ? clientPolicy.api_client_review : 'NOT_STARTED',
    api_data_retrieved_at: retrievedAt,
    delete_or_refresh_by: deleteOrRefreshBy,
    youtube_title: null,
    channel_id: null,
    channel_title: null,
    thumbnail: null,
    attribution_required: true,
    click_target: CLICK_TARGETS.has(clientPolicy?.click_target) ? clientPolicy.click_target : 'YOUTUBE_APP_OR_SYSTEM_BROWSER',
    embed_permission: EMBED_PERMISSIONS.has(source?.video_source?.embed_permission)
      ? source.video_source.embed_permission
      : 'UNKNOWN',
  };
}

function isExactYoutubeWatchUrl(value, videoId) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:'
      && (url.hostname === 'www.youtube.com' || url.hostname === 'youtube.com')
      && url.pathname === '/watch'
      && !url.username
      && !url.password
      && url.searchParams.getAll('v').length === 1
      && url.searchParams.get('v') === videoId;
  } catch {
    return false;
  }
}

function chooseReturnedThumbnail(thumbnails) {
  if (!thumbnails || typeof thumbnails !== 'object' || Array.isArray(thumbnails)) return null;
  const ordered = [
    ...THUMBNAIL_KEYS.filter(key => thumbnails[key]).map(key => [key, thumbnails[key]]),
    ...Object.entries(thumbnails).filter(([key]) => !THUMBNAIL_KEYS.includes(key)),
  ];
  for (const [key, image] of ordered) {
    if (typeof image?.url !== 'string') continue;
    try {
      const url = new URL(image.url);
      if (url.protocol !== 'https:' || url.username || url.password) continue;
    } catch {
      continue;
    }
    if (!Number.isInteger(image.width) || image.width <= 0) continue;
    if (!Number.isInteger(image.height) || image.height <= 0) continue;
    return {key, url: image.url, width: image.width, height: image.height};
  }
  return null;
}

function validTimestampWindow(runtime, now) {
  const retrievedAt = Date.parse(runtime?.api_data_retrieved_at);
  const deleteOrRefreshBy = Date.parse(runtime?.delete_or_refresh_by);
  return Number.isFinite(retrievedAt)
    && Number.isFinite(deleteOrRefreshBy)
    && Number.isFinite(now)
    && retrievedAt <= now
    && deleteOrRefreshBy > now
    && deleteOrRefreshBy <= retrievedAt + MAX_API_DATA_AGE_MS;
}

/**
 * Convert a videos.list response into the GOAL96 YoutubeThumbnailRuntime/0.1
 * sidecar. This is a pure adapter: it does not make requests or persist data.
 */
export function createYoutubeThumbnailRuntime(source, apiResponse, clientPolicy, now = Date.now()) {
  const videoId = source?.video_id;
  const sourceId = sourceIdFor(source);
  const retrievedAt = Number.isFinite(now) ? new Date(now).toISOString() : null;
  const review = CLIENT_REVIEWS.has(clientPolicy?.api_client_review)
    ? clientPolicy.api_client_review
    : 'NOT_STARTED';

  if (source?.provider !== 'YOUTUBE_OFFICIAL' || !sourceId || typeof videoId !== 'string' || !YOUTUBE_VIDEO_ID.test(videoId)
    || !isExactYoutubeWatchUrl(source?.source_url, videoId)) {
    return emptyRuntime(source, {...clientPolicy, api_client_review: review}, 'UNAVAILABLE', retrievedAt);
  }
  if (review !== 'APPROVED') {
    return emptyRuntime(source, {...clientPolicy, api_client_review: review}, 'NOT_CONFIGURED', null);
  }
  if (!apiResponse || !Array.isArray(apiResponse.items) || apiResponse.items.length === 0) {
    return emptyRuntime(source, {...clientPolicy, api_client_review: review}, 'UNAVAILABLE', retrievedAt);
  }
  if (apiResponse.items.length !== 1) {
    return emptyRuntime(source, {...clientPolicy, api_client_review: review}, 'UNAVAILABLE', retrievedAt);
  }

  const item = apiResponse.items[0];
  if (item?.id !== videoId) {
    return emptyRuntime(source, {...clientPolicy, api_client_review: review}, 'ID_MISMATCH', retrievedAt, typeof item?.id === 'string' ? item.id : '');
  }
  const snippet = item?.snippet;
  const verifiedChannelId = source?.provenance?.verified_youtube_channel_id;
  if (!verifiedChannelId || typeof snippet?.channelId !== 'string' || snippet.channelId !== verifiedChannelId) {
    return emptyRuntime(source, {...clientPolicy, api_client_review: review}, 'PUBLISHER_MISMATCH', retrievedAt, item.id);
  }
  const thumbnail = chooseReturnedThumbnail(snippet.thumbnails);
  if (typeof snippet.title !== 'string' || !snippet.title.trim()
    || typeof snippet.channelTitle !== 'string' || !snippet.channelTitle.trim()
    || !thumbnail
    || !CLICK_TARGETS.has(clientPolicy?.click_target)) {
    return emptyRuntime(source, {...clientPolicy, api_client_review: review}, 'UNAVAILABLE', retrievedAt, item.id);
  }

  return {
    provider: 'YOUTUBE_DATA_API',
    source_id: sourceId,
    provider_video_id: item.id,
    status: 'CURRENT',
    api_client_review: review,
    api_data_retrieved_at: retrievedAt,
    delete_or_refresh_by: new Date(now + MAX_API_DATA_AGE_MS).toISOString(),
    youtube_title: snippet.title,
    channel_id: snippet.channelId,
    channel_title: snippet.channelTitle,
    thumbnail,
    attribution_required: true,
    click_target: clientPolicy.click_target,
    embed_permission: EMBED_PERMISSIONS.has(source?.video_source?.embed_permission)
      ? source.video_source.embed_permission
      : 'UNKNOWN',
  };
}

/**
 * Resolve only an already-reviewed GOAL96 runtime sidecar for the exact source.
 * Catalog thumbnail_url values are deliberately not consulted here.
 */
export function resolveYoutubeThumbnail(source, runtime, now = Date.now()) {
  if (source?.provider !== 'YOUTUBE_OFFICIAL') return {status: 'NOT_YOUTUBE', thumbnail: null};
  const videoId = source?.video_id;
  if (typeof videoId !== 'string' || !YOUTUBE_VIDEO_ID.test(videoId)) return {status: 'INVALID_VIDEO_ID', thumbnail: null};
  if (!isExactYoutubeWatchUrl(source?.source_url, videoId)) return {status: 'SOURCE_URL_MISMATCH', thumbnail: null};
  if (runtime?.provider !== 'YOUTUBE_DATA_API' || runtime?.api_client_review !== 'APPROVED') {
    return {status: 'CLIENT_NOT_APPROVED', thumbnail: null};
  }
  if (runtime?.source_id !== sourceIdFor(source) || runtime?.provider_video_id !== videoId) {
    return {status: 'SOURCE_OR_VIDEO_ID_MISMATCH', thumbnail: null};
  }
  if (runtime?.status !== 'CURRENT' || !validTimestampWindow(runtime, now)) {
    return {status: 'STALE_OR_NOT_CURRENT', thumbnail: null};
  }
  const verifiedChannelId = source?.provenance?.verified_youtube_channel_id;
  if (!verifiedChannelId || runtime.channel_id !== verifiedChannelId) {
    return {status: 'PUBLISHER_MISMATCH', thumbnail: null};
  }
  const thumbnail = chooseReturnedThumbnail(runtime.thumbnail?.key ? {[runtime.thumbnail.key]: runtime.thumbnail} : null);
  if (!thumbnail || runtime.attribution_required !== true
    || !CLICK_TARGETS.has(runtime.click_target)
    || !EMBED_PERMISSIONS.has(runtime.embed_permission)
    || typeof runtime.youtube_title !== 'string' || !runtime.youtube_title.trim()
    || typeof runtime.channel_title !== 'string' || !runtime.channel_title.trim()) {
    return {status: 'RUNTIME_CONTRACT_INVALID', thumbnail: null};
  }
  return {
    status: 'CURRENT',
    source_id: runtime.source_id,
    video_id: runtime.provider_video_id,
    title: runtime.youtube_title,
    channel_id: runtime.channel_id,
    channel_title: runtime.channel_title,
    thumbnail,
    retrieved_at: runtime.api_data_retrieved_at,
    refresh_or_delete_by: runtime.delete_or_refresh_by,
    attribution_required: runtime.attribution_required,
    click_target: runtime.click_target,
    embed_permission: runtime.embed_permission,
  };
}
