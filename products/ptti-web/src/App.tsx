import { useEffect, useMemo, useState } from 'react';
import { pulseItems, starProfiles } from './data/content';
import { appendFeedback, readFeedback } from './feedback-storage.mjs';
import { LOCALE_STORAGE_KEY, matchNote, message, pulseCopy, readSavedLocale, starCopy } from './i18n';
import type { Locale, MessageKey } from './i18n';
import { filterMatchRecords, getMatchDestination, getWatchFilterCounts, hasVerifiedVisualPlayback } from './watch-filter.mjs';
import type { WatchFilter } from './watch-filter.mjs';
import type { Discipline, FeedbackEntry, FeedbackIssue, MatchRecord, MatchRouteType, PulseTopic } from './types';

type Page = 'cinema' | 'pulse' | 'stars' | 'feedback';
type PulseFilter = 'all' | 'highlight' | 'video' | 'player' | 'training' | 'international' | 'event';
const disciplines = [
  ['all', 'discipline.all'],
  ['MS', 'discipline.MS'],
  ['WS', 'discipline.WS'],
  ['MD', 'discipline.MD'],
  ['WD', 'discipline.WD'],
  ['XD', 'discipline.XD'],
] as const;
const pulseFilters: PulseFilter[] = ['all', 'highlight', 'video', 'player', 'training', 'international', 'event'];
const navMessages: Record<Exclude<Page, 'feedback'>, MessageKey> = {
  cinema: 'nav.cinema',
  pulse: 'nav.pulse',
  stars: 'nav.stars',
};
const pulseFilterMessages: Record<PulseFilter, MessageKey> = {
  all: 'pulse.topic.all',
  highlight: 'pulse.topic.highlight',
  video: 'pulse.topic.video',
  player: 'pulse.topic.player',
  training: 'pulse.topic.training',
  international: 'pulse.topic.international',
  event: 'pulse.topic.event',
};
const pulseTopicMessages: Record<PulseTopic, MessageKey> = {
  highlight: 'pulse.topic.highlight',
  player: 'pulse.topic.player',
  event: 'pulse.topic.event',
};
const disciplineMessages: Record<Discipline, MessageKey> = {
  MS: 'discipline.MS',
  WS: 'discipline.WS',
  MD: 'discipline.MD',
  WD: 'discipline.WD',
  XD: 'discipline.XD',
};
const watchFilterMessages: Record<WatchFilter, MessageKey> = {
  all: 'filter.watch.all',
  'verified-video': 'filter.watch.verified',
  'event-page': 'filter.watch.event',
  'source-only': 'filter.watch.source',
  unverified: 'filter.watch.unverified',
};

function ExternalLink({ href, children, className = '' }: { href: string; children: React.ReactNode; className?: string }) {
  return <a className={className} href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
}

function eventCategoryLabel(locale: Locale, value: string): string {
  const key: Record<string, MessageKey> = {
    'WTT Finals': 'event.category.finals',
    'WTT Cup Finals': 'event.category.cupFinals',
    'WTT Champions': 'event.category.champions',
  };
  return key[value] ? message(locale, key[value]) : value;
}

function roundLabel(locale: Locale, value: string): string {
  const key: Record<string, MessageKey> = {
    Final: 'event.round.final',
    Semifinal: 'event.round.semifinal',
    Quarterfinal: 'event.round.quarterfinal',
  };
  return key[value] ? message(locale, key[value]) : value;
}

function platformLabel(locale: Locale, value: string): string {
  if (locale === 'zh-CN' && value === 'WTT result article (evidence only)') return 'WTT 赛事报道（仅作来源依据）';
  return value;
}

function routeTypeLabel(locale: Locale, routeType: MatchRouteType): string {
  const key: Record<MatchRouteType, MessageKey> = {
    'event-page': 'source.route.event',
    'video-page': 'source.route.video',
    'source-only': 'source.route.only',
  };
  return message(locale, key[routeType]);
}

function localizedResult(locale: Locale, value: string | undefined): string | undefined {
  if (!value || locale === 'en') return value;
  const result = value.match(/^(.+?) won ([\d–-]+)$/);
  if (!result) return value;
  return result[1] + ' 以 ' + result[2].replace(/[–-]/, ' 比 ') + ' 获胜';
}

function App() {
  const [locale, setLocale] = useState<Locale>(() => readSavedLocale());
  const [page, setPage] = useState<Page>('cinema');
  const [matches, setMatches] = useState<MatchRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [search, setSearch] = useState('');
  const [discipline, setDiscipline] = useState('all');
  const [event, setEvent] = useState('all');
  const [source, setSource] = useState('all');
  const [watchFilter, setWatchFilter] = useState<WatchFilter>('all');
  const [pulseFilter, setPulseFilter] = useState<PulseFilter>('all');
  const [feedbackCount, setFeedbackCount] = useState(() => readFeedback(localStorage).length);
  const [feedbackSaved, setFeedbackSaved] = useState(false);
  const [feedbackSaveError, setFeedbackSaveError] = useState(false);

  const t = (key: MessageKey) => message(locale, key);

  async function loadMatches() {
    setLoading(true);
    setLoadError(false);
    try {
      const response = await fetch('/data/cinema.json', { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('Match list unavailable');
      const data = (await response.json()) as MatchRecord[];
      setMatches(data);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadMatches(); }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = t('document.title');
    const description = document.querySelector('meta[name="description"]');
    description?.setAttribute('content', t('document.description'));
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    } catch {
      // The current view still updates if browser storage is disabled.
    }
  }, [locale]);

  const events = useMemo(() => [...new Set(matches.map((match) => match.eventCategory))].sort(), [matches]);
  const sources = useMemo(() => [...new Set(matches.map((match) => match.platform))].sort(), [matches]);
  const watchCounts = useMemo(() => getWatchFilterCounts(matches, {
    query: search,
    discipline,
    event,
    platform: source,
  }), [matches, search, discipline, event, source]);
  const verifiedVideoCount = watchCounts['verified-video'];
  const filteredMatches = useMemo(() => filterMatchRecords(matches, {
    query: search,
    discipline,
    event,
    platform: source,
    watchFilter,
  }), [matches, search, discipline, event, source, watchFilter]);

  const filteredPulse = useMemo(() => pulseItems.filter((item) => {
    if (pulseFilter === 'all') return true;
    if (pulseFilter === 'video') return false;
    return item.topic === pulseFilter;
  }), [pulseFilter]);

  function changePage(next: Page) {
    setPage(next);
    if (next === 'pulse') setPulseFilter('all');
    setFeedbackSaved(false);
    setFeedbackSaveError(false);
  }

  function resetFilters() {
    setSearch('');
    setDiscipline('all');
    setEvent('all');
    setSource('all');
    setWatchFilter('all');
  }

  function showVerifiedVideos() {
    setWatchFilter('verified-video');
    document.getElementById('match-heading')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function saveFeedback(entry: FeedbackEntry): boolean {
    try {
      const entries = appendFeedback(localStorage, entry);
      setFeedbackCount(entries.length);
      setFeedbackSaved(true);
      setFeedbackSaveError(false);
      return true;
    } catch {
      setFeedbackSaved(false);
      setFeedbackSaveError(true);
      return false;
    }
  }

  function downloadFeedback() {
    const contents = JSON.stringify(readFeedback(localStorage), null, 2);
    const blob = new Blob([contents], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'ptti-web-feedback.json';
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className={'app-shell ' + (locale === 'zh-CN' ? 'locale-zh' : 'locale-en')}>
      <header className="site-header">
        <button className="wordmark" onClick={() => changePage('cinema')} aria-label={t('aria.home')}>
          <span className="wordmark-icon">P</span>
          <span>PTTI<small>{t('brand.tagline')}</small></span>
        </button>
        <nav className="primary-nav" aria-label={t('aria.navigation')}>
          {(['cinema', 'pulse', 'stars'] as const).map((item) => (
            <button key={item} className={page === item ? 'nav-link active' : 'nav-link'} onClick={() => changePage(item)} aria-current={page === item ? 'page' : undefined}>
              {t(navMessages[item])}
            </button>
          ))}
        </nav>
        <div className="header-actions">
          <div className="locale-switch" role="group" aria-label={t('aria.language')}>
            {(['zh-CN', 'en'] as const).map((value) => (
              <button key={value} type="button" className={locale === value ? 'locale-option active' : 'locale-option'} aria-pressed={locale === value} onClick={() => setLocale(value)}>
                {t(value === 'zh-CN' ? 'language.chinese' : 'language.english')}
              </button>
            ))}
          </div>
          <button className="feedback-nav" onClick={() => changePage('feedback')}>{t('nav.feedback')} <span aria-hidden="true">↗</span></button>
        </div>
      </header>

      <main>
        {page === 'cinema' && <>
          <section className="hero" aria-labelledby="cinema-title">
            <div className="hero-copy">
              <p className="eyebrow">{t('cinema.kicker')}</p>
              <h1 id="cinema-title">{t('cinema.title.first')}<br /><em>{t('cinema.title.second')}</em></h1>
              <p className="hero-description">{t('cinema.description')}</p>
              <div className="hero-actions">
                <button className="button button-primary" onClick={() => document.getElementById('match-search')?.focus()}>{t('cinema.action')} <span aria-hidden="true">↓</span></button>
                <button className="button button-secondary" onClick={showVerifiedVideos}>{t('cinema.watchVerified')} <strong>{verifiedVideoCount}</strong></button>
              </div>
              <p className="hero-watch-note">{t('cinema.watchVerifiedHint')}</p>
            </div>
            <div className="hero-feature" aria-label={t('cinema.feature.label')}>
              <div className="court-lines" aria-hidden="true"><span /><span /><i /></div>
              <div className="feature-label">{t('cinema.feature.label')} <span>{t('cinema.feature.sample')}</span></div>
              <div className="feature-stat"><strong>{verifiedVideoCount.toString().padStart(2, '0')}</strong><span>{t('cinema.feature.verifiedCount')}</span></div>
              <div className="feature-foot"><span>{t('cinema.feature.official')}</span><span>{t('cinema.feature.playback')}</span></div>
            </div>
          </section>

          <section className="section-heading" aria-labelledby="match-heading">
            <div><p className="eyebrow">{t('cinema.section.kicker')}</p><h2 id="match-heading">{t('cinema.section.title')}</h2></div>
            <p className="section-note">{t('cinema.section.note')}</p>
          </section>

          <section className="filter-panel" aria-label={t('search.label')}>
            <label className="search-field"><span className="sr-only">{t('search.label')}</span><span aria-hidden="true">⌕</span><input id="match-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t('search.placeholder')} /></label>
            <label><span className="sr-only">{t('filter.discipline')}</span><select value={discipline} onChange={(e) => setDiscipline(e.target.value)}>{disciplines.map(([value, key]) => <option key={value} value={value}>{t(key)}</option>)}</select></label>
            <label><span className="sr-only">{t('filter.event')}</span><select value={event} onChange={(e) => setEvent(e.target.value)}><option value="all">{t('filter.event.all')}</option>{events.map((item) => <option key={item} value={item}>{eventCategoryLabel(locale, item)}</option>)}</select></label>
            <label><span className="sr-only">{t('filter.platform')}</span><select value={source} onChange={(e) => setSource(e.target.value)}><option value="all">{t('filter.platform.all')}</option>{sources.map((item) => <option key={item} value={item}>{platformLabel(locale, item)}</option>)}</select></label>
          </section>

          <div className="watch-filter-toolbar" role="group" aria-label={t('filter.watchStatus')}>
            <span className="watch-filter-label">{t('filter.watchStatus')}</span>
            {(Object.keys(watchFilterMessages) as WatchFilter[]).map((filter) => (
              <button key={filter} type="button" className={watchFilter === filter ? 'watch-filter-chip active' : 'watch-filter-chip'} aria-pressed={watchFilter === filter} onClick={() => setWatchFilter(filter)}>
                <span>{t(watchFilterMessages[filter])}</span><span className="filter-count">{watchCounts[filter]}</span>
              </button>
            ))}
          </div>

          <div className="results-meta" aria-live="polite">
            <span>{loading ? t('results.loading') : filteredMatches.length + ' ' + t(filteredMatches.length === 1 ? 'results.one' : 'results.many')}</span>
            <button className="text-button" onClick={resetFilters}>{t('filters.reset')}</button>
          </div>
          {loading && <div className="state-card" role="status"><span className="spinner" />{t('loading.matches')}</div>}
          {!loading && loadError && <div className="state-card state-error" role="alert"><strong>{t('load.errorTitle')}</strong><p>{t('load.error')}</p><button className="button" onClick={() => void loadMatches()}>{t('load.retry')}</button></div>}
          {!loading && !loadError && filteredMatches.length === 0 && <div className="state-card"><strong>{t('empty.title')}</strong><p>{t('empty.description')}</p><button className="button" onClick={resetFilters}>{t('empty.action')}</button></div>}
          {!loading && !loadError && filteredMatches.length > 0 && <div className="match-grid">{filteredMatches.map((match) => <MatchCard key={match.id} match={match} locale={locale} />)}</div>}
          <div className="notice-strip"><span className="notice-mark">i</span><p>{t('source.notice')}</p><ExternalLink href="https://www.worldtabletennis.com/">{t('source.browseWtt')} <span aria-hidden="true">↗</span></ExternalLink></div>
        </>}

        {page === 'pulse' && <section className="page-section">
          <PageIntro kicker={t('pulse.kicker')} title={t('pulse.title')} description={t('pulse.description')} />
          <div className="pulse-topics" role="group" aria-label={t('pulse.kicker')}>
            {pulseFilters.map((filter) => <button key={filter} type="button" className={pulseFilter === filter ? 'topic-chip active' : 'topic-chip'} aria-pressed={pulseFilter === filter} onClick={() => setPulseFilter(filter)}>{t(pulseFilterMessages[filter])}</button>)}
          </div>
          {filteredPulse.length > 0 ? <div className="pulse-grid">{filteredPulse.map((item) => {
            const localized = pulseCopy(locale, item.id);
            return <article className="pulse-card" key={item.id}>
              <div className={'pulse-art ' + item.format}><span className="pulse-art-mark">{item.format === 'video' ? '▶' : 'PT'}</span><span className="pulse-art-type">{t(pulseTopicMessages[item.topic])}</span><span className="pulse-art-rule" /></div>
              <div className="pulse-card-body"><div className="card-meta"><span>{item.platform}</span><span>{t(item.format === 'video' ? 'pulse.video' : 'pulse.article')}</span></div><h3>{localized.title}</h3><p>{localized.summary}</p><div className="publisher-line">{t('pulse.publisher')} <strong>{item.publisher}</strong></div><ExternalLink className="button button-outline" href={item.url}>{t(item.format === 'video' ? 'pulse.openVideo' : 'pulse.readArticle')} <span aria-hidden="true">↗</span></ExternalLink><ExternalLink className="evidence-link" href={item.evidenceUrl}>{t('pulse.evidence')}</ExternalLink><p className="tiny-status">{t('pulse.checked')} {item.verifiedAt} · {t('pulse.playback')}</p></div>
            </article>;
          })}</div> : <div className="state-card state-inline"><strong>{t('pulse.empty.title')}</strong><p>{t('pulse.empty.description')}</p></div>}
          <p className="pulse-live-note">{t('pulse.noLive')}</p>
        </section>}

        {page === 'stars' && <section className="page-section">
          <PageIntro kicker={t('stars.kicker')} title={t('stars.title')} description={t('stars.description')} />
          <div className="stars-list">{starProfiles.map((star) => {
            const relatedMatch = matches.find((match) => match.id === star.relatedMatchId);
            const localized = starCopy(locale, star.id);
            return <article className="star-card" key={star.id}>
              <div className="star-monogram" aria-hidden="true">{star.name.split(' ').map((part) => part[0]).join('')}</div>
              <div className="star-main"><div className="card-meta"><span>{t('stars.player')}</span><span>{star.countryCode}</span></div><h3>{star.name}</h3><p className="star-intro">{localized.intro}</p><p>{localized.publicFact}</p><div className="star-links"><ExternalLink className="button button-outline" href={star.sourceUrl}>{t('stars.openEvent')} <span aria-hidden="true">↗</span></ExternalLink>{relatedMatch?.sourceEvidence[0] && <ExternalLink className="text-link" href={relatedMatch.sourceEvidence[0]}>{t('stars.openMatch')}</ExternalLink>}{star.newsUrl && <ExternalLink className="text-link" href={star.newsUrl}>{t('stars.openStory')} ↗</ExternalLink>}</div><div className="social-row"><span>{t('stars.social')}</span>{star.socialUrl ? <><ExternalLink href={star.socialUrl}>{t('stars.openCandidate')} ↗</ExternalLink><small>{localized.socialStatus}</small></> : <small>{localized.socialStatus || t('stars.noSocial')}</small>}</div></div>
            </article>;
          })}</div>
        </section>}

        {page === 'feedback' && <FeedbackPage locale={locale} count={feedbackCount} saved={feedbackSaved} saveError={feedbackSaveError} onSave={saveFeedback} onDownload={downloadFeedback} />}
      </main>

      <footer className="site-footer"><span>{t('footer.version')}</span><span>{t('footer.links')}</span><button onClick={() => changePage('feedback')}>{t('footer.feedback')}</button></footer>
    </div>
  );
}

function MatchCard({ match, locale }: { match: MatchRecord; locale: Locale }) {
  const destination = getMatchDestination(match);
  const verifiedVisualPlayback = hasVerifiedVisualPlayback(match);
  const buttonKey: MessageKey = destination?.type === 'video-page'
    ? 'source.videoButton'
    : destination?.type === 'event-page' ? 'source.eventButton' : 'source.onlyButton';
  const playbackKey: MessageKey = verifiedVisualPlayback
    ? 'source.playback.verified'
    : match.playbackStatus === 'RESTRICTED' ? 'source.playback.restricted'
      : match.playbackStatus === 'PLAYBACK_FAIL' ? 'source.playback.failed'
        : 'source.playback.pending';
  const evidenceUrl = match.sourceEvidence[0];
  const region = match.regionRestriction.toLowerCase().startsWith('unknown')
    ? message(locale, 'source.regionUnknown')
    : match.regionRestriction;
  return <article className="match-card">
    <div className="match-art" aria-hidden="true"><div className="match-art-top"><span>PTTI</span><span>{match.eventYear}</span></div><div className="table-mark"><span /><i /><b /></div><div className="match-art-bottom"><span>{message(locale, disciplineMessages[match.discipline])}</span><span>{roundLabel(locale, match.round)}</span></div></div>
    <div className="match-card-body"><div className="card-meta"><span>{eventCategoryLabel(locale, match.eventCategory)}</span><span>{message(locale, disciplineMessages[match.discipline])} · {roundLabel(locale, match.round)}</span></div><h3>{match.players.map((player, index) => <span key={player}>{index > 0 && <span className="versus"> vs </span>}{player}</span>)}</h3><p className="event-name">{match.event}</p>{match.result && <p className="result-line">{localizedResult(locale, match.result)}</p>}
      <div className="match-status-row" aria-label={message(locale, 'source.statusLabel')}>
        <span className={'route-badge route-' + (destination?.type ?? 'unavailable')}>{routeTypeLabel(locale, match.routeType)}</span>
        <span className={'playback-badge playback-' + match.playbackStatus.toLowerCase() + (verifiedVisualPlayback ? ' visual-verified' : '')}>{message(locale, playbackKey)}</span>
      </div>
      <div className="source-detail"><span>{message(locale, 'source.platform')}</span><strong>{platformLabel(locale, match.platform)}</strong><span>{message(locale, 'source.routeLabel')}</span><strong>{routeTypeLabel(locale, match.routeType)}</strong><span>{message(locale, 'source.lastChecked')}</span><strong>{new Date(match.lastVerifiedAt + 'T00:00:00').toLocaleDateString(locale)}</strong><span>{message(locale, 'source.region')}</span><strong>{region}</strong><span>{message(locale, 'source.embed')}</span><strong>{match.embedAllowed === null ? message(locale, 'source.embedUnknown') : match.embedAllowed ? message(locale, 'source.embedAllowed') : message(locale, 'source.embedNo')}</strong></div>
      {verifiedVisualPlayback && <p className="playback-evidence-note">{message(locale, 'source.playback.verifiedHint')}</p>}
      <p className="match-note">{matchNote(locale, match.id)}</p>
      <div className="match-actions">{destination ? <ExternalLink className={destination.type === 'video-page' ? 'button button-primary' : 'button button-outline'} href={destination.url}>{message(locale, buttonKey)} <span aria-hidden="true">↗</span></ExternalLink> : <span className="no-route" role="status">{message(locale, 'source.noRoute')}</span>}{evidenceUrl && evidenceUrl !== destination?.url && <ExternalLink className="evidence-link" href={evidenceUrl}>{message(locale, 'source.evidence')}</ExternalLink>}</div>
    </div>
  </article>;
}

function PageIntro({ kicker, title, description }: { kicker: string; title: string; description: string }) {
  return <div className="page-intro"><p className="eyebrow">{kicker}</p><h1>{title}</h1><p>{description}</p></div>;
}

function FeedbackPage({ locale, count, saved, saveError, onSave, onDownload }: { locale: Locale; count: number; saved: boolean; saveError: boolean; onSave: (entry: FeedbackEntry) => boolean; onDownload: () => void }) {
  function t(key: MessageKey) {
    return message(locale, key);
  }

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const entry: FeedbackEntry = {
      id: crypto.randomUUID(),
      createdAt: new Date().toISOString(),
      role: form.get('role') as FeedbackEntry['role'],
      foundMatch: form.get('foundMatch') as FeedbackEntry['foundMatch'],
      clickOutcome: form.get('clickOutcome') as FeedbackEntry['clickOutcome'],
      issueCategory: form.get('issueCategory') as FeedbackIssue,
      statusClarity: Number(form.get('statusClarity')),
      friction: String(form.get('friction') ?? '').trim().slice(0, 500),
      returnIntent: form.get('returnIntent') as FeedbackEntry['returnIntent'],
    };
    if (onSave(entry)) event.currentTarget.reset();
  }

  return <section className="page-section feedback-layout">
    <div><PageIntro kicker={t('feedback.kicker')} title={t('feedback.title')} description={t('feedback.description')} /><div className="feedback-summary"><strong>{count}</strong><span>{t('feedback.count')}</span><button className="text-button" onClick={onDownload}>{t('feedback.export')} ↓</button></div><div className="privacy-note"><strong>{t('feedback.privacyTitle')}</strong><p>{t('feedback.privacy')}</p></div></div>
    <form className="feedback-form" onSubmit={submit}>
      <div className="form-heading"><span>{t('feedback.form.title')}</span><span>{t('feedback.form.time')}</span></div>
      <label>{t('feedback.role')}<select name="role" defaultValue="fan"><option value="fan">{t('feedback.role.fan')}</option><option value="athlete">{t('feedback.role.athlete')}</option><option value="coach">{t('feedback.role.coach')}</option><option value="other">{t('feedback.role.other')}</option></select></label>
      <label>{t('feedback.find')}<select name="foundMatch" defaultValue="yes"><option value="yes">{t('feedback.yes')}</option><option value="partly">{t('feedback.partly')}</option><option value="no">{t('feedback.no')}</option></select></label>
      <label>{t('feedback.click')}<select name="clickOutcome" defaultValue="not-tried"><option value="opened">{t('feedback.click.opened')}</option><option value="blocked">{t('feedback.click.blocked')}</option><option value="not-tried">{t('feedback.click.notTried')}</option></select></label>
      <label>{t('feedback.issue')}<select name="issueCategory" defaultValue="none"><option value="none">{t('feedback.issue.none')}</option><option value="find-match">{t('feedback.issue.find')}</option><option value="official-link">{t('feedback.issue.link')}</option><option value="unclear-page">{t('feedback.issue.understand')}</option><option value="mobile-display">{t('feedback.issue.mobile')}</option><option value="other">{t('feedback.issue.other')}</option></select></label>
      <label>{t('feedback.clarity')} <span className="range-hint">{t('feedback.clarityHint')}</span><select name="statusClarity" defaultValue="4"><option value="1">1 — {t('feedback.unclear')}</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5 — {t('feedback.clear')}</option></select></label>
      <label>{t('feedback.friction')}<textarea name="friction" rows={3} maxLength={500} placeholder={t('feedback.optional')} /></label>
      <label>{t('feedback.return')}<select name="returnIntent" defaultValue="yes"><option value="yes">{t('feedback.return.yes')}</option><option value="unsure">{t('feedback.return.unsure')}</option><option value="no">{t('feedback.return.no')}</option></select></label>
      <button className="button button-primary" type="submit">{t('feedback.save')}</button>
      {saved && <p className="form-success" role="status">{t('feedback.saved')}</p>}
      {saveError && <p className="form-error" role="alert">{t('feedback.saveError')}</p>}
      <p className="form-footnote">{t('feedback.onlyReal')}</p>
    </form>
    <div className="test-plan-callout"><span>{t('feedback.testTask')}</span><p>“{t('feedback.testPrompt')}”</p><span>{t('feedback.noResults')}</span></div>
  </section>;
}

export default App;
