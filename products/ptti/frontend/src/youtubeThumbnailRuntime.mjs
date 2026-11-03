const YOUTUBE_VIDEO_ID = /^[A-Za-z0-9_-]{11}$/;
export const YOUTUBE_API_DATA_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;
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
  const deleteOrRefreshBy = Number.isFinite(now) ? new Date(now + YOUTUBE_API_DATA_MAX_AGE_MS).toISOString() : null;
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

export function isExactYoutubeWatchUrl(value, videoId) {
  if (typeof value !== 'string') return false;
  try {
    const url = new URL(value);
    return url.protocol === 'https:'
      && (url.hostname === 'www.youtube.com' || url.hostname === 'youtube.com')
      && url.pathname === '/watch'
      && !url.username
      && !url.password
      && !url.hash
      && url.searchParams.getAll('v').length === 1
      && url.searchParams.get('v') === videoId;
  } catch {
    return false;
  }
}

export function chooseYoutubeReturnedThumbnail(thumbnails, desiredWidth) {
  if (!thumbnails || typeof thumbnails !== 'object' || Array.isArray(thumbnails)) return null;
  const ordered = [
    ...THUMBNAIL_KEYS.filter(key => thumbnails[key]).map(key => [key, thumbnails[key]]),
    ...Object.entries(thumbnails).filter(([key]) => !THUMBNAIL_KEYS.includes(key)),
  ];
  const valid = [];
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
    valid.push({key, url: image.url, width: image.width, height: image.height});
  }
  if (Number.isFinite(desiredWidth) && desiredWidth > 0) valid.sort((a,b)=>Math.abs(a.width-desiredWidth)-Math.abs(b.width-desiredWidth));
  return valid[0] ?? null;
}

export function parseYoutubeApiTimestamp(value) {
  if (typeof value !== 'string') return NaN;
  const parts = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.exec(value);
  if (!parts) return NaN;
  const [year, month, day, hour, minute, second] = parts.slice(1).map(Number);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31,leap?29:28,31,30,31,30,31,31,30,31,30,31];
  if (month < 1 || month > 12 || day < 1 || day > days[month-1] || hour > 23 || minute > 59 || second > 59) return NaN;
  return Date.parse(value);
}

export function classifyYoutubeApiFreshness(retrievedAt, refreshBy, now = Date.now()) {
  const fetched = parseYoutubeApiTimestamp(retrievedAt);
  const expiry = parseYoutubeApiTimestamp(refreshBy);
  if (!Number.isFinite(now) || !Number.isFinite(fetched) || !Number.isFinite(expiry)
    || fetched > now || expiry <= fetched || expiry > fetched + YOUTUBE_API_DATA_MAX_AGE_MS) return 'INVALID';
  return expiry > now ? 'FRESH' : 'STALE';
}

function validTimestampWindow(runtime, now) {
  return classifyYoutubeApiFreshness(runtime?.api_data_retrieved_at, runtime?.delete_or_refresh_by, now) === 'FRESH';
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
  const thumbnail = chooseYoutubeReturnedThumbnail(snippet.thumbnails);
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
    delete_or_refresh_by: new Date(now + YOUTUBE_API_DATA_MAX_AGE_MS).toISOString(),
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
  const thumbnail = chooseYoutubeReturnedThumbnail(runtime.thumbnail?.key ? {[runtime.thumbnail.key]: runtime.thumbnail} : null);
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
