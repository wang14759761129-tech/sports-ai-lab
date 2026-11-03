import { useState } from 'react';
import { ProWorkbench } from './ProWorkbench';
import type { MatchRecord } from './types';
import { message, matchNote } from './i18n';
import type { Locale, MessageKey } from './i18n';
import { getMatchDestination, hasVerifiedVisualPlayback, playerLabel } from './watch-filter.mjs';
import { createSharePng, createShareText } from './match-share.mjs';

export function MatchDetail({ match, locale, pageUrl, onBack }: { match: MatchRecord; locale: Locale; pageUrl: string; onBack: () => void }) {
  const t = (key: MessageKey) => message(locale, key);
  const [centerMode, setCenterMode] = useState<'fan' | 'pro'>('fan');
  const destination = getMatchDestination(match);
  const evidenceUrls = match.sourceEvidence.filter(value => { try { return new URL(value).protocol === 'https:'; } catch { return false; } });
  const verified = hasVerifiedVisualPlayback(match);
  const routeKey = match.routeType === 'unknown' ? 'bridge.sourceUnknown' : match.routeType === 'video-page' ? 'source.route.video' : match.routeType === 'event-page' ? 'source.route.event' : 'source.route.only';
  const statusKey = verified ? 'source.playback.verified' : match.playbackStatus === 'RESTRICTED' ? 'source.playback.restricted' : match.playbackStatus === 'PLAYBACK_FAIL' ? 'source.playback.failed' : 'source.playback.pending';
  const summaryKey = match.routeType === 'unknown' ? 'bridge.sourceUnknownHint' : match.routeType === 'video-page' ? 'match.videoHint' : match.routeType === 'event-page' ? 'match.eventHint' : 'match.articleHint';
  const players = (match.players.length ? match.players : [t('bridge.unchecked')]).map(name => playerLabel(name, locale));
  const round = match.round === 'Final' ? t('event.round.final') : match.round === 'Semifinal' ? t('event.round.semifinal') : match.round === 'Quarterfinal' ? t('event.round.quarterfinal') : match.round;
  const meta = (match.discipline === 'UNKNOWN' ? t('bridge.unchecked') : t(('discipline.' + match.discipline) as MessageKey)) + ' · ' + (round || t('bridge.unchecked'));
  const status = t(statusKey);
  const route = t(routeKey);
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'manual' | 'downloaded' | 'export-error'>('idle');
  const [manualText, setManualText] = useState('');
  const scope = verified ? t('source.playback.verifiedHint') : t(summaryKey);
  const shareText = createShareText({ players, event: match.event, meta, route, status, officialUrl: destination?.url, pageUrl, scope, localHint: t('match.localLink') });
  const shortScope = t(verified ? 'share.scopeVerified' : match.routeType === 'unknown' ? 'bridge.scopeUnknown' : match.routeType === 'video-page' ? 'share.scopePending' : 'share.scopeNoVideo');
  const cardCopy = { players, event: match.event, meta, result: match.result, route, status, checked: t('source.lastChecked') + ' · ' + (match.lastVerifiedAt || t('bridge.unchecked')), footer: shortScope, verified };

  async function copy(value: string) {
    try { await navigator.clipboard.writeText(value); setManualText(''); setCopyStatus('copied'); }
    catch { setManualText(value); setCopyStatus('manual'); }
  }
  async function downloadCard() {
    try {
    const url = URL.createObjectURL(await createSharePng(cardCopy));
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = 'ptti-' + match.id + '-' + locale + '.png'; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setCopyStatus('downloaded');
    } catch { setCopyStatus('export-error'); }
  }
  return <section className="selected-match detail-rc" aria-label={t('center.mode')}>
    <button className="button button-outline" onClick={onBack}>← {t('match.back')}</button>
    <div className="match-center-tabs" role="group" aria-label={t('center.mode')}>
      <button type="button" className={centerMode === 'fan' ? 'active' : ''} aria-pressed={centerMode === 'fan'} onClick={() => setCenterMode('fan')}>{t('center.fan')}</button>
      <button type="button" className={centerMode === 'pro' ? 'active' : ''} aria-pressed={centerMode === 'pro'} onClick={() => setCenterMode('pro')}>{t('center.pro')}</button>
    </div>
    <div hidden={centerMode !== 'fan'}>
    <div className="detail-layout">
      <div className="match-identity">
        <p className="eyebrow">{t('detail.kicker')}</p>
        <p className="detail-event">{match.event || t('bridge.unchecked')}</p>
        <h1 id="selected-match-heading" tabIndex={-1}>{players[0]}<span className="detail-vs">VS</span>{players.slice(1).join(' / ')}</h1>
        {locale === 'zh-CN' && <p className="detail-original-names">{match.players.join(' vs ')}</p>}
        <div className="detail-meta"><span>{meta}</span><span>{t('detail.archive')}</span></div>
        {match.bridge?.identityStatus === 'UNKNOWN' && <p className="bridge-identity-note">{t('bridge.identity')}</p>}
        {match.bridge?.resultInvalid && <p className="bridge-identity-note">{t('bridge.resultIssue')}</p>}
        {match.result && <p className="detail-result"><span>{t('detail.result')}</span>{match.result}</p>}
      </div>
      <article data-source-id={match.bridge?.source?.id} data-match-id={match.id} className="watch-source-card" aria-labelledby="source-heading">
        <p className="eyebrow">{t('detail.watch')}</p><h2 id="source-heading">{match.platform || t('bridge.unchecked')}</h2>
        <div className="match-status-row"><span className={'route-badge route-' + match.routeType}>{route}</span><span className={'playback-badge' + (verified ? ' visual-verified' : '')}>{status}</span></div>
        <div className="match-actions">{destination ? <a className={'button ' + (destination.type === 'video-page' ? 'button-primary' : 'button-outline')} href={destination.url} target="_blank" rel="noopener noreferrer">{t(destination.type === 'video-page' ? 'source.videoButton' : destination.type === 'event-page' ? 'source.eventButton' : match.routeType === 'unknown' ? 'bridge.sourceButton' : 'detail.sourceOnly')} ↗</a> : <p className="no-route" role="status">{t('source.noRoute')}</p>}</div>
        <p className="selected-route-summary">{t(summaryKey)}</p>
        {destination?.type !== 'video-page' && <p className="no-route">{t('detail.noVideo')}</p>}
        {verified && <p className="playback-evidence-note">{t('source.playback.verifiedHint')}</p>}
        {match.bridge && <div className="bridge-source-facts"><dl><dt>{t('bridge.matchId')}</dt><dd>{match.bridge.matchId}</dd><dt>{t('bridge.sourceId')}</dt><dd>{match.bridge.source?.id || t('bridge.unchecked')}</dd><dt>{t('bridge.linkStatus')}</dt><dd>{match.bridge.source?.matchLinkStatus === 'UNKNOWN' ? t('bridge.unchecked') : match.bridge.source?.matchLinkStatus || t('bridge.unchecked')}</dd></dl></div>}
        <details className="detail-evidence"><summary>{t('detail.evidence')}</summary>
          <dl><dt>{t('source.lastChecked')}</dt><dd>{match.lastVerifiedAt || t('bridge.unchecked')}</dd><dt>{t('source.region')}</dt><dd>{match.regionRestriction.toLowerCase().startsWith('unknown') ? t('source.regionUnknown') : match.regionRestriction}</dd><dt>{t('source.embed')}</dt><dd>{match.embedAllowed === null ? t('source.embedUnknown') : match.embedAllowed ? t('source.embedAllowed') : t('source.embedNo')}</dd></dl>
          <p>{match.bridge ? match.note : matchNote(locale, match.id)}</p>
          {match.bridge && <><dl><dt>{t('bridge.eventId')}</dt><dd>{match.bridge.eventId || t('bridge.unchecked')}</dd><dt>{t('bridge.publisher')}</dt><dd>{match.bridge.source?.publisher || t('bridge.unchecked')}</dd></dl>
            <h3>{t('bridge.rights')}</h3><dl>{(['metadata_listing','external_viewing','embedding','thumbnail_display','local_analysis','model_training','redistribution'] as const).map(key => <div className="bridge-fact" key={key}><dt>{key}</dt><dd data-permission={key}>{match.bridge?.source?.rights[key] || 'UNKNOWN'}</dd></div>)}</dl>
            <h3>{t('bridge.evidence')}</h3><dl>{(['page_access','external_video_page','embed_playback','desktop_native_playback'] as const).map(key => <div className="bridge-fact" key={key}><dt>{key}</dt><dd data-evidence={key}>{match.bridge?.source?.evidence[key]?.status || 'UNKNOWN'}</dd></div>)}<dt>{t('bridge.audio')}</dt><dd>{String(match.bridge.source?.evidence.external_video_page?.audio_status || 'UNKNOWN')}</dd></dl>
          </>}
          {evidenceUrls.map(url => <a className="evidence-link" href={url} key={url} target="_blank" rel="noopener noreferrer">{t('source.evidence')} · {new URL(url).hostname} ↗</a>)}
        </details>
      </article>
    </div>
    <section className="match-share-section" aria-labelledby="share-heading">
      <div className="share-intro"><p className="eyebrow">PTTI · MATCH CARD</p><h2 id="share-heading">{t('share.title')}</h2><p>{t('share.description')}</p></div>
      <div className="share-layout">
        <article className="fan-share-card" aria-label={t('share.title')}><div className="fan-card-top"><strong>PTTI</strong><span>{meta}</span></div><p>{match.event}</p><div className="fan-card-players">{players[0]}<small>VS</small>{players.slice(1).join(' / ')}</div>{match.result && <p>{t('detail.result')} · {match.result}</p>}<div className="fan-card-bottom"><strong>{route}</strong><span>{status}</span><small>{t('source.lastChecked')} · {match.lastVerifiedAt || t('bridge.unchecked')}</small><small>{shortScope}</small><small>{t('share.cardFooter')}</small></div></article>
        <div className="match-save"><label htmlFor="match-link">{t('match.saveLabel')}</label><p>{t('match.saveHint')}</p><input id="match-link" readOnly value={pageUrl} onFocus={e => e.target.select()} />
          <div className="share-buttons"><button className="button button-secondary copy-match-link" onClick={() => void copy(pageUrl)}>{t('match.copy')}</button><button className="button button-outline copy-share-text" onClick={() => void copy(shareText)}>{t('share.copyText')}</button><button className="button button-primary download-match-card" onClick={() => void downloadCard()}>{t('share.download')} ↓</button></div>
          <p role="status">{copyStatus === 'copied' ? t('match.copied') : copyStatus === 'manual' ? t('share.manual') : copyStatus === 'downloaded' ? t('share.downloaded') : copyStatus === 'export-error' ? t('share.exportError') : ''}</p>
          {manualText && <label className="manual-share-copy">{t(manualText === pageUrl ? 'match.saveLabel' : 'share.textLabel')}<textarea readOnly value={manualText} rows={5} onFocus={e => e.target.select()} /></label>}
          <p className="share-local-note">{t('match.localLink')}</p>
        </div>
      </div>
    </section>
    </div>
    <div hidden={centerMode !== 'pro'}><ProWorkbench locale={locale} realMatch={match} /></div>
  </section>;
}
