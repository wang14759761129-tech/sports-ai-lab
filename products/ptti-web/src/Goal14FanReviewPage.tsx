import { useEffect, useMemo, useState } from 'react';
import { evaluateWatchRoute } from '@ptti/watch-routing';
import { message } from './i18n';
import type { Locale, MessageKey } from './i18n';
import { consumeGoal14FanDelivery, evaluateGoal14WatchRoutes } from './fan-content-delivery.mjs';
import type { Goal14Clip, Goal14Event, Goal14FanDelivery, Goal14Star } from './fan-content-delivery.mjs';

type FanPage = 'cinema' | 'stars' | 'clips' | 'watch';
type RouteDecision = { mode: string; decision: { state?: string; reason?: string; playbackEvidence?: string } | null };

const routeNames: Record<string, MessageKey> = {
  OFFICIAL_EMBED: 'fan.route.embed', OFFICIAL_PAGE: 'fan.route.page', AUTHORIZED_SOURCE: 'fan.route.authorized',
  REPLAY: 'fan.route.replay', LIVE_SCORE: 'fan.route.score',
};
const reasonNames: Record<string, MessageKey> = {
  ROUTE_ELIGIBLE: 'fan.route.eligible', SOURCE_REFERENCE_UNVERIFIED: 'fan.route.sourceUnknown',
  SOURCE_REFERENCE_MISSING: 'fan.route.sourceMissing', VIEW_PERMISSION_UNKNOWN: 'fan.route.permissionUnknown',
  VIEW_PERMISSION_DENIED: 'fan.route.permissionDenied', ROUTE_TYPE_MISMATCH: 'fan.route.typeMismatch',
  EMBED_PERMISSION_UNKNOWN: 'fan.route.embedUnknown', EMBED_PERMISSION_DENIED: 'fan.route.embedDenied',
  RIGHTS_EVIDENCE_REQUIRED: 'fan.route.rightsRequired', LIVE_SCORE_UNVERIFIED: 'fan.route.scoreUnknown',
};

function translatedTitle(locale: Locale, item: { title_original: string; title_zh: string }) {
  return locale === 'zh-CN' ? item.title_zh : item.title_original;
}

export function Goal14FanReviewPage({ active, mode, locale, onNavigate }: {
  active: boolean; mode: FanPage; locale: Locale; onNavigate: (page: FanPage) => void;
}) {
  const t = (key: MessageKey, values?: Record<string, string | number>) => {
    let result = message(locale, key);
    for (const [name, value] of Object.entries(values ?? {})) result = result.replaceAll(`{${name}}`, String(value));
    return result;
  };
  const [delivery, setDelivery] = useState<Goal14FanDelivery | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [query, setQuery] = useState('');
  const [eventFilter, setEventFilter] = useState('all');
  const [starContextFilter, setStarContextFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [selectedStarId, setSelectedStarId] = useState<string | null>(null);
  const [selectedClipId, setSelectedClipId] = useState<string | null>(null);
  const [returnPage, setReturnPage] = useState<FanPage>('clips');

  useEffect(() => {
    let current = true;
    setLoading(true);
    setError(false);
    void (async () => {
      try {
        const response = await fetch('/__ptti/goal14/fan-delivery.json', {
          cache: 'no-store',
          headers: { Accept: 'application/json', 'X-PTTI-Internal-Review': 'local-only' },
        });
        if (!response.ok) throw new Error('internal-review-unavailable');
        const parsed = consumeGoal14FanDelivery(await response.json());
        if (current) setDelivery(parsed);
      } catch {
        if (current) { setDelivery(null); setError(true); }
      } finally {
        if (current) setLoading(false);
      }
    })();
    return () => { current = false; };
  }, []);

  const normalizedQuery = query.trim().toLocaleLowerCase();
  const events = delivery?.events ?? [];
  const stars = delivery?.stars ?? [];
  const clips = delivery?.clips ?? [];
  const sources = delivery?.watch_sources ?? [];
  const evidence = delivery?.source_index ?? [];
  const eventById = useMemo(() => new Map(events.map((event) => [event.event_id, event])), [events]);
  const starById = useMemo(() => new Map(stars.map((star) => [star.athlete_id, star])), [stars]);
  const sourceById = useMemo(() => new Map(sources.map((source) => [source.watch_source_id, source])), [sources]);
  const evidenceById = useMemo(() => new Map(evidence.map((item) => [item.evidence_id, item])), [evidence]);
  const activeEvent = selectedEventId ? eventById.get(selectedEventId) ?? null : null;
  const activeStar = selectedStarId ? starById.get(selectedStarId) ?? null : null;
  const activeClip = selectedClipId ? clips.find((clip) => clip.clip_id === selectedClipId) ?? null : null;
  const activeWatchSource = activeClip ? sourceById.get(activeClip.watch_source_id) ?? null : null;
  const activeEventForClip = activeClip ? eventById.get(activeClip.event_id) ?? null : null;

  const starEvents = (starId: string) => (delivery?.relationships ?? [])
    .filter((row) => row.from_type === 'ATHLETE' && row.from_id === starId && row.to_type === 'EVENT'
      && row.relationship_kind === 'LISTED_ON_EVENT_PLAYER_ROSTER' && row.confidence_scope === 'EVENT_ROSTER_LISTING_ONLY_NOT_CLIP_APPEARANCE')
    .map((row) => ({ event: eventById.get(row.to_id), relationship: row }))
    .filter((row): row is { event: Goal14Event; relationship: typeof row.relationship } => Boolean(row.event));

  const starMatchesQuery = (star: Goal14Star) => !normalizedQuery
    || [star.name_en, star.name_zh, star.athlete_id, star.association].some((value) => value?.toLocaleLowerCase().includes(normalizedQuery));
  const eventHasQuery = (event: Goal14Event) => !normalizedQuery
    || [event.name, event.title_original, event.title_zh, event.event_id, ...clips.filter((clip) => clip.event_id === event.event_id).flatMap((clip) => [clip.title_original, clip.title_zh])]
      .some((value) => value?.toLocaleLowerCase().includes(normalizedQuery));
  const filteredEvents = events.filter(eventHasQuery);
  const filteredStars = stars.filter(starMatchesQuery);
  const selectedEvent = activeEvent;
  const eventClips = (eventId: string) => clips.filter((clip) => clip.event_id === eventId);

  const eventIdsInRosterContext = starContextFilter === 'all'
    ? null
    : new Set(starEvents(starContextFilter).map(({ event }) => event.event_id));
  const filteredClips = clips.filter((clip) => {
    const event = eventById.get(clip.event_id);
    if (eventFilter !== 'all' && clip.event_id !== eventFilter) return false;
    if (eventIdsInRosterContext && !eventIdsInRosterContext.has(clip.event_id)) return false;
    if (typeFilter !== 'all' && clip.content_type !== typeFilter) return false;
    if (!normalizedQuery) return true;
    return [clip.title_original, clip.title_zh, event?.name, event?.title_zh, clip.provider, clip.content_type]
      .some((value) => value?.toLocaleLowerCase().includes(normalizedQuery));
  });
  const contentTypes = [...new Set(clips.map((clip) => clip.content_type))].sort();
  const directCount = clips.filter((clip) => clip.video_id !== null).length;
  const listingCount = clips.length - directCount;

  function openEvent(eventId: string) { setSelectedEventId(eventId); setSelectedStarId(null); onNavigate('cinema'); }
  function openStar(starId: string) { setSelectedStarId(starId); setSelectedEventId(null); onNavigate('stars'); }
  function openClip(clip: Goal14Clip, from: FanPage) { setReturnPage(from); setSelectedClipId(clip.clip_id); onNavigate('watch'); }
  function clearFilters() { setEventFilter('all'); setStarContextFilter('all'); setTypeFilter('all'); setQuery(''); }

  function sourceRouteCard(clip: Goal14Clip) {
    const source = sourceById.get(clip.watch_source_id);
    return <article className="fan-content-card goal14-clip-card" key={clip.clip_id} data-goal14-clip-id={clip.clip_id}>
      <div className="fan-owned-art" aria-hidden="true"><span>PTTI</span><b>{source?.provider ?? 'SOURCE'}</b></div>
      <div className="fan-content-body">
        <div className="fan-card-meta"><span>{t('goal14.internalOnly')}</span><span>{clip.video_id ? t('goal14.exactVideoRoute') : t('goal14.eventListingRoute')}</span></div>
        <h3>{translatedTitle(locale, clip)}</h3>
        {locale === 'zh-CN' && <p className="goal14-original-title">{clip.title_original}</p>}
        <p>{eventById.get(clip.event_id)?.title_zh ?? clip.event_id} · {eventById.get(clip.event_id)?.name}</p>
        <p className="fan-claim">{t(`goal14.content.${clip.content_type}` as MessageKey)} · {t('goal14.playbackNotTested')}</p>
        <p className="fan-claim">{t('goal14.matchLinkUnknown')} · {t('goal14.licenseUnknown')}</p>
        <p className="fan-claim">{t('goal14.publisher', { publisher: clip.publisher || t('fan.unknown') })}</p>
        <button type="button" className="button button-secondary" onClick={() => openClip(clip, mode)}>{t('fan.openWatch')} →</button>
      </div>
    </article>;
  }

  function selectedEventView(event: Goal14Event) {
    const related = eventClips(event.event_id);
    const rosterRows = (delivery?.relationships ?? []).filter((row) => row.to_type === 'EVENT' && row.to_id === event.event_id && row.from_type === 'ATHLETE' && row.relationship_kind === 'LISTED_ON_EVENT_PLAYER_ROSTER');
    return <section className="fan-match-detail goal14-detail" aria-labelledby="goal14-event-title" data-goal14-event-detail>
      <button type="button" className="button button-outline" onClick={() => setSelectedEventId(null)}>← {t('goal14.backToList')}</button>
      <p className="eyebrow">{t('goal14.internalOnly')} · {event.event_id}</p>
      <h2 id="goal14-event-title">{locale === 'zh-CN' ? event.title_zh : event.title_original}</h2>
      {locale === 'zh-CN' && <p>{event.title_original}</p>}
      <p>{t('goal14.eventTitle')}: {event.name} · {event.event_year ?? t('fan.unknown')}</p>
      <p className="fan-claim">{t('goal14.playbackNotTested')} · {t('goal14.licenseUnknown')} · {t('goal14.matchLinkUnknown')}</p>
      <a className="button button-outline" href={event.official_event_page_url} target="_blank" rel="noopener noreferrer">{t('goal14.openEventSource')} ↗</a>
      <p className="goal14-small-note">{t('goal14.sourceReviewNotice')}</p>
      <h3>{t('goal14.eventCandidates')} · {related.length}</h3>
      {rosterRows.length > 0 && <p className="goal14-small-note">{t('goal14.rosterScope')}</p>}
      {related.length ? <div className="fan-content-grid">{related.map(sourceRouteCard)}</div> : <p className="fan-empty-inline">{t('goal14.noClipCandidates')}</p>}
    </section>;
  }

  function selectedStarView(star: Goal14Star) {
    const relations = starEvents(star.athlete_id);
    return <section className="fan-match-detail goal14-detail" aria-labelledby="goal14-star-title" data-goal14-star-detail>
      <button type="button" className="button button-outline" onClick={() => setSelectedStarId(null)}>← {t('goal14.backToList')}</button>
      <p className="eyebrow">{t('goal14.internalOnly')} · {star.athlete_id}</p>
      <h2 id="goal14-star-title">{locale === 'zh-CN' ? star.name_zh : star.name_en}</h2>
      {locale === 'zh-CN' && <p>{star.name_en}</p>}
      <p>{t('goal14.athleteAssociation', { association: star.association ?? t('fan.unknown') })} · ITTF ID: {star.ittf_id ?? t('fan.unknown')}</p>
      <p>{t('goal14.profileSnapshot', { date: star.profile_snapshot_verified_at?.slice(0, 10) ?? t('fan.unknown') })}</p>
      <p>{t('goal14.currentProfile')} · {t('goal14.licenseUnknown')}</p>
      {star.official_profile_url && <a className="button button-outline" href={star.official_profile_url} target="_blank" rel="noopener noreferrer">{t('goal14.openProfile')} ↗</a>}
      <h3>{t('goal14.rosterEvents')}</h3>
      <p className="goal14-small-note">{t('goal14.rosterScope')}</p>
      {relations.length ? <div className="goal14-relation-list">{relations.map(({ event, relationship }) => <article key={relationship.relationship_id}>
        <strong>{locale === 'zh-CN' ? event.title_zh : event.title_original}</strong>
        <p>{event.name} · {relationship.relationship_kind}</p>
        <small>{t('goal14.rosterScope')} · {relationship.evidence_ids.join(', ')}</small>
        <button type="button" className="text-button" onClick={() => openEvent(event.event_id)}>{t('goal14.viewEventClips')} →</button>
      </article>)}</div> : <p className="fan-empty-inline">{t('goal14.noRosterEvents')}</p>}
      {relations.length > 0 && <p className="goal14-small-note">{t('goal14.clipsFromRosterEvent')}</p>}
    </section>;
  }

  function selectedWatchView(clip: Goal14Clip) {
    const source = activeWatchSource;
    const event = activeEventForClip;
    const decisions = source ? evaluateGoal14WatchRoutes(source, evidenceById, evaluateWatchRoute) as RouteDecision[] : [];
    const ids = [...new Set([...clip.source_evidence_ids, ...(source?.evidence_ids ?? [])])];
    return <section className="fan-match-detail goal14-detail goal14-watch-detail" aria-labelledby="goal14-watch-heading" data-goal14-watch-detail>
      <button type="button" className="button button-outline" onClick={() => onNavigate(returnPage)}>← {t('goal14.backToList')}</button>
      <p className="eyebrow">PTTI · WATCH · {t('goal14.internalOnly')}</p>
      <h2 id="goal14-watch-heading">{translatedTitle(locale, clip)}</h2>
      {locale === 'zh-CN' && <p>{clip.title_original}</p>}
      <p>{event ? (locale === 'zh-CN' ? event.title_zh : event.title_original) : clip.event_id} · {source?.provider}</p>
      <div className="goal14-watch-status-grid">
        <span>{clip.video_id ? t('goal14.exactVideoRoute') : t('goal14.eventListingRoute')}</span>
        <span>{t('goal14.playbackNotTested')}</span>
        <span>{t('goal14.licenseUnknown')}</span>
        <span>{t('goal14.matchLinkUnknown')}</span>
      </div>
      {source && <>
        <p className="goal14-small-note">{t('goal14.sourceReviewNotice')}</p>
        <a className="button button-primary" href={source.url} target="_blank" rel="noopener noreferrer" data-goal14-source-link>{t('goal14.openSourceReview')}</a>
        <p className="goal14-small-note">{t('goal14.sourceLinksOnly')}</p>
        <details className="goal14-route-details"><summary>{t('goal14.routeContract')}</summary><dl>
          {decisions.map(({ mode: routeMode, decision }) => <div key={routeMode} data-goal14-route-mode={routeMode} data-route-state={decision?.state ?? 'BLOCKED'}>
            <dt>{t(routeNames[routeMode] ?? 'fan.route.unavailable')}</dt>
            <dd>{decision?.state ?? 'BLOCKED'} · {t(reasonNames[decision?.reason ?? ''] ?? 'fan.route.unavailable')} · {decision?.playbackEvidence ?? 'NOT_TESTED'}</dd>
          </div>)}
        </dl></details>
      </>}
      <details className="goal14-source-evidence"><summary>{t('goal14.sourceEvidence')}</summary>
        <ul>{ids.map((id) => { const item = evidenceById.get(id); return <li key={id}>
          <b>{id}</b> · {item?.kind ?? t('fan.unknown')}<br />
          {item?.url && <a href={item.url} target="_blank" rel="noopener noreferrer">{item.url} ↗</a>}
          <small>{item?.limitations}</small>
        </li>; })}</ul>
      </details>
    </section>;
  }

  const pageTitle: Record<FanPage, MessageKey> = { cinema: 'goal14.cinemaTitle', stars: 'goal14.starsTitle', clips: 'goal14.clipsTitle', watch: 'goal14.watchTitle' };
  const pageDescription: Record<FanPage, MessageKey> = { cinema: 'goal14.cinemaDescription', stars: 'goal14.starsDescription', clips: 'goal14.clipsDescription', watch: 'goal14.watchDescription' };

  return <section className="fan-library goal14-fan-library" hidden={!active} data-goal14-mode={mode} data-goal14-internal="true" aria-labelledby="goal14-page-title">
    <header className="page-intro"><p className="eyebrow">{t('goal14.bannerTitle')}</p><h1 id="goal14-page-title">{t(pageTitle[mode])}</h1><p>{t(pageDescription[mode])}</p></header>
    <div className="goal14-data-boundary" role="status"><strong>{t('goal14.bannerTitle')}</strong><span>{t('goal14.bannerDetail')}</span></div>
    {loading && <p className="fan-status" role="status">{t('goal14.loading')}</p>}
    {error && <div className="state-card state-error" role="alert"><strong>{t('goal14.loadError')}</strong><p>{t('goal14.loadErrorDetail')}</p></div>}
    {!loading && !error && delivery && <>
      <div className="goal14-inventory" data-goal14-counts>
        <strong>{t('goal14.inventory', { events: events.length, stars: stars.length, clips: clips.length })}</strong>
        <span>{t('goal14.sourceInventory', { direct: directCount, listing: listingCount })}</span>
        <small>{t('goal14.publicZero')}</small>
      </div>
      {mode !== 'watch' && <label className="fan-search goal14-search"><span>{t('goal14.search')}</span><input value={query} onChange={(event) => setQuery(event.target.value)} type="search" placeholder={t('goal14.searchPlaceholder')} /></label>}

      {mode === 'cinema' && !selectedEvent && <>
        {normalizedQuery && filteredStars.length > 0 && <section className="goal14-search-stars"><h2>{t('fan.searchStarResults')}</h2><div className="fan-content-grid">{filteredStars.map((star) => <article className="fan-content-card goal14-star-card" key={star.athlete_id} data-athlete-id={star.athlete_id}>
          <div className="fan-owned-art" aria-hidden="true"><span>PTTI</span><b>STAR</b></div><div className="fan-content-body"><div className="fan-card-meta"><span>{t('goal14.internalOnly')}</span><span>{star.association}</span></div><h3>{locale === 'zh-CN' ? star.name_zh : star.name_en}</h3><p>{locale === 'zh-CN' ? star.name_en : star.name_zh}</p><button type="button" className="button button-secondary" onClick={() => openStar(star.athlete_id)}>{t('fan.openStar')} →</button></div>
        </article>)}</div></section>}
        <div className="fan-content-grid">{filteredEvents.map((event) => <article className="fan-content-card goal14-event-card" key={event.event_id} data-event-id={event.event_id}>
          <div className="fan-owned-art" aria-hidden="true"><span>PTTI</span><b>EVENT</b></div><div className="fan-content-body">
            <div className="fan-card-meta"><span>{t('goal14.internalOnly')}</span><span>{event.event_year}</span></div>
            <h3>{locale === 'zh-CN' ? event.title_zh : event.title_original}</h3>
            {locale === 'zh-CN' && <p>{event.title_original}</p>}
            <p>{event.event_id} · {event.name}</p>
            <p className="fan-claim">{eventClips(event.event_id).length} · {t('goal14.eventCandidates')} · {t('goal14.playbackNotTested')}</p>
            <p className="fan-claim">{t('goal14.licenseUnknown')} · {t('goal14.matchLinkUnknown')}</p>
            <div className="goal14-card-actions"><button type="button" className="button button-secondary" onClick={() => openEvent(event.event_id)}>{t('goal14.viewEventClips')} →</button><a className="button button-outline" href={event.official_event_page_url} target="_blank" rel="noopener noreferrer">{t('goal14.openEventSource')} ↗</a></div>
          </div></article>)}</div>
        {filteredEvents.length === 0 && <p className="fan-empty-inline" role="status">{t('goal14.noEvents')}</p>}
      </>}
      {mode === 'cinema' && selectedEvent && selectedEventView(selectedEvent)}

      {mode === 'stars' && !activeStar && <div className="fan-content-grid">{filteredStars.map((star) => <article className="fan-content-card goal14-star-card" key={star.athlete_id} data-athlete-id={star.athlete_id}>
        <div className="fan-owned-art" aria-hidden="true"><span>PTTI</span><b>STAR</b></div><div className="fan-content-body">
          <div className="fan-card-meta"><span>{t('goal14.internalOnly')}</span><span>{star.association}</span></div><h3>{locale === 'zh-CN' ? star.name_zh : star.name_en}</h3><p>{locale === 'zh-CN' ? star.name_en : star.name_zh}</p>
          <p className="fan-claim">{star.athlete_id} · ITTF ID {star.ittf_id}</p><p className="fan-claim">{t('goal14.profileSnapshot', { date: star.profile_snapshot_verified_at.slice(0, 10) })}</p>
          <p className="fan-claim">{t('goal14.licenseUnknown')}</p><button type="button" className="button button-secondary" onClick={() => setSelectedStarId(star.athlete_id)}>{t('fan.openStar')} →</button>
        </div></article>)}</div>}
      {mode === 'stars' && activeStar && selectedStarView(activeStar)}

      {mode === 'clips' && <>
        <div className="fan-clip-filters goal14-clip-filters" role="group" aria-label={t('goal14.clipFilters')}>
          <label><span>{t('goal14.filterEvent')}</span><select value={eventFilter} onChange={(event) => setEventFilter(event.target.value)}><option value="all">{t('goal14.allEvents')}</option>{events.map((event) => <option key={event.event_id} value={event.event_id}>{locale === 'zh-CN' ? event.title_zh : event.title_original}</option>)}</select></label>
          <label><span>{t('goal14.filterStarContext')}</span><select value={starContextFilter} onChange={(event) => setStarContextFilter(event.target.value)}><option value="all">{t('goal14.allStarContexts')}</option>{stars.filter((star) => starEvents(star.athlete_id).length > 0).map((star) => <option key={star.athlete_id} value={star.athlete_id}>{locale === 'zh-CN' ? star.name_zh : star.name_en}</option>)}</select></label>
          <label><span>{t('goal14.filterType')}</span><select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="all">{t('goal14.allTypes')}</option>{contentTypes.map((type) => <option key={type} value={type}>{t(`goal14.content.${type}` as MessageKey)}</option>)}</select></label>
          {(eventFilter !== 'all' || starContextFilter !== 'all' || typeFilter !== 'all' || normalizedQuery) && <button type="button" className="button button-outline" onClick={clearFilters}>{t('goal14.clearFilters')}</button>}
        </div>
        {starContextFilter !== 'all' && <p className="goal14-small-note">{t('goal14.rosterScope')}</p>}
        <p className="fan-inventory" data-goal14-clip-count>{filteredClips.length} / {clips.length}</p>
        <div className="fan-content-grid">{filteredClips.map(sourceRouteCard)}</div>
        {filteredClips.length === 0 && <p className="fan-empty-inline" role="status">{t('goal14.noClipsForFilters')}</p>}
      </>}

      {mode === 'watch' && activeClip && selectedWatchView(activeClip)}
      {mode === 'watch' && !activeClip && <div className="fan-empty" role="status"><strong>{t('fan.emptyWatch')}</strong><p>{t('goal14.watchDescription')}</p><button type="button" className="button button-secondary" onClick={() => onNavigate('clips')}>{t('goal14.backToList')}</button></div>}
    </>}
  </section>;
}
