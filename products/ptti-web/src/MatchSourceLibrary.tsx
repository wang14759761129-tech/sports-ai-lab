import { useRef, useState } from 'react';
import { catalogMode } from './catalog-mode';
import { consumeMatchLibrary } from './match-library.mjs';
import type { LibraryProjection } from './match-library.mjs';
import { message } from './i18n';
import type { Locale, MessageKey } from './i18n';

export function MatchSourceLibrary({ locale }: { locale: Locale }) {
  const t = (key: MessageKey) => message(locale, key);
  const [library, setLibrary] = useState<LibraryProjection | null>(null);
  const [issue, setIssue] = useState('');
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const pending = useRef(false);
  async function load() {
    if (pending.current || library) return;
    pending.current = true; setLoading(true); setIssue('');
    try {
      const response = await fetch(catalogMode === 'review' ? '/__ptti/match-library.json' : '/data/match-library-strict-public.json', catalogMode === 'review' ? { headers: { 'X-PTTI-Review': 'local-only' } } : {});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setLibrary(consumeMatchLibrary(await response.json(), catalogMode === 'review' ? 'INTERNAL_REVIEW' : 'STRICT_PUBLIC'));
    } catch (error) { setIssue(error instanceof Error ? error.message : 'invalid-library'); }
    finally { pending.current = false; setLoading(false); }
  }
  const rows = library?.sources.filter(source => `${source.title} ${source.event} ${source.source_id}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())) ?? [];
  return <details className="source-library" data-source-library onToggle={event => { if (event.currentTarget.open) void load(); }}>
    <summary>{t(catalogMode === 'review' ? 'library.reviewTitle' : 'library.publicTitle')}</summary>
    <p>{t(catalogMode === 'review' ? 'library.reviewBoundary' : 'library.publicBoundary')}</p>
    {loading && <p role="status">{t('loading.matches')}</p>}
    {issue && <div role="alert" data-library-error><p>{t('library.failed')} · {issue}</p><button type="button" className="button button-secondary" onClick={() => void load()}>{t('load.retry')}</button></div>}
    {library && <><p data-library-count>{t('library.inventory').replace('{sources}', String(library.source_count)).replace('{matches}', String(library.registered_match_count))}</p>
      {library.sources.length > 0 ? <><label className="source-library-search">{t('library.search')}<input value={query} onChange={event => setQuery(event.target.value)} /></label><div className="metadata-grid">{rows.map(source => <article key={source.source_id} data-library-source={source.source_id}>
        <p className="eyebrow">INTERNAL_REVIEW · {source.platform}</p><h3>{source.title}</h3><p>{source.event} · {source.match_type}</p>
        <p><strong>{t('library.history')}</strong> <code>{source.recorded_playback_status}</code></p><small>{t('library.noCurrentPlayback')} · {source.territory}</small>
        <details><summary>{t('library.audit')}</summary><code className="library-identity">{source.source_id}</code><p>{t('library.identity')} <code>{source.source_identity_status}</code></p><p>{t('library.publisher')} <code>{source.publisher_identity_status}</code></p>
          <dl>{Object.entries(source.rights).map(([key, value]) => <div key={key}><dt>{t(`library.right.${key}` as MessageKey)}</dt><dd>{value}</dd></div>)}</dl><p>{t('library.unlinked')}</p></details>
        {source.url ? <a className="button button-outline" href={source.url} target="_blank" rel="noopener noreferrer">{t('library.openSource')} ↗</a> : <small>{t('library.externalDenied')}</small>}
      </article>)}</div>{!rows.length && <p role="status">{t('empty.title')}</p>}</> : <p role="status" data-library-empty>{t('library.empty')}</p>}</>}
  </details>;
}
