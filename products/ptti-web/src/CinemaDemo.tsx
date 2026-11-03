import { useEffect, useState } from 'react';
import { catalogMode, isLocalReleaseCandidate } from './catalog-mode';
import { prepareQuickSource, validateReviewTargets } from './review-targets.mjs';
import type { ReviewTargetsV01 } from './contracts/review-targets-v0.1';
import { message } from './i18n';
import type { Locale, MessageKey } from './i18n';

export function CinemaDemo({ locale, onLoad, onLoaded, canReplace }: { locale: Locale; onLoad: (quick: unknown, targets: ReviewTargetsV01) => Promise<boolean>; onLoaded?: () => void; canReplace: boolean }) {
  const t = (key: MessageKey) => message(locale, key);
  const [demo, setDemo] = useState<{ quick: unknown; targets: ReviewTargetsV01 } | null>(null);
  const [issue, setIssue] = useState(false);
  const [loadPending, setLoadPending] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  useEffect(() => {
    if (catalogMode !== 'review' && !isLocalReleaseCandidate) return;
    let active = true;
    void (async () => {
      try {
        const response = await fetch('/__ptti/demo-review.json');
        if (!response.ok) throw new Error('demo-unavailable');
        const payload = await response.json();
        const source = await prepareQuickSource(JSON.stringify(payload.quick));
        const targets = validateReviewTargets(payload.targets, source);
        if (targets.evidence_status !== 'SIMULATED_ONLY') throw new Error('not-demo');
        if (active) setDemo({ quick: payload.quick, targets });
      } catch { if (active) setIssue(true); }
    })();
    return () => { active = false; };
  }, []);
  async function handleLoad() {
    if (!demo || !canReplace || loadPending) return;
    setLoadPending(true);
    setLoadFailed(false);
    try {
      const loaded = await onLoad(demo.quick, demo.targets);
      if (!loaded) {
        setLoadFailed(true);
        return;
      }
      onLoaded?.();
    } catch {
      setLoadFailed(true);
    } finally {
      setLoadPending(false);
    }
  }
  const target = demo?.targets.review_targets.find(item => item.subject_role === 'player' && item.observed_rally_stage === 'END_AFTER_3_4_CONTACTS');
  return <aside className="cinema-demo-panel" data-cinema-demo>
    <p className="eyebrow">INSIGHT / REVIEW</p><h3>{t('cinema.demo.title')}</h3>
    <span className="demo-status-badge">SIMULATED_ONLY</span>
    <p>{t('cinema.demo.boundary')}</p>
    {demo && <><div className="cinema-demo-n"><strong>{demo.targets.sample.point_count}</strong><span>{t('cinema.demo.points')}</span></div>
      {target && <div data-demo-target><strong>{t('cinema.demo.stage')} · N={target.lost_count}</strong>{target.point_ids.map(id => <code key={id}>{id.split('/').at(-1)}</code>)}<p>{t('cinema.demo.noReplay')}</p></div>}
      <button type="button" className="button button-secondary" data-load-golden disabled={!canReplace || loadPending} onClick={() => void handleLoad()}>{t('cinema.demo.load')}</button></>}
    {loadFailed && <p role="alert">{t('cinema.demo.loadFailed')}</p>}
    {!demo && <p role="status">{t(issue ? 'cinema.demo.unavailable' : catalogMode === 'review' || isLocalReleaseCandidate ? 'loading.matches' : 'cinema.demo.private')}</p>}
    <small>{t('cinema.demo.separate')}</small>
  </aside>;
}
