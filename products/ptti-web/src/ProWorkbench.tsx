import { useEffect, useMemo, useRef, useState } from 'react';
import type { MatchRecord } from './types';
import { message } from './i18n';
import type { Locale, MessageKey } from './i18n';
import {
  applyDemoEditsWithLineage,
  computeDemoSummary,
  createDemoExport,
  DEMO_BUNDLE_URL,
  loadDemoRecord,
  saveDemoRecord,
  updateDemoPoint,
  validateDemoRecord,
  validatePoint,
} from './pro-demo.mjs';
import type { DemoPoint, DemoRecord } from './pro-demo.mjs';
import { TrainingReviewImport } from './TrainingReviewImport';
import { LocalVideoReview } from './LocalVideoReview';

function localStorageOrNull(): Storage | null {
  try { return window.localStorage; } catch { return null; }
}

const optionKeys: Record<string, MessageKey> = {
  player: 'pro.option.player', opponent: 'pro.option.opponent', unknown: 'pro.option.unknown', unclear: 'pro.option.unclear', not_applicable: 'pro.option.notApplicable',
  forehand: 'pro.option.forehand', backhand: 'pro.option.backhand', middle: 'pro.option.middle', other: 'pro.option.other',
  short: 'pro.option.short', half_long: 'pro.option.halfLong', long: 'pro.option.long',
  backspin: 'pro.option.backspin', sidespin: 'pro.option.sidespin', topspin: 'pro.option.topspin', no_spin: 'pro.option.noSpin', mixed: 'pro.option.mixed',
  push: 'pro.option.push', flick: 'pro.option.flick', chiquita: 'pro.option.chiquita', drive: 'pro.option.drive', loop: 'pro.option.loop', long_push: 'pro.option.longPush', short_touch: 'pro.option.shortTouch',
  yes: 'pro.option.yes', no: 'pro.option.no', successful: 'pro.option.successful', unsuccessful: 'pro.option.unsuccessful', win: 'pro.option.win', loss: 'pro.option.loss',
};

const fieldChoices: { field: keyof DemoPoint; label: MessageKey; options: string[] }[] = [
  { field: 'serve_side', label: 'pro.field.serveSide', options: ['forehand', 'backhand', 'unclear', 'not_applicable', 'unknown'] },
  { field: 'serve_length', label: 'pro.field.serveLength', options: ['short', 'half_long', 'long', 'unclear', 'not_applicable', 'unknown'] },
  { field: 'serve_location', label: 'pro.field.serveLocation', options: ['forehand', 'middle', 'backhand', 'unclear', 'not_applicable', 'unknown'] },
  { field: 'serve_spin', label: 'pro.field.serveSpin', options: ['backspin', 'sidespin', 'topspin', 'no_spin', 'mixed', 'unclear', 'not_applicable', 'unknown'] },
  { field: 'receive_type', label: 'pro.field.receiveType', options: ['push', 'flick', 'chiquita', 'drive', 'loop', 'long_push', 'short_touch', 'other', 'unclear', 'not_applicable', 'unknown'] },
  { field: 'third_ball_attack', label: 'pro.field.thirdAttack', options: ['yes', 'no', 'unclear', 'not_applicable', 'unknown'] },
  { field: 'third_ball_side', label: 'pro.field.thirdSide', options: ['forehand', 'backhand', 'other', 'unclear', 'not_applicable', 'unknown'] },
  { field: 'third_ball_outcome', label: 'pro.field.thirdOutcome', options: ['successful', 'unsuccessful', 'unclear', 'not_applicable', 'unknown'] },
];

function rowKey(point: DemoPoint) { return `${point.game_number}:${point.point_number}`; }
function pointLabel(locale: Locale, point: DemoPoint) { return locale === 'zh-CN' ? `${point.game_number}局第${point.point_number}分` : `Game ${point.game_number} · Point ${point.point_number}`; }
function valueLabel(t: (key: MessageKey) => string, value: string | number) { return typeof value === 'string' && optionKeys[value] ? t(optionKeys[value]) : String(value); }
function percent(value: number | null) { return value === null ? '—' : `${(value * 100).toFixed(1)}%`; }
function statusMessage(status: string): MessageKey {
  return status === 'NOT_ESTIMABLE' ? 'pro.status.notEstimable' : status === 'INSUFFICIENT_SAMPLE' ? 'pro.status.insufficient' : 'pro.status.descriptive';
}

export function ProWorkbench({ locale, realMatch, active = true, oneGameMode = false, onBrowseMatches, onOpenProLab, onReturnMyMatches, onOpenJournal }: { locale: Locale; realMatch?: MatchRecord; active?: boolean; oneGameMode?: boolean; onBrowseMatches?: () => void; onOpenProLab?: () => void; onReturnMyMatches?: () => void; onOpenJournal?: () => void }) {
  const t = (key: MessageKey) => message(locale, key);
  const [record, setRecord] = useState<DemoRecord | null>(null);
  const [sourceRecord, setSourceRecord] = useState<DemoRecord | null>(null);
  const [savedRecord, setSavedRecord] = useState<DemoRecord | null>(null);
  const [history, setHistory] = useState<DemoRecord[]>([]);
  const [loadIssue, setLoadIssue] = useState<'unavailable' | 'invalid' | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [selectedKey, setSelectedKey] = useState('1:1');
  const [draft, setDraft] = useState<DemoPoint | null>(null);
  const [saveState, setSaveState] = useState<'idle' | 'dirty' | 'saved' | 'memory-only' | 'invalid'>('idle');
  const [saveError, setSaveError] = useState('');
  const [downloaded, setDownloaded] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const demoLoadedRef = useRef(false);

  useEffect(() => {
    if (oneGameMode || demoLoadedRef.current) {
      setLoading(false);
      return undefined;
    }
    let active = true;
    async function loadBundle() {
      setLoading(true);
      setLoadError(false);
      try {
        const response = await fetch(DEMO_BUNDLE_URL, { headers: { Accept: 'application/json' } });
        if (!response.ok) throw new Error('Demo bundle request failed');
        const source = await response.json();
        if (!validateDemoRecord(source).ok) throw new Error('Demo bundle does not match MainDex contract');
        const loaded = await loadDemoRecord(localStorageOrNull(), source);
        if (!loaded.record || loaded.history.length === 0) throw new Error('Demo bundle could not be safely loaded');
        if (!active) return;
        demoLoadedRef.current = true;
        setRecord(loaded.record);
        setSourceRecord(source);
        setSavedRecord(loaded.record);
        setHistory(loaded.history);
        setLoadIssue(loaded.issue === 'invalid' || loaded.issue === 'unavailable' ? loaded.issue : null);
        const first = loaded.record.points[0];
        setSelectedKey(rowKey(first));
        setDraft(structuredClone(first));
      } catch {
        if (active) setLoadError(true);
      } finally {
        if (active) setLoading(false);
      }
    }
    void loadBundle();
    return () => { active = false; };
  }, [retryCount, oneGameMode]);

  const summary = useMemo(() => computeDemoSummary(record?.points ?? []), [record]);
  const baseline = useMemo(() => computeDemoSummary(sourceRecord?.points ?? []), [sourceRecord]);
  const attackRate = summary.third_ball_attack_rate;
  const immediateRate = summary.third_ball_immediate_outcome.rate;
  const pointWins = summary.point_wins;
  const distribution = summary.serve_distributions.serve_length;
  const currentEdit = record?.dataset.provenance.method === 'SIMULATED_INTERACTIVE_EDIT' ? record.dataset.provenance : null;
  const editHistory = history.slice(1).flatMap((snapshot) => {
    const provenance = snapshot.dataset.provenance;
    return provenance.method === 'SIMULATED_INTERACTIVE_EDIT' ? [{ datasetId: snapshot.dataset.dataset_id, edit: provenance.edit }] : [];
  });

  function choosePoint(key: string) {
    if (!record) return;
    const point = record.points.find((item) => rowKey(item) === key);
    if (!point) return;
    setSelectedKey(key);
    setDraft(structuredClone(point));
    setSaveState((current) => current === 'dirty' ? current : 'idle');
  }

  function editField(field: keyof DemoPoint, value: string) {
    if (!draft || !record) return;
    let next = { ...draft, [field]: value } as DemoPoint;
    if (field === 'third_ball_attack') {
      const applicable = value === 'no' || value === 'not_applicable';
      const preserve = value === 'yes' && draft.third_ball_attack === 'yes';
      next = {
        ...next,
        third_ball_side: applicable ? 'not_applicable' : preserve ? draft.third_ball_side : 'unknown',
        third_ball_outcome: applicable ? 'not_applicable' : preserve ? draft.third_ball_outcome : 'unknown',
      };
    }
    setDraft(next);
    if (validatePoint(next).ok) setRecord((current) => current ? updateDemoPoint(current, next) : current);
    setSaveState('dirty');
    setSaveError('');
    setDownloaded(false);
  }

  async function finalizeCurrentEdits() {
    if (!record || !savedRecord) throw new Error('No editable demo record is loaded');
    return applyDemoEditsWithLineage(savedRecord, record, history);
  }

  async function savePoint() {
    if (!record || !savedRecord || !draft || !validatePoint(draft).ok) {
      setSaveState('invalid');
      return;
    }
    try {
      const preview = updateDemoPoint(record, draft);
      const finalized = await applyDemoEditsWithLineage(savedRecord, preview, history);
      setRecord(finalized.record);
      setSavedRecord(finalized.record);
      setHistory(finalized.history);
      setDraft(structuredClone(finalized.record.points.find((point) => rowKey(point) === selectedKey)!));
      const result = await saveDemoRecord(localStorageOrNull(), finalized.record, finalized.history);
      if (!result.ok && result.reason !== 'storage unavailable') throw new Error(result.reason);
      setSaveError('');
      setSaveState(result.ok ? 'saved' : 'memory-only');
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Validation failed');
      setSaveState('invalid');
    }
  }

  async function exportRecord() {
    if (!record || !savedRecord) return;
    try {
      const finalized = await finalizeCurrentEdits();
      const exported = await createDemoExport(finalized.record, finalized.history);
      const blob = new Blob([JSON.stringify(exported, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'ptti-match-intelligence-simulated-demo-export.json';
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setDownloaded(true);
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Export validation failed');
      setDownloaded(false);
    }
  }

  const rateDelta = attackRate.value === null || baseline.third_ball_attack_rate.value === null
    ? '—'
    : `${((attackRate.value - baseline.third_ball_attack_rate.value) * 100).toFixed(1)} pp`;
  const percentShares = (metric: { counts: Record<string, number>; shares_of_observed: Record<string, number> }) => Object.entries(metric.counts).map(([key, count]) => `${valueLabel(t, key)} ${count} (${percent(metric.shares_of_observed[key])})`).join(' · ');

  return <section className="pro-workbench" aria-labelledby={oneGameMode ? 'local-video-title' : 'pro-title'}>
    {!oneGameMode && <header className="pro-heading">
      <div><p className="eyebrow">PTTI · MATCH CENTER</p><h2 id="pro-title">{t('cinema.workspace.title')}</h2><p>{t('cinema.workspace.description')}</p><small>{t('cinema.workspace.scope')}</small></div>
    </header>}

    <LocalVideoReview locale={locale} active={active} oneGameMode={oneGameMode} onBrowseMatches={onBrowseMatches} onOpenProLab={onOpenProLab} onReturnMyMatches={onReturnMyMatches} onOpenJournal={onOpenJournal} />

    {!oneGameMode && <details className="cinema-more-tools"><summary>{t('cinema.moreTools')}</summary>
    <TrainingReviewImport locale={locale} />

    {realMatch && <aside className="pro-no-real-data" role="status">
      <strong>{t('pro.realEmptyTitle')}</strong><p>{t('pro.realEmptyDescription')}</p>
      <small>{realMatch.event} · {realMatch.bridge?.matchId || realMatch.id}</small>
    </aside>}

    {loading && <div className="state-card" role="status"><span className="spinner" />{t('pro.loading')}</div>}
    {!loading && loadError && <div className="state-card state-error" role="alert"><strong>{t('pro.loadError')}</strong><button className="button" type="button" onClick={() => setRetryCount((count) => count + 1)}>{t('pro.retry')}</button></div>}

    {!loading && record && <section className="pro-demo-lab" data-demo-match-id={record.dataset.match_id} data-dataset-class={record.dataset.dataset_class} data-contract-version={record.contract_version} aria-labelledby="demo-title">
      <div className="pro-demo-title"><div><p className="eyebrow">{t('pro.demoKicker')}</p><h3 id="demo-title">{t('pro.demoTitle')}</h3></div><span className="demo-status-badge">SIMULATED_ONLY · DEMO</span></div>
      <p className="pro-demo-warning">{t('pro.demoWarning')}</p>
      <p className="pro-manual-csv-note">{t('pro.manualCsvNotice')}</p>
      {loadIssue && <p className="pro-storage-warning" role="status">{t(loadIssue === 'invalid' ? 'pro.storageRecovered' : 'pro.storageUnavailable')}</p>}

      <div className="pro-match-label"><strong>{record.dataset.dataset_id}</strong><span>{t('pro.playerA')} · {t('pro.playerB')}</span><small>{t('pro.identitySpace')} · {record.dataset.match_id}</small><small>{t('pro.protocolLabel')} · {record.contract_version} · Protocol v{record.dataset.source_protocol.version}</small><small>{t('pro.pointCount')}: {summary.point_count} · {t('pro.gameCount')}: {Object.keys(summary.by_game).length}</small></div>

      <section className="pro-source-panel" aria-labelledby="pro-source-title">
        <div><p className="eyebrow">{t('pro.sourceKicker')}</p><h4 id="pro-source-title">{t('pro.sourceTitle')}</h4></div>
        <dl>
          <dt>{t('pro.datasetId')}</dt><dd data-lineage-dataset>{record.dataset.dataset_id}</dd>
          <dt>{t('pro.provenance')}</dt><dd data-lineage-method>{record.dataset.provenance.method}</dd>
          <dt>{t('pro.evidenceStatus')}</dt><dd>SIMULATED_ONLY</dd>
          <dt>{t('pro.sourceBinding')}</dt><dd>{record.dataset.source_binding.status}</dd>
          <dt>{t('pro.protocolRevision')}</dt><dd>{record.dataset.source_protocol.schema_revision}</dd>
          {currentEdit ? <>
            <dt>{t('pro.parentDataset')}</dt><dd data-lineage-parent>{currentEdit.parent_dataset_id}</dd>
            <dt>{t('pro.parentSha')}</dt><dd className="break-all" data-lineage-sha>{currentEdit.parent_input_sha256}</dd>
            <dt>{t('pro.editHistory')}</dt><dd><ol className="pro-edit-history">{editHistory.map(({ datasetId, edit }) => <li key={datasetId} data-lineage-edit>{edit.point_id} · <code>{edit.field}</code> · {String(edit.before)} → {String(edit.after)}</li>)}</ol></dd>
            <dt>{t('pro.chainLength')}</dt><dd>{history.length} {t('pro.snapshots')}</dd>
          </> : <>
            <dt>{t('pro.parentDataset')}</dt><dd>{t('pro.notApplicable')}</dd>
            <dt>{t('pro.parentSha')}</dt><dd>{t('pro.notApplicable')}</dd>
            <dt>{t('pro.editHistory')}</dt><dd>{t('pro.noEditYet')}</dd>
          </>}
        </dl>
        <p>{t('pro.shaCaution')}</p>
      </section>

      <section className="pro-points-section" aria-labelledby="pro-points-title">
        <div className="pro-stats-heading"><div><p className="eyebrow">{t('pro.pointsKicker')}</p><h4 id="pro-points-title">{t('pro.pointsTitle')}</h4></div><span>{summary.point_count} {t('pro.pointsUnit')}</span></div>
        <div className="pro-table-scroll" role="region" aria-label={t('pro.pointsTitle')} tabIndex={0}>
          <table className="pro-points-table">
            <thead><tr><th>{t('pro.gamePoint')}</th><th>{t('pro.field.server')}</th><th>{t('pro.scoreBefore')}</th><th>{t('pro.serveLength')}</th><th>{t('pro.serveSpin')}</th><th>{t('pro.thirdAttack')}</th><th>{t('pro.field.thirdSide')}</th><th>{t('pro.thirdOutcome')}</th><th>{t('pro.pointWinner')}</th><th><span className="sr-only">{t('pro.editPoint')}</span></th></tr></thead>
            <tbody>{record.points.map((point) => <tr key={rowKey(point)} className={selectedKey === rowKey(point) ? 'selected' : undefined} data-point-row={rowKey(point)}>
              <th scope="row">{pointLabel(locale, point)}</th>
              <td>{valueLabel(t, point.server)}</td>
              <td>{point.server_score_before} – {point.receiver_score_before}</td>
              <td>{valueLabel(t, point.serve_length)}</td><td>{valueLabel(t, point.serve_spin)}</td>
              <td>{valueLabel(t, point.third_ball_attack)}</td><td>{valueLabel(t, point.third_ball_side)}</td><td>{valueLabel(t, point.third_ball_outcome)}</td><td>{valueLabel(t, point.point_winner)}</td>
              <td><button className="pro-row-edit" type="button" aria-label={`${t('pro.editPoint')} ${pointLabel(locale, point)}`} onClick={() => choosePoint(rowKey(point))}>{t('pro.editPoint')}</button></td>
            </tr>)}</tbody>
          </table>
        </div>
        <p className="pro-table-note">{t('pro.scoreNote')}</p>
      </section>

      {draft && <>
        <label className="pro-point-picker"><span>{t('pro.choosePoint')}</span><select aria-label={t('pro.choosePoint')} value={selectedKey} onChange={(event) => choosePoint(event.target.value)}>
          {record.points.map((point) => <option key={rowKey(point)} value={rowKey(point)}>{pointLabel(locale, point)} · {t('pro.thirdAttackShort')}: {valueLabel(t, point.third_ball_attack)}</option>)}
        </select></label>
        <div className="pro-editor-heading"><div><h4>{t('pro.editorTitle')}</h4><p>{t('pro.editorHint')}</p></div></div>
        <form className="pro-point-editor" onSubmit={(event) => { event.preventDefault(); void savePoint(); }}>
          <div className="pro-point-meta"><span>{pointLabel(locale, draft)}</span><span>{t('pro.playerA')} · {t('pro.playerB')}</span></div>
          <div className="pro-fields">
            {fieldChoices.map(({ field, label, options }) => <label key={field}>
              <span>{t(label)}</span>
              <select aria-label={t(label)} value={String(draft[field])} onChange={(event) => editField(field, event.target.value)}>
                {options.map((value) => <option key={value} value={value}>{valueLabel(t, value)}</option>)}
              </select>
            </label>)}
          </div>
          <p className="pro-uncertainty-note">{t('pro.uncertainty')}</p>
          <div className="pro-actions">
            <button className="button button-primary" type="submit">{t('pro.savePoint')}</button>
            <button className="button button-secondary" type="button" onClick={() => { void exportRecord(); }}>{t('pro.export')}</button>
          </div>
          <p className="pro-save-status" role="status" aria-live="polite">
            {saveState === 'saved' ? t('pro.saved') : saveState === 'memory-only' ? t('pro.memoryOnly') : saveState === 'invalid' ? t('pro.invalidPoint') : saveState === 'dirty' ? t('pro.unsaved') : downloaded ? t('pro.exported') : ''}
          </p>
          {saveError && <p className="form-error" role="alert">{saveError}</p>}
        </form>
      </>}

      <section className="pro-stats" aria-labelledby="pro-stats-title">
        <div className="pro-stats-heading"><div><p className="eyebrow">{t('pro.statsKicker')}</p><h4 id="pro-stats-title">{t('pro.statsTitle')}</h4></div><span>{t('pro.statsSource')} · {summary.point_count} {t('pro.pointsUnit')}</span></div>
        {summary.point_count === 0 ? <p className="pro-no-records" role="status">{t('pro.noData')}</p> : <>
          <p className="pro-baseline-note" data-stat-delta>{t('pro.baselineAttack')} {percent(baseline.third_ball_attack_rate.value)} → {percent(attackRate.value)} ({rateDelta})</p>
          <div className="pro-stat-grid">
            <article><h5>{t('pro.pointWins')}</h5><p>{t('pro.option.player')} <strong data-stat="player-wins">{pointWins.counts.player}</strong> · {t('pro.option.opponent')} <strong>{pointWins.counts.opponent}</strong></p><small>{t('pro.winnerDenominator')} {pointWins.denominator} · {percent(pointWins.rates.player.value)} · {t(statusMessage(pointWins.status))}</small><small>{t('pro.pointWinsBasis')}</small></article>
            <article><h5>{t('pro.serveLength')}</h5><p data-stat="serve-length-counts">{percentShares(distribution)}</p><small>{t('pro.observedCount')} {distribution.observed_denominator}/{distribution.eligible_denominator} · {t('pro.uncertainCount')} {distribution.unknown_count + distribution.unclear_count} · {t('pro.notApplicable')} {distribution.not_applicable_count} · {t(statusMessage(distribution.status))}</small><small>{t('pro.serveBasis')}</small></article>
            <article><h5>{t('pro.serveSpin')}</h5><p>{percentShares(summary.serve_distributions.serve_spin)}</p><small>{t('pro.observedCount')} {summary.serve_distributions.serve_spin.observed_denominator}/{summary.serve_distributions.serve_spin.eligible_denominator} · {t('pro.uncertainCount')} {summary.serve_distributions.serve_spin.unknown_count + summary.serve_distributions.serve_spin.unclear_count} · {t(statusMessage(summary.serve_distributions.serve_spin.status))}</small><small>{t('pro.serveBasis')}</small></article>
            <article><h5>{t('pro.thirdAttack')}</h5><p>{t('pro.option.yes')} <strong data-stat="third-yes">{attackRate.numerator}</strong> · {t('pro.option.no')} <strong data-stat="third-no">{record.points.filter((point) => point.third_ball_attack === 'no').length}</strong></p><p>{t('pro.attackRate')} <strong data-stat="third-rate">{percent(attackRate.value)}</strong> <small>({attackRate.numerator}/{attackRate.denominator}) · {t(statusMessage(attackRate.status))}</small></p><small>{t('pro.unresolved')} {attackRate.unresolved_eligibility} · {t('pro.notApplicable')} {attackRate.not_applicable}</small><small>{t('pro.attackBasis')}</small></article>
            <article><h5>{t('pro.thirdBallSide')}</h5><p>{percentShares(summary.third_ball_attack_side)}</p><small>{t('pro.observedCount')} {summary.third_ball_attack_side.observed_denominator}/{summary.third_ball_attack_side.eligible_denominator} · {t('pro.uncertainCount')} {summary.third_ball_attack_side.unknown_count + summary.third_ball_attack_side.unclear_count} · {t(statusMessage(summary.third_ball_attack_side.status))}</small><small>{t('pro.thirdSideBasis')}</small></article>
            <article><h5>{t('pro.thirdOutcome')}</h5><p>{t('pro.option.successful')} <strong>{immediateRate.numerator}</strong> · {t('pro.option.unsuccessful')} <strong>{immediateRate.denominator - immediateRate.numerator}</strong></p><p>{t('pro.outcomeRate')} <strong data-stat="third-outcome-rate">{percent(immediateRate.value)}</strong> <small>({immediateRate.numerator}/{immediateRate.denominator}) · {t(statusMessage(immediateRate.status))}</small></p><small>{t('pro.outcomeDenominator')} {summary.third_ball_attack_rate.numerator} · {t('pro.unresolved')} {immediateRate.unknown + immediateRate.unclear}</small><small>{t('pro.outcomeBasis')}</small></article>
            <article><h5>{t('pro.pointConversion')}</h5><p><strong data-stat="point-conversion">{percent(summary.third_ball_point_conversion.value)}</strong> <small>({summary.third_ball_point_conversion.numerator}/{summary.third_ball_point_conversion.denominator}) · {t(statusMessage(summary.third_ball_point_conversion.status))}</small></p><small>{t('pro.conversionExcluded')} {summary.third_ball_point_conversion.excluded_confirmed_attack_rows}</small><small>{t('pro.conversionBasis')}</small></article>
            <article><h5>{t('pro.serverWinRate')}</h5><p><strong>{percent(summary.server_point_win_rate.value)}</strong> <small>({summary.server_point_win_rate.numerator}/{summary.server_point_win_rate.denominator}) · {t(statusMessage(summary.server_point_win_rate.status))}</small></p><small>{t('pro.excludedRows')} {summary.server_point_win_rate.excluded_rows}</small><small>{t('pro.serverWinBasis')}</small></article>
            <article><h5>{t('pro.rallyLength')}</h5><p><strong>{summary.rally_length.mean === null ? '—' : summary.rally_length.mean}</strong> <small>({summary.rally_length.numerator_sum}/{summary.rally_length.denominator}) · {t(statusMessage(summary.rally_length.status))}</small></p><small>{t('pro.uncertainCount')} {summary.rally_length.unknown_count + summary.rally_length.unclear_count} · {t('pro.notApplicable')} {summary.rally_length.not_applicable_count}</small><small>{t('pro.rallyBasis')}</small></article>
          </div>
          <p className="pro-threshold-note">{t('pro.thresholdNote')}</p>
        </>}
      </section>
      <p className="pro-local-note">{t('pro.localOnly')}</p>
    </section>}
    </details>}
  </section>;
}
