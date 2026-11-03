import { useEffect, useReducer, useState } from 'react';
import {
  ARENA_TACTICS,
  createArenaChallengeState,
  createArenaLearningTakeaway,
  createArenaTakeawayCopyGuard,
  formatArenaLearningTakeaway,
  reduceArenaChallenge,
} from './arena-challenge.mjs';
import type { ArenaChallengeAction, ArenaChallengeState } from './arena-challenge.mjs';
import { message } from './i18n';
import type { Locale, MessageKey } from './i18n';

export function ArenaChallengePage({ locale, onBack, onOpenJournal }: { locale: Locale; onBack: () => void; onOpenJournal?: () => void }) {
  const [state, dispatch] = useReducer(reduceArenaChallenge, createArenaChallengeState());
  const [copyGuard] = useState(createArenaTakeawayCopyGuard);
  const [copyStatus, setCopyStatus] = useState<'' | 'copied' | 'manual'>('');
  const [manualCopyText, setManualCopyText] = useState('');

  useEffect(() => () => copyGuard.invalidate(), [copyGuard]);
  useEffect(() => {
    copyGuard.invalidate();
    setCopyStatus('');
    setManualCopyText('');
  }, [copyGuard, locale]);

  function act(action: ArenaChallengeAction) {
    if (action.type === 'choose' || action.type === 'retry') {
      copyGuard.invalidate();
      setCopyStatus('');
      setManualCopyText('');
    }
    dispatch(action);
  }

  async function copyTakeaway(text: string) {
    const writeText = typeof navigator !== 'undefined' && navigator.clipboard?.writeText
      ? (value: string) => navigator.clipboard.writeText(value)
      : undefined;
    const result = await copyGuard.copy(text, writeText);
    if (result === null) return;
    setCopyStatus(result);
    setManualCopyText(result === 'manual' ? text : '');
  }

  return <ArenaChallengeView
    locale={locale}
    state={state}
    onAction={act}
    onBack={onBack}
    onOpenJournal={onOpenJournal}
    onCopyTakeaway={copyTakeaway}
    copyStatus={copyStatus}
    manualCopyText={manualCopyText}
  />;
}

export function ArenaChallengeView({ locale, state, onAction, onBack, onOpenJournal, onCopyTakeaway, copyStatus = '', manualCopyText = '' }: {
  locale: Locale;
  state: ArenaChallengeState;
  onAction: (action: ArenaChallengeAction) => void;
  onBack: () => void;
  onOpenJournal?: () => void;
  onCopyTakeaway?: (text: string) => void | Promise<void>;
  copyStatus?: '' | 'copied' | 'manual';
  manualCopyText?: string;
}) {
  const t = (key: MessageKey | string) => message(locale, key as MessageKey);
  const selected = ARENA_TACTICS.find((tactic) => tactic.id === state.selectedChoice);
  const takeaway = state.takeawayGenerated && selected ? createArenaLearningTakeaway(selected.id) : null;
  const takeawayText = selected ? formatArenaLearningTakeaway(selected.id, t) ?? '' : '';
  return <section className="arena-challenge" data-arena-simulated="true" data-arena-attempt={state.attempt} aria-labelledby="arena-title">
    <header className="arena-challenge-toolbar">
      <button type="button" className="button button-outline" data-arena-back onClick={onBack}>{t('arena.back')}</button>
      <span className="arena-challenge-brand">PTTI · ARENA</span>
      <span className="arena-challenge-attempt">{String(state.attempt).padStart(2, '0')}</span>
    </header>

    <div className="arena-challenge-shell">
      <div className="arena-challenge-copy">
        <p className="eyebrow">{t('arena.kicker')}</p>
        <h1 id="arena-title">{t('arena.title')}</h1>
        <p className="arena-challenge-intro">{t('arena.intro')}</p>
        <p className="arena-simulation-note" role="note"><span aria-hidden="true">●</span>{t('arena.simulated')}</p>

        <div className="arena-situation" aria-label={t('arena.scoreLabel')}>
          <div className="arena-situation-label"><span>{t('arena.scoreLabel')}</span><small>{t('arena.scenarioDetail')}</small></div>
          <strong className="arena-score" aria-label={locale === 'zh-CN' ? '9比9' : '9 to 9'} data-arena-score="9:9">9 <i aria-hidden="true">:</i> 9</strong>
          <h2>{t('arena.scenario')}</h2>
        </div>

        <p className="arena-no-answer">{t('arena.noAbsolute')}</p>
      </div>

      <div className="arena-decision-panel">
        <p className="eyebrow">{t('arena.choosePrompt')}</p>
        <div className="arena-choice-list" role="group" aria-label={t('arena.choosePrompt')}>
          {ARENA_TACTICS.map((tactic, index) => <button
            type="button"
            className="arena-choice"
            key={tactic.id}
            data-arena-choice={tactic.id}
            aria-pressed={state.selectedChoice === tactic.id}
            onClick={() => onAction({ type: 'choose', choice: tactic.id })}
          >
            <span className="arena-choice-number" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
            <span className="arena-choice-copy"><strong>{t(tactic.title)}</strong><small>{t(tactic.hint)}</small></span>
            <span className="arena-choice-mark" aria-hidden="true">↗</span>
          </button>)}
        </div>

        {selected ? <section className="arena-result" data-arena-result={selected.id} aria-live="polite" aria-labelledby="arena-result-title">
          <p className="eyebrow">{t('arena.resultTitle')}</p>
          <h2 id="arena-result-title">{t(selected.title)}</h2>
          <dl>
            {(['intent', 'advantage', 'risk', 'when'] as const).map((field) => <div key={field}>
              <dt>{t(`arena.label.${field}`)}</dt>
              <dd>{t(selected[field])}</dd>
            </div>)}
          </dl>
          {!state.takeawayGenerated && <button type="button" className="button button-primary arena-generate-takeaway" data-arena-generate onClick={() => onAction({ type: 'generate-takeaway' })}>{t('arena.learning.generate')}</button>}
          {takeaway && <article className="arena-learning-card" data-arena-learning="simulated" aria-labelledby="arena-learning-title">
            <p className="eyebrow">{t(takeaway.simulated)}</p>
            <h3 id="arena-learning-title">{t('arena.learning.title')}</h3>
            <p className="arena-learning-scenario"><strong>{t('arena.scenarioDetail')}</strong> · {t(takeaway.scenario)}</p>
            <dl>
              {(['choice', 'purpose', 'advantage', 'risk', 'conditions', 'question'] as const).map((field) => <div key={field}>
                <dt>{t(`arena.learning.label.${field}`)}</dt>
                <dd>{field === 'question'
                  ? <>{t(takeaway.question)} {t(takeaway.conditions)}{t('arena.learning.questionEnd')}</>
                  : t(takeaway[field])}</dd>
              </div>)}
            </dl>
            <div className="arena-learning-actions">
              <button type="button" className="button button-primary" data-arena-copy onClick={() => onCopyTakeaway?.(takeawayText)}>{t('arena.learning.copy')}</button>
              {onOpenJournal && <button type="button" className="button button-outline" data-arena-open-journal onClick={onOpenJournal}>{t('arena.learning.openJournal')}</button>}
            </div>
            <p className="arena-learning-journal-hint">{t('arena.learning.journalHint')}</p>
            {copyStatus && <p className="arena-learning-status" role="status" aria-live="polite">{t(copyStatus === 'copied' ? 'arena.learning.copied' : 'arena.learning.copyManual')}</p>}
            {manualCopyText && <label className="arena-learning-manual">{t('arena.learning.manualLabel')}<textarea readOnly value={manualCopyText} rows={8} onFocus={(event) => event.currentTarget.select()} /></label>}
          </article>}
          <button type="button" className="button button-outline arena-retry" data-arena-retry onClick={() => onAction({ type: 'retry' })}>{t('arena.retry')} <span aria-hidden="true">↺</span></button>
        </section> : <p className="arena-selection-prompt" role="status">{t('arena.choosePrompt')}</p>}
      </div>
    </div>
  </section>;
}
