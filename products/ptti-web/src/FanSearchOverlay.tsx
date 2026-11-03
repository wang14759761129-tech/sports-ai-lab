import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { filterFanClips, searchFanCatalog } from './fan-catalog.mjs';
import type { FanCatalog, FanMatch, FanSource, FanStar } from './fan-catalog.mjs';
import { message } from './i18n';
import { usePublicFanCatalog } from './PublicFanCatalog';
import type { Locale, MessageKey } from './i18n';

type Category = 'matches' | 'stars' | 'highlights' | 'clips';
const key = (category: Category): MessageKey => `search.category.${category}` as MessageKey;
const nameFor = (locale: Locale, star: FanStar) => locale === 'zh-CN'
  ? star.name_zh || star.name_en || star.athlete_id
  : star.name_en || star.name_zh || star.athlete_id;
const matchNames = (catalog: FanCatalog, locale: Locale, match: FanMatch) => match.participants.map((person) => {
  const star = person.athlete_id ? catalog.stars.find((item) => item.athlete_id === person.athlete_id) : undefined;
  return star ? nameFor(locale, star) : person.name_en || person.athlete_id || person.side;
}).join(' vs ');

export function FanSearchOverlay({ locale, onClose, onOpenMatch, onOpenStar, onOpenWatch }: {
  locale: Locale; onClose: () => void; onOpenMatch: (id: string) => void; onOpenStar: (id: string) => void;
  onOpenWatch: (sourceId: string, context?: { matchId: string | null; starId: string | null }) => void;
}) {
  const { catalog, loading, error: loadFailed } = usePublicFanCatalog();
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<Category>('matches');
  const input = useRef<HTMLInputElement>(null);
  const dialog = useRef<HTMLElement>(null);
  const tabsId = useId();
  const t = (id: MessageKey) => message(locale, id);

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    input.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); }
      if (event.key !== 'Tab' || !dialog.current) return;
      const controls = [...dialog.current.querySelectorAll<HTMLElement>('button:not(:disabled), input, a[href]')].filter((node) => node.tabIndex >= 0 && node.getClientRects().length > 0);
      const first = controls[0];
      const last = controls.at(-1);
      if (event.shiftKey && (document.activeElement === first || !dialog.current.contains(document.activeElement))) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => { window.removeEventListener('keydown', onKeyDown); document.body.style.overflow = previousOverflow; if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true }); };
  }, [onClose]);

  const results = useMemo(() => {
    if (!catalog || !query.trim()) return { matches: [] as FanMatch[], stars: [] as FanStar[], highlights: [] as FanSource[], clips: [] as FanSource[] };
    return { ...searchFanCatalog(catalog, query), clips: filterFanClips(catalog, { query }) };
  }, [catalog, query]);
  const activeCount = category === 'matches' ? results.matches.length : category === 'stars' ? results.stars.length : category === 'highlights' ? results.highlights.length : results.clips.length;
  const openSource = (source: FanSource) => onOpenWatch(source.source_id, {
    matchId: source.match_link_status === 'HUMAN_VERIFIED' ? source.canonical_match_id : null,
    starId: null,
  });

  return <div className="fan-search-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section ref={dialog} className="fan-search-dialog" role="dialog" aria-modal="true" aria-labelledby="fan-search-dialog-title">
      <header><div><p className="eyebrow">PTTI · SEARCH</p><h2 id="fan-search-dialog-title">{t('search.dialogTitle')}</h2></div>
        <button type="button" className="button button-outline" onClick={onClose}>{t('search.close')}</button></header>
      <label className="fan-search-overlay-input"><span className="sr-only">{t('nav.search')}</span><input ref={input} type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('fan.searchPlaceholder')} autoComplete="off" /><button type="button" className="button button-outline" disabled={!query} onClick={() => { setQuery(''); input.current?.focus(); }}>{t('fan.clearSearch')}</button></label>
      <p className="fan-search-overlay-hint">{t('search.hint')}</p>
      <div className="fan-search-categories" role="tablist" aria-label={t('aria.navigation')}>
        {(['matches', 'stars', 'highlights', 'clips'] as const).map((item, index, items) => <button type="button" role="tab" id={`${tabsId}-${item}`} aria-controls={`${tabsId}-results`} aria-selected={category === item} tabIndex={category === item ? 0 : -1} className={category === item ? 'active' : ''} key={item} onClick={() => setCategory(item)} onKeyDown={(event) => {
          const next = event.key === 'ArrowRight' ? items[(index + 1) % items.length] : event.key === 'ArrowLeft' ? items[(index + items.length - 1) % items.length] : event.key === 'Home' ? items[0] : event.key === 'End' ? items.at(-1) : null;
          if (next) { event.preventDefault(); setCategory(next); document.getElementById(`${tabsId}-${next}`)?.focus(); }
        }}>{t(key(item))}{query.trim() && <span className="fan-search-count">{results[item].length}</span>}</button>)}
      </div>
      <div className="fan-search-overlay-results" id={`${tabsId}-results`} role="tabpanel" aria-labelledby={`${tabsId}-${category}`} aria-live="polite">
        {loading ? <p role="status">{t('fan.loading')}</p> : loadFailed ? <p role="alert">{t('fan.loadErrorDetail')}</p> : !query.trim() ? <p>{t('search.empty')}</p> : category === 'matches' ? results.matches.map((match) => <article key={match.match_id} className="fan-search-result">
          <div><strong>{matchNames(catalog!, locale, match)}</strong><span>{locale === 'zh-CN' ? match.event_zh || match.event : match.event} · {locale === 'zh-CN' ? match.round_zh || match.round : match.round}</span></div>
          <button type="button" className="button button-outline" onClick={() => onOpenMatch(match.match_id)}>{t('search.openMatch')}</button>
        </article>) : category === 'stars' ? results.stars.map((star) => <article key={star.athlete_id} className="fan-search-result">
          <div><strong>{nameFor(locale, star)}</strong><span>{star.association || t('metadata.noBiography')}</span></div>
          <button type="button" className="button button-outline" onClick={() => onOpenStar(star.athlete_id)}>{t('fan.openStar')}</button>
        </article>) : category === 'highlights' ? results.highlights.map((source) => <article key={source.source_id} className="fan-search-result" data-search-highlight-id={source.source_id}>
          <div><strong>{locale === 'zh-CN' ? source.display_title_zh || source.title : source.title}</strong><span>{locale === 'zh-CN' ? source.event_zh || source.event : source.event} · {t('fan.eventLevelSource')}</span></div>
          {source.url && <button type="button" className="button button-outline" onClick={() => openSource(source)}>{t('fan.openWatch')}</button>}
        </article>) : results.clips.map((source) => <article key={source.source_id} className="fan-search-result">
          <div><strong>{locale === 'zh-CN' ? source.display_title_zh || source.title : source.title}</strong><span>{source.publisher} · {t(`fan.clipType.${source.content_type_claim}` as MessageKey)}</span></div>
          {source.url && <button type="button" className="button button-outline" onClick={() => openSource(source)}>{t('fan.openWatch')}</button>}
        </article>)}
        {!loading && !loadFailed && query.trim() && activeCount === 0 && <p role="status">{category === 'clips' ? t('search.noClips') : t('fan.noSearchResults')}</p>}
      </div>
    </section>
  </div>;
}
