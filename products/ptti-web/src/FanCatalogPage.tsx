import { useEffect, useMemo, useState } from 'react';
import { loadOptionalReviewEvidence } from './optional-review-evidence.mjs';
import type { FormEvent, KeyboardEvent } from 'react';
import { evaluateWatchRoute } from '@ptti/watch-routing';
import { deriveFanRivalries, filterFanClips, filterFanHighlights, findAdmittedFullMatch, normalizeFanSearch, searchFanCatalog } from './fan-catalog.mjs';
import type { FanCatalog, FanMatch, FanSource, FanStar } from './fan-catalog.mjs';
import { evaluateFanWatchRoutes } from './fan-watch-routing.mjs';
import { discoverFanContent } from './fan-discovery.mjs';
import { FAN_INSPIRATION_SHA } from './fan-inspiration.mjs';
import { getLinkedReportAthletes } from './match-report-evidence.mjs';
import { message } from './i18n';
import type { Locale, MessageKey } from './i18n';

import { FanArtwork as OriginalFanArtwork } from './FanArtwork';
import { AthletePortrait } from './MediaAsset';
import { usePublicFanCatalog } from './PublicFanCatalog';
import { PrivateTheaterFrame } from './PrivateTheaterFrame';
import { createWatchCopyGuard } from './watch-copy-guard.mjs';
import { appendUserWatchFeedback, createUserWatchFeedbackReport, readUserWatchFeedback, serializeUserWatchFeedback } from './watch-user-feedback.mjs';
import type { UserWatchFeedbackReport } from './watch-user-feedback.mjs';

type UserReportedPlaybackRow = {
  report_id: string; source_id: string; official_target_url: string; evidence_type: 'USER_REPORTED';
  conclusion: 'STARTED_PLAYBACK'; feedback_source: 'USER_PROVIDED_IN_REQUEST'; tested_at: null; recorded_on: string;
};
type WatchFollowUpItem = {
  source: FanSource; evidence: import('./watchability-evidence.mjs').WatchabilityEvidenceRow;
  priority: number; priorityKey: MessageKey;
};

export type FanCatalogMode = 'cinema' | 'stars' | 'clips' | 'highlights' | 'watch' | 'rivalries';

const routeLabels: Record<string, MessageKey> = {
  OFFICIAL_EMBED: 'fan.route.embed', OFFICIAL_PAGE: 'fan.route.page', AUTHORIZED_SOURCE: 'fan.route.authorized',
  REPLAY: 'fan.route.replay', LIVE_SCORE: 'fan.route.score',
};
const reasonLabels: Record<string, MessageKey> = {
  ROUTE_ELIGIBLE: 'fan.route.eligible', SOURCE_REFERENCE_UNVERIFIED: 'fan.route.sourceUnknown',
  SOURCE_REFERENCE_MISSING: 'fan.route.sourceMissing', VIEW_PERMISSION_UNKNOWN: 'fan.route.permissionUnknown',
  VIEW_PERMISSION_DENIED: 'fan.route.permissionDenied', ROUTE_TYPE_MISMATCH: 'fan.route.typeMismatch',
  EMBED_PERMISSION_UNKNOWN: 'fan.route.embedUnknown', EMBED_PERMISSION_DENIED: 'fan.route.embedDenied',
  RIGHTS_EVIDENCE_REQUIRED: 'fan.route.rightsRequired', LOCAL_MEDIA_UNAVAILABLE: 'fan.route.localUnavailable',
  LOCAL_MEDIA_NOT_SELECTED: 'fan.route.localNotSelected', LOCAL_VIEW_PERMISSION_UNKNOWN: 'fan.route.localPermissionUnknown',
  LOCAL_VIEW_PERMISSION_DENIED: 'fan.route.localPermissionDenied', LIVE_SCORE_UNVERIFIED: 'fan.route.scoreUnknown',
};

function localName(locale: Locale, star: FanStar) {
  return locale === 'zh-CN' ? star.name_zh || star.name_en || star.athlete_id : star.name_en || star.name_zh || star.athlete_id;
}

function participantsLabel(locale: Locale, catalog: FanCatalog | null, match: FanMatch) {
  return match.participants.map((person) => {
    const star = person.athlete_id ? catalog?.stars.find((item) => item.athlete_id === person.athlete_id) : undefined;
    return (locale === 'zh-CN' ? star?.name_zh : star?.name_en) || person.name_en || person.athlete_id || person.side;
  }).join(' vs ');
}

function matchTitleLabel(locale: Locale, catalog: FanCatalog | null, match: FanMatch) {
  return locale === 'zh-CN' && match.display_title_zh ? match.display_title_zh : participantsLabel(locale, catalog, match);
}

function matchEventLabel(locale: Locale, match: FanMatch) {
  return locale === 'zh-CN' && match.event_zh ? match.event_zh : match.event;
}

function matchRoundLabel(locale: Locale, match: FanMatch) {
  return locale === 'zh-CN' && match.round_zh ? match.round_zh : match.round;
}

function sourceTitleLabel(locale: Locale, source: FanSource) {
  return locale === 'zh-CN' && source.display_title_zh ? source.display_title_zh : source.title;
}

function sourceEventLabel(locale: Locale, source: FanSource) {
  return locale === 'zh-CN' && source.event_zh ? source.event_zh : source.event;
}

export function FanCatalogPage({ locale, mode, onGoCinema, onGoStars, onGoInsight, onGoClips, onGoHighlights, onOpenMatch, onChooseVideo, selectedSourceId, onOpenWatch, onOpenStar, onOpenRivalry, onGoCorner, onOpenArena, onFeedback, initialRivalryId, initialStarId, initialMatchId, onGoBack, savedMatchIds = [], followedAthleteIds = [], onToggleSavedMatch, onToggleFollowedAthlete, onOpenTrain, onOpenGear, onOpenCommunity }: {
  locale: Locale; mode: FanCatalogMode; onGoCinema: () => void; onGoStars?: () => void; onGoInsight: () => void;
  onOpenMatch: (matchId: string) => void;
  onChooseVideo?: () => void;
  onGoClips?: () => void;
  onGoHighlights?: () => void;
  selectedSourceId?: string | null; onOpenWatch?: (sourceId: string, context?: { matchId: string | null; starId: string | null }) => void;
  onOpenRivalry?: (rivalryId: string) => void; onGoCorner?: () => void; onOpenArena?: () => void; initialRivalryId?: string | null;
  onOpenStar?: (athleteId: string) => void; initialStarId?: string | null; initialMatchId?: string | null; onGoBack?: () => void;
  savedMatchIds?: string[]; followedAthleteIds?: string[]; onToggleSavedMatch?: (matchId: string) => void; onToggleFollowedAthlete?: (athleteId: string) => void;
  onOpenTrain?: () => void; onOpenGear?: () => void; onOpenCommunity?: () => void;
  onFeedback?: (context?: { sourceId?: string; matchId?: string; starId?: string }) => void;
}) {
  const t = (key: MessageKey, values?: Record<string, string | number>) => {
    let text = message(locale, key);
    for (const [name, value] of Object.entries(values ?? {})) text = text.replaceAll(`{${name}}`, String(value));
    return text;
  };
  const sourceStatusLabel = (value: string) => {
    const keys: Record<string, MessageKey> = {
      VERIFIED_FROM_OFFICIAL_VIDEO_METADATA: 'fan.status.sourceMetadataVerified',
      VERIFIED_OFFICIAL_CHANNEL: 'fan.status.publisherVerified',
      EMBED_BLOCKED_HISTORICAL: 'fan.status.historicalEmbedBlocked',
      UNVERIFIED: 'fan.status.unverified',
      UNKNOWN: 'fan.unknown',
      NOT_TESTED: 'fan.status.notTested',
    };
    return keys[value] ? t(keys[value]) : value;
  };
  const { catalog, inspiration, error, loading, retry, matchReports, matchReportsLoading, matchReportsError } = usePublicFanCatalog();
  const [query, setQuery] = useState('');
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(initialMatchId ?? null);
  const [selectedStarId, setSelectedStarId] = useState<string | null>(initialStarId ?? null);
  const [selectedRivalryId, setSelectedRivalryId] = useState<string | null>(initialRivalryId ?? null);
  const [clipAthleteId, setClipAthleteId] = useState('all');
  const [clipType, setClipType] = useState('all');
  const [discoveryPlatform, setDiscoveryPlatform] = useState('all');
  const [discoveryEvent, setDiscoveryEvent] = useState('all');
  const [discoveryTraining, setDiscoveryTraining] = useState('all');
  const [heroIndex, setHeroIndex] = useState(0);
  const [watchEvidenceState, setWatchEvidenceState] = useState<'not-enabled' | 'loading' | 'ready' | 'error'>('not-enabled');
  const [watchEvidenceRows, setWatchEvidenceRows] = useState<Record<string, import('./watchability-evidence.mjs').WatchabilityEvidenceRow>>({});
  const [userReportedPlaybackRows, setUserReportedPlaybackRows] = useState<Record<string, UserReportedPlaybackRow>>({});
  const [watchFollowUpQueue, setWatchFollowUpQueue] = useState<WatchFollowUpItem[]>([]);
  const [watchFeedbackReports, setWatchFeedbackReports] = useState<UserWatchFeedbackReport[]>([]);
  const [watchFeedbackError, setWatchFeedbackError] = useState(false);
  const [watchFeedbackSaved, setWatchFeedbackSaved] = useState(false);
  const [watchUrlCopyState, setWatchUrlCopyState] = useState<'idle' | 'copied' | 'manual'>('idle');
  const [officialOpenAttempted, setOfficialOpenAttempted] = useState(false);
  const [watchCopyGuard] = useState(createWatchCopyGuard);
  const [playbackStarted, setPlaybackStarted] = useState('');
  const [loginRequired, setLoginRequired] = useState('');
  const [territoryRestricted, setTerritoryRestricted] = useState('');
  useEffect(() => { setSelectedStarId(initialStarId ?? null); }, [initialStarId]);
  useEffect(() => { setSelectedMatchId(initialMatchId ?? null); }, [initialMatchId]);
  useEffect(() => { setSelectedRivalryId(initialRivalryId ?? null); }, [initialRivalryId]);
  useEffect(() => { setOfficialOpenAttempted(false); setWatchUrlCopyState('idle'); }, [selectedSourceId]);

  const normalizedQuery = normalizeFanSearch(query);
  const searchResults = useMemo(() => searchFanCatalog(catalog, query), [catalog, query]);
  const matches = normalizedQuery ? searchResults.matches : (catalog?.matches ?? []);
  const stars = normalizedQuery ? searchResults.stars : (catalog?.stars ?? []);
  const matchingHighlights = searchResults.highlights;
  const clipEligibleSources = useMemo(() => filterFanClips(catalog), [catalog]);
  const officialHighlights = useMemo(() => filterFanHighlights(catalog), [catalog]);
  const visibleHighlights = normalizedQuery ? matchingHighlights : officialHighlights;
  const rivalries = useMemo(() => deriveFanRivalries(catalog), [catalog]);
  const selectedRivalry = rivalries.find((item) => item.rivalry_id === selectedRivalryId) ?? null;
  const rivalryStars = selectedRivalry?.athlete_ids.map((id) => catalog?.stars.find((star) => star.athlete_id === id)).filter((star): star is FanStar => Boolean(star)) ?? [];
  const admittedFullMatch = useMemo(() => findAdmittedFullMatch(catalog), [catalog]);
  const clipTypes = useMemo(() => [...new Set(clipEligibleSources.map((source) => source.content_type_claim))].sort(), [clipEligibleSources]);
  const clipAthletes = useMemo(() => (catalog?.stars ?? []).filter((star) => star.linked_matches.some((matchId) => clipEligibleSources.some((source) => source.canonical_match_id === matchId))), [catalog, clipEligibleSources]);
  const discoveryRows = useMemo(() => discoverFanContent(catalog, { query, athleteId: clipAthleteId, platform: discoveryPlatform, event: discoveryEvent, trainingType: discoveryTraining }), [catalog, query, clipAthleteId, discoveryPlatform, discoveryEvent, discoveryTraining]);
  const clipSources = useMemo(() => filterFanClips(catalog, { query: normalizedQuery, athleteId: clipAthleteId, contentType: clipType }).filter((source) => discoveryRows.some((row) => row.source_id === source.source_id)), [catalog, normalizedQuery, clipAthleteId, clipType, discoveryRows]);
  const clipFiltersActive = Boolean(query.trim()) || clipAthleteId !== 'all' || clipType !== 'all';
  const heroMatches = catalog?.matches ?? [];
  const featuredMatch = heroMatches.length ? heroMatches[heroIndex % heroMatches.length] : admittedFullMatch;
  const featuredSource = featuredMatch?.video_source_ids
    .map((id) => catalog?.sources.find((source) => source.source_id === id))
    .find((source): source is FanSource => Boolean(source
      && source.match_link_status === 'HUMAN_VERIFIED' && source.canonical_match_id === featuredMatch?.match_id
      && source.external_viewing === 'ALLOWED' && source.url));
  const featuredRoute = featuredSource ? evaluateFanWatchRoutes(featuredSource, evaluateWatchRoute).find((route) => route.mode === 'OFFICIAL_PAGE') : undefined;
  const featuredRouteEligible = featuredRoute?.decision?.state === 'ELIGIBLE' && Boolean(featuredRoute.url);
  const featuredStarId = featuredMatch?.participants.find((participant) => participant.athlete_id && catalog?.stars.some((star) => star.athlete_id === participant.athlete_id))?.athlete_id ?? null;

  function clearClipFilters() {
    setQuery('');
    setClipAthleteId('all');
    setClipType('all');
    setDiscoveryPlatform('all'); setDiscoveryEvent('all'); setDiscoveryTraining('all');
  }

  const selectedMatch = catalog?.matches.find((match) => match.match_id === selectedMatchId) ?? null;
  const selectedMatchReport = selectedMatch ? matchReports.find((report) => report.match_id === selectedMatch.match_id) ?? null : null;
  const reportWinner = selectedMatchReport ? catalog?.stars.find((star) => star.athlete_id === selectedMatchReport.recorded_result.winner_id) : null;
  const reportMatchId = 'pro:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final';
  const selectedStar = catalog?.stars.find((star) => star.athlete_id === selectedStarId) ?? null;
  const selectedSource = catalog?.sources.find((source) => source.source_id === selectedSourceId) ?? null;
  const activeWatchSource = selectedSource ?? (!selectedSourceId ? featuredSource : null);
  const linkedSources = selectedMatch
    ? selectedMatch.video_source_ids.map((id) => catalog?.sources.find((source) => source.source_id === id)).filter((source): source is FanSource => Boolean(source))
    : [];

  useEffect(() => {
    if (mode !== 'watch' || !import.meta.env.DEV || !catalog) {
      setWatchEvidenceState('not-enabled');
      setWatchEvidenceRows({});
      setUserReportedPlaybackRows({});
      setWatchFollowUpQueue([]);
      return;
    }
    let current = true;
    setWatchEvidenceState('loading');
    void (async () => {
      try {
        const payload = await loadOptionalReviewEvidence();
        if (!payload) {
          if (current) {
            setWatchEvidenceRows({});
            setUserReportedPlaybackRows({});
            setWatchFollowUpQueue([]);
            setWatchEvidenceState('not-enabled');
          }
          return;
        }
        const [validator, followUp] = await Promise.all([
          import('./watchability-evidence.mjs'),
          import('./watch-follow-up.mjs'),
        ]);
        const raw = payload.evidenceRaw;
        const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(raw));
        const actualSha = [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
        if (actualSha !== validator.GOAL19_WATCHABILITY_SHA256) throw new Error('watchability-evidence-sha-mismatch');
        const evidence = JSON.parse(raw);
        const baselineSources = catalog.sources.filter((source) => evidence.sources.some((row: { source_id: string }) => row.source_id === source.source_id));
        const rows = validator.createWatchabilityEvidenceIndex(evidence, baselineSources);
        const reportRaw = payload.reportsRaw;
        const reportDigest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(reportRaw));
        const reportSha = [...new Uint8Array(reportDigest)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
        if (reportSha !== followUp.USER_WATCH_PLAYBACK_REPORTS_SHA256) throw new Error('user-playback-reports-sha-mismatch');
        const reports = followUp.indexUserReportedPlaybackEvidence(JSON.parse(reportRaw), catalog.sources);
        let localReports: UserWatchFeedbackReport[] = [];
        try { localReports = readUserWatchFeedback(localStorage); } catch { /* malformed local feedback stays visible as an error in its own form */ }
        const allReported = followUp.mergeLocalUserFeedbackSources(reports, catalog.sources, localReports);
        const queue = followUp.buildWatchFollowUpQueue(baselineSources, rows, allReported);
        if (!current) return;
        setWatchEvidenceRows(Object.fromEntries(rows));
        setUserReportedPlaybackRows(Object.fromEntries(reports));
        setWatchFollowUpQueue(queue);
        setWatchEvidenceState('ready');
      } catch {
        if (!current) return;
        setWatchEvidenceRows({});
        setUserReportedPlaybackRows({});
        setWatchFollowUpQueue([]);
        setWatchEvidenceState('error');
      }
    })();
    return () => { current = false; };
  }, [mode, catalog]);

  useEffect(() => {
    watchCopyGuard.invalidate();
    if (mode !== 'watch' || !activeWatchSource) return () => watchCopyGuard.invalidate();
    setWatchUrlCopyState('idle');
    setOfficialOpenAttempted(false);
    setWatchFeedbackSaved(false);
    setPlaybackStarted('');
    setLoginRequired('');
    setTerritoryRestricted('');
    try {
      setWatchFeedbackReports(readUserWatchFeedback(localStorage).filter((report) => report.source_id === activeWatchSource.source_id));
      setWatchFeedbackError(false);
    } catch {
      setWatchFeedbackReports([]);
      setWatchFeedbackError(true);
    }
    return () => watchCopyGuard.invalidate();
  }, [mode, activeWatchSource?.source_id, watchCopyGuard]);

  function saveWatchFeedback(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeWatchSource?.url) return;
    try {
      const report = createUserWatchFeedbackReport({
        reportId: globalThis.crypto?.randomUUID?.() ?? `watch-report-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        source: { source_id: activeWatchSource.source_id, url: activeWatchSource.url },
        testedAt: new Date().toISOString(),
        playbackStarted: playbackStarted as 'YES' | 'NO' | 'UNSURE',
        loginRequired: loginRequired as 'YES' | 'NO' | 'UNKNOWN',
        territoryRestricted: territoryRestricted as 'YES' | 'NO' | 'UNKNOWN',
      });
      const allReports = appendUserWatchFeedback(localStorage, report);
      setWatchFeedbackReports(allReports.filter((row) => row.source_id === activeWatchSource.source_id));
      setWatchFollowUpQueue((current) => current.filter((item) => item.source.source_id !== report.source_id));
      setWatchFeedbackError(false);
      setWatchFeedbackSaved(true);
      setPlaybackStarted('');
      setLoginRequired('');
      setTerritoryRestricted('');
    } catch {
      setWatchFeedbackSaved(false);
      setWatchFeedbackError(true);
    }
  }

  async function copyOfficialWatchUrl() {
    if (!activeWatchSource?.url) return;
    const result = await watchCopyGuard.copy(activeWatchSource.url, navigator.clipboard?.writeText
      ? (url) => navigator.clipboard.writeText(url) : undefined);
    if (result !== null) setWatchUrlCopyState(result);
  }

  function exportWatchFeedback() {
    try {
      const text = serializeUserWatchFeedback(readUserWatchFeedback(localStorage));
      const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'ptti-user-watch-feedback.json';
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
      setWatchFeedbackError(false);
    } catch {
      setWatchFeedbackError(true);
    }
  }

  function sourceCard(source: FanSource) {
    const routeDecisions = evaluateFanWatchRoutes(source, evaluateWatchRoute);
    const officialPage = routeDecisions.find((route) => route.mode === 'OFFICIAL_PAGE');
    const officialPageEligible = officialPage?.decision?.state === 'ELIGIBLE' && officialPage.url;
    return <article className="fan-content-card fan-source-card" key={source.source_id} data-public-source-id={source.source_id}>
      {officialPageEligible && onOpenWatch ? <button type="button" className="fan-source-visual" aria-label={`${t('fan.openWatch')}: ${sourceTitleLabel(locale, source)}`} onClick={() => onOpenWatch(source.source_id, { matchId: source.match_link_status === 'HUMAN_VERIFIED' ? source.canonical_match_id : null, starId: selectedStar?.athlete_id ?? null })}>
        <OriginalFanArtwork locale={locale} kind="match" identity={source.source_id} title={sourceEventLabel(locale, source)} subtitle={t(`fan.clipType.${source.content_type_claim}` as MessageKey)} />
        <span className="fan-visual-action" aria-hidden="true">↗</span>
      </button> : <OriginalFanArtwork locale={locale} kind="match" identity={source.source_id} title={sourceEventLabel(locale, source)} />}
      <div className="fan-content-body">
        <div className="fan-card-meta"><span>{source.publisher}</span><span>{source.platform}</span></div>
        <h3>{sourceTitleLabel(locale, source)}</h3>
        <p>{source.inspiration_category === 'SEASON_HIGHLIGHTS_TITLE_CLAIM' ? t('inspiration.seasonScope') : source.content_type_claim === 'HIGHLIGHTS' ? t('fan.eventLevelSource') : t(`fan.clipType.${source.content_type_claim}` as MessageKey)}</p>
        {officialPageEligible && onOpenWatch
          ? <button type="button" className="fan-section-link" onClick={() => onOpenWatch(source.source_id, { matchId: source.match_link_status === 'HUMAN_VERIFIED' ? source.canonical_match_id : null, starId: selectedStar?.athlete_id ?? null })}>{t('fan.openWatch')} ↗</button>
          : <p className="fan-no-watch" role="status">{t('fan.noEligibleWatchRoute')}</p>}
        <small className="fan-media-scope">{t('fan.externalSource')} · {t('fan.playbackNotTested')}</small>
        <details className="fan-content-rights"><summary>{t('discovery.sourceRights')}</summary><p>{t('discovery.rightsExplanation')}</p><dl><dt>{t('discovery.externalPermission')}</dt><dd>{t(`discovery.permission.${source.external_viewing}` as MessageKey)}</dd><dt>{t('discovery.embedPermission')}</dt><dd>{t(`discovery.permission.${source.embedding}` as MessageKey)}</dd><dt>{t('discovery.thumbnailPermission')}</dt><dd>{t(`discovery.permission.${source.thumbnail_display}` as MessageKey)}</dd></dl>{source.url && <a href={source.url} target="_blank" rel="noopener noreferrer">{t('discovery.originalSource')} ↗</a>}</details>
      </div>
    </article>;
  }

  function matchCard(match: FanMatch) {
    const linked = match.video_source_ids.map((id) => catalog?.sources.find((source) => source.source_id === id)).filter((source): source is FanSource => Boolean(source));
    const playableRoute = linked.map((source) => ({ source, route: evaluateFanWatchRoutes(source, evaluateWatchRoute).find((route) => route.mode === 'OFFICIAL_PAGE' && route.decision?.state === 'ELIGIBLE' && route.url) })).find((row) => row.route);
    const open = () => mode !== 'rivalries' && playableRoute?.source && onOpenWatch
      ? onOpenWatch(playableRoute.source.source_id, { matchId: match.match_id, starId: selectedStar?.athlete_id ?? null })
      : onOpenMatch(match.match_id);
    const keyOpen = (event: KeyboardEvent<HTMLElement>) => { if (event.currentTarget !== event.target) return; if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); open(); } };
    return <article className="fan-content-card fan-match-card" key={match.match_id} data-public-match-id={match.match_id} role="link" tabIndex={0} aria-label={t(mode !== 'rivalries' && playableRoute?.source && onOpenWatch ? 'fan.openWatchCard' : 'fan.openMatchCard', { match: participantsLabel(locale, catalog, match) })} onClick={open} onKeyDown={keyOpen}>
      <OriginalFanArtwork locale={locale} kind="match" identity={match.match_id} title={matchTitleLabel(locale, catalog, match)} subtitle={matchEventLabel(locale, match)} />
      <div className="fan-content-body"><div className="fan-card-meta"><span>{matchEventLabel(locale, match)}</span><span>{matchRoundLabel(locale, match)}</span></div>
        <h3>{matchTitleLabel(locale, catalog, match)}</h3><p className="fan-match-platform">{linked.map((source) => source.publisher).filter((value, index, all) => all.indexOf(value) === index).join(" · ") || t('fan.noLinkedVideo')}</p>
        <div className="fan-match-actions"><button type="button" className="button button-outline" onClick={(event) => { event.stopPropagation(); setSelectedMatchId(match.match_id); }}>{t('fan.openMatch')}</button>
          {linked.map((source) => evaluateFanWatchRoutes(source, evaluateWatchRoute).some((route) => route.mode === 'OFFICIAL_PAGE' && route.decision?.state === 'ELIGIBLE' && route.url) && onOpenWatch
            ? <button type="button" className="button button-primary" key={source.source_id} onClick={(event) => { event.stopPropagation(); onOpenWatch(source.source_id, { matchId: match.match_id, starId: selectedStar?.athlete_id ?? null }); }}>{t('fan.watchMatchCta')} ↗</button>
            : null)}
          {onToggleSavedMatch && <button type="button" className="button button-outline fan-save-button" aria-pressed={savedMatchIds.includes(match.match_id)} onClick={(event) => { event.stopPropagation(); onToggleSavedMatch(match.match_id); }}>{t(savedMatchIds.includes(match.match_id) ? 'fan.saved' : 'fan.save')}</button>}
        </div>

      </div>
    </article>;
  }

  function selectedMatchView() {
    if (!selectedMatch) return null;
    return <section className="fan-match-detail" aria-labelledby="fan-match-title" data-fan-match-detail data-public-match-id={selectedMatch.match_id}>
      <button type="button" className="button button-outline" onClick={() => setSelectedMatchId(null)}>← {t(selectedStar ? 'fan.backToStars' : 'fan.backToCinema')}</button>
      <div className="fan-match-detail-heading"><div><p className="eyebrow">{t('fan.matchCenter')}</p><h1 id="fan-match-title">{matchTitleLabel(locale, catalog, selectedMatch)}</h1><p>{matchEventLabel(locale, selectedMatch)} · {matchRoundLabel(locale, selectedMatch)} · {selectedMatch.match_type}</p></div><OriginalFanArtwork locale={locale} kind="match" identity={selectedMatch.match_id} title={matchTitleLabel(locale, catalog, selectedMatch)} subtitle={matchEventLabel(locale, selectedMatch)} /></div>
      {onToggleSavedMatch && <button type="button" className="button button-outline fan-detail-save" aria-pressed={savedMatchIds.includes(selectedMatch.match_id)} onClick={() => onToggleSavedMatch(selectedMatch.match_id)}>{t(savedMatchIds.includes(selectedMatch.match_id) ? 'fan.saved' : 'fan.save')}</button>}
      {selectedMatch.recorded_result && selectedMatch.result_status === 'OFFICIAL_EVENT_RESULT_CROSSCHECKED' && <p className="fan-recorded-result"><span>{t('fan.recordedResult')}</span><strong>{selectedMatch.recorded_result.player_a_games}–{selectedMatch.recorded_result.player_b_games}</strong></p>}
      {selectedMatchReport && <section className="fan-match-report" data-match-report-id={selectedMatchReport.report_id} aria-labelledby="fan-match-report-title">
        <div className="fan-section-heading"><div><p className="eyebrow">WTT · {t('fan.matchReportEvidence')}</p><h2 id="fan-match-report-title">{t('fan.matchReportTitle')}</h2></div></div>
        <p className="fan-recorded-result"><span>{t('fan.recordedResult')}</span><strong>{t('fan.matchReportResult', { winner: reportWinner ? localName(locale, reportWinner) : selectedMatchReport.recorded_result.winner_name })}</strong></p>
        <p className="fan-report-game-scores"><strong>{t('fan.matchReportGameScores')}:</strong> {selectedMatchReport.game_scores.map((score) => score.join('–')).join(' · ')}</p>
        <p lang={locale === 'zh-CN' ? 'zh-CN' : 'en'}>{locale === 'zh-CN' ? selectedMatchReport.editorial_summary_zh : t('fan.matchReportSummaryEn')}</p>
        <div className="fan-report-athletes" aria-label={t('fan.matchReportParticipants')}>
          {getLinkedReportAthletes(selectedMatchReport, catalog!).map((star) => onOpenStar
            ? <button type="button" className="button button-outline" key={star.athlete_id} data-report-athlete-id={star.athlete_id} onClick={() => onOpenStar(star.athlete_id)}>{localName(locale, star)}</button>
            : <span className="fan-report-athlete-unlinked" key={star.athlete_id}>{localName(locale, star)}</span>)}
          {selectedMatchReport.participants.filter((person) => !catalog?.stars.some((star) => star.athlete_id === person.athlete_id)).map((person) => <span className="fan-report-athlete-unlinked" key={person.athlete_id} data-report-athlete-unlinked={person.athlete_id}>{person.name_en}</span>)}
        </div>
        <p className="fan-report-source-observation">{t('fan.matchReportSourceObservation')}</p>
        <p className="fan-report-date-unknown">{t('fan.matchReportDateUnknown')}</p>
        <a className="button button-outline" href={selectedMatchReport.article.url} target="_blank" rel="noopener noreferrer">{t('fan.openOfficialMatchReport')} ↗</a>
      </section>}
      {selectedMatch.match_id === reportMatchId && matchReportsLoading && <p className="fan-report-load-status" role="status">{t('fan.matchReportLoading')}</p>}
      {selectedMatch.match_id === reportMatchId && matchReportsError && <p className="fan-report-load-status" role="status">{t('fan.matchReportUnavailable')}</p>}
      <h3>{t('fan.matchSources')}</h3>
      {linkedSources.length ? <div className="fan-source-list">{linkedSources.map(sourceCard)}</div> : <p className="fan-empty-inline" role="status">{t('fan.noLinkedVideo')}</p>}
      {selectedMatch.reference_url && !selectedMatchReport && <a className="fan-text-link" href={selectedMatch.reference_url} target="_blank" rel="noopener noreferrer">{t('fan.openReference')} ↗</a>}
      <details className="fan-identity-details"><summary>{t('fan.sourceDetails')}</summary><code>{selectedMatch.match_id}</code><p>{t('fan.noSyntheticJoin')}</p></details>
    </section>;
  }

  function selectedStarView() {
    if (!selectedStar) return null;
    const related = selectedStar.linked_matches.map((id) => catalog?.matches.find((item) => item.match_id === id)).filter((item): item is FanMatch => Boolean(item));
    const relatedRivalries = rivalries.filter((rivalry) => rivalry.athlete_ids.includes(selectedStar.athlete_id));
    const monogram = localName(locale, selectedStar).split(/\s+/).map((part) => part[0]).join('').slice(0, 3);
    return <section className="fan-star-profile" aria-labelledby="fan-star-title" data-fan-star-detail>
      <button type="button" className="button button-outline" onClick={() => setSelectedStarId(null)}>← {t('fan.backToStars')}</button>
      <div className="fan-profile-hero"><AthletePortrait athleteId={selectedStar.athlete_id} fallback={<OriginalFanArtwork locale={locale} kind="star" identity={selectedStar.athlete_id} monogram={monogram} title={localName(locale, selectedStar)} subtitle={selectedStar.association || undefined} />} /><div>
        <p className="eyebrow">{t('fan.starProfile')}</p><h1 id="fan-star-title">{localName(locale, selectedStar)}</h1>
        <p className="fan-profile-original-name">{locale === 'en' ? selectedStar.name_zh || '' : selectedStar.name_en || ''}</p>
        {selectedStar.association && <span className="fan-association-pill">{selectedStar.association}</span>}
        <div className="fan-profile-shortcuts"><a className="fan-section-link" href="#fan-profile-matches">{t('fan.relatedMatches')} ↓</a>{relatedRivalries.length > 0 && <a className="fan-section-link" href="#fan-profile-rivalries">{t('fan.relatedRivalries')} ↓</a>}</div>
        {onToggleFollowedAthlete && <><button type="button" className="button button-primary" aria-pressed={followedAthleteIds.includes(selectedStar.athlete_id)} onClick={() => onToggleFollowedAthlete(selectedStar.athlete_id)}>{t(followedAthleteIds.includes(selectedStar.athlete_id) ? 'fan.following' : 'fan.follow')}</button><small className="fan-save-scope">{t('fan.localOnly')}</small></>}
        {selectedStar.official_profile_url && <a className="button button-outline" href={selectedStar.official_profile_url} target="_blank" rel="noopener noreferrer">{t('fan.openProfile')} ↗</a>}
      </div></div>
      <details className="fan-profile-about"><summary>{t('fan.profileAbout')}</summary><p>{t('fan.bioScope')}</p><p>{t('fan.equipmentUnknown')}</p></details>
      <section className="fan-profile-matches" id="fan-profile-matches"><div className="fan-section-heading"><div><p className="eyebrow">{t('fan.profileMatchesKicker')}</p><h3>{t('fan.relatedMatches')}</h3></div><span>{related.length}</span></div>
        {related.length ? <div className="fan-content-grid">{related.map(matchCard)}</div> : <p className="fan-empty-inline" role="status">{t('fan.noRelatedMatches')}</p>}
      </section>
      <section className="fan-star-content" aria-label={t('discovery.starContent')}><h3>{t('discovery.starContent')}</h3><p>{t('inspiration.starScope')}</p>{inspiration?.international_reactions.filter((reaction) => selectedStar.linked_matches.includes(reaction.related_match_id ?? '')).map((reaction) => <article className="fan-reaction-card" key={reaction.reaction_id} data-reaction-id={reaction.reaction_id}><p className="eyebrow">{reaction.publisher} · {reaction.published_at} · {reaction.language}</p><h4 lang={reaction.language}>{reaction.source_title}</h4><p lang="zh-CN">{reaction.summary_zh}</p><small>{t('inspiration.singleReport')}</small><a className="button button-outline" href={reaction.source_url} target="_blank" rel="noopener noreferrer">{t('inspiration.openArticle')} ↗</a></article>)}<div className="fan-empty-actions"><button type="button" className="button button-outline" onClick={onGoClips}>{t('nav.clips')}</button>{selectedStar.official_profile_url && <a className="button button-outline" href={selectedStar.official_profile_url} target="_blank" rel="noopener noreferrer">{t('fan.openProfile')} ↗</a>}</div></section>
      {relatedRivalries.length > 0 && <section className="fan-profile-rivalries" id="fan-profile-rivalries"><div className="fan-section-heading"><div><p className="eyebrow">HEAD TO HEAD</p><h3>{t('fan.relatedRivalries')}</h3></div><span>{relatedRivalries.length}</span></div>
        <div className="fan-rivalry-grid">{relatedRivalries.map((rivalry) => <button type="button" className="fan-rivalry-card" key={rivalry.rivalry_id} onClick={() => onOpenRivalry?.(rivalry.rivalry_id)}>
          <strong>{rivalry.athlete_ids.map((id) => { const star = catalog?.stars.find((item) => item.athlete_id === id); return star ? localName(locale, star) : id; }).join(' vs ')}</strong><span>{rivalry.match_ids.length} · {t('fan.relatedRivalries')}</span><small>{t('rivalry.scope')}</small>
        </button>)}</div>
      </section>}
    </section>;
  }

  function selectedRivalryView() {
    if (!selectedRivalry) return null;
    const linkedMatches = selectedRivalry.match_ids.map((id) => catalog?.matches.find((match) => match.match_id === id)).filter((match): match is FanMatch => Boolean(match));
    return <section className="fan-rivalry-detail" data-rivalry-detail data-rivalry-id={selectedRivalry.rivalry_id}>
      <button type="button" className="button button-outline" onClick={() => setSelectedRivalryId(null)}>← {t('rivalry.back')}</button>
      <div className="fan-rivalry-heading"><p className="eyebrow">{t('rivalry.kicker')}</p><h2>{rivalryStars.map((star) => localName(locale, star)).join(' vs ')}</h2><p>{t('rivalry.scope')}</p></div>
      <div className="fan-section-heading"><h3>{t('rivalry.linkedMatches')}</h3><span>{linkedMatches.length}</span></div>
      {linkedMatches.length ? <div className="fan-content-grid">{linkedMatches.map((match) => <article className="fan-content-card fan-match-card" key={match.match_id} data-public-match-id={match.match_id}>
        <OriginalFanArtwork locale={locale} kind="match" /><div className="fan-content-body"><div className="fan-card-meta"><span>{matchEventLabel(locale, match)}</span><span>{matchRoundLabel(locale, match)}</span></div><h3>{participantsLabel(locale, catalog, match)}</h3><p>{match.match_type}</p>
          {match.recorded_result && match.result_status === 'OFFICIAL_EVENT_RESULT_CROSSCHECKED' ? <p className="fan-recorded-result"><span>{t('fan.recordedResult')}</span><strong>{match.recorded_result.player_a_games}–{match.recorded_result.player_b_games}</strong></p> : <p className="fan-empty-inline">{t('rivalry.noResult')}</p>}
          <div className="fan-match-actions"><button type="button" className="button button-outline" onClick={() => onOpenMatch(match.match_id)}>{t('fan.openMatch')}</button>
            {match.video_source_ids.map((id) => catalog?.sources.find((source) => source.source_id === id)).filter((source): source is FanSource => Boolean(source && source.external_viewing === 'ALLOWED' && source.url)).map((source) => <button type="button" key={source.source_id} className="button button-primary" onClick={() => onOpenWatch?.(source.source_id, { matchId: match.match_id, starId: null })}>{t('rivalry.watch')} ↗</button>)}
          </div><small>{match.match_id}</small>
        </div></article>)}</div> : <p className="fan-empty-inline" role="status">{t('rivalry.noResult')}</p>}
    </section>;
  }

  function selectedSourceView() {
    const activeSource = activeWatchSource;
    if (!activeSource) return <div className="fan-empty private-theater-empty" role="status"><strong>{t(selectedSourceId ? 'fan.sourceNotFound' : 'fan.emptyWatch')}</strong><p>{t('fan.emptyWatchDetail')}</p><div className="fan-empty-actions"><button type="button" className="button button-outline" onClick={onGoCinema}>{t('fan.goCinema')}</button><button type="button" className="button button-outline" onClick={onGoClips}>{t('fan.goClips')}</button></div></div>;
    const sourceMatch = activeSource.canonical_match_id
      ? catalog?.matches.find((match) => match.match_id === activeSource.canonical_match_id) ?? null
      : null;
    const relatedOfficialHighlights = officialHighlights.filter((source) => source.event === activeSource.event && source.source_id !== activeSource.source_id).slice(0, 3);
    const routeDecisions = evaluateFanWatchRoutes(activeSource, evaluateWatchRoute);
    const officialPage = routeDecisions.find((route) => route.mode === 'OFFICIAL_PAGE');
    const canOpenOfficialPage = officialPage?.decision?.state === 'ELIGIBLE' && officialPage.url;
    return <PrivateTheaterFrame key={activeSource.source_id} locale={locale} sourceId={activeSource.source_id} onBack={onGoBack ?? onGoCinema} main={<>
      <div className="fan-watch-hero"><OriginalFanArtwork locale={locale} kind="match" identity={sourceMatch?.match_id ?? activeSource.source_id} title={sourceMatch ? matchTitleLabel(locale, catalog, sourceMatch) : sourceEventLabel(locale, activeSource)} subtitle={t(`fan.clipType.${activeSource.content_type_claim}` as MessageKey)} /><div className="fan-watch-copy">
        <p className="eyebrow fan-publisher-badge"><span aria-hidden="true">↗</span> {activeSource.publisher} · {activeSource.platform}</p><h1 id="fan-watch-title">{sourceMatch ? matchTitleLabel(locale, catalog, sourceMatch) : sourceTitleLabel(locale, activeSource)}</h1>
        <p>{sourceEventLabel(locale, activeSource)}{activeSource.event_year ? ` · ${activeSource.event_year}` : ''} · {activeSource.platform}</p>
        <p className="theater-route-label">{t(canOpenOfficialPage ? 'theater.externalMode' : 'theater.recordMode')}</p>
        {sourceMatch && activeSource.match_link_status !== 'HUMAN_VERIFIED' && <p className="theater-license-note">{t(activeSource.match_link_status === 'OFFICIAL_TITLE_ASSOCIATED_VISUAL_NOT_TESTED' ? 'fan.matchLinkTitleOnly' : 'fan.sourceUnlinked')}</p>}
        {canOpenOfficialPage ? <div className="fan-watch-actions"><a className="button button-primary" href={officialPage.url!} target="_blank" rel="noopener noreferrer" onClick={() => setOfficialOpenAttempted(true)}>{activeSource.platform === 'YOUTUBE' ? t('fan.openYouTube') : t('fan.openPlatform')} ↗</a>
          <button type="button" className="button button-outline" onClick={() => void copyOfficialWatchUrl()}>{t('fan.copyOfficialUrl')}</button></div> : <p className="fan-no-watch" role="status">{t('fan.noEligibleWatchRoute')}</p>}
        {officialOpenAttempted && <p className="fan-official-open-hint" role="status">{t('fan.officialOpenAttempted')}</p>}
        {sourceMatch && onToggleSavedMatch && <button type="button" className="button button-quiet fan-watch-save" aria-pressed={savedMatchIds.includes(sourceMatch.match_id)} onClick={() => onToggleSavedMatch(sourceMatch.match_id)}>{t(savedMatchIds.includes(sourceMatch.match_id) ? 'fan.saved' : 'fan.save')}</button>}
        {watchUrlCopyState === 'copied' && <p className="watch-url-copy-status" role="status">{t('fan.officialUrlCopied')}</p>}
        {watchUrlCopyState === 'manual' && activeSource.url && <div className="watch-url-copy-status" role="status"><p>{t('fan.officialUrlManualCopy')}</p><input aria-label={t('fan.officialUrlLabel')} readOnly value={activeSource.url} onFocus={(event) => event.currentTarget.select()} /></div>}
        <span className="fan-source-state">{t('fan.externalSource')} · {t('fan.playbackNotTested')} · {t(`fan.clipType.${activeSource.content_type_claim}` as MessageKey)}</span>
        {activeSource.inspiration_category === 'SEASON_HIGHLIGHTS_TITLE_CLAIM' && <p>{t('inspiration.seasonScope')}</p>}
        <p className="theater-license-note">{t(canOpenOfficialPage ? 'theater.externalBoundary' : 'theater.recordBoundary')}</p>
        <dl className="theater-source-facts"><div><dt>{t('fan.embedding')}</dt><dd>{t(`theater.embed.${activeSource.embedding}` as MessageKey)}</dd></div><div><dt>{t('theater.completeness')}</dt><dd>{t(activeSource.completeness_status === 'VERIFIED' ? 'theater.completenessRecorded' : 'theater.completenessUnverified')}</dd></div></dl>
        <small className="fan-third-party-note">{t('gm.noMediaGuarantee')}</small>
        <details className="fan-watch-help"><summary>{t('fan.watchHelpTitle')}</summary><p>{t('fan.watchHelpBody')}</p><div className="fan-empty-actions">{canOpenOfficialPage && <button type="button" className="button button-outline" onClick={() => void copyOfficialWatchUrl()}>{t('fan.copyOfficialUrl')}</button>}{onFeedback && <button type="button" className="button button-outline" onClick={() => onFeedback({ sourceId: activeSource.source_id, ...(sourceMatch ? { matchId: sourceMatch.match_id } : {}) })}>{t('voice.open')}</button>}</div></details>
      </div></div>
      <div className="fan-empty-actions fan-watch-personal-actions">{sourceMatch && <button type="button" className="button button-outline" data-theater-match-id={sourceMatch.match_id} onClick={() => onOpenMatch(sourceMatch.match_id)}>{t('fan.openMatch')} →</button>}{onGoCorner && <button type="button" className="button button-outline" onClick={onGoCorner}>{t('lobby.collection')}</button>}{onFeedback && <button type="button" className="button button-outline" onClick={() => onFeedback({ sourceId: activeSource.source_id, ...(sourceMatch ? { matchId: sourceMatch.match_id } : {}) })}>{t('voice.open')}</button>}</div>
      </>} secondary={<>
      {import.meta.env.DEV && <section className="watch-evidence-panel" data-watchability-evidence aria-labelledby="watch-evidence-title">
        <div className="watch-evidence-heading"><div><p className="eyebrow">{t('watchEvidence.kicker')}</p><h2 id="watch-evidence-title">{t('watchEvidence.title')}</h2></div><span className="watch-evidence-source-id">{activeSource.source_id}</span></div>
        <p className="watch-evidence-intro">{t('watchEvidence.intro')}</p>
        {watchEvidenceState === 'loading' && <p className="watch-evidence-state" role="status">{t('watchEvidence.loading')}</p>}
        {watchEvidenceState === 'error' && <p className="watch-evidence-state" role="status">{t('watchEvidence.unavailable')}</p>}
        {watchEvidenceState === 'ready' && (() => {
          const evidence = watchEvidenceRows[activeSource.source_id];
          if (!evidence) return <p className="watch-evidence-state" role="status">{t('watchEvidence.notInAddendum')}</p>;
          const fetchStatus = evidence.current_page_fetch.status;
          const pageKey: MessageKey = fetchStatus === 'PAGE_TITLE_SURFACED' ? 'watchEvidence.pageTitleSurfaced'
            : fetchStatus === 'BLOCKED_FETCH_THROTTLED' ? 'watchEvidence.pageThrottled'
              : 'watchEvidence.pageNotTested';
          const targetKey: MessageKey = evidence.verification_levels.official_target_correct === 'PARTIAL_TITLE_MATCH_WITH_BASELINE_VERIFIED_PUBLISHER'
            ? 'watchEvidence.targetPartial' : 'watchEvidence.targetNotReconfirmed';
          const matchLinkKey: MessageKey = evidence.match_link_baseline === 'HUMAN_VERIFIED' ? 'watchEvidence.matchLinkHumanVerified'
            : evidence.match_link_baseline.includes('TITLE_MATCH_ASSOCIATION') ? 'watchEvidence.matchLinkTitleOnly'
              : 'watchEvidence.matchLinkUnknown';
          const userPlaybackReport = userReportedPlaybackRows[activeSource.source_id];
          return <>
            <dl className="watch-evidence-levels">
              <div><dt>{t('watchEvidence.matchLink')}</dt><dd>{t(matchLinkKey)}</dd></div>
              <div><dt>{t('watchEvidence.pageFetch')}</dt><dd>{t(pageKey)}</dd></div>
              <div><dt>{t('watchEvidence.targetCheck')}</dt><dd>{t(targetKey)}</dd></div>
              <div><dt>{t('watchEvidence.browserOpen')}</dt><dd>{t('watchEvidence.notTested')}</dd></div>
              <div><dt>{t('watchEvidence.videoStart')}</dt><dd>{t('watchEvidence.notTested')}</dd></div>
              <div><dt>{t('watchEvidence.completeWatch')}</dt><dd>{t('watchEvidence.unverified')}</dd></div>
            </dl>
            {evidence.video_type_claim === 'FULL_MATCH_TITLE_CLAIM' && <p className="watch-evidence-caveat">{t('watchEvidence.fullMatchTitleOnly')}</p>}
            {userPlaybackReport && <div className="watch-user-provided-playback" data-user-provided-playback="USER_REPORTED">
              <strong>USER_REPORTED · {t('watchEvidence.reportedStarted')}</strong>
              <p>{t('watchEvidence.reportedOn', { date: userPlaybackReport.recorded_on })}</p>
              <p>{t('watchEvidence.reportedTimeNotProvided')}</p>
              <code>{userPlaybackReport.official_target_url}</code>
            </div>}
            <details className="watch-evidence-source-details"><summary>{t('watchEvidence.recordDetails')}</summary>
              <p><strong>{t('watchEvidence.sourceUrl')}:</strong> <code>{evidence.official_target_url}</code></p>
              {evidence.current_page_fetch.checked_on && <p><strong>{t('watchEvidence.checkedOn')}:</strong> {evidence.current_page_fetch.checked_on}</p>}
              {evidence.current_page_fetch.note && <p>{evidence.current_page_fetch.note}</p>}
            </details>
            <details className="watch-follow-up-queue" data-watch-follow-up-queue>
              <summary>{t('watchEvidence.followUpQueue', { count: watchFollowUpQueue.length })}</summary>
              <p>{t('watchEvidence.followUpIntro')}</p>
              <ol>{watchFollowUpQueue.map(({ source, priority, priorityKey }) => <li key={source.source_id} data-priority={priority}>
                <div><strong>{t(priorityKey)} · {sourceTitleLabel(locale, source)}</strong><small>{sourceEventLabel(locale, source)} · {source.source_id}</small><code>{source.url}</code></div>
                <button type="button" className="button button-outline" onClick={() => onOpenWatch?.(source.source_id, { matchId: source.canonical_match_id, starId: null })}>{t('watchEvidence.openWatchRecord')}</button>
              </li>)}</ol>
            </details>
          </>;
        })()}
      </section>}
      {activeSource.url && <section className="watch-user-feedback" data-user-watch-feedback aria-labelledby="watch-user-feedback-title">
        <div className="watch-evidence-heading"><div><p className="eyebrow">{t('watchEvidence.userReported')}</p><h2 id="watch-user-feedback-title">{t('watchEvidence.feedbackTitle')}</h2></div></div>
        <p className="watch-evidence-intro">{t('watchEvidence.feedbackIntro')}</p>
        <form className="watch-feedback-form" onSubmit={saveWatchFeedback}>
          <label>{t('watchEvidence.videoStartQuestion')}<select required value={playbackStarted} onChange={(event) => setPlaybackStarted(event.target.value)}><option value="" disabled>{t('watchEvidence.choose')}</option><option value="YES">{t('watchEvidence.yes')}</option><option value="NO">{t('watchEvidence.no')}</option><option value="UNSURE">{t('watchEvidence.unsure')}</option></select></label>
          <label>{t('watchEvidence.loginQuestion')}<select required value={loginRequired} onChange={(event) => setLoginRequired(event.target.value)}><option value="" disabled>{t('watchEvidence.choose')}</option><option value="YES">{t('watchEvidence.yes')}</option><option value="NO">{t('watchEvidence.no')}</option><option value="UNKNOWN">{t('watchEvidence.unknown')}</option></select></label>
          <label>{t('watchEvidence.regionQuestion')}<select required value={territoryRestricted} onChange={(event) => setTerritoryRestricted(event.target.value)}><option value="" disabled>{t('watchEvidence.choose')}</option><option value="YES">{t('watchEvidence.yes')}</option><option value="NO">{t('watchEvidence.no')}</option><option value="UNKNOWN">{t('watchEvidence.unknown')}</option></select></label>
          <button className="button button-outline" type="submit">{t('watchEvidence.saveReport')}</button>
          <button className="button button-outline" type="button" disabled={watchFeedbackReports.length === 0} onClick={exportWatchFeedback}>{t('watchEvidence.exportReports')}</button>
        </form>
        {watchFeedbackSaved && <p className="watch-feedback-notice" role="status">{t('watchEvidence.savedReport')}</p>}
        {watchFeedbackError && <p className="watch-feedback-notice is-error" role="alert">{t('watchEvidence.feedbackError')}</p>}
        {watchFeedbackReports.length > 0 && <details className="watch-feedback-saved"><summary>{t('watchEvidence.savedReports', { count: watchFeedbackReports.length })}</summary><ul>
          {watchFeedbackReports.map((report) => <li key={report.report_id} data-evidence-class="USER_REPORTED"><strong>USER_REPORTED</strong> · {new Date(report.tested_at).toLocaleString(locale === 'zh-CN' ? 'zh-CN' : 'en')}<br />{t('watchEvidence.videoStart')}: {t(`watchEvidence.value.${report.playback_started}` as MessageKey)} · {t('watchEvidence.loginQuestion')}: {t(`watchEvidence.value.${report.login_required}` as MessageKey)} · {t('watchEvidence.regionQuestion')}: {t(`watchEvidence.value.${report.territory_restricted}` as MessageKey)}<br /><code>{report.source_url}</code></li>)}
        </ul></details>}
      </section>}
      {sourceMatch && <div className="fan-linked-watch-match" data-linked-match-id={sourceMatch.match_id}>
        <h3>{matchTitleLabel(locale, catalog, sourceMatch)}</h3>
        <p>{matchEventLabel(locale, sourceMatch)} · {matchRoundLabel(locale, sourceMatch)} · {sourceMatch.match_type}</p>
        {sourceMatch.recorded_result && sourceMatch.result_status === 'OFFICIAL_EVENT_RESULT_CROSSCHECKED' && <p className="fan-recorded-result"><span>{t('fan.recordedResult')}</span><strong>{sourceMatch.recorded_result.player_a_games}–{sourceMatch.recorded_result.player_b_games}</strong></p>}
        <div className="fan-watch-player-links">{sourceMatch.participants.filter((participant) => participant.athlete_id && catalog?.stars.some((star) => star.athlete_id === participant.athlete_id)).map((participant) => {
          const star = catalog?.stars.find((item) => item.athlete_id === participant.athlete_id);
          return star && onOpenStar ? <button type="button" className="button button-outline" key={star.athlete_id} onClick={() => onOpenStar(star.athlete_id)}>{t('fan.meetPlayerName', { player: localName(locale, star) })} →</button> : null;
        })}</div>
        <small>{t(activeSource.match_link_status === 'HUMAN_VERIFIED' ? 'fan.matchLinkScope' : activeSource.match_link_status === 'OFFICIAL_TITLE_ASSOCIATED_VISUAL_NOT_TESTED' ? 'fan.matchLinkTitleOnly' : 'fan.sourceUnlinked')}</small>
        {sourceMatch.reference_url && <p><a className="button button-outline" href={sourceMatch.reference_url} target="_blank" rel="noopener noreferrer">{t('fan.openReference')} ↗</a></p>}
      </div>}
      {relatedOfficialHighlights.length > 0 && <section className="fan-watch-related" aria-label={t('gm.moreOfficial')}><div className="fan-section-heading"><h2>{t('gm.moreOfficial')}</h2></div><div className="fan-highlights-shelf">{relatedOfficialHighlights.map(sourceCard)}</div></section>}
      <details className="fan-source-evidence"><summary>{t('fan.sourceDetails')}</summary>
        <dl><div><dt>{t('fan.sourceIdentity')}</dt><dd><code>{activeSource.source_id}</code></dd></div>{sourceMatch && <div><dt>{t('fan.matchIdentity')}</dt><dd><code>{sourceMatch.match_id}</code></dd></div>}</dl>
        <p>{t('fan.publisher')}: {activeSource.publisher} · {sourceStatusLabel(activeSource.source_identity_status)}</p>
        <dl className="fan-rights-grid"><div><dt>{t('fan.externalViewing')}</dt><dd>{activeSource.external_viewing}</dd></div><div><dt>{t('fan.embedding')}</dt><dd>{activeSource.embedding}</dd></div><div><dt>{t('fan.thumbnail')}</dt><dd>{activeSource.thumbnail_display}</dd></div><div><dt>{t('fan.territory')}</dt><dd>{activeSource.territory}</dd></div></dl>
        <dl className="fan-route-statuses">{routeDecisions.map((route) => <div key={route.mode} data-route-mode={route.mode} data-route-state={route.decision?.state ?? 'BLOCKED'}><dt>{t(routeLabels[route.mode])}</dt><dd>{t(reasonLabels[route.decision?.reason ?? 'UNKNOWN'] ?? 'fan.route.unavailable')} · {route.decision?.playbackEvidence ?? 'NOT_TESTED'}</dd></div>)}</dl>
      </details>
    </>} />;
  }

  const titleKey: MessageKey = mode === 'cinema' ? 'fan.cinemaTitle' : mode === 'stars' ? 'fan.starsTitle' : mode === 'clips' ? 'fan.clipsTitle' : mode === 'highlights' ? 'fan.highlightsTitle' : mode === 'rivalries' ? 'rivalry.title' : 'fan.watchTitle';
  const descriptionKey: MessageKey = mode === 'cinema' ? 'fan.cinemaDescription' : mode === 'stars' ? 'fan.starsDescription' : mode === 'clips' ? 'fan.clipsDescription' : mode === 'highlights' ? 'fan.highlightsPageDescription' : mode === 'rivalries' ? 'rivalry.description' : 'fan.watchDescription';
  const emptyKey: MessageKey = mode === 'cinema' ? 'fan.emptyMatches' : mode === 'stars' ? 'fan.emptyStars' : mode === 'clips' ? 'fan.emptyClips' : mode === 'highlights' ? 'fan.emptyHighlights' : mode === 'rivalries' ? 'rivalry.empty' : 'fan.emptyWatch';
  const showCinemaHome = mode === 'cinema' && !selectedMatch && !selectedStar && !normalizedQuery;

  function starCard(star: FanStar, compact = false) {
    const displayName = localName(locale, star);
    return <div className={`fan-star-card-wrap${compact ? ' compact' : ''}`} key={star.athlete_id}>
      <button type="button" className={`fan-star-tile${compact ? ' compact' : ''}`} data-athlete-id={star.athlete_id} onClick={() => onOpenStar?.(star.athlete_id)}>
        <OriginalFanArtwork locale={locale} kind="star" identity={star.athlete_id} title={displayName} subtitle={star.association || 'PTTI · PLAYER'} />
        <span className="fan-star-tile-copy"><strong>{displayName}</strong><small>{locale === 'en' ? star.name_zh || '' : star.name_en || ''}</small>
          {star.association && <em>{star.association}</em>}
          {star.linked_matches.length > 0 && <small>{t('fan.profileMatchCount', { count: star.linked_matches.length })}</small>}
        </span>
      </button>
      {onToggleFollowedAthlete && <button type="button" className="fan-follow-control" aria-pressed={followedAthleteIds.includes(star.athlete_id)} onClick={() => onToggleFollowedAthlete(star.athlete_id)}>{t(followedAthleteIds.includes(star.athlete_id) ? 'fan.following' : 'fan.follow')}</button>}
    </div>;
  }

  return <section className={`fan-library fan-mode-${mode}`} data-fan-mode={mode} data-inspiration-version={inspiration?.contract_version} data-inspiration-sha={inspiration ? FAN_INSPIRATION_SHA : undefined} aria-label={t(titleKey)}>
    {mode === 'cinema' && !selectedMatch && !selectedStar && <>
      <div className="fan-cinema-discovery"><label className="fan-search fan-home-search"><span>{t('fan.search')}</span><span className="fan-search-control"><span aria-hidden="true">⌕</span><input data-fan-search value={query} onChange={(event) => setQuery(event.target.value)} type="search" placeholder={t('fan.searchPlaceholder')} /></span></label>{onGoCorner && <button type="button" className="button button-outline lobby-collection-entry" data-lobby-collector onClick={onGoCorner}>{t('lobby.collection')} <span>{savedMatchIds.length} →</span></button>}</div>
      {!normalizedQuery && !loading && !error && <section className="fan-cinema-hero grand-lobby" aria-labelledby="fan-cinema-title" data-fan-welcome data-hero-match-id={featuredMatch?.match_id ?? ''}>
        <div className="fan-cinema-copy">
          <p className="eyebrow">PTTI · GRAND LOBBY</p>
          <span className="fan-feature-label">{t(featuredMatch ? 'fan.featuredMatch' : 'fan.discoverMatches')}</span>
          <h1 id="fan-cinema-title" aria-live="polite">{featuredMatch ? matchTitleLabel(locale, catalog, featuredMatch).split(/\s+vs\s+/i).map((name, index) => <span className="fan-hero-player" key={index}>{index > 0 && <em>VS</em>}{name}</span>) : t('fan.noFeaturedTitle')}</h1>
          {featuredMatch && <p className="fan-feature-event">{matchEventLabel(locale, featuredMatch)} <span>·</span> {matchRoundLabel(locale, featuredMatch)}</p>}
          <p className="fan-hero-description lobby-manifesto">{t('lobby.manifesto')}</p>
          <div className="fan-hero-actions">
            {featuredSource && featuredRouteEligible && onOpenWatch
              ? <button type="button" className="button button-primary" data-featured-watch onClick={() => onOpenWatch(featuredSource.source_id, { matchId: featuredMatch!.match_id, starId: null })}>{t('fan.openWatch')} <span aria-hidden="true">↗</span></button>
              : featuredMatch
                ? <button type="button" className="button button-primary" onClick={() => onOpenMatch(featuredMatch.match_id)}>{t('fan.openMatch')}</button>
                : <button type="button" className="button button-primary" onClick={onChooseVideo}>{t('fan.entryLocalAction')}</button>}
          {(featuredStarId && onOpenStar) || onGoStars ? <button type="button" className="button button-outline" onClick={() => featuredStarId && onOpenStar ? onOpenStar(featuredStarId) : onGoStars?.()}>{t('fan.exploreStars')}</button> : null}
            {featuredMatch && onToggleSavedMatch && <><button type="button" className="button button-quiet" aria-pressed={savedMatchIds.includes(featuredMatch.match_id)} onClick={() => onToggleSavedMatch(featuredMatch.match_id)}>{t(savedMatchIds.includes(featuredMatch.match_id) ? 'fan.saved' : 'fan.save')}</button><span className="fan-save-scope">{t('fan.localOnly')}</span></>}
          </div>
          {featuredSource && <p className="fan-hero-source-state"><span>{featuredSource.platform}</span><span>{t('fan.externalSource')}</span><span>{t('fan.playbackNotTested')}</span></p>}
          {featuredMatch && !featuredRouteEligible && <p className="fan-hero-source-state">{t('lobby.noSource')}</p>}
          {heroMatches.length > 1 && <div className="fan-hero-carousel" role="group" aria-label={t('fan.featuredMatches')}>
            <button type="button" className="button button-quiet" aria-label={t('fan.previousFeatured')} onClick={() => setHeroIndex((index) => (index + heroMatches.length - 1) % heroMatches.length)}>‹</button>
            <span>{(heroIndex % heroMatches.length) + 1} / {heroMatches.length}</span>
            <button type="button" className="button button-quiet" aria-label={t('fan.nextFeatured')} onClick={() => setHeroIndex((index) => (index + 1) % heroMatches.length)}>›</button>
          </div>}

        </div>
        <div className="grand-lobby-stage">
          <OriginalFanArtwork locale={locale} kind="match" identity={featuredMatch?.match_id} decorative priority />
          <div className="grand-lobby-stage-caption"><span>{t('lobby.originalStage')}</span>{featuredMatch && <button type="button" className="lobby-detail-link" data-lobby-detail-id={featuredMatch.match_id} onClick={() => onOpenMatch(featuredMatch.match_id)}>{t('fan.openMatch')} →</button>}</div>
        </div>
      </section>}
      {!normalizedQuery && !loading && !error && heroMatches.length > 0 && <section className="lobby-programme" aria-labelledby="lobby-programme-title">
        <div className="lobby-programme-heading"><h2 id="lobby-programme-title">{t('lobby.programme')}</h2><p>{t('lobby.curatedNotice')}</p></div>
        <div className="lobby-programme-track" role="group" aria-label={t('fan.featuredMatches')}>{heroMatches.map((match, index) => <button type="button" className="lobby-programme-item" key={match.match_id} data-lobby-match-id={match.match_id} aria-label={t('lobby.selectMatch', { match: matchTitleLabel(locale, catalog, match) })} aria-pressed={index === heroIndex % heroMatches.length} onClick={() => setHeroIndex(index)}>
          <span className="lobby-programme-number" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span><span><strong>{matchTitleLabel(locale, catalog, match)}</strong><small>{matchEventLabel(locale, match)} · {matchRoundLabel(locale, match)}</small></span><span className="lobby-programme-focus">{t('lobby.focus')}</span>
        </button>)}</div>
      </section>}
      {normalizedQuery && <header className="fan-search-heading"><p className="eyebrow">PTTI · SEARCH</p><h1 id="fan-cinema-title">{t('fan.searchResultsTitle')}</h1></header>}
    </>}

    {mode !== 'cinema' && mode !== 'watch' && !(mode === 'stars' && (selectedStar || selectedMatch)) && <header className="fan-page-header"><div><p className="eyebrow">PTTI · {mode.toUpperCase()}</p><h1 id="fan-library-title">{t(titleKey)}</h1><p>{t(descriptionKey)}</p></div>
      {(mode === 'stars' || mode === 'highlights' || mode === 'clips') && <label className="fan-search"><span>{t('fan.search')}</span><span className="fan-search-control"><span aria-hidden="true">⌕</span><input data-fan-search value={query} onChange={(event) => setQuery(event.target.value)} type="search" placeholder={t('fan.searchPlaceholder')} /></span></label>}
    </header>}

    {(mode === 'cinema' || mode === 'stars') && selectedMatchView()}
    {mode === 'stars' && !selectedMatch && selectedStarView()}
    {mode === 'watch' && selectedSourceView()}
    {mode === 'rivalries' && selectedRivalry && selectedRivalryView()}
    {!loading && !error && catalog && <p className="fan-inventory sr-only" data-fan-counts>{t('fan.inventory', { matches: catalog.matches.length, stars: catalog.stars.length, clips: mode === 'clips' ? clipEligibleSources.length : catalog.sources.length })}</p>}
    {loading && <div className="fan-loading fan-skeleton" role="status" aria-busy="true"><span className="sr-only">{t('fan.loading')}</span><span /><span /><span /></div>}
    {error && <div className="state-card state-error fan-load-error" role="alert"><strong>{t('fan.loadError')}</strong><p>{t('fan.loadErrorDetail')}</p><button type="button" className="button" onClick={retry}>{t('load.retry')}</button></div>}

    {!loading && !error && catalog && mode === 'cinema' && !selectedMatch && !selectedStar && <>
      {showCinemaHome && <>
        <section className="fan-home-matches" aria-labelledby="fan-hot-matches-heading" data-featured-matches>
          <div className="fan-section-heading"><div><p className="eyebrow">{t('fan.hotMatchesKicker')}</p><h2 id="fan-hot-matches-heading">{t('fan.featuredMatches')}</h2></div><span>{catalog.matches.length}</span></div>
          {catalog.matches.length ? <div className="fan-content-grid fan-hot-match-grid">{catalog.matches.map(matchCard)}</div> : <div className="fan-empty-inline" role="status">{t('fan.emptyMatches')}</div>}
        </section>
        <section className="fan-home-stars" aria-labelledby="fan-stars-heading">
          <div className="fan-section-heading"><div><p className="eyebrow">{t('fan.starsKicker')}</p><h2 id="fan-stars-heading">{t('fan.meetTheStars')}</h2></div>{catalog.stars[0] && <button type="button" className="fan-section-link" onClick={() => onGoStars ? onGoStars() : onOpenStar?.(catalog.stars[0].athlete_id)}>{t('fan.exploreStars')} ↗</button>}</div>
          <div className="fan-star-shelf">{catalog.stars.map((star) => starCard(star, true))}</div>
        </section>
        {officialHighlights.length > 0 && <section className="fan-home-highlights" aria-labelledby="fan-highlights-heading" data-fan-highlights>
          <div className="fan-section-heading"><div><p className="eyebrow">PTTI · {t('fan.eventHighlights')}</p><h2 id="fan-highlights-heading">{t('fan.highlightsShelfTitle')}</h2><p>{t('fan.highlightsShelfDescription')}</p></div><div className="fan-highlights-actions"><span>{officialHighlights.length}</span>{onGoHighlights && <button type="button" className="fan-section-link" onClick={onGoHighlights}>{t('fan.viewAllHighlights')} ↗</button>}</div></div>
          <div className="fan-highlights-shelf">{officialHighlights.map(sourceCard)}</div>
        </section>}
        <section className="fan-home-rivalries" aria-labelledby="fan-rivalries-home-heading" data-fan-rivalries>
          <div className="fan-section-heading"><div><p className="eyebrow">HEAD TO HEAD</p><h2 id="fan-rivalries-home-heading">{t('fan.rivalriesHomeTitle')}</h2></div><span>{rivalries.length}</span></div>
          {rivalries.length ? <div className="fan-rivalry-grid">{rivalries.map((rivalry) => <button type="button" key={rivalry.rivalry_id} className="fan-rivalry-card" data-rivalry-id={rivalry.rivalry_id} onClick={() => onOpenRivalry?.(rivalry.rivalry_id)}>
            <strong>{rivalry.athlete_ids.map((id) => { const star = catalog.stars.find((item) => item.athlete_id === id); return star ? localName(locale, star) : id; }).join(' vs ')}</strong>
            <span>{rivalry.match_ids.length} · {t('fan.relatedRivalries')}</span><small>{t('rivalry.scope')}</small>
          </button>)}</div> : <p className="fan-empty-inline" role="status">{t('rivalry.empty')}</p>}
          {rivalries.length > 0 && <button className="fan-section-link" type="button" onClick={() => onOpenRivalry?.(rivalries[0].rivalry_id)}>{t('rivalry.view')} ↗</button>}
        </section>
        <section className="fan-quick-hits" aria-labelledby="fan-quick-hits-heading">
          <div><p className="eyebrow">QUICK HITS</p><h2 id="fan-quick-hits-heading">{t('gm.quickTitle')}</h2><p>{t('fan.quickHitsEmpty')}</p></div>
          <button type="button" className="button button-outline" onClick={onGoClips}>{t('fan.entryClipsAction')} →</button>
        </section>
        {onOpenArena && <section className="fan-arena-entry" data-arena-entry aria-labelledby="fan-arena-entry-title">
          <div className="fan-arena-entry-score" aria-hidden="true"><span>9</span><i>:</i><span>9</span></div>
          <div className="fan-arena-entry-copy"><p className="eyebrow">{t('arena.entryKicker')}</p><h2 id="fan-arena-entry-title">{t('arena.entryTitle')}</h2><p>{t('arena.entryDescription')}</p></div>
          <button type="button" className="button button-outline" onClick={onOpenArena}>{t('arena.entryAction')} <span aria-hidden="true">↗</span></button>
        </section>}
        {onGoCorner && <section className="fan-corner-invite" aria-labelledby="fan-saved-heading"><div><p className="eyebrow">COLLECTOR'S LOUNGE</p><h2 id="fan-saved-heading">{t('gm.cornerTitle')}</h2><p>{t('gm.cornerDescription')}</p></div><div className="fan-corner-numbers"><span><b>{savedMatchIds.length}</b>{t('gm.savedMatches')}</span><span><b>{followedAthleteIds.length}</b>{t('gm.followingStars')}</span></div><button className="button button-primary" type="button" onClick={onGoCorner}>{t('lobby.collection')} →</button></section>}
        <section className="fan-ecosystem-explore" aria-labelledby="fan-explore-more-heading">
          <div className="fan-section-heading"><div><p className="eyebrow">PTTI · EXPLORE</p><h2 id="fan-explore-more-heading">{t('fan.exploreMore')}</h2></div></div>
        <section className="fan-home-tools" aria-label={t('fan.quickActions')}>
          <button type="button" className="fan-tool-card" onClick={onChooseVideo}><span className="fan-tool-icon" aria-hidden="true">▶</span><span><strong>{t('fan.entryLocalTitle')}</strong><small>{t('fan.entryLocalDescription')}</small></span><b aria-hidden="true">↗</b></button>
          <button type="button" className="fan-tool-card" onClick={onGoInsight}><span className="fan-tool-icon fan-tool-icon-red" aria-hidden="true">◎</span><span><strong>{t('fan.entryDemoTitle')}</strong><small>{t('fan.entryDemoDescription')}</small></span><b aria-hidden="true">↗</b></button>
        </section>
          <div className="fan-ecosystem-grid">
            {onOpenTrain && <button type="button" className="fan-ecosystem-card" onClick={onOpenTrain}><strong>{t('nav.train')}</strong><span>{t('fan.exploreTrain')}</span><b aria-hidden="true">↗</b></button>}
            {onOpenGear && <button type="button" className="fan-ecosystem-card" onClick={onOpenGear}><strong>{t('nav.gear')}</strong><span>{t('fan.exploreGear')}</span><b aria-hidden="true">↗</b></button>}
            {onOpenCommunity && <button type="button" className="fan-ecosystem-card" onClick={onOpenCommunity}><strong>{t('nav.community')}</strong><span>{t('fan.exploreCommunity')}</span><b aria-hidden="true">↗</b></button>}
            {onGoCorner && <button type="button" className="fan-ecosystem-card" onClick={onGoCorner}><strong>{t('nav.corner')}</strong><span>{t('fan.exploreCorner')}</span><b aria-hidden="true">↗</b></button>}
          </div>
        </section>

      </>}
      {normalizedQuery && <section className="fan-search-results" aria-live="polite">
        {stars.length > 0 && <div className="fan-search-star-results"><h2>{t('fan.searchStarResults')}</h2><div className="fan-star-shelf">{stars.map((star) => starCard(star, true))}</div></div>}
        {matches.length > 0 && <div className="fan-search-match-results"><h2>{t('fan.searchMatchResults')}</h2><div className="fan-content-grid">{matches.map(matchCard)}</div></div>}
        {matchingHighlights.length > 0 && <div className="fan-search-highlight-results"><h2>{t('fan.highlightsShelfTitle')}</h2><div className="fan-content-grid">{matchingHighlights.map(sourceCard)}</div></div>}
        {stars.length === 0 && matches.length === 0 && matchingHighlights.length === 0 && <div className="fan-empty fan-search-empty" role="status"><strong>{t('fan.noSearchResults')}</strong><p>{t('fan.noSearchResultsHint')}</p><button type="button" className="button button-outline" onClick={() => setQuery('')}>{t('fan.clearSearch')}</button></div>}
      </section>}
    </>}

    {!loading && !error && catalog && mode === 'stars' && !selectedMatch && !selectedStar && <div className="fan-star-grid">{stars.map((star) => starCard(star))}{stars.length === 0 && <div className="fan-empty" role="status"><strong>{t(emptyKey)}</strong><p>{t('fan.emptyBoundary')}</p><button type="button" className="button button-outline" onClick={onGoCinema}>{t('fan.goCinema')}</button></div>}</div>}

    {!loading && !error && catalog && mode === 'highlights' && <section className="fan-highlights-page" aria-labelledby="fan-library-title" data-official-highlights-page>
      <p className="fan-highlights-count">{t('fan.officialSource')} · {visibleHighlights.length}</p>
      {visibleHighlights.length > 0 ? <div className="fan-content-grid">{visibleHighlights.map(sourceCard)}</div> : <div className="fan-empty" role="status"><strong>{t(emptyKey)}</strong><p>{t('fan.emptyHighlightsDetail')}</p><button type="button" className="button button-outline" onClick={onGoCinema}>{t('fan.goCinema')}</button></div>}
    </section>}

    {!loading && !error && catalog && mode === 'rivalries' && !selectedRivalry && <section className="fan-rivalry-list" data-rivalry-list>
      {rivalries.length ? <div className="fan-rivalry-grid">{rivalries.map((rivalry) => <button type="button" className="fan-rivalry-card" key={rivalry.rivalry_id} data-rivalry-id={rivalry.rivalry_id} onClick={() => { setSelectedRivalryId(rivalry.rivalry_id); onOpenRivalry?.(rivalry.rivalry_id); }}>
        <strong>{rivalry.athlete_ids.map((id) => { const star = catalog.stars.find((item) => item.athlete_id === id); return star ? localName(locale, star) : id; }).join(' vs ')}</strong><span>{rivalry.match_ids.length} · {t('fan.relatedRivalries')}</span><small>{t('rivalry.scope')}</small>
      </button>)}</div> : <div className="fan-empty" role="status"><strong>{t(emptyKey)}</strong><button type="button" className="button button-outline" onClick={onGoCinema}>{t('fan.goCinema')}</button></div>}
    </section>}

    {!loading && !error && catalog && mode === 'clips' && <>
      <section className="fan-discovery" data-fan-discovery aria-labelledby="fan-discovery-title">
        <div className="fan-section-heading"><div><p className="eyebrow">DISCOVER · ORIGINAL SOURCES</p><h2 id="fan-discovery-title">{t('discovery.title')}</h2><p>{t('discovery.scope')}</p></div><span>{officialHighlights.length} · {t('fan.eventHighlights')}</span></div>
        <div className="fan-discovery-filters">
          <label>{t('discovery.platform')}<select value={discoveryPlatform} onChange={(event) => setDiscoveryPlatform(event.target.value)}><option value="all">{t('discovery.all')}</option>{[...new Set([...clipEligibleSources, ...officialHighlights].map((source) => source.platform))].map((platform) => <option key={platform} value={platform}>{platform}</option>)}</select></label>
          <label>{t('fan.filterPlayer')}<select value={clipAthleteId} onChange={(event) => setClipAthleteId(event.target.value)}><option value="all">{t('fan.filterAllPlayers')}</option>{catalog.stars.map((star) => <option key={star.athlete_id} value={star.athlete_id}>{localName(locale, star)}</option>)}</select></label>
          <label>{t('discovery.event')}<select value={discoveryEvent} onChange={(event) => setDiscoveryEvent(event.target.value)}><option value="all">{t('discovery.all')}</option>{[...new Set([...clipEligibleSources, ...officialHighlights].map((source) => source.event))].map((event) => <option key={event} value={event}>{event}</option>)}</select></label>
          <label>{t('discovery.training')}<select value={discoveryTraining} onChange={(event) => setDiscoveryTraining(event.target.value)}>{['all', 'serve', 'receive', 'technique', 'mindset', 'UNKNOWN'].map((value) => <option key={value} value={value}>{t(`discovery.training.${value}` as MessageKey)}</option>)}</select></label>
        </div>
        <div className="fan-discovery-result"><span role="status">{t('discovery.results', { count: discoveryRows.length })}</span><button type="button" className="text-button" onClick={clearClipFilters}>{t('fan.clearClipFilters')}</button></div>
        <p className="fan-media-scope">{t('discovery.noInference')}</p>
        {discoveryRows.length === 0 && <p className="fan-empty-inline" role="status">{t('discovery.noResults')}</p>}
        <div className="fan-content-grid">{discoveryRows.filter((source) => source.content_type_claim === 'HIGHLIGHTS').map(sourceCard)}</div>
      </section>
      {clipEligibleSources.length > 0 ? <>
        <div className="fan-clip-filters" role="group" aria-label={t('fan.clipFilters')}>
          <label><span>{t('fan.filterPlayer')}</span><select value={clipAthleteId} onChange={(event) => setClipAthleteId(event.target.value)}><option value="all">{t('fan.filterAllPlayers')}</option>{clipAthletes.map((star) => <option key={star.athlete_id} value={star.athlete_id}>{localName(locale, star)}</option>)}</select></label>
          <label><span>{t('fan.filterContentType')}</span><select value={clipType} onChange={(event) => setClipType(event.target.value)}><option value="all">{t('fan.filterAllTypes')}</option>{clipTypes.map((type) => <option key={type} value={type}>{t(`fan.clipType.${type}` as MessageKey)}</option>)}</select></label>
          {clipFiltersActive && <button type="button" className="button button-outline" onClick={clearClipFilters}>{t('fan.clearClipFilters')}</button>}
        </div>
        <div className="fan-content-grid">{clipSources.map(sourceCard)}</div>
        {clipSources.length === 0 && <div className="fan-empty-inline" role="status"><p>{t('fan.noClipsForFilters')}</p>{clipFiltersActive && <button type="button" className="button button-outline" onClick={clearClipFilters}>{t('fan.clearClipFilters')}</button>}</div>}
      </> : <div className="fan-clips-empty" role="status" data-clips-empty>
        <OriginalFanArtwork locale={locale} kind="clip" />
        <div><p className="eyebrow">{t('fan.quickHitsKicker')}</p><h2>{t(emptyKey)}</h2><p>{t('fan.emptyClipsDetail')}</p>
          <div className="fan-empty-actions">
            {admittedFullMatch && <button type="button" className="button button-outline" data-fan-open-match-id={admittedFullMatch.match_id} onClick={() => onOpenMatch(admittedFullMatch.match_id)}>{t('fan.openAvailableMatch')} →</button>}
            {featuredSource && featuredRouteEligible && onOpenWatch
            ? <button type="button" className="button button-primary" onClick={() => onOpenWatch(featuredSource.source_id, { matchId: featuredMatch!.match_id, starId: null })}>{t('fan.openWatch')} ↗</button>
            : <button type="button" className="button button-primary" onClick={onGoCinema}>{t('fan.goCinema')}</button>}
            <button type="button" className="button button-outline" onClick={onGoInsight}>{t('fan.tryDemo')}</button></div>
        </div>
      </div>}
    </>}


  </section>;
}
