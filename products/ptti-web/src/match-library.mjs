const fields = ['public_listing', 'external_viewing', 'thumbnail_display', 'embedding', 'local_analysis', 'redistribution'];
const rightsValues = ['ALLOWED', 'NOT_ALLOWED', 'UNKNOWN'];
function requireValue(ok, issue) { if (!ok) throw new Error(issue); }
function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
export function consumeMatchLibrary(input, view) {
  requireValue(object(input) && input.contract_version === 'ptti.match-library-index/0.1', 'unsupported-library-version');
  requireValue(['INTERNAL_REVIEW', 'STRICT_PUBLIC'].includes(view) && input.view === view, 'library-view-mismatch');
  for (const key of ['matches', 'video_sources', 'stars', 'local_video_assets', 'evidence_sources', 'source_manifest']) requireValue(Array.isArray(input[key]), `invalid-${key}`);
  requireValue(input.local_video_assets.length === 0, 'private-media-not-allowed');
  const compatibility = input.analysis_compatibility;
  requireValue(object(compatibility) && compatibility.automatic_join_by_title_or_player_name === false && compatibility.join_policy === 'EXACT_MATCH_ID_AND_SOURCE_ID_WITH_EVIDENCE_ONLY' && compatibility.playback_eligibility === 'NOT_EVALUATED_CURRENT_SESSION', 'unsafe-library-join-policy');
  if (view === 'STRICT_PUBLIC') {
    requireValue(['matches', 'video_sources', 'stars', 'evidence_sources'].every(key => input[key].length === 0), 'public-grant-evidence-not-supported');
    return { view, sources: [], registered_match_count: 0, source_count: 0 };
  }
  requireValue(input.matches.every(match => object(match) && Array.isArray(match.video_source_ids) && match.video_source_ids.length === 0 && match.match_video_link_status === 'UNKNOWN'), 'unreviewed-match-association');
  const seen = new Set();
  const sources = input.video_sources.map(source => {
    requireValue(object(source) && ['YOUTUBE','BILIBILI'].includes(source.platform) && typeof source.video_id === 'string' && source.video_id.length > 0, 'invalid-source');
    requireValue(source.source_id === `video-source:${source.platform.toLowerCase()}:${source.video_id}` && !seen.has(source.source_id), 'duplicate-or-invalid-source-id'); seen.add(source.source_id);
    requireValue(source.canonical_match_id === null && source.match_link_status === 'UNKNOWN', 'unreviewed-source-association');
    requireValue(source.watch_entry === 'OPEN_OFFICIAL_PLATFORM_URL', 'invalid-watch-entry');
    let url; try { url = new URL(source.official_url); } catch { throw new Error('invalid-source-url'); }
    requireValue(url.protocol === 'https:' && !url.username && !url.password && !url.port && (source.platform === 'YOUTUBE' ? url.hostname === 'www.youtube.com' && url.pathname === '/watch' && url.searchParams.get('v') === source.video_id : url.hostname === 'www.bilibili.com' && url.pathname === `/video/${source.video_id}/`), 'invalid-source-url');
    requireValue(object(source.thumbnail) && source.thumbnail.url === null, 'thumbnail-permission-unknown');
    requireValue(object(source.rights) && fields.every(key => (['local_analysis','redistribution'].includes(key) ? [...rightsValues, 'NOT_GRANTED'] : rightsValues).includes(source.rights[key])), 'invalid-rights');
    requireValue(object(source.availability) && source.availability.current_session_eligibility === 'NOT_EVALUATED_CURRENT_SESSION' && source.availability.vision_analysis === 'NOT_TESTED', 'invalid-playback-evidence');
    for (const key of ['title', 'event', 'match_type', 'source_identity_status', 'publisher_identity_status']) requireValue(typeof source[key] === 'string', `invalid-${key}`);
    requireValue(typeof source.availability.latest_recorded_playback_status === 'string' && typeof source.availability.territory_availability === 'string', 'invalid-availability');
    return { source_id: source.source_id, title: source.title, event: source.event, match_type: source.match_type, url: source.rights.external_viewing === 'NOT_ALLOWED' ? null : url.href, platform: source.platform, source_identity_status: source.source_identity_status, publisher_identity_status: source.publisher_identity_status, recorded_playback_status: source.availability.latest_recorded_playback_status, territory: source.availability.territory_availability, rights: Object.fromEntries(fields.map(key => [key, source.rights[key]])), match_link_status: 'UNKNOWN', current_session_eligibility: 'NOT_EVALUATED_CURRENT_SESSION' };
  });
  return { view, sources, registered_match_count: input.matches.length, source_count: sources.length };
}
