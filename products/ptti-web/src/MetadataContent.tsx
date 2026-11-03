import type { MatchRecord } from './types';
import { message } from './i18n';
import type { Locale, MessageKey } from './i18n';
import { getMatchDestination } from './watch-filter.mjs';

function sourceUrl(match: MatchRecord) {
  const candidates = [getMatchDestination(match)?.url, ...match.sourceEvidence];
  return candidates.find(url => { try { return url && new URL(url).protocol === 'https:'; } catch { return false; } });
}

export function MetadataContent({ locale, matches, view, onSelect }: { locale: Locale; matches: MatchRecord[]; view: 'stars' | 'explore' | 'preview'; onSelect: (id: string) => void }) {
  const t = (key: MessageKey) => message(locale, key);
  const names = [...new Set(matches.filter(sourceUrl).flatMap(match => match.players))];
  const events = matches.filter(sourceUrl).filter((match, index, all) => all.findIndex(other => other.event === match.event) === index);
  return <section className="metadata-content" data-metadata-view={view}>
    <h2>{t(view === 'explore' ? 'metadata.explore' : 'metadata.stars')}</h2><p>{t('metadata.scope')}</p>
    {view !== 'explore' && <div className="metadata-grid">{(view === 'preview' ? names.slice(0, 4) : names).map(name => {
      const associated = matches.filter(match => match.players.includes(name) && sourceUrl(match));
      return <article key={name} data-player-card><span className="eyebrow">{t('stars.player')}</span><h3>{name}</h3><p>{associated.map(match => match.event).filter((event, i, all) => all.indexOf(event) === i).join(' · ')}</p>
        <small>{t('metadata.noBiography')}</small><div className="metadata-links">{associated.map(match => <button type="button" key={match.id} className="text-button" onClick={() => onSelect(match.id)}>{match.players.join(' vs ')} ↗</button>)}
          <a href={sourceUrl(associated[0])} target="_blank" rel="noopener noreferrer">{t('metadata.source')} ↗</a></div></article>;
    })}</div>}
    {view === 'explore' && <>
      <div className="metadata-grid" data-explore-events>{events.map(match => <article key={match.event}><p className="eyebrow">{t('metadata.event')}</p><h3>{match.event}</h3><p>{match.players.join(' vs ')}</p><a href={sourceUrl(match)} target="_blank" rel="noopener noreferrer">{t('metadata.source')} ↗</a><small>{t('metadata.eventNotVideo')}</small></article>)}</div>
      <div className="review-guide-grid" data-review-guide-cards>
        <article data-review-guide-card="stages"><p className="eyebrow">PTTI · REVIEW</p><h3>{t('metadata.boardTitle')}</h3><p>{t('metadata.boardCopy')}</p><small>ptti.quick-annotation/0.2 · observed_rally_stage</small></article>
        <article data-review-guide-card="samples"><p className="eyebrow">PTTI · DATA NOTES</p><h3>{t('metadata.sampleTitle')}</h3><p>{t('metadata.sampleCopy')}</p><small>{t('metadata.sampleScope')}</small></article>
        <article data-review-guide-card="annotation"><p className="eyebrow">PTTI · WORKFLOW</p><h3>{t('metadata.annotationTitle')}</h3><p>{t('metadata.annotationCopy')}</p><small>{t('metadata.annotationScope')}</small></article>
      </div>
      <p>{t('metadata.equipment')}</p>
    </>}
    {!names.length && <p role="status">{t('metadata.noApproved')}</p>}
  </section>;
}
