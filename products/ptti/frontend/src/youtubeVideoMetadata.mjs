import {
  youtubeThumbnailSourceId, isExactYoutubeWatchUrl, chooseYoutubeReturnedThumbnail,
  classifyYoutubeApiFreshness, parseYoutubeApiTimestamp, YOUTUBE_API_DATA_MAX_AGE_MS, resolveYoutubeThumbnail,
} from './youtubeThumbnailRuntime.mjs';
import {resolveEditorialMatchPhoto} from './thumbnailPermission.mjs';

const VIDEO_ID = /^[A-Za-z0-9_-]{11}$/;
export const YOUTUBE_METADATA_MAX_AGE_MS = YOUTUBE_API_DATA_MAX_AGE_MS;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);

/** Validate provider field types before normalization. Missing fields stay unknown. */
export function validateYoutubeVideosListResponse(response) {
  const fail = () => {throw new TypeError('Invalid YouTube videos.list response contract');};
  if (!object(response) || !Array.isArray(response.items)) fail();
  for (const item of response.items) {
    if (!object(item) || typeof item.id !== 'string' || !VIDEO_ID.test(item.id)) fail();
    if (item.snippet !== undefined) {
      if (!object(item.snippet)) fail();
      for (const key of ['title','channelId','channelTitle','publishedAt']) {
        if (item.snippet[key] !== undefined && typeof item.snippet[key] !== 'string') fail();
      }
      if (item.snippet.publishedAt !== undefined && !Number.isFinite(parseYoutubeApiTimestamp(item.snippet.publishedAt))) fail();
      if (item.snippet.thumbnails !== undefined) {
        if (!object(item.snippet.thumbnails)) fail();
        for (const image of Object.values(item.snippet.thumbnails)) {
          if (!object(image)) fail();
          if (image.url !== undefined && typeof image.url !== 'string') fail();
          for (const key of ['width','height']) if (image[key] !== undefined && (!Number.isInteger(image[key]) || image[key] <= 0)) fail();
        }
      }
    }
    if (item.contentDetails !== undefined && (!object(item.contentDetails)
      || item.contentDetails.duration !== undefined && (typeof item.contentDetails.duration !== 'string'
      || !/^P(?=.+)(?:[0-9]+D)?(?:T(?=.+)(?:[0-9]+H)?(?:[0-9]+M)?(?:[0-9]+(?:\.[0-9]+)?S)?)?$/.test(item.contentDetails.duration)))) fail();
    if (item.status !== undefined && (!object(item.status)
      || item.status.privacyStatus !== undefined && !['public','private','unlisted'].includes(item.status.privacyStatus)
      || item.status.embeddable !== undefined && typeof item.status.embeddable !== 'boolean')) fail();
  }
  return true;
}

function validThumbnail(image) { return chooseYoutubeReturnedThumbnail({candidate:image}) !== null; }

/** Preserve the exact returned URL and dimensions; selection delegates to the existing runtime. */
export function chooseApiThumbnail(thumbnails, desiredWidth = 480) {
  const image = chooseYoutubeReturnedThumbnail(thumbnails, desiredWidth);
  return image ? {...image, aspect_ratio: image.width / image.height,
    aspect_ratio_is_16_9: Math.abs(image.width / image.height - 16 / 9) < 0.01} : null;
}

/** Map a batch API response to already registered rows. Does not infer new IDs or match links. */
export function mapYoutubeVideosList(catalogRows, apiResponse, fetchedAt, {dataOrigin = 'UNVERIFIED_RESPONSE'} = {}) {
  if (!Array.isArray(catalogRows)) throw new TypeError('catalogRows must be an array');
  validateYoutubeVideosListResponse(apiResponse);
  const fetchedMs = parseYoutubeApiTimestamp(fetchedAt);
  if (!Number.isFinite(fetchedMs)) throw new TypeError('fetchedAt must be a valid timestamp');
  const itemsById = new Map();
  const duplicateIds = new Set();
  for (const item of apiResponse.items) {
    if (typeof item?.id !== 'string' || !VIDEO_ID.test(item.id)) continue;
    if (itemsById.has(item.id)) duplicateIds.add(item.id);
    else itemsById.set(item.id, item);
  }

  return catalogRows.filter(row => row?.provider === 'YOUTUBE_OFFICIAL').map(row => {
    const videoId = row.video_id;
    const registeredId = typeof videoId === 'string' && VIDEO_ID.test(videoId) ? videoId : null;
    const sourceId = registeredId ? youtubeThumbnailSourceId(row) : null;
    const validSourceUrl = registeredId && isExactYoutubeWatchUrl(row.source_url, registeredId) ? row.source_url : null;
    const item = registeredId ? itemsById.get(registeredId) : null;
    const identityStatus = !registeredId || !validSourceUrl
      ? 'CATALOG_ID_OR_URL_INVALID'
      : duplicateIds.has(registeredId)
        ? 'DUPLICATE_API_ID'
        : !item
          ? 'NOT_RETURNED'
          : item.id === registeredId ? 'VIDEO_ID_MATCH' : 'VIDEO_ID_MISMATCH';
    const snippet = item?.snippet;
    const thumbnail = identityStatus === 'VIDEO_ID_MATCH' ? chooseApiThumbnail(snippet?.thumbnails) : null;
    const expectedChannelId = row?.provenance?.verified_youtube_channel_id;
    return {
      schema_version: 'ptti.youtube-video-metadata-poc/0.1',
      data_origin: ['MOCK', 'LIVE_API_TRANSPORT'].includes(dataOrigin) ? dataOrigin : 'UNVERIFIED_RESPONSE',
      source_id: sourceId,
      video_id: registeredId,
      match_id: typeof row.match_id === 'string' ? row.match_id : null,
      source_url: validSourceUrl,
      identity_status: identityStatus,
      title: identityStatus === 'VIDEO_ID_MATCH' && typeof snippet?.title === 'string' ? snippet.title : null,
      channel_id: identityStatus === 'VIDEO_ID_MATCH' && typeof snippet?.channelId === 'string' ? snippet.channelId : null,
      channel_title: identityStatus === 'VIDEO_ID_MATCH' && typeof snippet?.channelTitle === 'string' ? snippet.channelTitle : null,
      channel_identity_status: !expectedChannelId ? 'UNVERIFIED' : snippet?.channelId === expectedChannelId ? 'MATCH' : 'MISMATCH',
      published_at: identityStatus === 'VIDEO_ID_MATCH' ? snippet?.publishedAt ?? null : null,
      thumbnails: identityStatus === 'VIDEO_ID_MATCH' && snippet?.thumbnails && typeof snippet.thumbnails === 'object'
        ? Object.fromEntries(Object.entries(snippet.thumbnails).filter(([, image]) => validThumbnail(image)).map(([key, image]) => [key, {url:image.url, width:image.width, height:image.height}]))
        : {},
      selected_thumbnail: thumbnail,
      duration: identityStatus === 'VIDEO_ID_MATCH' ? item?.contentDetails?.duration ?? null : null,
      privacy_status: identityStatus === 'VIDEO_ID_MATCH' ? item?.status?.privacyStatus ?? null : null,
      embeddable: identityStatus === 'VIDEO_ID_MATCH' && typeof item?.status?.embeddable === 'boolean' ? item.status.embeddable : null,
      embedding_evidence_status: 'API_FIELD_ONLY_NOT_PERMISSION',
      fetched_at: fetchedAt,
      refresh_or_delete_by: new Date(fetchedMs + YOUTUBE_METADATA_MAX_AGE_MS).toISOString(),
      metadata_freshness: 'FRESH_AT_FETCH',
      display_state: 'NO_IMAGE_FALLBACK',
      display_block_reason: 'API client and specific thumbnail display review are not approved; metadata alone grants no display permission.',
    };
  });
}

export function classifyMetadataFreshness(record, now = Date.now()) {
  return classifyYoutubeApiFreshness(record?.fetched_at, record?.refresh_or_delete_by, now);
}

/** Refresh failure may use a still-fresh prior response, never an expired one. In-memory only. */
export function keepFreshMetadataAfterRefreshFailure(previous, now = Date.now()) {
  return classifyMetadataFreshness(previous, now) === 'FRESH' ? previous : null;
}

/** Delegates all image permission checks to the existing Cinema gates. No independent grant rules. */
export function resolveMetadataCoverState({metadata, source, manifest, runtime = null, mode = 'DISTRIBUTABLE', now = Date.now()}) {
  const photo = resolveEditorialMatchPhoto(source, now);
  const listed = photo && Array.isArray(manifest?.assets) && manifest.assets.some(asset =>
    asset?.source_id === youtubeThumbnailSourceId(source) && asset?.video_id === source?.video_id
      && asset?.media_sha256 === photo.media_sha256 && asset?.display_url === photo.display_url);
  if (listed) return {state:'AUTHORIZED_MEDIA',url:photo.display_url,source_id:youtubeThumbnailSourceId(source)};

  const resolved = resolveYoutubeThumbnail(source, runtime, now);
  const sameRawImage = resolved.thumbnail && Object.values(metadata?.thumbnails ?? {}).some(image =>
    image?.url === resolved.thumbnail.url && image?.width === resolved.thumbnail.width && image?.height === resolved.thumbnail.height);
  if (mode === 'INTERNAL_FOUNDER_REVIEW' && metadata?.data_origin === 'LIVE_API_TRANSPORT'
    && classifyMetadataFreshness(metadata, now) === 'FRESH' && metadata?.identity_status === 'VIDEO_ID_MATCH'
    && metadata?.privacy_status === 'public' && metadata?.channel_identity_status === 'MATCH'
    && metadata?.video_id === source?.video_id && metadata?.source_id === youtubeThumbnailSourceId(source)
    && metadata?.source_url === source?.source_url && metadata?.channel_id === resolved.channel_id
    && metadata?.title === resolved.title && resolved.status === 'CURRENT' && sameRawImage) {
    return {state:'YOUTUBE_API_THUMBNAIL',url:resolved.thumbnail.url,source_id:resolved.source_id};
  }
  return {state:'NO_IMAGE_FALLBACK',url:null,source_id:metadata?.source_id ?? null};
}
