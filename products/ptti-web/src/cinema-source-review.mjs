const REVIEW_VERSION = 'ptti.cinema-source-review/0.1';
const SOURCE_VERSION = 'ptti.match-library-index/0.1';
const INPUT_VERSION = 'ptti.cinema-source-review-input/0.1';
const REVIEW_AUDIENCE = 'INTERNAL_REVIEW_ONLY';
const DISCIPLINES = new Set(['MS', 'WS', 'MD', 'WD', 'XD']);
const PERMISSIONS = new Set(['ALLOWED', 'NOT_ALLOWED', 'NOT_GRANTED', 'UNKNOWN']);
const DATE_STATUSES = new Set(['OFFICIAL_REPORT_DATE', 'SECONDARY_CATALOG_ONLY', 'UNKNOWN']);
const COMPLETENESS = new Set(['VERIFIED', 'UNVERIFIED']);
const EVIDENCE_HOSTS = new Map([
  ['OFFICIAL_MATCH_RESULT', new Set(['worldtabletennis.com', 'www.worldtabletennis.com', 'china-smash.com', 'www.china-smash.com', 'ittf.com', 'www.ittf.com', 'singaporesmash.com', 'www.singaporesmash.com'])],
  ['OFFICIAL_EVENT_INFO', new Set(['worldtabletennis.com', 'www.worldtabletennis.com', 'china-smash.com', 'www.china-smash.com', 'ittf.com', 'www.ittf.com', 'singaporesmash.com', 'www.singaporesmash.com'])],
  ['SECONDARY_STREAMING_CATALOG', new Set(['mewatch.sg', 'www.mewatch.sg'])],
]);

function reject(condition, message) {
  if (!condition) throw new Error(`Cinema source review rejected: ${message}`);
}

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function exactKeys(value, expected, label) {
  reject(isObject(value), `${label} must be an object`);
  const actual = Object.keys(value).sort();
  const sorted = [...expected].sort();
  reject(actual.length === sorted.length && actual.every((key, index) => key === sorted[index]), `${label} has unsupported or missing fields`);
}

function text(value, label) {
  reject(typeof value === 'string' && value.trim().length > 0, `${label} must be non-empty text`);
  return value;
}

function timestamp(value, label) {
  text(value, label);
  reject(/(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value)), `${label} must be a timezone-qualified timestamp`);
  return value;
}

function httpsUrl(value, label, allowedHosts = null) {
  text(value, label);
  let url;
  try { url = new URL(value); } catch { throw new Error(`Cinema source review rejected: ${label} must be a valid HTTPS URL`); }
  reject(url.protocol === 'https:' && !url.username && !url.password && !url.port, `${label} must be HTTPS without credentials or a custom port`);
  if (allowedHosts) reject(allowedHosts.has(url.hostname), `${label} host is not allowed for its evidence role`);
  return url;
}

function permission(value, label) {
  reject(PERMISSIONS.has(value), `${label} has an unsupported permission state`);
  return value;
}

function consumeEvidence(row, index) {
  const label = `evidence_sources[${index}]`;
  exactKeys(row, ['role', 'url', 'claims'], label);
  reject(EVIDENCE_HOSTS.has(row.role), `${label}.role is unsupported`);
  httpsUrl(row.url, `${label}.url`, EVIDENCE_HOSTS.get(row.role));
  reject(Array.isArray(row.claims) && row.claims.length > 0 && row.claims.every((claim) => typeof claim === 'string' && claim.trim()), `${label}.claims must be a non-empty text list`);
  return { role: row.role, url: row.url, claims: [...row.claims] };
}

function consumeSource(row, index) {
  const label = `featured_sources[${index}]`;
  exactKeys(row, ['source_id', 'catalog_record_id', 'video_id', 'platform', 'original_source_url', 'watch_entry', 'publisher_metadata', 'match_claim', 'match_link', 'watch_status', 'content_claim', 'rights', 'thumbnail', 'audience', 'next_evidence_needed'], label);
  const sourceId = text(row.source_id, `${label}.source_id`);
  const videoId = text(row.video_id, `${label}.video_id`);
  reject(row.platform === 'YOUTUBE', `${label}.platform must match the v0.1 reviewed YouTube subset`);
  const sourceUrl = httpsUrl(row.original_source_url, `${label}.original_source_url`);
  reject(sourceUrl.hostname === 'www.youtube.com' && sourceUrl.pathname === '/watch' && sourceUrl.searchParams.get('v') === videoId && sourceUrl.searchParams.getAll('v').length === 1,
    `${label}.original_source_url must identify this exact YouTube video`);
  reject(row.watch_entry === 'OPEN_OFFICIAL_PLATFORM_URL', `${label}.watch_entry is unsupported`);
  reject(row.audience === REVIEW_AUDIENCE, `${label}.audience is not internal-only`);

  exactKeys(row.publisher_metadata, ['method', 'checked_at', 'title', 'author_name', 'author_url', 'status'], `${label}.publisher_metadata`);
  reject(row.publisher_metadata.method === 'YOUTUBE_OEMBED_SINGLE_LOOKUP', `${label}.publisher_metadata.method is unsupported`);
  timestamp(row.publisher_metadata.checked_at, `${label}.publisher_metadata.checked_at`);
  text(row.publisher_metadata.title, `${label}.publisher_metadata.title`);
  text(row.publisher_metadata.author_name, `${label}.publisher_metadata.author_name`);
  httpsUrl(row.publisher_metadata.author_url, `${label}.publisher_metadata.author_url`, new Set(['www.youtube.com']));
  reject(row.publisher_metadata.status === 'MATCHES_SNAPSHOT_METADATA_AFFILIATION_AND_RIGHTS_SCOPE_NOT_PROVEN', `${label}.publisher_metadata.status overstates or changes evidence`);

  const claim = row.match_claim;
  exactKeys(claim, ['event_name', 'event_year', 'discipline', 'round', 'participants', 'status', 'match_date', 'event_window', 'evidence_sources', 'official_source_references_video_id'], `${label}.match_claim`);
  text(claim.event_name, `${label}.match_claim.event_name`);
  reject(Number.isInteger(claim.event_year) && claim.event_year >= 1900 && claim.event_year <= 2100, `${label}.match_claim.event_year is invalid`);
  reject(DISCIPLINES.has(claim.discipline), `${label}.match_claim.discipline is unsupported`);
  text(claim.round, `${label}.match_claim.round`);
  reject(Array.isArray(claim.participants) && [2, 4].includes(claim.participants.length) && claim.participants.every((name) => typeof name === 'string' && name.trim()), `${label}.match_claim.participants is invalid`);
  text(claim.status, `${label}.match_claim.status`);
  exactKeys(claim.match_date, ['value', 'status', 'local_start_time'], `${label}.match_claim.match_date`);
  reject(DATE_STATUSES.has(claim.match_date.status), `${label}.match_claim.match_date.status is unsupported`);
  reject(claim.match_date.local_start_time === null, `${label}.match_claim.match_date.local_start_time must remain unknown`);
  if (claim.match_date.value === null) reject(claim.match_date.status === 'UNKNOWN', `${label}.null match date must remain UNKNOWN`);
  else {
    reject(typeof claim.match_date.value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(claim.match_date.value) && Number.isFinite(Date.parse(`${claim.match_date.value}T00:00:00Z`)), `${label}.match_claim.match_date.value must be an ISO date or null`);
    reject(claim.match_date.status !== 'UNKNOWN' && Number(claim.match_date.value.slice(0, 4)) === claim.event_year, `${label}.dated claim must retain a non-UNKNOWN matching year`);
  }
  if (claim.event_window === null) {
    // An absent event window remains absent; it is not inferred from the video title.
  } else {
    exactKeys(claim.event_window, ['start', 'end', 'status'], `${label}.match_claim.event_window`);
    for (const key of ['start', 'end']) reject(typeof claim.event_window[key] === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(claim.event_window[key]) && Number.isFinite(Date.parse(`${claim.event_window[key]}T00:00:00Z`)), `${label}.match_claim.event_window.${key} is invalid`);
    reject(claim.event_window.status === 'OFFICIAL_EVENT_INFO' && claim.event_window.start <= claim.event_window.end, `${label}.match_claim.event_window status or order is invalid`);
  }
  reject(Array.isArray(claim.evidence_sources) && claim.evidence_sources.length > 0, `${label}.match_claim.evidence_sources is missing`);
  const evidence = claim.evidence_sources.map(consumeEvidence);
  reject(claim.official_source_references_video_id === false, `${label} cannot establish a canonical video-to-match link`);

  exactKeys(row.match_link, ['canonical_match_id', 'status', 'unlinked_review_candidate_match_id', 'reason', 'join_policy'], `${label}.match_link`);
  reject(row.match_link.canonical_match_id === null && row.match_link.status === 'UNKNOWN', `${label}.match_link cannot be promoted`);
  reject(row.match_link.unlinked_review_candidate_match_id === null || typeof row.match_link.unlinked_review_candidate_match_id === 'string', `${label}.unlinked_review_candidate_match_id is invalid`);
  text(row.match_link.reason, `${label}.match_link.reason`);
  reject(row.match_link.join_policy === 'EXACT_EVIDENCE_REQUIRED_NO_AUTOMATIC_JOIN_BY_TITLE_EVENT_OR_PLAYER_NAME', `${label}.match_link.join_policy is unsafe`);

  exactKeys(row.watch_status, ['official_page_request', 'page_checked_at', 'external_visual_video_playback', 'external_viewing_rights', 'territory_status', 'login_or_region_check', 'in_app_embedding_permission', 'latest_recorded_embed_technical_status', 'in_app_entry', 'unavailability_or_limit_reason'], `${label}.watch_status`);
  reject(['HTTP_200_PAGE_ONLY', 'HTTP_NON_200_REVIEW_REQUIRED'].includes(row.watch_status.official_page_request), `${label}.watch_status.official_page_request is invalid`);
  timestamp(row.watch_status.page_checked_at, `${label}.watch_status.page_checked_at`);
  reject(row.watch_status.external_visual_video_playback === 'NOT_TESTED' && row.watch_status.login_or_region_check === 'NOT_TESTED', `${label} cannot claim visual playback or region/login verification`);
  permission(row.watch_status.external_viewing_rights, `${label}.watch_status.external_viewing_rights`);
  permission(row.watch_status.in_app_embedding_permission, `${label}.watch_status.in_app_embedding_permission`);
  text(row.watch_status.territory_status, `${label}.watch_status.territory_status`);
  text(row.watch_status.latest_recorded_embed_technical_status, `${label}.watch_status.latest_recorded_embed_technical_status`);
  reject(row.watch_status.in_app_entry === 'EXTERNAL_ONLY_PERMISSION_UNVERIFIED', `${label}.watch_status.in_app_entry must remain external-only`);
  text(row.watch_status.unavailability_or_limit_reason, `${label}.watch_status.unavailability_or_limit_reason`);

  exactKeys(row.content_claim, ['publisher_title_claim', 'completeness', 'completeness_status'], `${label}.content_claim`);
  reject(['FULL_MATCH', 'HIGHLIGHTS', 'SESSION', 'CLIP', 'UNKNOWN'].includes(row.content_claim.publisher_title_claim), `${label}.content_claim.publisher_title_claim is invalid`);
  reject(COMPLETENESS.has(row.content_claim.completeness), `${label}.content_claim.completeness is invalid`);
  reject(row.content_claim.completeness_status === 'UNVERIFIED_TITLE_IS_NOT_COMPLETENESS_EVIDENCE', `${label}.content_claim.completeness_status overstates completeness`);

  exactKeys(row.rights, ['public_listing', 'external_viewing', 'thumbnail_display', 'embedding', 'local_analysis', 'redistribution'], `${label}.rights`);
  const rights = Object.fromEntries(Object.entries(row.rights).map(([key, value]) => [key, permission(value, `${label}.rights.${key}`)]));
  exactKeys(row.thumbnail, ['url', 'display_permission', 'presentation'], `${label}.thumbnail`);
  reject(row.thumbnail.url === null && row.thumbnail.presentation === 'PTTI_BRAND_PLACEHOLDER_ONLY', `${label}.thumbnail must not expose an unlicensed image URL`);
  permission(row.thumbnail.display_permission, `${label}.thumbnail.display_permission`);
  reject(Array.isArray(row.next_evidence_needed) && row.next_evidence_needed.length > 0 && row.next_evidence_needed.every((item) => typeof item === 'string' && item.trim()), `${label}.next_evidence_needed must be explicit`);

  return {
    source_id: sourceId,
    catalog_record_id: text(row.catalog_record_id, `${label}.catalog_record_id`),
    video_id: videoId,
    platform: row.platform,
    original_source_url: sourceUrl.href,
    watch_entry: 'EXTERNAL_SOURCE_LINK_ONLY',
    publisher_metadata: { ...row.publisher_metadata },
    match_claim: { ...claim, participants: [...claim.participants], evidence_sources: evidence },
    match_link: { ...row.match_link },
    watch_status: { ...row.watch_status },
    content_claim: { ...row.content_claim },
    rights,
    thumbnail: { url: null, display_permission: row.thumbnail.display_permission, presentation: 'PTTI_BRAND_PLACEHOLDER_ONLY' },
    audience: REVIEW_AUDIENCE,
    next_evidence_needed: [...row.next_evidence_needed],
  };
}

export function consumeCinemaSourceReview(input) {
  exactKeys(input, ['contract_version', 'source_contract_version', 'input_contract_version', 'audience', 'generated_at', 'catalog_snapshot', 'summary', 'featured_sources', 'notice'], 'report');
  reject(input.contract_version === REVIEW_VERSION && input.source_contract_version === SOURCE_VERSION && input.input_contract_version === INPUT_VERSION, 'unsupported protocol version');
  reject(input.audience === REVIEW_AUDIENCE, 'report is not internal-review-only');
  timestamp(input.generated_at, 'generated_at');
  exactKeys(input.catalog_snapshot, ['unique_video_sources', 'registered_match_records', 'canonical_video_match_links', 'strict_public_video_source_count'], 'catalog_snapshot');
  for (const key of ['unique_video_sources', 'registered_match_records', 'canonical_video_match_links', 'strict_public_video_source_count']) reject(Number.isSafeInteger(input.catalog_snapshot[key]) && input.catalog_snapshot[key] >= 0, `catalog_snapshot.${key} must be a non-negative integer`);
  reject(input.catalog_snapshot.strict_public_video_source_count === 0 && input.catalog_snapshot.canonical_video_match_links === 0, 'public or canonical match projection must remain empty');
  exactKeys(input.summary, ['selected_sources', 'official_pages_http_200', 'external_visual_playback_pass', 'canonical_match_links', 'public_projection_fallback'], 'summary');
  reject(Array.isArray(input.featured_sources) && input.featured_sources.length >= 1 && input.featured_sources.length <= 3, 'featured_sources must contain one to three selected records');
  reject(input.summary.selected_sources === input.featured_sources.length, 'selected source count does not match records');
  reject(Number.isSafeInteger(input.summary.official_pages_http_200) && input.summary.official_pages_http_200 >= 0 && input.summary.official_pages_http_200 <= input.featured_sources.length, 'official page count is invalid');
  reject(input.summary.external_visual_playback_pass === 0 && input.summary.canonical_match_links === 0 && input.summary.public_projection_fallback === false, 'summary promotes playback, match links, or public fallback');
  const seen = new Set();
  const sources = input.featured_sources.map((row, index) => {
    const source = consumeSource(row, index);
    reject(!seen.has(source.source_id), 'duplicate source_id');
    seen.add(source.source_id);
    return source;
  });
  text(input.notice, 'notice');
  return {
    contract_version: REVIEW_VERSION,
    source_contract_version: SOURCE_VERSION,
    audience: REVIEW_AUDIENCE,
    generated_at: input.generated_at,
    catalog_snapshot: { ...input.catalog_snapshot },
    summary: { ...input.summary },
    sources,
    notice: input.notice,
  };
}
