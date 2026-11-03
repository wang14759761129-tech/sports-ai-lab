const VERSION = 'ptti.match-media/0.2';
const permissionKeys = ['metadata_listing','thumbnail_display','external_viewing','embedding','local_analysis','model_training','redistribution'];
const synthetic = row => /synthetic/i.test(row.provenance?.method ?? '') || /synthetic/i.test(row.provenance?.review_status ?? '');
const object = value => value && typeof value === 'object' && !Array.isArray(value);
const string = value => typeof value === 'string' ? value : '';
export function httpsUrl(value) { try { const u = new URL(value); return u.protocol === 'https:' && !u.username && !u.password ? u.href : null; } catch { return null; } }
export function consumeReadonlyProjection(payload, { view = 'public', localReview = false } = {}) {
  if (!object(payload) || payload.contract_version !== VERSION) throw new Error('Expected exact ptti.match-media/0.2');
  if (!['public','review'].includes(view) || (view === 'review' && !localReview)) throw new Error('Review requires trusted local context');
  for (const key of ['matches','video_sources','local_video_assets','timeline_mappings']) if (!Array.isArray(payload[key])) throw new Error('Invalid Web projection');
  if (payload.local_video_assets.length || payload.timeline_mappings.length) throw new Error('Local assets/timelines are not Web catalog data');
  const matches = structuredClone(payload.matches), sources = structuredClone(payload.video_sources);
  const ids = new Set(), sourceIds = new Set();
  for (const m of matches) {
    if (!object(m) || !string(m.match_id) || ids.has(m.match_id) || !object(m.event) || !Array.isArray(m.participants)) throw new Error('Invalid/duplicate match ID');
    ids.add(m.match_id);
    if (m.participant_names_unassigned != null && (!Array.isArray(m.participant_names_unassigned) || m.participant_names_unassigned.some(n => typeof n !== 'string'))) throw new Error('Invalid participant names');
  }
  for (const s of sources) {
    if (!object(s) || !string(s.source_id) || sourceIds.has(s.source_id) || !ids.has(s.match_id)) throw new Error('Invalid source/reference');
    sourceIds.add(s.source_id);
    if (s.rights != null && !object(s.rights)) throw new Error('Invalid rights');
    s.rights = s.rights ?? {};
    for (const key of permissionKeys) { const value = s.rights[key] ?? 'UNKNOWN'; if (!['ALLOWED','DENIED','UNKNOWN'].includes(value)) throw new Error('Invalid permission'); s.rights[key] = value; }
    s.evidence = object(s.evidence) ? s.evidence : {};
    s.territory = object(s.territory) ? s.territory : { status: 'UNKNOWN', territories: [] };
    if (s.canonical_url != null && !httpsUrl(s.canonical_url)) throw new Error('Unsafe canonical URL');
  }
  const allowed = sources.filter(s => !synthetic(s) && (view === 'review' || (s.rights.metadata_listing === 'ALLOWED' && s.rights.external_viewing === 'ALLOWED')));
  return { version: VERSION, view, matches: matches.filter(m => !synthetic(m)).flatMap(m => {
    const selected = allowed.filter(s => s.match_id === m.match_id);
    if (view === 'public' && !selected.length) return [];
    return [{ id: m.match_id, identityStatus: m.identity_status ?? 'UNKNOWN', event: m.event, discipline: m.discipline ?? 'UNKNOWN', round: m.round ?? null, result: m.result ?? null, unassignedNames: m.participant_names_unassigned ?? [], participants: m.participants, sources: selected.map(s => ({ id: s.source_id, matchId: s.match_id, matchLinkStatus: s.match_link_status ?? 'UNKNOWN', kind: s.resource_kind ?? 'UNKNOWN', platform: s.platform ?? '', canonicalUrl: s.canonical_url ?? null, publisher: s.publisher ?? null, verifiedAt: s.verified_at ?? null, rights: s.rights, territory: s.territory, evidence: s.evidence, provenance: s.provenance ?? {} })) }];
  }) };
}
export function hasBridgeVisualEvidence(source) {
  const e = source?.evidence?.external_video_page;
  return source?.kind === 'VIDEO_PAGE' && e?.status === 'EXTERNAL_VIDEO_PAGE_VISUAL_PASS'
    && source.canonicalUrl === e.requested_url && source.canonicalUrl === e.final_url && !!httpsUrl(source.canonicalUrl)
    && e.url_exact_match === true && e.visual_frames_changed === true && e.source_evidence_verified === true
    && Array.isArray(e.source_evidence_urls) && e.source_evidence_urls.includes(source.canonicalUrl)
    && e.publisher_verified === true && e.title_matches_match === true && !!string(e.publisher) && !!string(e.page_title)
    && Number.isFinite(e.time_first_seconds) && e.time_first_seconds >= 0 && Number.isFinite(e.time_last_seconds) && e.time_last_seconds - e.time_first_seconds >= 5
    && typeof e.checked_at === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(e.checked_at) && Number.isFinite(Date.parse(e.checked_at)) && new Date(e.checked_at).toISOString().slice(0,10) === e.checked_at && e.checked_at <= new Date().toISOString().slice(0,10)
    && e.login_prompt_seen === false && e.region_prompt_seen === false && e.verification_prompt_seen === false;
}
export function projectBridgeMatches(payload, options) {
  const catalog = consumeReadonlyProjection(payload, options);
  return catalog.matches.map(m => {
    const source = m.sources[0] ?? null;
    const kind = source?.kind ?? 'UNKNOWN';
    const names = m.unassignedNames.length ? m.unassignedNames : m.participants.flatMap(p => Array.isArray(p?.members) ? p.members.map(x => x.name).filter(n => typeof n === 'string') : []);
    const resultInvalid = typeof m.result === 'string' && /[\uFFFD]/.test(m.result);
    const routeType = kind === 'VIDEO_PAGE' ? 'video-page' : kind === 'OFFICIAL_EVENT_PAGE' ? 'event-page' : kind === 'ARTICLE' ? 'source-only' : 'unknown';
    const refs = [...new Set([...(source?.provenance.source_urls ?? []), ...(source?.evidence.external_video_page?.source_evidence_urls ?? [])].filter(v => httpsUrl(v)))];
    return { id: m.id, event: string(m.event.name), eventCategory: '', eventYear: Number.isFinite(m.event.year) ? m.event.year : 0, discipline: ['MS','WS','MD','WD','XD'].includes(m.discipline) ? m.discipline : 'UNKNOWN', round: string(m.round), players: names, result: typeof m.result === 'string' && !resultInvalid ? m.result : undefined,
      platform: string(source?.platform), routeType, platformUrl: source?.canonicalUrl ?? null, videoOriginalUrl: kind === 'VIDEO_PAGE' ? source.canonicalUrl : null, sourceStatus: 'no-verified-route', playbackTested: false, playbackStatus: 'NOT_TESTED', regionRestriction: string(source?.territory.notes) || 'Unknown', embedAllowed: source?.rights.embedding === 'ALLOWED' ? true : source?.rights.embedding === 'DENIED' ? false : null, lastVerifiedAt: string(source?.verifiedAt), sourceEvidence: refs, note: '', bridge: { matchId: m.id, source, sources: m.sources, eventId: m.event.event_id ?? null, identityStatus: m.identityStatus, participants: m.participants, resultInvalid } };
  });
}
