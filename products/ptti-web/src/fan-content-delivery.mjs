const DELIVERY_VERSION = 'ptti.fan-content-delivery/0.1';
const BASE_VERSION = 'ptti.fan-content-intelligence/0.1';
const ALL_ZERO_RIGHTS = Object.freeze({
  public_listing: 'UNKNOWN',
  external_viewing: 'UNKNOWN',
  embedding: 'UNKNOWN',
  thumbnail_display: 'UNKNOWN',
  local_analysis: 'NOT_GRANTED',
  download: 'NOT_GRANTED',
  redistribution: 'NOT_GRANTED',
  evidence_status: 'NO_SCOPED_GRANT_RECORDED',
});

function fail(code) { throw new Error(code); }
function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function requireObject(value, code) { if (!object(value)) fail(code); }
function requireArray(value, code) { if (!Array.isArray(value)) fail(code); }
function requireString(value, code) { if (typeof value !== 'string' || !value.trim()) fail(code); }
function requireHash(value, code) { if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) fail(code); }
function requireRights(rights, code) {
  requireObject(rights, code);
  for (const [key, expected] of Object.entries(ALL_ZERO_RIGHTS)) {
    if (rights[key] !== expected) fail(code);
  }
}
function safeHttps(value, allowedHosts, code) {
  let url;
  try { url = new URL(value); } catch { fail(code); }
  if (url.protocol !== 'https:' || url.username || url.password || !allowedHosts.includes(url.hostname)) fail(code);
  return url;
}
function uniqueMap(rows, key, code) {
  const map = new Map();
  for (const row of rows) {
    requireObject(row, code);
    requireString(row[key], code);
    if (map.has(row[key])) fail(code);
    map.set(row[key], row);
  }
  return map;
}

/**
 * Consumer for Main's ptti.fan-content-delivery/0.1 projection.
 * It intentionally keeps event-level candidates separate from matches and
 * never upgrades source, playback, territory, or rights states.
 */
export function consumeGoal14FanDelivery(input) {
  requireObject(input, 'invalid-delivery');
  if (input.contract_version !== DELIVERY_VERSION || input.base_contract_version !== BASE_VERSION) fail('unsupported-delivery-version');
  if (input.view !== 'INTERNAL_REVIEW') fail('internal-review-view-required');
  for (const key of ['stars', 'events', 'matches', 'clips', 'watch_sources', 'relationships', 'relationship_gaps', 'source_index']) requireArray(input[key], `invalid-${key}`);
  if (input.matches.length !== 0) fail('goal14-match-identity-not-established');
  requireObject(input.source_manifest, 'invalid-source-manifest');
  requireHash(input.source_manifest.base_dataset_sha256, 'invalid-base-dataset-sha256');
  requireHash(input.source_manifest.localization_sha256, 'invalid-localization-sha256');
  requireObject(input.quality_summary, 'invalid-quality-summary');
  requireString(input.notice, 'invalid-notice');
  if (!Number.isFinite(Date.parse(input.generated_at))) fail('invalid-generated-at');

  const evidence = uniqueMap(input.source_index, 'evidence_id', 'invalid-source-evidence');
  for (const row of evidence.values()) {
    requireString(row.kind, 'invalid-source-evidence');
    requireString(row.observed_at, 'invalid-source-evidence');
    requireArray(row.claims, 'invalid-source-evidence');
    requireString(row.limitations, 'invalid-source-evidence');
    safeHttps(row.url, ['www.worldtabletennis.com', 'www.youtube.com'], 'unsafe-source-evidence-url');
  }

  const events = uniqueMap(input.events, 'event_id', 'invalid-event');
  for (const event of events.values()) {
    requireString(event.title_original, 'invalid-event');
    requireString(event.title_zh, 'invalid-event');
    requireString(event.provider, 'invalid-event');
    requireRights(event.rights, 'rights-escalation');
    if (event.public_status !== 'INTERNAL_ONLY_PENDING_RIGHTS_REVIEW') fail('public-event-not-admitted');
    const eventUrl = safeHttps(event.official_event_page_url, ['www.worldtabletennis.com'], 'unsafe-event-url');
    if (event.official_viewing_route?.url !== eventUrl.href || event.official_viewing_route?.current_access !== 'NOT_TESTED_CURRENT_SESSION'
      || event.official_viewing_route?.territory !== 'UNKNOWN' || event.official_viewing_route?.login_or_paywall !== 'NOT_TESTED') fail('invalid-event-route-state');
  }

  const stars = uniqueMap(input.stars, 'athlete_id', 'invalid-star');
  for (const star of stars.values()) {
    requireString(star.name_en, 'invalid-star');
    requireString(star.name_zh, 'invalid-star');
    if (star.public_listing !== 'UNKNOWN') fail('public-star-not-admitted');
    if (star.official_profile_url !== null) safeHttps(star.official_profile_url, ['www.worldtabletennis.com'], 'unsafe-profile-url');
    if (star.portrait_url !== null) fail('unlicensed-portrait-present');
    if (star.display_permissions && ['profile_listing', 'portrait_display', 'biography_reuse'].some((key) => star.display_permissions[key] !== 'UNKNOWN')) fail('star-permission-escalation');
  }

  const watchSources = uniqueMap(input.watch_sources, 'watch_source_id', 'invalid-watch-source');
  for (const source of watchSources.values()) {
    requireRights(source.rights, 'rights-escalation');
    requireArray(source.evidence_ids, 'invalid-watch-source');
    if (source.current_access !== 'NOT_TESTED_CURRENT_SESSION' || source.playback_status !== 'NOT_TESTED' || source.territory !== 'UNKNOWN'
      || source.login_or_paywall !== 'NOT_TESTED' || source.embed_status !== 'UNKNOWN') fail('watch-state-escalation');
    for (const id of source.evidence_ids) if (!evidence.has(id)) fail('unknown-watch-evidence');
    if (source.route_kind === 'OFFICIAL_YOUTUBE_VIDEO') {
      const url = safeHttps(source.url, ['www.youtube.com'], 'unsafe-watch-url');
      if (url.pathname !== '/watch' || !url.searchParams.get('v') || source.route_status !== 'URL_IDENTIFIED_PLAYBACK_NOT_TESTED') fail('invalid-direct-video-route');
    } else if (source.route_kind === 'OFFICIAL_EVENT_PAGE_LISTING') {
      const url = safeHttps(source.url, ['www.worldtabletennis.com'], 'unsafe-watch-url');
      if (!url.pathname.startsWith('/eventInfo') && !url.pathname.startsWith('/description')) fail('invalid-event-listing-route');
      if (source.route_status !== 'OFFICIAL_LISTING_ONLY_VIDEO_URL_UNRESOLVED') fail('invalid-event-listing-route');
    } else fail('unknown-watch-route-kind');
    if (!source.evidence_ids.some((id) => evidence.get(id)?.url === source.url)) fail('watch-url-not-bound-to-evidence');
  }

  const clips = uniqueMap(input.clips, 'clip_id', 'invalid-clip');
  let exactVideoUrlCount = 0;
  for (const clip of clips.values()) {
    requireString(clip.title_original, 'invalid-clip');
    requireString(clip.title_zh, 'invalid-clip');
    requireString(clip.content_type, 'invalid-clip');
    if (!events.has(clip.event_id)) fail('unknown-clip-event');
    if (clip.match_id !== null || clip.match_link_status !== 'UNKNOWN') fail('guessed-match-link');
    if (clip.playback_status !== 'NOT_TESTED' || clip.territory !== 'UNKNOWN' || clip.login_or_paywall !== 'NOT_TESTED' || clip.embed_status !== 'UNKNOWN') fail('clip-state-escalation');
    if (clip.thumbnail_url !== null) fail('unlicensed-thumbnail-present');
    if (clip.public_status !== 'INTERNAL_ONLY_PENDING_RIGHTS_REVIEW') fail('public-clip-not-admitted');
    requireRights(clip.rights, 'rights-escalation');
    requireArray(clip.source_evidence_ids, 'invalid-clip-evidence');
    if (!clip.source_evidence_ids.length || clip.source_evidence_ids.some((id) => !evidence.has(id))) fail('unknown-clip-evidence');
    const route = watchSources.get(clip.watch_source_id);
    if (!route) fail('unknown-clip-watch-source');
    if (clip.video_id !== null) {
      exactVideoUrlCount += 1;
      const expected = `https://www.youtube.com/watch?v=${clip.video_id}`;
      if (clip.provider !== 'YOUTUBE' || clip.official_video_url !== expected || route.url !== expected || route.route_kind !== 'OFFICIAL_YOUTUBE_VIDEO'
        || route.watch_source_id !== `watch:youtube:${clip.video_id}`) fail('video-id-url-mismatch');
    } else {
      if (clip.official_video_url !== null || route.route_kind !== 'OFFICIAL_EVENT_PAGE_LISTING'
        || route.url !== events.get(clip.event_id).official_event_page_url || route.watch_source_id !== `watch:event-page:${clip.event_id.replace(/^event:/, '')}`) fail('event-page-fallback-mismatch');
    }
  }

  // Check every edge target by its typed ID; the projection must not invent matches.
  for (const relation of input.relationships) {
    requireArray(relation.evidence_ids, 'invalid-relationship');
    if (!relation.evidence_ids.length || relation.evidence_ids.some((id) => !evidence.has(id))) fail('unknown-relationship-evidence');
    const hasRef = (type, id) => type === 'ATHLETE' ? stars.has(id)
      : type === 'EVENT' ? events.has(id)
        : type === 'WATCH_SOURCE' ? watchSources.has(id)
          : type === 'CLIP_CANDIDATE' || type === 'CONTENT_CANDIDATE' ? clips.has(id)
            : false;
    if (!hasRef(relation.from_type, relation.from_id) || !hasRef(relation.to_type, relation.to_id)) fail('dangling-relationship');
    if (relation.to_type === 'MATCH' || relation.from_type === 'MATCH') fail('goal14-match-identity-not-established');
    if (relation.from_type === 'ATHLETE' && relation.to_type === 'EVENT'
      && (relation.relationship_kind !== 'LISTED_ON_EVENT_PLAYER_ROSTER' || relation.confidence_scope !== 'EVENT_ROSTER_LISTING_ONLY_NOT_CLIP_APPEARANCE')) fail('invalid-athlete-event-scope');
  }

  const q = input.quality_summary;
  const expectedSummary = {
    star_count: stars.size,
    event_count: events.size,
    verified_match_count: 0,
    clip_candidate_count: clips.size,
    unique_watch_source_count: watchSources.size,
    exact_video_url_count: exactVideoUrlCount,
    event_page_only_count: clips.size - exactVideoUrlCount,
    playback_pass_count: 0,
    public_eligible_count: 0,
    match_video_links: 0,
  };
  for (const [key, value] of Object.entries(expectedSummary)) if (q[key] !== value) fail(`quality-summary-mismatch:${key}`);
  if (input.relationship_gaps.some((gap) => gap.status !== 'NOT_ESTABLISHED' || !['STAR_TO_MATCH', 'MATCH_TO_CLIP'].includes(gap.path))) fail('invalid-relationship-gap');

  return input;
}

export function consumeGoal14StrictPublic(input) {
  requireObject(input, 'invalid-strict-public');
  if (input.contract_version !== BASE_VERSION || input.view !== 'STRICT_PUBLIC') fail('strict-public-contract-required');
  for (const key of ['events', 'stars', 'content_candidates', 'relationships', 'evidence_sources', 'source_manifest']) requireArray(input[key], `invalid-strict-public-${key}`);
  if (['events', 'stars', 'content_candidates', 'relationships', 'evidence_sources', 'source_manifest'].some((key) => input[key].length !== 0)) fail('strict-public-must-remain-empty');
  const summary = input.quality_summary;
  requireObject(summary, 'invalid-strict-public-summary');
  for (const key of ['event_count', 'star_count', 'candidate_count', 'exact_video_url_count', 'event_page_only_count', 'playback_pass_count', 'public_eligible_count', 'match_video_links']) {
    if (summary[key] !== 0) fail('strict-public-summary-not-empty');
  }
  return input;
}

export function canonicalJsonSha256Input(value) {
  const sort = (item) => Array.isArray(item) ? item.map(sort)
    : object(item) ? Object.fromEntries(Object.keys(item).sort().map((key) => [key, sort(item[key])]))
      : item;
  return `${JSON.stringify(sort(value))}\n`;
}

/** Evaluate all five explicit route modes using the pinned Playback adapter. */
export function evaluateGoal14WatchRoutes(source, evidenceRows, evaluateWatchRoute) {
  if (typeof evaluateWatchRoute !== 'function') throw new TypeError('watch-route-evaluator-required');
  const evidence = evidenceRows instanceof Map ? evidenceRows : new Map((evidenceRows ?? []).map((row) => [row.evidence_id, row]));
  const exactSourceEvidence = (source?.evidence_ids ?? []).some((id) => evidence.get(id)?.url === source?.url);
  const reference = exactSourceEvidence ? 'VERIFIED' : 'UNKNOWN';
  const base = { sourceReference: reference, viewingPermission: 'UNKNOWN', playbackEvidence: 'NOT_TESTED' };
  const candidates = [
    { mode: 'OFFICIAL_EMBED', ...base, playbackType: 'OFFICIAL_EMBED', embedPermission: 'UNKNOWN' },
    { mode: 'OFFICIAL_PAGE', ...base, playbackType: 'OFFICIAL_PAGE' },
    { mode: 'AUTHORIZED_SOURCE', ...base, playbackType: 'AUTHORIZED_STREAM', rightsEvidence: 'UNKNOWN' },
    { mode: 'REPLAY', ...base, playbackType: 'AUTHORIZED_REPLAY', replayType: 'AUTHORIZED_ON_DEMAND', rightsEvidence: 'UNKNOWN' },
    { mode: 'LIVE_SCORE', ...base, liveScore: 'UNKNOWN' },
  ];
  return candidates.map((candidate) => ({ mode: candidate.mode, decision: evaluateWatchRoute(candidate) }));
}

export const GOAL14_DELIVERY_VERSION = DELIVERY_VERSION;
