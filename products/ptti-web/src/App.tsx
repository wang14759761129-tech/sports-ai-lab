import { useEffect, useMemo, useState } from 'react';
import { pulseItems, starProfiles } from './data/content';
import type { FeedbackEntry, MatchRecord, SourceStatus } from './types';

type Page = 'cinema' | 'pulse' | 'stars' | 'feedback';
const FEEDBACK_KEY = 'ptti-web-feedback-v0.1';
const disciplines = [
  ['all', 'All events'],
  ['MS', "Men’s singles"],
  ['WS', "Women’s singles"],
  ['MD', "Men’s doubles"],
  ['WD', "Women’s doubles"],
  ['XD', 'Mixed doubles'],
];

function readFeedback(): FeedbackEntry[] {
  try {
    const value = localStorage.getItem(FEEDBACK_KEY);
    return value ? (JSON.parse(value) as FeedbackEntry[]) : [];
  } catch {
    return [];
  }
}

function ExternalLink({ href, children, className = '' }: { href: string; children: React.ReactNode; className?: string }) {
  return <a className={className} href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
}

function App() {
  const [page, setPage] = useState<Page>('cinema');
  const [matches, setMatches] = useState<MatchRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [search, setSearch] = useState('');
  const [discipline, setDiscipline] = useState('all');
  const [event, setEvent] = useState('all');
  const [source, setSource] = useState('all');
  const [status, setStatus] = useState<'all' | SourceStatus>('all');
  const [feedbackCount, setFeedbackCount] = useState(() => readFeedback().length);
  const [feedbackSaved, setFeedbackSaved] = useState(false);

  async function loadMatches() {
    setLoading(true);
    setLoadError('');
    try {
      const response = await fetch('/data/cinema.json', { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`The reviewed match list could not be loaded (${response.status}).`);
      const data = (await response.json()) as MatchRecord[];
      setMatches(data);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'The reviewed match list could not be loaded.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadMatches(); }, []);

  const events = useMemo(() => [...new Set(matches.map((match) => match.eventCategory))].sort(), [matches]);
  const sources = useMemo(() => [...new Set(matches.map((match) => match.platform))].sort(), [matches]);
  const filteredMatches = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return matches.filter((match) => {
      const searchable = [match.event, match.round, ...match.players, match.discipline].join(' ').toLocaleLowerCase();
      return (!query || searchable.includes(query))
        && (discipline === 'all' || match.discipline === discipline)
        && (event === 'all' || match.eventCategory === event)
        && (source === 'all' || match.platform === source)
        && (status === 'all' || match.sourceStatus === status);
    });
  }, [matches, search, discipline, event, source, status]);

  function resetFilters() {
    setSearch('');
    setDiscipline('all');
    setEvent('all');
    setSource('all');
    setStatus('all');
  }

  function saveFeedback(entry: FeedbackEntry) {
    const entries = [...readFeedback(), entry];
    localStorage.setItem(FEEDBACK_KEY, JSON.stringify(entries));
    setFeedbackCount(entries.length);
    setFeedbackSaved(true);
  }

  function downloadFeedback() {
    const contents = JSON.stringify(readFeedback(), null, 2);
    const blob = new Blob([contents], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'ptti-web-feedback.json';
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <button className="wordmark" onClick={() => setPage('cinema')} aria-label="PTTI home">
          <span className="wordmark-icon">P</span>
          <span>PTTI<small>THE WORLD OF TABLE TENNIS</small></span>
        </button>
        <nav className="primary-nav" aria-label="Main navigation">
          {(['cinema', 'pulse', 'stars'] as const).map((item) => (
            <button key={item} className={page === item ? 'nav-link active' : 'nav-link'} onClick={() => { setPage(item); setFeedbackSaved(false); }}>
              {item}
            </button>
          ))}
        </nav>
        <button className="feedback-nav" onClick={() => { setPage('feedback'); setFeedbackSaved(false); }}>Share feedback <span aria-hidden="true">↗</span></button>
      </header>

      <main>
        {page === 'cinema' && <>
          <section className="hero" aria-labelledby="cinema-title">
            <div className="hero-copy">
              <p className="eyebrow"><span className="live-dot" /> MATCH FINDER · PILOT 01</p>
              <h1 id="cinema-title">The match is here.<br /><em>The next click is clear.</em></h1>
              <p className="hero-description">Find a match, see who hosts its official source, and choose where to continue watching.</p>
              <button className="button button-primary" onClick={() => document.getElementById('match-search')?.focus()}>Find a match <span aria-hidden="true">↓</span></button>
            </div>
            <div className="hero-feature" aria-label="Source status summary">
              <div className="court-lines" aria-hidden="true"><span /><span /><i /></div>
              <div className="feature-label">PTTI CINEMA <span>CURATED SAMPLE</span></div>
              <div className="feature-stat"><strong>{matches.length.toString().padStart(2, '0')}</strong><span>source reviewed<br />match routes</span></div>
              <div className="feature-foot"><span>OFFICIAL SOURCES</span><span>PLAYBACK STATUS · UNVERIFIED</span></div>
            </div>
          </section>

          <section className="section-heading" aria-labelledby="match-heading">
            <div><p className="eyebrow">A SMALL, TRACEABLE START</p><h2 id="match-heading">Find a match</h2></div>
            <p className="section-note">A source page opening does not confirm video playback.</p>
          </section>

          <section className="filter-panel" aria-label="Match search and filters">
            <label className="search-field"><span className="sr-only">Search players and events</span><span aria-hidden="true">⌕</span><input id="match-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search a player or event" /></label>
            <label><span className="sr-only">Discipline</span><select value={discipline} onChange={(e) => setDiscipline(e.target.value)}>{disciplines.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label><span className="sr-only">Event type</span><select value={event} onChange={(e) => setEvent(e.target.value)}><option value="all">All tournament types</option>{events.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label><span className="sr-only">Source platform</span><select value={source} onChange={(e) => setSource(e.target.value)}><option value="all">All platforms</option>{sources.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label><span className="sr-only">Source status</span><select value={status} onChange={(e) => setStatus(e.target.value as 'all' | SourceStatus)}><option value="all">Any source status</option><option value="official-listing-found">Official listing found</option><option value="no-verified-route">No verified watch route</option></select></label>
          </section>

          <div className="results-meta" aria-live="polite"><span>{loading ? 'Loading reviewed matches…' : `${filteredMatches.length} ${filteredMatches.length === 1 ? 'match' : 'matches'}`}</span><button className="text-button" onClick={resetFilters}>Reset filters</button></div>
          {loading && <div className="state-card" role="status"><span className="spinner" />Loading the local source list…</div>}
          {!loading && loadError && <div className="state-card state-error" role="alert"><strong>We couldn’t load Cinema.</strong><p>{loadError}</p><button className="button" onClick={() => void loadMatches()}>Try again</button></div>}
          {!loading && !loadError && filteredMatches.length === 0 && <div className="state-card"><strong>No reviewed match fits those filters.</strong><p>Clear a filter or try another player name. This pilot includes a small source-checked sample.</p><button className="button" onClick={resetFilters}>Show all sample matches</button></div>}
          {!loading && !loadError && filteredMatches.length > 0 && <div className="match-grid">{filteredMatches.map((match) => <MatchCard key={match.id} match={match} />)}</div>}
          <div className="notice-strip"><span className="notice-mark">i</span><p>Some events have a source page but no individual video URL. Territory availability is unknown unless a source says otherwise.</p><ExternalLink href="https://www.worldtabletennis.com/">Browse World Table Tennis <span aria-hidden="true">↗</span></ExternalLink></div>
        </>}

        {page === 'pulse' && <section className="page-section">
          <PageIntro kicker="PTTI PULSE · CURATED SOURCES" title="A little closer to the game." description="Official highlights, player stories and event notes from named publishers. This list is curated by hand; it does not update in real time." />
          <div className="pulse-grid">{pulseItems.map((item) => <article className="pulse-card" key={item.id}>
            <div className={`pulse-art ${item.format}`}><span className="pulse-art-mark">{item.format === 'video' ? '▶' : 'PT'}</span><span className="pulse-art-type">{item.category.toUpperCase()}</span><span className="pulse-art-rule" /></div>
            <div className="pulse-card-body"><div className="card-meta"><span>{item.platform}</span><span>{item.format === 'video' ? 'VIDEO LINK' : 'ARTICLE'}</span></div><h3>{item.title}</h3><p>{item.summary}</p><div className="publisher-line">Published by <strong>{item.publisher}</strong></div><ExternalLink className="button button-outline" href={item.url}>{item.format === 'video' ? 'Open original video' : 'Read original story'} <span aria-hidden="true">↗</span></ExternalLink><ExternalLink className="evidence-link" href={item.evidenceUrl}>Source record</ExternalLink><p className="tiny-status">Source checked {item.verifiedAt} · playback not tested</p></div>
          </article>)}</div>
          <div className="state-card state-inline"><strong>Other sources are waiting for verification.</strong><p>Training clips and third-party public reactions will appear after publisher, original link and permission context are checked.</p></div>
        </section>}

        {page === 'stars' && <section className="page-section">
          <PageIntro kicker="PTTI STARS · PUBLIC SOURCES" title="Follow the players." description="Short profiles built from public event records and WTT-published stories. No invented quotes, private training diaries or player portraits." />
          <div className="stars-list">{starProfiles.map((star) => {
            const relatedMatch = matches.find((match) => match.id === star.relatedMatchId);
            return <article className="star-card" key={star.id}>
              <div className="star-monogram" aria-hidden="true">{star.name.split(' ').map((part) => part[0]).join('')}</div>
              <div className="star-main"><div className="card-meta"><span>PLAYER PROFILE</span><span>{star.countryCode}</span></div><h3>{star.name}</h3><p className="star-intro">{star.intro}</p><p>{star.publicFact}</p><div className="star-links"><ExternalLink className="button button-outline" href={star.sourceUrl}>Representative event ↗</ExternalLink>{relatedMatch?.platformUrl && <ExternalLink className="text-link" href={relatedMatch.platformUrl}>Open match source</ExternalLink>}{star.newsUrl && <ExternalLink className="text-link" href={star.newsUrl}>{star.newsTitle ?? 'WTT story'} ↗</ExternalLink>}</div><div className="social-row"><span>OFFICIAL SOCIAL</span>{star.socialUrl ? <><ExternalLink href={star.socialUrl}>Weibo profile ↗</ExternalLink><small>{star.socialStatus}</small></> : <small>{star.socialStatus}</small>}</div></div>
            </article>;
          })}</div>
        </section>}

        {page === 'feedback' && <FeedbackPage count={feedbackCount} saved={feedbackSaved} onSave={saveFeedback} onDownload={downloadFeedback} />}
      </main>

      <footer className="site-footer"><span>PTTI WEB MVP · v0.1</span><span>External links remain with their original publishers.</span><button onClick={() => setPage('feedback')}>User test & feedback</button></footer>
    </div>
  );
}

function MatchCard({ match }: { match: MatchRecord }) {
  const route = match.videoOriginalUrl ?? match.platformUrl;
  const buttonText = match.videoOriginalUrl ? 'Open official video' : 'Open official event page';
  return <article className="match-card">
    <div className="match-art" aria-hidden="true"><div className="match-art-top"><span>PTTI</span><span>{match.eventYear}</span></div><div className="table-mark"><span /><i /><b /></div><div className="match-art-bottom"><span>{match.discipline}</span><span>{match.round.toUpperCase()}</span></div></div>
    <div className="match-card-body"><div className="card-meta"><span>{match.eventCategory}</span><span>{match.discipline} · {match.round}</span></div><h3>{match.players.map((player, index) => <span key={player}>{index > 0 && <span className="versus"> vs </span>}{player}</span>)}</h3><p className="event-name">{match.event}</p>{match.result && <p className="result-line">{match.result}</p>}
      <div className="source-status"><span className={match.sourceStatus === 'official-listing-found' ? 'status-dot found' : 'status-dot pending'} />{match.sourceStatus === 'official-listing-found' ? 'Official media listing found' : 'No match-specific watch route verified'}</div>
      <div className="source-detail"><span>PLATFORM</span><strong>{match.platform}</strong><span>PLAYBACK</span><strong>{match.playbackTested ? 'Tested' : 'Not tested'}</strong><span>LAST CHECKED</span><strong>{match.lastVerifiedAt}</strong><span>REGION</span><strong>{match.regionRestriction.startsWith('Unknown') ? 'Unknown / may vary' : match.regionRestriction}</strong><span>EMBED</span><strong>{match.embedAllowed === null ? 'Not verified' : match.embedAllowed ? 'Allowed' : 'Not allowed'}</strong></div>
      <p className="match-note">{match.note}</p>
      <div className="match-actions">{route ? <ExternalLink className="button button-primary" href={route}>{buttonText} <span aria-hidden="true">↗</span></ExternalLink> : <span className="no-route" role="status">No match-specific official watch URL is verified in this sample.</span>}{match.sourceEvidence[0] && <ExternalLink className="evidence-link" href={match.sourceEvidence[0]}>Evidence</ExternalLink>}</div>
    </div>
  </article>;
}

function PageIntro({ kicker, title, description }: { kicker: string; title: string; description: string }) {
  return <div className="page-intro"><p className="eyebrow">{kicker}</p><h1>{title}</h1><p>{description}</p></div>;
}

function FeedbackPage({ count, saved, onSave, onDownload }: { count: number; saved: boolean; onSave: (entry: FeedbackEntry) => void; onDownload: () => void }) {
  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const entry: FeedbackEntry = {
      id: crypto.randomUUID(),
      createdAt: new Date().toISOString(),
      role: form.get('role') as FeedbackEntry['role'],
      foundMatch: form.get('foundMatch') as FeedbackEntry['foundMatch'],
      clickOutcome: form.get('clickOutcome') as FeedbackEntry['clickOutcome'],
      statusClarity: Number(form.get('statusClarity')),
      friction: String(form.get('friction') ?? '').trim().slice(0, 500),
      returnIntent: form.get('returnIntent') as FeedbackEntry['returnIntent'],
    };
    onSave(entry);
    event.currentTarget.reset();
  }

  return <section className="page-section feedback-layout">
    <div><PageIntro kicker="USER TEST · LOCAL ONLY" title="Help us make the next click easier." description="A short test record helps us learn whether fans can find a match and understand its source." /><div className="feedback-summary"><strong>{count}</strong><span>responses saved in this browser</span><button className="text-button" onClick={onDownload}>Export local responses ↓</button></div><div className="privacy-note"><strong>No name or email needed.</strong><p>Your answers stay in this browser’s local storage until you choose to export them. PTTI does not send them to a server.</p></div></div>
    <form className="feedback-form" onSubmit={submit}>
      <div className="form-heading"><span>QUICK EXIT SURVEY</span><span>ABOUT 1 MINUTE</span></div>
      <label>Your role<select name="role" defaultValue="fan"><option value="fan">Table tennis fan</option><option value="athlete">Athlete / enthusiast</option><option value="coach">Coach</option><option value="other">Other</option></select></label>
      <label>Could you find the match you were looking for?<select name="foundMatch" defaultValue="yes"><option value="yes">Yes</option><option value="partly">Partly</option><option value="no">No</option></select></label>
      <label>What happened after you opened the official source?<select name="clickOutcome" defaultValue="not-tried"><option value="opened">The source opened</option><option value="blocked">It was blocked or unavailable</option><option value="not-tried">I did not try it</option></select></label>
      <label>How clear was the playback status? <span className="range-hint">1 = unclear · 5 = clear</span><select name="statusClarity" defaultValue="4"><option value="1">1 — Unclear</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5 — Clear</option></select></label>
      <label>Where did anything feel slow or confusing?<textarea name="friction" rows={3} maxLength={500} placeholder="Optional · do not include names or private information" /></label>
      <label>Would you use PTTI again to find a match?<select name="returnIntent" defaultValue="yes"><option value="yes">Yes</option><option value="unsure">Not sure</option><option value="no">No</option></select></label>
      <button className="button button-primary" type="submit">Save feedback on this device</button>
      {saved && <p className="form-success" role="status">Saved locally. Thanks for recording an actual user response.</p>}
      <p className="form-footnote">Only submit observations from a real session. Do not enter personal or sensitive details.</p>
    </form>
    <div className="test-plan-callout"><span>TEST TASK</span><p>“Find Fan Zhendong’s WTT Finals Doha match. Tell us whether PTTI verified playback, then open the official source.”</p><span>There are no research results in this MVP until people complete a real test.</span></div>
  </section>;
}

export default App;
