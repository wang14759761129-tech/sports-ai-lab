const CONTRACT = 'ptti.match-library-index/0.1';
const RIGHT_VALUES = ['ALLOWED', 'NOT_ALLOWED', 'UNKNOWN'];

function requireValue(condition, code) {
  if (!condition) throw new Error(code);
}

/** Normalize Chinese/English player and event queries without accent or punctuation sensitivity. */
export function normalizeFanSearch(value) {
  return String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, '');
}

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function requireKeys(value, keys, code) {
  requireValue(isObject(value) && keys.every((key) => Object.hasOwn(value, key)), code);
}

function requireWebUrl(value, code) {
  let url;
  try { url = new URL(value); } catch { throw new Error(code); }
  requireValue(['http:', 'https:'].includes(url.protocol) && !url.username && !url.password, code);
  return url.href;
}

function requireHttps(value, code) {
  const href = requireWebUrl(value, code);
  requireValue(new URL(href).protocol === 'https:', code);
  return href;
}

function requirePlatformUrl(platform, videoId, value) {
  const href = requireHttps(value, 'invalid-source-url');
  const url = new URL(href);
  const youtube = platform === 'YOUTUBE' && url.hostname === 'www.youtube.com' && url.pathname === '/watch' && url.searchParams.get('v') === videoId;
  const bilibili = platform === 'BILIBILI' && url.hostname === 'www.bilibili.com' && url.pathname === `/video/${videoId}/`;
  requireValue(youtube || bilibili, 'invalid-source-url');
  return href;
}

function requireRights(rights, source = false) {
  requireValue(isObject(rights), 'invalid-rights');
  requireValue(RIGHT_VALUES.includes(rights.public_listing), 'invalid-public-listing-right');
  if (source) {
    for (const key of ['external_viewing', 'thumbnail_display', 'embedding']) {
      requireValue(RIGHT_VALUES.includes(rights[key]), `invalid-${key}-right`);
    }
    requireValue(['ALLOWED', 'NOT_ALLOWED', 'UNKNOWN', 'NOT_GRANTED'].includes(rights.local_analysis), 'invalid-local-analysis-right');
    requireValue(['ALLOWED', 'NOT_ALLOWED', 'UNKNOWN', 'NOT_GRANTED'].includes(rights.redistribution), 'invalid-redistribution-right');
  }
}

function projectSourceEvidenceIds(source, evidenceIds) {
  const fromProvenance = [];
  for (const row of source.provenance) {
    requireValue(isObject(row), 'invalid-source-provenance');
    if (!Object.hasOwn(row, 'source_id')) continue;
    const id = row.source_id;
    requireValue(typeof id === 'string' && id.trim().length > 0 && evidenceIds.has(id), 'invalid-source-evidence-id');
    fromProvenance.push(id);
  }

  const fromRights = Object.hasOwn(source.rights, 'evidence_source_ids')
    ? source.rights.evidence_source_ids
    : [];
  requireValue(Array.isArray(fromRights), 'invalid-source-evidence-ids');
  for (const id of fromRights) {
    requireValue(typeof id === 'string' && id.trim().length > 0 && evidenceIds.has(id), 'invalid-source-evidence-id');
  }

  return [...new Set([...fromProvenance, ...fromRights])];
}

/**
 * Consume only Main's STRICT_PUBLIC match-library projection. This deliberately
 * fails closed: internal review data, guessed joins, unlisted rows, and unsafe
 * watch URLs can never become Fan content.
 */
export function consumeFanCatalog(input) {
  requireValue(isObject(input) && input.contract_version === CONTRACT, 'unsupported-library-version');
  requireKeys(input, ['view', 'generated_at', 'source_manifest', 'matches', 'video_sources', 'local_video_assets', 'stars', 'evidence_sources', 'quality_summary', 'analysis_compatibility', 'notice'], 'missing-library-field');
  requireValue(input.view === 'STRICT_PUBLIC', 'strict-public-view-required');
  for (const key of ['matches', 'video_sources', 'local_video_assets', 'stars', 'evidence_sources', 'source_manifest']) {
    requireValue(Array.isArray(input[key]), `invalid-${key}`);
  }
  requireValue(input.local_video_assets.length === 0, 'private-media-not-allowed');
  if (Object.hasOwn(input, 'rights_review_queue')) requireValue(Array.isArray(input.rights_review_queue), 'invalid-rights-review-queue');
  requireValue(typeof input.generated_at === 'string' && typeof input.notice === 'string' && isObject(input.quality_summary), 'invalid-library-metadata');
  for (const item of input.source_manifest) {
    requireKeys(item, ['file', 'sha256'], 'invalid-source-manifest-entry');
    requireValue(typeof item.file === 'string' && /^[a-f0-9]{64}$/.test(item.sha256), 'invalid-source-manifest-entry');
  }
  const compatibility = input.analysis_compatibility;
  requireKeys(compatibility, ['review_targets_version', 'review_evidence_pack_version', 'join_policy', 'automatic_join_by_title_or_player_name', 'playback_eligibility'], 'invalid-analysis-compatibility');
  requireValue(isObject(compatibility)
    && compatibility.review_targets_version === 'ptti.review-targets/0.1'
    && compatibility.review_evidence_pack_version === 'ptti.review-evidence-pack/0.1'
    && compatibility.automatic_join_by_title_or_player_name === false
    && compatibility.join_policy === 'EXACT_MATCH_ID_AND_SOURCE_ID_WITH_EVIDENCE_ONLY'
    && compatibility.playback_eligibility === 'NOT_EVALUATED_CURRENT_SESSION', 'unsafe-library-join-policy');

  const matchesById = new Map();
  const sourcesById = new Map();
  const starsById = new Map();
  const evidenceIds = new Set();

  for (const item of input.evidence_sources) {
    requireKeys(item, ['source_id', 'source_type', 'url', 'retrieved_at', 'description'], 'invalid-evidence-source');
    requireValue(typeof item.source_id === 'string' && item.source_id.length > 0 && typeof item.source_type === 'string' && typeof item.description === 'string', 'invalid-evidence-source');
    requireWebUrl(item.url, 'invalid-evidence-source-url');
    requireValue(!evidenceIds.has(item.source_id), 'duplicate-evidence-source-id');
    evidenceIds.add(item.source_id);
  }

  for (const match of input.matches) {
    requireKeys(match, ['match_id', 'identity_status', 'event', 'match_type', 'round', 'participants', 'recorded_result', 'result_status', 'reference_url', 'evidence_source_ids', 'video_source_ids', 'match_video_link_status', 'rights'], 'invalid-match');
    requireValue(isObject(match) && typeof match.match_id === 'string' && match.match_id.length > 0, 'invalid-match');
    requireRights(match.rights);
    requireValue(match.rights.public_listing === 'ALLOWED', 'unapproved-public-match');
    requireValue(Array.isArray(match.video_source_ids) && Array.isArray(match.evidence_source_ids), 'invalid-match-references');
    requireValue(Array.isArray(match.participants), 'invalid-match-participants');
    requireValue(['UNKNOWN', 'HUMAN_VERIFIED'].includes(match.match_video_link_status), 'invalid-match-video-link-status');
    requireValue(!matchesById.has(match.match_id), 'duplicate-match-id');
    const referenceUrl = match.reference_url === null ? null : requireWebUrl(match.reference_url, 'invalid-match-reference-url');
    matchesById.set(match.match_id, {
      match_id: match.match_id,
      event: isObject(match.event) && typeof match.event.name === 'string' ? match.event.name : 'UNKNOWN',
      event_zh: isObject(match.event) && typeof match.event.name_zh === 'string' ? match.event.name_zh : (typeof match.event_display_zh === 'string' ? match.event_display_zh : null),
      event_id: isObject(match.event) && typeof match.event.event_id === 'string' ? match.event.event_id : null,
      round: typeof match.round === 'string' ? match.round : 'UNKNOWN',
      round_zh: typeof match.round_zh === 'string' ? match.round_zh : null,
      display_title_zh: typeof match.display_title_zh === 'string' ? match.display_title_zh : null,
      match_type: typeof match.match_type === 'string' ? match.match_type : 'UNKNOWN',
      recorded_result: isObject(match.recorded_result)
        && Number.isInteger(match.recorded_result.player_a_games) && match.recorded_result.player_a_games >= 0
        && Number.isInteger(match.recorded_result.player_b_games) && match.recorded_result.player_b_games >= 0
        ? { player_a_games: match.recorded_result.player_a_games, player_b_games: match.recorded_result.player_b_games }
        : null,
      result_status: typeof match.result_status === 'string' ? match.result_status : 'UNKNOWN',
      participants: match.participants.filter(isObject).map((person) => ({
        side: typeof person.side === 'string' ? person.side : 'UNKNOWN',
        athlete_id: typeof person.athlete_id === 'string' ? person.athlete_id : null,
        name_en: typeof person.name_en === 'string' ? person.name_en : null,
      })),
      reference_url: referenceUrl,
      evidence_source_ids: [...match.evidence_source_ids],
      video_source_ids: [...match.video_source_ids],
      match_video_link_status: match.match_video_link_status,
    });
  }

  for (const source of input.video_sources) {
    requireKeys(source, ['catalog_record_id', 'source_id', 'video_id', 'platform', 'official_url', 'watch_entry', 'title', 'event', 'event_year', 'match_type', 'round', 'participants_claimed', 'publisher', 'source_verified_at', 'source_identity_status', 'identity_conflicts', 'canonical_match_id', 'match_link_status', 'content_type_claim', 'completeness_status', 'rights', 'thumbnail', 'availability', 'provenance'], 'invalid-source');
    requireValue(isObject(source) && ['YOUTUBE', 'BILIBILI'].includes(source.platform)
      && typeof source.source_id === 'string' && typeof source.video_id === 'string', 'invalid-source');
    requireValue(source.source_id === `video-source:${source.platform.toLowerCase()}:${source.video_id}`, 'invalid-source-id');
    requireValue(!sourcesById.has(source.source_id), 'duplicate-source-id');
    requireValue(source.watch_entry === 'OPEN_OFFICIAL_PLATFORM_URL', 'invalid-watch-entry');
    requireValue(typeof source.title === 'string' && typeof source.event === 'string'
      && typeof source.publisher === 'string' && typeof source.source_identity_status === 'string'
      && typeof source.publisher_identity_status === 'string' && Array.isArray(source.identity_conflicts)
      && Array.isArray(source.provenance) && isObject(source.participants_claimed)
      && ['MS', 'WS', 'MD', 'WD', 'XD', 'UNKNOWN'].includes(source.match_type)
      && ['FULL_MATCH', 'HIGHLIGHTS', 'SESSION', 'CLIP', 'UNKNOWN'].includes(source.content_type_claim)
      && ['VERIFIED', 'UNVERIFIED'].includes(source.completeness_status), 'invalid-source-fields');
    requireRights(source.rights, true);
    requireValue(source.rights.public_listing === 'ALLOWED', 'unapproved-public-source');
    requireValue(isObject(source.thumbnail) && source.thumbnail.url === null, 'thumbnail-permission-unknown');
    requireValue(isObject(source.availability)
      && source.availability.current_session_eligibility === 'NOT_EVALUATED_CURRENT_SESSION'
      && source.availability.vision_analysis === 'NOT_TESTED', 'invalid-playback-evidence');
    requireValue(['UNKNOWN', 'HUMAN_VERIFIED'].includes(source.match_link_status), 'invalid-match-link-status');
    const canonicalMatchId = source.canonical_match_id ?? null;
    requireValue(source.match_link_status === 'UNKNOWN' ? canonicalMatchId === null : typeof canonicalMatchId === 'string', 'invalid-match-link');
    const officialUrl = requirePlatformUrl(source.platform, source.video_id, source.official_url);
    const link = source.rights.external_viewing === 'ALLOWED' ? officialUrl : null;
    sourcesById.set(source.source_id, {
      source_id: source.source_id,
      title: typeof source.title === 'string' ? source.title : 'UNKNOWN',
      display_title_zh: typeof source.display_title_zh === 'string' ? source.display_title_zh : null,
      event: typeof source.event === 'string' ? source.event : 'UNKNOWN',
      event_zh: typeof source.event_display_zh === 'string' ? source.event_display_zh : null,
      round_zh: typeof source.round_zh === 'string' ? source.round_zh : null,
      event_year: Number.isInteger(source.event_year) ? source.event_year : null,
      match_type: typeof source.match_type === 'string' ? source.match_type : 'UNKNOWN',
      round: typeof source.round === 'string' ? source.round : 'UNKNOWN',
      participants_claimed: isObject(source.participants_claimed) ? source.participants_claimed : {},
      platform: source.platform,
      video_id: source.video_id,
      watch_entry: source.watch_entry,
      url: link,
      publisher: typeof source.publisher === 'string' ? source.publisher : 'UNKNOWN',
      publisher_url: source.publisher_url === null ? null : (typeof source.publisher_url === 'string' ? requireWebUrl(source.publisher_url, 'invalid-publisher-url') : null),
      source_verified_at: typeof source.source_verified_at === 'string' ? source.source_verified_at : null,
      external_viewing: source.rights.external_viewing,
      thumbnail_display: source.rights.thumbnail_display,
      embedding: source.rights.embedding,
      source_identity_status: typeof source.source_identity_status === 'string' ? source.source_identity_status : 'UNKNOWN',
      publisher_identity_status: typeof source.publisher_identity_status === 'string' ? source.publisher_identity_status : 'UNKNOWN',
      content_type_claim: typeof source.content_type_claim === 'string' ? source.content_type_claim : 'UNKNOWN',
      completeness_status: typeof source.completeness_status === 'string' ? source.completeness_status : 'UNVERIFIED',
      territory: typeof source.availability.territory_availability === 'string' ? source.availability.territory_availability : 'UNKNOWN',
      recorded_playback_status: typeof source.availability.latest_recorded_playback_status === 'string' ? source.availability.latest_recorded_playback_status : 'NOT_TESTED',
      current_session_eligibility: 'NOT_EVALUATED_CURRENT_SESSION',
      canonical_match_id: canonicalMatchId,
      match_link_status: source.match_link_status,
      evidence_source_ids: projectSourceEvidenceIds(source, evidenceIds),
    });
  }

  for (const match of matchesById.values()) {
    const linkedIds = match.video_source_ids;
    requireValue(linkedIds.every((id) => sourcesById.has(id)), 'missing-linked-source');
    requireValue(linkedIds.length === 0 ? match.match_video_link_status !== 'HUMAN_VERIFIED' : match.match_video_link_status === 'HUMAN_VERIFIED', 'invalid-match-video-link-status');
    for (const id of linkedIds) {
      const source = sourcesById.get(id);
      requireValue(source.canonical_match_id === match.match_id && source.match_link_status === 'HUMAN_VERIFIED', 'match-source-link-mismatch');
    }
  }
  for (const source of sourcesById.values()) {
    if (source.match_link_status === 'HUMAN_VERIFIED') {
      const match = matchesById.get(source.canonical_match_id);
      requireValue(match && match.video_source_ids.includes(source.source_id), 'orphan-verified-match-link');
    }
  }

  for (const star of input.stars) {
    requireKeys(star, ['athlete_id', 'name_en', 'name_zh', 'association', 'official_profile_url', 'evidence_source_ids', 'public_listing', 'equipment', 'coach_observations', 'interviews', 'sponsorships', 'social_feedback'], 'invalid-star');
    requireValue(isObject(star) && typeof star.athlete_id === 'string' && star.athlete_id.length > 0, 'invalid-star');
    requireValue(star.public_listing === 'ALLOWED', 'unapproved-public-star');
    requireValue(Array.isArray(star.evidence_source_ids) && !starsById.has(star.athlete_id), 'duplicate-athlete-id');
    const profileUrl = star.official_profile_url === null ? null : requireWebUrl(star.official_profile_url, 'invalid-profile-url');
    requireValue((typeof star.name_en === 'string' || star.name_en === null)
      && (typeof star.name_zh === 'string' || star.name_zh === null)
      && (typeof star.association === 'string' || star.association === null)
      && Boolean(star.name_en || star.name_zh)
      && isObject(star.equipment) && star.equipment.status === 'UNKNOWN' && Array.isArray(star.equipment.items) && star.equipment.items.length === 0,
    'invalid-star-fields');
    starsById.set(star.athlete_id, {
      athlete_id: star.athlete_id,
      name_en: typeof star.name_en === 'string' ? star.name_en : null,
      name_zh: typeof star.name_zh === 'string' ? star.name_zh : null,
      association: typeof star.association === 'string' ? star.association : null,
      official_profile_url: profileUrl,
      profile_last_verified_at: typeof star.profile_last_verified_at === 'string' ? star.profile_last_verified_at : null,
      evidence_source_ids: [...star.evidence_source_ids],
      equipment_status: isObject(star.equipment) && star.equipment.status === 'UNKNOWN' ? 'UNKNOWN' : 'UNKNOWN',
      linked_matches: [],
    });
  }

  for (const match of matchesById.values()) {
    for (const participant of match.participants) {
      if (participant.athlete_id && starsById.has(participant.athlete_id)) {
        starsById.get(participant.athlete_id).linked_matches.push(match.match_id);
      }
    }
  }

  return {
    contract_version: CONTRACT,
    generated_at: typeof input.generated_at === 'string' ? input.generated_at : null,
    matches: [...matchesById.values()],
    sources: [...sourcesById.values()],
    stars: [...starsById.values()],
  };
}

/** Filter clips by query, exact linked athlete ID, and source-claimed content type. */
export function filterFanSources(catalog, { query = '', athleteId = 'all', contentType = 'all' } = {}) {
  const normalizedQuery = normalizeFanSearch(query);
  return (catalog?.sources ?? []).filter((source) => {
    if (normalizedQuery && ![source.title, source.display_title_zh, source.event, source.event_zh, source.round, source.round_zh, source.platform, source.source_id, source.publisher]
      .some((value) => normalizeFanSearch(value ?? '').includes(normalizedQuery))) return false;
    if (contentType !== 'all' && source.content_type_claim !== contentType) return false;
    if (athleteId === 'all') return true;
    return Boolean(source.canonical_match_id && catalog.stars.some((star) => star.athlete_id === athleteId && star.linked_matches.includes(source.canonical_match_id)));
  });
}

/** Clips are only rows explicitly claimed as CLIP. Event-level HIGHLIGHTS stay in their own shelf. */
export function filterFanClips(catalog, filters = {}) {
  return filterFanSources(catalog, filters).filter((source) => source.content_type_claim === 'CLIP');
}

/** Event-level highlight sources stay separate from short clips and are never joined by title. */
export function filterFanHighlights(catalog, filters = {}) {
  return filterFanSources(catalog, { ...filters, contentType: 'HIGHLIGHTS' });
}

/** Shared bilingual search over only records already admitted by the strict-public consumer. */
export function searchFanCatalog(catalog, query = '') {
  const normalizedQuery = normalizeFanSearch(query);
  if (!normalizedQuery) return { matches: [], stars: [], highlights: [] };
  const matches = (catalog?.matches ?? []).filter((match) => {
    const exactStarNames = match.participants.flatMap((person) => {
      const star = person.athlete_id ? catalog?.stars.find((item) => item.athlete_id === person.athlete_id) : undefined;
      return [person.name_en, star?.name_zh, star?.name_en];
    });
    return [match.event, match.event_zh, match.round, match.round_zh, match.display_title_zh, match.match_type, ...exactStarNames]
      .some((value) => normalizeFanSearch(value ?? '').includes(normalizedQuery));
  });
  const stars = (catalog?.stars ?? []).filter((star) => [star.name_en, star.name_zh, star.association]
    .some((value) => normalizeFanSearch(value ?? '').includes(normalizedQuery)));
  const highlights = filterFanHighlights(catalog, { query });
  return { matches, stars, highlights };
}

/** Find an exact-ID-linked full match for the Clips empty-state escape route. */
export function findAdmittedFullMatch(catalog) {
  for (const match of catalog?.matches ?? []) {
    if (match.match_video_link_status !== 'HUMAN_VERIFIED') continue;
    const hasLinkedFullMatch = match.video_source_ids.some((sourceId) => {
      const source = catalog?.sources.find((item) => item.source_id === sourceId);
      return source?.content_type_claim === 'FULL_MATCH'
        && source.match_link_status === 'HUMAN_VERIFIED'
        && source.canonical_match_id === match.match_id;
    });
    if (hasLinkedFullMatch) return match;
  }
  return null;
}

/** Group only admitted men's/women's singles matches by their two exact athlete IDs. */
export function deriveFanRivalries(catalog) {
  const knownAthletes = new Set((catalog?.stars ?? []).map((star) => star.athlete_id));
  const grouped = new Map();
  for (const match of catalog?.matches ?? []) {
    if (match.match_type !== 'MS' && match.match_type !== 'WS') continue;
    if (match.participants.length !== 2) continue;
    const participantIds = match.participants.map((person) => person.athlete_id);
    if (participantIds.some((id) => !id || !knownAthletes.has(id))) continue;
    const athleteIds = [...new Set(participantIds)].sort();
    if (athleteIds.length !== 2) continue;
    const rivalryId = `rivalry:${athleteIds.map((id) => encodeURIComponent(id)).join(':')}`;
    const current = grouped.get(rivalryId) ?? { rivalry_id: rivalryId, athlete_ids: athleteIds, match_ids: [] };
    current.match_ids.push(match.match_id);
    grouped.set(rivalryId, current);
  }
  return [...grouped.values()];
}
