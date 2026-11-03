export function approvedOfficialThumbnail(source) {
  const permissions = [
    source?.thumbnail_display_permission,
    source?.provenance?.thumbnail_display_permission,
    source?.video_source?.provenance?.thumbnail_display_permission,
  ];
  if (!permissions.includes('ALLOWED') || typeof source?.thumbnail_url !== 'string') return false;
  try {
    const url = new URL(source.thumbnail_url);
    return url.protocol === 'https:' && !url.username && !url.password;
  } catch {
    return false;
  }
}

// Founder-only visual review mode. This returns the exact historical remote URL
// only; it never fetches, transforms, caches, or writes thumbnail bytes.
const founderQaVideoIds = new Set([
  '0QgbtsBWZhk', 'vYsJLPTEIaI', 'aFs7HJ0NX18', 'JTUWXpB-NVo',
  'H77vNFk3neg', 'ekfCZiIEYi0', 'DTPNEl3-2b0', 'iQhVLkcGCFE',
]);
export function resolveInternalFounderQaThumbnail(source, mode = 'DISTRIBUTABLE') {
  if (mode !== 'INTERNAL_FOUNDER_QA' || source?.provider !== 'YOUTUBE_OFFICIAL' ||
      typeof source?.video_id !== 'string' || !/^[A-Za-z0-9_-]{11}$/.test(source.video_id) ||
      !founderQaVideoIds.has(source.video_id) ||
      typeof source?.source_url !== 'string' || typeof source?.thumbnail_url !== 'string') return null;
  const nested = source.video_source;
  if (nested?.source_id && nested.source_id !== source.video_id) return null;
  if (nested?.provider && !['YOUTUBE', 'YOUTUBE_OFFICIAL'].includes(nested.provider)) return null;
  try {
    const watch = new URL(source.source_url);
    const thumbnail = new URL(source.thumbnail_url);
    if (watch.protocol !== 'https:' || watch.hostname !== 'www.youtube.com' || watch.pathname !== '/watch' ||
        watch.username || watch.password || watch.hash || watch.searchParams.getAll('v').length !== 1 ||
        watch.searchParams.get('v') !== source.video_id ||
        thumbnail.protocol !== 'https:' || thumbnail.hostname !== 'i.ytimg.com' ||
        thumbnail.username || thumbnail.password || thumbnail.hash || thumbnail.search ||
        thumbnail.pathname !== `/vi/${source.video_id}/hqdefault.jpg`) return null;
    return source.thumbnail_url;
  } catch {
    return null;
  }
}

// A publisher editorial-use notice is not written permission to distribute an app asset.
export function resolveEditorialMatchPhoto(source, now = Date.now()) {
  const photo = source?.editorial_match_photo;
  const permission = photo?.written_permission;
  if (!Number.isFinite(now) || !photo || photo.schema_version !== 'ptti.editorial-match-photo/0.1' ||
      photo.display_permission !== 'APPROVED_FOR_SPECIFIC_DISPLAY' ||
      photo.distribution_permission !== 'ALLOWED' ||
      !['WEB','WINDOWS_DESKTOP'].every(target=>photo.distribution_targets?.includes(target)&&permission?.targets?.includes(target)) ||
      permission?.local_packaging !== 'ALLOWED' || !permission.evidence_id || !/^[a-f0-9]{64}$/.test(permission.evidence_sha256) ||
      !Number.isFinite(Date.parse(permission.valid_from)) || !Number.isFinite(Date.parse(permission.valid_until)) ||
      now < Date.parse(permission.valid_from) || now >= Date.parse(permission.valid_until) ||
      photo.purpose !== 'EDITORIAL_MATCH_CARD' || photo.permission_basis !== 'WTT_WRITTEN_PERMISSION' ||
      photo.match_relationship !== 'EXACT_MATCH_PHOTOGRAPH' || source.provider !== 'YOUTUBE_OFFICIAL' ||
      photo.source_id !== `video-source:youtube:${source.video_id}` || photo.video_id !== source.video_id ||
      (photo.match_id ?? null) !== (source.match_id ?? null) ||
      photo.watch_url !== source.source_url || photo.binding?.title !== source.title ||
      photo.binding?.event_name !== source.event_name || photo.binding?.round_label !== source.round_label ||
      photo.binding?.discipline !== source.discipline ||
      JSON.stringify(photo.binding?.athlete_names) !== JSON.stringify(source.athlete_names) ||
      (source.video_source?.source_id && source.video_source.source_id !== photo.video_id) ||
      (source.video_source?.provider && !['YOUTUBE','YOUTUBE_OFFICIAL'].includes(source.video_source.provider)) ||
      (source.source_key && ![`YOUTUBE:${photo.video_id}`,`YOUTUBE_OFFICIAL:${photo.video_id}`].includes(source.source_key)) ||
      !/^\/media\/editorial\/wtt-\d+\.jpg$/.test(photo.display_url) ||
      !/^[a-f0-9]{64}$/.test(photo.media_sha256) || !photo.attribution ||
      photo.photo_page_url !== `https://www.flickr.com/photos/wttglobal/${photo.photo_id}/` ||
      photo.permission_evidence_url !== photo.photo_page_url || photo.fit !== 'contain' ||
      photo.crop_permission !== 'NOT_ALLOWED' || photo.promotional_use !== 'NOT_ALLOWED' ||
      !Number.isFinite(Date.parse(photo.reviewed_at)) || !Number.isFinite(Date.parse(photo.review_expires_at)) ||
      now < Date.parse(photo.reviewed_at) || now >= Date.parse(photo.review_expires_at)) return null;
  return photo;
}
