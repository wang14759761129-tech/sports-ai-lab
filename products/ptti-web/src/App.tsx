import type { TheaterPresentation } from './PrivateTheaterFrame';
import { FanCatalogPage } from './FanCatalogPage';
import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import { catalogMode, catalogUrl } from './catalog-mode';
import { appendFeedback, readFeedback } from './feedback-storage.mjs';
import { LOCALE_STORAGE_KEY, message, readSavedLocale } from './i18n';
import type { Locale, MessageKey } from './i18n';
import { matchPageUrl, readMatchId, resolveSelectedMatch } from './match-location.mjs';
import { createFanStarDestination, createFanWatchReturn, restoreFanWatchReturn } from './fan-navigation.mjs';
import { fanLocationUrl, readFanLocation } from './fan-location.mjs';
import type { FanPage } from './fan-navigation.mjs';
import { emptyFanLocalData, readFanLocalData, toggleLocalId, writeFanLocalData } from './fan-local-data.mjs';
import type { FanLocalData } from './fan-local-data.mjs';
import type { FeedbackEntry, FeedbackIssue, MatchRecord } from './types';

const FirstExperienceDemo = lazy(() => import('./FirstExperienceDemo').then(module => ({ default: module.FirstExperienceDemo })));
const MatchDetail = lazy(() => import('./MatchDetail').then((module) => ({ default: module.MatchDetail })));
const FanSearchOverlay = lazy(() => import('./FanSearchOverlay').then((module) => ({ default: module.FanSearchOverlay })));
const ProWorkbench = lazy(() => import('./ProWorkbench').then((module) => ({ default: module.ProWorkbench })));
const MatchSourceLibrary = lazy(() => import('./MatchSourceLibrary').then((module) => ({ default: module.MatchSourceLibrary })));
const Goal14FanReviewPage = lazy(() => import('./Goal14FanReviewPage').then((module) => ({ default: module.Goal14FanReviewPage })));
const ArenaChallengePage = lazy(() => import('./ArenaChallengePage').then((module) => ({ default: module.ArenaChallengePage })));
const TrainingPage = lazy(() => import('./FanUniversePages').then((module) => ({ default: module.TrainingPage })));
const MyCornerPage = lazy(() => import('./FanUniversePages').then((module) => ({ default: module.MyCornerPage })));
const GearPage = lazy(() => import('./FanUniversePages').then((module) => ({ default: module.GearPage })));
const CommunityPage = lazy(() => import('./FanUniversePages').then((module) => ({ default: module.CommunityPage })));

type Page = 'cinema' | 'pro' | 'clips' | 'highlights' | 'stars' | 'watch' | 'feedback' | 'internal-review' | 'train' | 'gear' | 'community' | 'corner' | 'rivalries' | 'arena' | 'my-matches';
type Goal14ReviewPage = 'cinema' | 'stars' | 'clips' | 'watch';
const goal14InternalReview = __PTTI_GOAL14_FAN_MODE__ === 'internal-review';
function readLocalFeedback() {
  try { return readFeedback(localStorage); } catch { return []; }
}
function readLocalFanData() {
  try { return { data: readFanLocalData(localStorage), available: true }; }
  catch { return { data: emptyFanLocalData(), available: false }; }
}

function App() {
  const [demoOpen, setDemoOpen] = useState(false);
  const initialFanLocation = readFanLocation(window.location.href);
  const [cinemaVisited, setCinemaVisited] = useState(initialFanLocation?.page === 'cinema' || !initialFanLocation);
  const [matchReturnPage, setMatchReturnPage] = useState<'cinema' | 'corner'>(initialFanLocation?.returnPage === 'corner' ? 'corner' : 'cinema');
  const [theaterPresentations, setTheaterPresentations] = useState<Record<string, TheaterPresentation>>({});
  const [locale, setLocale] = useState<Locale>(() => readSavedLocale());
  const [page, setPage] = useState<Page>(() => (initialFanLocation?.page ?? 'cinema') as Page);
  const [proVisited, setProVisited] = useState(() => initialFanLocation?.page === 'my-matches');
  const [goal14ReviewPage, setGoal14ReviewPage] = useState<Goal14ReviewPage>('cinema');
  const [proFocus, setProFocus] = useState<'insight' | 'review'>('review');
  const [selectedId, setSelectedId] = useState(() => goal14InternalReview ? '' : readMatchId(window.location.href));
  const [matches, setMatches] = useState<MatchRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [feedbackReturn, setFeedbackReturn] = useState<Page>('cinema');
  const [feedbackContext, setFeedbackContext] = useState<FeedbackEntry['context']>();
  const [feedbackCount, setFeedbackCount] = useState(() => readLocalFeedback().length);
  const [feedbackSaved, setFeedbackSaved] = useState(false);
  const [feedbackSaveError, setFeedbackSaveError] = useState(false);
  const [watchSourceId, setWatchSourceId] = useState<string | null>(initialFanLocation?.sourceId ?? null);
  const [watchReturn, setWatchReturn] = useState<{ page: FanPage; matchId: string | null; starId: string | null }>(() => ({ page: (initialFanLocation?.returnPage ?? 'cinema') as FanPage, matchId: initialFanLocation?.matchId ?? null, starId: initialFanLocation?.starId ?? null }));
  const [fanMatchId, setFanMatchId] = useState<string | null>(initialFanLocation?.matchId ?? null);
  const [fanStarId, setFanStarId] = useState<string | null>(initialFanLocation?.starId ?? null);
  const [fanRivalryId, setFanRivalryId] = useState<string | null>(initialFanLocation?.rivalryId ?? null);
  const [fanSearchOpen, setFanSearchOpen] = useState(false);
  const [fanActionNotice, setFanActionNotice] = useState<MessageKey | null>(null);
  const closeFanSearch = useCallback(() => setFanSearchOpen(false), []);
  const [fanLocalBoot] = useState(readLocalFanData);
  const [fanLocalData, setFanLocalData] = useState<FanLocalData>(fanLocalBoot.data);
  const [fanLocalStorageAvailable, setFanLocalStorageAvailable] = useState(fanLocalBoot.available);

  const t = (key: MessageKey) => message(locale, key);

  async function loadMatches() {
    setLoading(true);
    setLoadError(false);
    try {
      const [{ projectBridgeMatches }, response] = await Promise.all([import('./readonly-catalog.mjs'), fetch(catalogUrl, { headers: { Accept: 'application/json' } })]);
      if (!response.ok) throw new Error('Match list unavailable');
      const data = projectBridgeMatches(await response.json(), { view: catalogMode, localReview: catalogMode === 'review' });
      setMatches(data);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { if (selectedId && !goal14InternalReview) void loadMatches(); }, [selectedId]);

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

  useEffect(() => {
    const previousRestoration = window.history.scrollRestoration;
    window.history.scrollRestoration = 'manual';
    const restore = () => {
      const location = readFanLocation(window.location.href);
      setSelectedId(readMatchId(window.location.href));
      setPage((location?.page ?? 'cinema') as Page);
      if (!location || location.page === 'cinema') { setCinemaVisited(true); setMatchReturnPage(location?.returnPage === 'corner' ? 'corner' : 'cinema'); }
      setFanMatchId(location?.matchId ?? null);
      setFanStarId(location?.starId ?? null);
      setWatchSourceId(location?.sourceId ?? null);
      setFanRivalryId(location?.rivalryId ?? null);
      setWatchReturn({ page: (location?.returnPage ?? 'cinema') as FanPage, matchId: location?.matchId ?? null, starId: location?.starId ?? null });
    };
    window.addEventListener('popstate', restore);
    return () => { window.removeEventListener('popstate', restore); window.history.scrollRestoration = previousRestoration; };
  }, []);

  useEffect(() => {
    if (selectedId || goal14InternalReview) return;
    const address = fanLocationUrl(window.location.href, {
      page, matchId: page === 'watch' ? watchReturn.matchId : fanMatchId,
      starId: page === 'watch' ? watchReturn.starId : fanStarId,
      sourceId: watchSourceId, rivalryId: fanRivalryId, returnPage: page === 'cinema' ? matchReturnPage : watchReturn.page,
    });
    if (address !== window.location.href) window.history.replaceState(null, '', address);
  }, [page, selectedId, fanMatchId, fanStarId, watchSourceId, watchReturn, fanRivalryId, matchReturnPage]);

  useEffect(() => {
    if (!fanActionNotice) return;
    const timer = window.setTimeout(() => setFanActionNotice(null), 4000);
    return () => window.clearTimeout(timer);
  }, [fanActionNotice]);

  const selectedMatch = resolveSelectedMatch(matches, selectedId);
  const selectedUrl = matchPageUrl(window.location.href, selectedId);

  function selectMatch(id: string) {
    window.history.pushState(null, '', matchPageUrl(window.location.href, id));
    setSelectedId(id);

    setPage('cinema');
  }

  useEffect(() => {
    if (selectedMatch && page === 'cinema') {
      document.getElementById('selected-match-heading')?.focus({ preventScroll: true });
      window.scrollTo({ top: 0, behavior: 'instant' });
    }
  }, [selectedMatch, page]);

  function changePage(next: Page) {
    setPage(next);
    if (next === 'cinema') setCinemaVisited(true);
    window.scrollTo({ top: 0, behavior: 'instant' });
    setFeedbackSaved(false);
    setFeedbackSaveError(false);
  }

  function clearLegacyMatchSelection() {
    if (!selectedId) return;
    window.history.pushState(null, '', matchPageUrl(window.location.href, ''));
    setSelectedId('');
  }

  function updateFanLocalData(next: FanLocalData): boolean {
    try {
      const accepted = writeFanLocalData(localStorage, next);
      setFanLocalData(accepted);
      setFanLocalStorageAvailable(true);
      return true;
    } catch {
      setFanLocalStorageAvailable(false);
      return false;
    }
  }

  function adoptImportedFanLocalData(next: FanLocalData): boolean {
    setFanLocalData(next);
    setFanLocalStorageAvailable(true);
    return true;
  }

  function toggleSavedMatch(matchId: string) {
    const wasSaved = fanLocalData.saved_match_ids.includes(matchId);
    const success = updateFanLocalData({ ...fanLocalData, saved_match_ids: toggleLocalId(fanLocalData.saved_match_ids, matchId) });
    setFanActionNotice(success ? wasSaved ? 'gm.unsaved' : 'gm.saved' : 'universe.storage.warning');
    return success;
  }

  function toggleFollowedAthlete(athleteId: string) {
    const wasFollowed = fanLocalData.followed_athlete_ids.includes(athleteId);
    const success = updateFanLocalData({ ...fanLocalData, followed_athlete_ids: toggleLocalId(fanLocalData.followed_athlete_ids, athleteId) });
    setFanActionNotice(success ? wasFollowed ? 'gm.unfollowed' : 'gm.followed' : 'universe.storage.warning');
    return success;
  }

  function openFanStar(athleteId: string) {
    clearLegacyMatchSelection();
    const destination = createFanStarDestination(athleteId);
    setFanStarId(destination.starId);
    setFanMatchId(destination.matchId);
    setFanRivalryId(null);
    changePage('stars');
  }

  function openFanMatch(matchId: string) {
    setMatchReturnPage(page === 'corner' || (page === 'watch' && (watchReturn.page === 'corner' || matchReturnPage === 'corner')) ? 'corner' : 'cinema');
    clearLegacyMatchSelection();
    setFanMatchId(matchId);
    setFanStarId(null);
    setFanRivalryId(null);
    changePage('cinema');
  }

  function closeFanMatch() {
    const matchId = fanMatchId;
    setFanMatchId(null); setFanStarId(null);
    changePage(matchReturnPage);
    window.setTimeout(() => {
      const cards = document.querySelectorAll<HTMLElement>(matchReturnPage === 'corner' ? '[data-saved-match-id]' : '[data-public-match-id], [data-lobby-detail-id]');
      const card = Array.from(cards).find(item => (item.dataset.savedMatchId ?? item.dataset.publicMatchId ?? item.dataset.lobbyDetailId) === matchId);
      const target = card?.matches('button, [tabindex]') ? card : card?.querySelector<HTMLElement>('button, [tabindex]');
      (target ?? document.querySelector<HTMLElement>('[data-fan-search], #collector-title'))?.focus();
    }, 0);
  }

  function openFanRivalry(rivalryId: string) {
    setFanRivalryId(rivalryId);
    setFanMatchId(null);
    setFanStarId(null);
    changePage('rivalries');
  }

  function openRivalries() {
    setFanRivalryId(null);
    changePage('rivalries');
  }

  function openFanWatch(sourceId: string, context?: { matchId: string | null; starId: string | null }) {
    setWatchReturn(createFanWatchReturn(page === 'watch' ? watchReturn.page : page, context));
    setWatchSourceId(sourceId);
    changePage('watch');
  }

  function resumeFanWatch() {
    if (!watchSourceId) setWatchReturn({ page: 'cinema', matchId: null, starId: null });
    changePage('watch');
  }

  function returnFromWatch() {
    const destination = restoreFanWatchReturn(watchReturn);
    setFanMatchId(destination.matchId);
    setFanStarId(destination.starId);
    changePage(destination.page);
  }

  function openPro(focus: 'insight' | 'review') {
    setProVisited(true);
    setProFocus(focus);
    changePage('pro');
    window.setTimeout(() => document.querySelector(focus === 'review' ? '.local-video-review' : '[data-review-targets-panel], [data-loss-insights], .local-video-review')?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 100);
  }

  function openMyMatches() {
    clearLegacyMatchSelection();
    setFanMatchId(null);
    setFanStarId(null);
    setProVisited(true);
    setProFocus('review');
    changePage('my-matches');
  }

  function chooseLocalVideo() {
    openPro('review');
  }

  function openFanSearch() {
    setFanSearchOpen(true);
  }

  function openFeedback(context: { sourceId?: string; matchId?: string; starId?: string } = {}) {
    if (page === 'feedback') return;
    setFeedbackReturn(page);
    setFeedbackContext({ page, source_id: context.sourceId ?? null, match_id: context.matchId ?? null, athlete_id: context.starId ?? null });
    changePage('feedback');
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
    let url: string | undefined;
    try {
      const contents = JSON.stringify(readLocalFeedback(), null, 2);
      url = URL.createObjectURL(new Blob([contents], { type: 'application/json' }));
      const anchor = document.createElement('a');
      anchor.href = url; anchor.download = 'ptti-web-feedback.json'; anchor.click();
      setFeedbackSaveError(false);
    } catch { setFeedbackSaveError(true); }
    finally { if (url) { const createdUrl = url; window.setTimeout(() => URL.revokeObjectURL(createdUrl), 1000); } }
  }

  return (
    <div className={'app-shell ' + (locale === 'zh-CN' ? 'locale-zh' : 'locale-en')} data-page={page}>
      <a className="skip-link" href="#ptti-main">{t('gm.skip')}</a>
      {!demoOpen && <header className="site-header">
        <button className="wordmark" onClick={() => { selectMatch(''); setFanMatchId(null); setFanStarId(null); changePage('cinema'); }} aria-label={t('aria.home')}>
          <span className="wordmark-icon" aria-hidden="true"><svg viewBox="0 0 36 36"><path d="M8 29V8h11a8 8 0 0 1 0 16h-6" fill="none" stroke="currentColor" strokeWidth="4"/><circle cx="28" cy="8" r="3" fill="currentColor"/></svg></span>
          <span>PTTI<small>{t('brand.tagline')}</small></span>
        </button>
        <nav className="primary-nav" aria-label={t('aria.navigation')}>
          <button className={page === 'cinema' ? 'nav-link active' : 'nav-link'} onClick={() => { clearLegacyMatchSelection(); setFanMatchId(null); setFanStarId(null); changePage('cinema'); }} aria-current={page === 'cinema' ? 'page' : undefined}>{t('nav.cinema')}</button>
          <button className={page === 'watch' ? 'nav-link active' : 'nav-link'} onClick={resumeFanWatch} aria-current={page === 'watch' ? 'page' : undefined}>{t('nav.watch')}</button>
          <button className={page === 'stars' ? 'nav-link active' : 'nav-link'} onClick={() => { setFanMatchId(null); setFanStarId(null); changePage('stars'); }} aria-current={page === 'stars' ? 'page' : undefined}>{t('nav.stars')}</button>
          <button className={page === 'clips' ? 'nav-link active' : 'nav-link'} onClick={() => { setFanMatchId(null); setFanStarId(null); changePage('clips'); }} aria-current={page === 'clips' ? 'page' : undefined}>{t('nav.clips')}</button>
        </nav>
        <div className="header-actions">
          <button type="button" className="header-my-matches" aria-current={page === 'my-matches' ? 'page' : undefined} onClick={openMyMatches}>{t('nav.myMatches')}</button>
          <button type="button" className="header-search" aria-label={t('nav.search')} onClick={openFanSearch}><span aria-hidden="true">⌕</span><span>{t('nav.search')}</span></button>
          {page === 'pro' ? <div className="pro-mode-switch" role="group" aria-label={t('nav.pro')}>
            <button type="button" className={proFocus === 'insight' ? 'active' : ''} aria-pressed={proFocus === 'insight'} onClick={() => openPro('insight')}>{t('nav.insightShort')}</button>
            <button type="button" className={proFocus === 'review' ? 'active' : ''} aria-pressed={proFocus === 'review'} onClick={() => openPro('review')}>{t('nav.reviewShort')}</button>
          </div> : null}
          <button type="button" className="header-corner" aria-label={t('nav.corner')} aria-current={page === 'corner' ? 'page' : undefined} onClick={() => changePage('corner')}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4h12v17l-6-4-6 4V4Z" fill="none" stroke="currentColor" strokeWidth="1.5"/></svg><span>{t('nav.corner')}</span></button>
          <div className="locale-switch" role="group" aria-label={t('aria.language')}>
            {(['zh-CN', 'en'] as const).map((value) => (
              <button key={value} type="button" className={locale === value ? 'locale-option active' : 'locale-option'} aria-pressed={locale === value} onClick={() => setLocale(value)}>
                {t(value === 'zh-CN' ? 'language.chinese' : 'language.english')}
              </button>
            ))}
          </div>
        </div>
      </header>}

      <main id="ptti-main" data-catalog-mode={catalogMode}>
        {demoOpen && <Suspense fallback={<PageLoadFallback locale={locale} />}><FirstExperienceDemo locale={locale} onBack={() => { setDemoOpen(false); requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('[data-try-demo]')?.focus()); }} onReview={() => { setDemoOpen(false); openMyMatches(); }} /></Suspense>}
        <div hidden={demoOpen}>
        {page === 'cinema' && !fanMatchId && !selectedId && <aside className="first-experience-entry" aria-label={locale === 'zh-CN' ? '第一次使用' : 'First experience'}><span>{locale === 'zh-CN' ? '你的一局，值得认真回看。' : 'Your game deserves a closer look.'}</span><button data-try-demo type="button" onClick={() => setDemoOpen(true)}>{locale === 'zh-CN' ? '体验演示 · 无需视频' : 'Try a Demo · No video needed'}</button><button type="button" onClick={openMyMatches}>{locale === 'zh-CN' ? '复盘我的比赛' : 'Review My Match'}</button></aside>}
        {!fanLocalStorageAvailable && <p className="fan-local-storage-banner" role="status">{t('universe.storage.warning')}</p>}
        {goal14InternalReview && page === 'internal-review' && <aside className="catalog-mode-banner review" role="status"><strong>{t('goal14.bannerTitle')}</strong><span>{t('goal14.bannerDetail')}</span></aside>}
        {cinemaVisited && <div data-cinema-retained hidden={page !== 'cinema' || Boolean(selectedId)}><FanCatalogPage locale={locale} mode="cinema" onOpenMyMatches={openMyMatches} active={page === 'cinema' && !selectedId && !demoOpen} onCloseMatch={closeFanMatch} matchReturnPage={matchReturnPage} onGoCinema={() => changePage('cinema')} onGoStars={() => changePage('stars')} onGoInsight={() => openPro('insight')} onGoClips={() => changePage('clips')} onGoHighlights={() => changePage('highlights')} onChooseVideo={chooseLocalVideo} onOpenMatch={openFanMatch} onOpenStar={openFanStar} onOpenWatch={openFanWatch} onOpenRivalry={openFanRivalry} onGoCorner={() => changePage('corner')} onFeedback={openFeedback} initialMatchId={fanMatchId} savedMatchIds={fanLocalData.saved_match_ids} followedAthleteIds={fanLocalData.followed_athlete_ids} onToggleSavedMatch={toggleSavedMatch} onToggleFollowedAthlete={toggleFollowedAthlete} onOpenTrain={() => changePage('train')} onOpenGear={() => changePage('gear')} onOpenCommunity={() => changePage('community')} onOpenArena={() => changePage('arena')} /></div>}
        {proVisited && <div hidden={page !== 'pro' && page !== 'my-matches'} data-persistent-workspace><Suspense fallback={<PageLoadFallback locale={locale} />}><ProWorkbench locale={locale} active={!demoOpen && (page === 'pro' || page === 'my-matches')} oneGameMode={page === 'my-matches'} onOpenProLab={() => openPro('review')} onReturnMyMatches={openMyMatches} onOpenJournal={() => changePage('train')} onBrowseMatches={() => { setFanMatchId(null); setFanStarId(null); changePage('cinema'); window.setTimeout(() => document.querySelector<HTMLInputElement>('[data-fan-mode="cinema"] [data-fan-search]')?.focus(), 100); }} /></Suspense></div>}
        {page === 'cinema' && !goal14InternalReview && selectedId && loading && <div className="state-card" role="status"><span className="spinner" />{t('loading.matches')}</div>}
        {page === 'cinema' && !goal14InternalReview && selectedId && loadError && <div className="state-card state-error" role="alert"><strong>{t('load.errorTitle')}</strong><p>{t('load.error')}</p><button className="button" onClick={() => void loadMatches()}>{t('load.retry')}</button></div>}
        {page === 'cinema' && !goal14InternalReview && selectedId && !loading && !loadError && !selectedMatch && <div className="state-card" role="status"><strong>{t('match.missing')}</strong><button className="button" onClick={() => { selectMatch(''); setFanMatchId(null); }}>{t('empty.action')}</button></div>}
        {page === 'cinema' && !goal14InternalReview && selectedMatch && <Suspense fallback={<PageLoadFallback locale={locale} />}><MatchDetail key={selectedMatch.id} match={selectedMatch} locale={locale} pageUrl={selectedUrl} onBack={() => selectMatch('')} /></Suspense>}
        {page === 'cinema' && catalogMode === 'review' && !goal14InternalReview && <Suspense fallback={<PageLoadFallback locale={locale} />}><MatchSourceLibrary locale={locale} /></Suspense>}
        {page === 'stars' && <FanCatalogPage locale={locale} mode="stars" onGoCinema={() => changePage('cinema')} onGoInsight={() => openPro('insight')} onGoClips={() => changePage('clips')} onOpenMatch={openFanMatch} onOpenWatch={openFanWatch} onOpenStar={openFanStar} onOpenRivalry={openFanRivalry} onGoCorner={() => changePage('corner')} onFeedback={openFeedback} initialStarId={fanStarId} initialMatchId={fanMatchId} savedMatchIds={fanLocalData.saved_match_ids} followedAthleteIds={fanLocalData.followed_athlete_ids} onToggleSavedMatch={toggleSavedMatch} onToggleFollowedAthlete={toggleFollowedAthlete} />}
        {page === 'clips' && <FanCatalogPage locale={locale} mode="clips" onGoCinema={() => changePage('cinema')} onGoInsight={() => openPro('insight')} onGoClips={() => changePage('clips')} onOpenMatch={openFanMatch} onOpenWatch={openFanWatch} onOpenStar={openFanStar} onOpenRivalry={openFanRivalry} onGoCorner={() => changePage('corner')} onFeedback={openFeedback} initialMatchId={fanMatchId} initialStarId={fanStarId} savedMatchIds={fanLocalData.saved_match_ids} followedAthleteIds={fanLocalData.followed_athlete_ids} onToggleSavedMatch={toggleSavedMatch} onToggleFollowedAthlete={toggleFollowedAthlete} />}
        {page === 'watch' && <FanCatalogPage locale={locale} mode="watch" onOpenMyMatches={openMyMatches} theaterPresentations={theaterPresentations} onTheaterPresentationChange={(sourceId, value) => setTheaterPresentations(current => ({ ...current, [sourceId]: value }))} onOpenWatch={openFanWatch} selectedSourceId={watchSourceId} onGoCinema={() => changePage('cinema')} onGoInsight={() => openPro('insight')} onGoClips={() => changePage('clips')} onOpenMatch={openFanMatch} onOpenStar={openFanStar} onOpenRivalry={openFanRivalry} onGoCorner={() => changePage('corner')} onFeedback={openFeedback} onGoBack={returnFromWatch} initialMatchId={fanMatchId} initialStarId={fanStarId} savedMatchIds={fanLocalData.saved_match_ids} followedAthleteIds={fanLocalData.followed_athlete_ids} onToggleSavedMatch={toggleSavedMatch} onToggleFollowedAthlete={toggleFollowedAthlete} />}
          {page === 'arena' && <Suspense fallback={<PageLoadFallback locale={locale} />}><ArenaChallengePage locale={locale} onBack={() => changePage('cinema')} onOpenJournal={() => changePage('train')} /></Suspense>}
        {page === 'highlights' && <FanCatalogPage locale={locale} mode="highlights" onGoCinema={() => changePage('cinema')} onGoInsight={() => openPro('insight')} onGoClips={() => changePage('clips')} onOpenMatch={openFanMatch} onOpenWatch={openFanWatch} onOpenStar={openFanStar} onOpenRivalry={openFanRivalry} onGoCorner={() => changePage('corner')} onFeedback={openFeedback} savedMatchIds={fanLocalData.saved_match_ids} followedAthleteIds={fanLocalData.followed_athlete_ids} onToggleSavedMatch={toggleSavedMatch} onToggleFollowedAthlete={toggleFollowedAthlete} />}
        {page === 'rivalries' && <FanCatalogPage locale={locale} mode="rivalries" onGoCinema={() => changePage('cinema')} onGoInsight={() => openPro('insight')} onGoClips={() => changePage('clips')} onOpenMatch={openFanMatch} onOpenWatch={openFanWatch} onOpenStar={openFanStar} onOpenRivalry={openFanRivalry} onGoCorner={() => changePage('corner')} onFeedback={openFeedback} initialRivalryId={fanRivalryId} savedMatchIds={fanLocalData.saved_match_ids} followedAthleteIds={fanLocalData.followed_athlete_ids} onToggleSavedMatch={toggleSavedMatch} onToggleFollowedAthlete={toggleFollowedAthlete} />}
        {page === 'corner' && <Suspense fallback={<PageLoadFallback locale={locale} />}><MyCornerPage onOpenWatch={openFanWatch} onFeedback={() => openFeedback()} onOpenJournal={() => changePage('train')} onGoClips={() => changePage('clips')} onGoGear={() => changePage('gear')} locale={locale} data={fanLocalData} onChange={updateFanLocalData} onReplace={adoptImportedFanLocalData} onOpenMatch={openFanMatch} onOpenStar={openFanStar} onDiscover={() => { changePage('cinema'); openFanSearch(); }} /></Suspense>}
        {page === 'train' && <Suspense fallback={<PageLoadFallback locale={locale} />}><TrainingPage locale={locale} data={fanLocalData} onChange={updateFanLocalData} onReplace={adoptImportedFanLocalData} onGoPro={openPro} onOpenMatch={openFanMatch} /></Suspense>}
        {page === 'gear' && <Suspense fallback={<PageLoadFallback locale={locale} />}><GearPage locale={locale} onOpenMatch={openFanMatch} /></Suspense>}
        {page === 'community' && <Suspense fallback={<PageLoadFallback locale={locale} />}><CommunityPage locale={locale} data={fanLocalData} onChange={updateFanLocalData} onReplace={adoptImportedFanLocalData} onOpenMatch={openFanMatch} /></Suspense>}
        {goal14InternalReview && page === 'internal-review' && <Suspense fallback={<PageLoadFallback locale={locale} />}><Goal14FanReviewPage
          active={page === 'internal-review'}
          mode={goal14ReviewPage}
          locale={locale}
          onNavigate={(next) => setGoal14ReviewPage(next)}
        /></Suspense>}

        {page === 'feedback' && <FeedbackPage context={feedbackContext} onBack={() => changePage(feedbackReturn)} locale={locale} count={feedbackCount} saved={feedbackSaved} saveError={feedbackSaveError} onSave={saveFeedback} onDownload={downloadFeedback} />}
      </div>
      </main>

      {fanSearchOpen && <Suspense fallback={<PageLoadFallback locale={locale} />}><FanSearchOverlay locale={locale} onClose={closeFanSearch} onOpenMatch={(id) => { setFanSearchOpen(false); openFanMatch(id); }} onOpenStar={(id) => { setFanSearchOpen(false); openFanStar(id); }} onOpenWatch={(sourceId, context) => { setFanSearchOpen(false); openFanWatch(sourceId, context); }} /></Suspense>}

      <div className="fan-action-toast" role="status" aria-live="polite" aria-atomic="true">{fanActionNotice && <span key={fanActionNotice}>{fanActionNotice === 'universe.storage.warning' ? '!' : '✓'} {t(fanActionNotice)}</span>}</div>
      <nav className="mobile-bottom-nav" aria-label={t('aria.navigation')}>
        {(['cinema', 'watch', 'stars', 'clips'] as const).map((destination) => <button key={destination} type="button" className={page === destination ? 'active' : ''} aria-current={page === destination ? 'page' : undefined} onClick={() => {
          if (destination !== 'watch') clearLegacyMatchSelection();
          if (destination === 'watch') { resumeFanWatch(); return; }
          if (destination === 'cinema' || destination === 'stars' || destination === 'clips') { setFanMatchId(null); setFanStarId(null); }
          changePage(destination);
        }}>{t(destination === 'cinema' ? 'nav.cinema' : destination === 'watch' ? 'nav.watch' : destination === 'stars' ? 'nav.stars' : 'nav.clips')}</button>)}
      </nav>

      <footer className="site-footer"><span>{t('footer.version')}</span><span>{t('footer.links')}</span><div className="footer-universe-links"><button type="button" className="pro-nav" onClick={() => openPro('insight')}>{t('nav.pro')} ↗</button><button onClick={() => changePage('highlights')}>{t('fan.highlightsTitle')}</button><button onClick={() => changePage('corner')}>{t('nav.corner')}</button><button onClick={openRivalries}>{t('nav.rivalries')}</button><button onClick={() => changePage('train')}>{t('nav.train')}</button><button onClick={() => changePage('gear')}>{t('nav.gear')}</button><button onClick={() => changePage('community')}>{t('nav.community')}</button></div>{goal14InternalReview && <button onClick={() => changePage('internal-review')}>{t('nav.internalReview')}</button>}<button onClick={() => openFeedback()}>{t('footer.feedback')}</button></footer>
    </div>
  );
}

function PageLoadFallback({ locale }: { locale: Locale }) {
  return <div className="route-loading" role="status" aria-live="polite">{locale === 'zh-CN' ? '页面载入中…' : 'Loading page…'}</div>;
}

function PageIntro({ kicker, title, description }: { kicker: string; title: string; description: string }) {
  return <div className="page-intro"><p className="eyebrow">{kicker}</p><h1>{title}</h1><p>{description}</p></div>;
}

function FeedbackPage({ locale, count, saved, saveError, onSave, onDownload, context, onBack }: { context?: FeedbackEntry['context']; onBack: () => void; locale: Locale; count: number; saved: boolean; saveError: boolean; onSave: (entry: FeedbackEntry) => boolean; onDownload: () => void }) {
  function t(key: MessageKey) {
    return message(locale, key);
  }

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const entry: FeedbackEntry = {
      context,
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
    <div className="voice-context"><button type="button" className="button button-outline" onClick={onBack}>{t('voice.back')}</button><p>{t('voice.context')}</p></div>
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
