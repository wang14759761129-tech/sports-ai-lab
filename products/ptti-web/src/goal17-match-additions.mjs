/** Apply Main's pinned public GOAL17 delta after the GOAL15 strict-public consumer. */
export function applyGoal17MatchAdditions(base, delta) {
  if (!base || delta?.contract_version !== 'ptti.goal17.1-match-video-additions/0.1'
      || delta.view !== 'STRICT_PUBLIC_EXTERNAL_LINK_DELTA'
      || delta.base_goal15_library_sha256 !== '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930'
      || !Array.isArray(delta.matches) || !Array.isArray(delta.video_sources)
      || delta.matches.length !== 2 || delta.video_sources.length !== 2) throw new Error('GOAL17_DELTA_VERSION_OR_BASE_MISMATCH');
  const matches = [...base.matches];
  const sources = [...base.sources];
  const stars = base.stars.map((star) => ({ ...star, linked_matches: [...star.linked_matches] }));
  const ids = new Set(matches.map((row) => row.match_id));
  const sourceIds = new Set(sources.map((row) => row.source_id));
  if (!Number.isFinite(Date.parse(delta.generated_at))) throw new Error('GOAL17_DELTA_DATE_INVALID');
  for (const item of delta.matches) {
    if (typeof item.match_id !== 'string' || ids.has(item.match_id)
        || item.provider_match_id !== null || item.category !== 'MS'
        || item.event_id !== 'wtt-event:3231' || item.event_name !== 'WTT Champions Doha 2026'
        || item.event_page_url !== 'https://www.worldtabletennis.com/eventInfo?eventId=3231'
        || !['R16', 'SF'].includes(item.round) || item.match_date !== null
        || !Array.isArray(item.participants) || item.participants.length !== 2
        || !Array.isArray(item.video_source_ids) || item.video_source_ids.length !== 1
        || item.identity_evidence_source_id !== item.video_source_ids[0]
        || !item.identity_status.includes('VISUAL_MATCH_NOT_TESTED')) throw new Error('GOAL17_MATCH_IDENTITY_INVALID');
    const participant = item.participants[0];
    if (participant.athlete_id !== 'athlete:137237' || !stars.some((star) => star.athlete_id === participant.athlete_id)
        || item.participants[1].athlete_id !== null) throw new Error('GOAL17_ATHLETE_JOIN_INVALID');
    ids.add(item.match_id);
    matches.push({ match_id: item.match_id, event: item.event_name, event_zh: null, event_id: item.event_id,
      round: item.round, round_zh: null, display_title_zh: null, match_type: item.category,
      recorded_result: null, result_status: 'UNKNOWN',
      participants: item.participants.map((person, index) => ({ side: index === 0 ? 'A' : 'B', athlete_id: person.athlete_id,
        name_en: person.display_name })), reference_url: item.event_page_url,
      evidence_source_ids: [item.identity_evidence_source_id], video_source_ids: [...item.video_source_ids],
      match_video_link_status: 'OFFICIAL_TITLE_ASSOCIATED_VISUAL_NOT_TESTED' });
    stars.find((star) => star.athlete_id === participant.athlete_id).linked_matches.push(item.match_id);
  }
  for (const item of delta.video_sources) {
    if (typeof item.source_id !== 'string' || sourceIds.has(item.source_id)
        || item.provider !== 'YOUTUBE' || item.publisher !== 'World Table Tennis'
        || item.publisher_status !== 'OFFICIAL_VERIFIED_CHANNEL'
        || !/^[A-Za-z0-9_-]{11}$/.test(item.provider_video_id)
        || item.source_id !== `youtube:${item.provider_video_id}`
        || item.watch_url !== `https://www.youtube.com/watch?v=${item.provider_video_id}`
        || item.watch_route !== 'OFFICIAL_EXTERNAL_LINK_ONLY'
        || item.playback_status !== 'NOT_TESTED'
        || item.completeness_status !== 'TITLE_ASSERTS_FULL_MATCH; VISUAL_COMPLETENESS_NOT_VERIFIED'
        || item.embed_permission !== 'UNKNOWN_NOT_GRANTED'
        || item.thumbnail_display_permission !== 'NOT_GRANTED_PENDING_WRITTEN_APPROVAL'
        || item.download_permission !== 'NOT_GRANTED'
        || item.local_analysis_permission !== 'NOT_GRANTED'
        || item.redistribution_permission !== 'NOT_GRANTED'
        || item.territory_status !== 'UNKNOWN' || item.login_status !== 'UNKNOWN') throw new Error('GOAL17_SOURCE_RIGHTS_INVALID');
    const match = matches.find((row) => row.match_id === item.match_id);
    if (!match || !match.video_source_ids.includes(item.source_id)) throw new Error('GOAL17_SOURCE_MATCH_REFERENCE_INVALID');
    sourceIds.add(item.source_id);
    sources.push({ source_id: item.source_id, title: match.participants.map((person) => person.name_en).join(' vs '),
      display_title_zh: null, event: match.event, event_zh: null, round_zh: null, event_year: 2026,
      match_type: 'MS', round: match.round, participants_claimed: {}, platform: 'YOUTUBE',
      video_id: item.provider_video_id, watch_entry: 'OPEN_OFFICIAL_PLATFORM_URL', url: item.watch_url,
      publisher: item.publisher, publisher_url: null,
      // The package timestamp records Main's metadata handoff, not successful video playback.
      source_verified_at: delta.generated_at, external_viewing: 'ALLOWED', thumbnail_display: 'NOT_ALLOWED',
      embedding: 'UNKNOWN', source_identity_status: 'VERIFIED_FROM_OFFICIAL_VIDEO_METADATA',
      publisher_identity_status: 'VERIFIED_OFFICIAL_CHANNEL', content_type_claim: 'UNKNOWN',
      completeness_status: 'UNVERIFIED', territory: 'UNKNOWN', recorded_playback_status: 'NOT_TESTED',
      current_session_eligibility: 'NOT_EVALUATED_CURRENT_SESSION', canonical_match_id: match.match_id,
      match_link_status: 'OFFICIAL_TITLE_ASSOCIATED_VISUAL_NOT_TESTED', evidence_source_ids: [item.source_id] });
  }
  return { ...base, matches, sources, stars };
}
