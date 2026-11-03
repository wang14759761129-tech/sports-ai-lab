import { MomentumRiver } from './MomentumRiver';
import { TrainingActionLoop } from './TrainingActionLoop';
import { useEffect, useMemo, useRef, useState } from 'react';
import { message } from './i18n';
import type { Locale, MessageKey } from './i18n';
import type { LocalVideoSession, LocalVideoPoint, LocalGameContext } from './local-video-review.mjs';
import { createPersonalMatchReport, resolvePersonalReportSelection, serializePersonalMatchReport } from './personal-match-report.mjs';
import type { PersonalMatchReport as Report, TrainingQuestion, ReportStage } from './personal-match-report.mjs';
import { createWatchCopyGuard } from './watch-copy-guard.mjs';

export type ReportSelection = { key: string; questionId: string } | null;
const stages: Record<ReportStage['id'], MessageKey> = { AFTER_7_7: 'myMatch.intel.stageAfter7', AFTER_9_9: 'myMatch.intel.stageAfter9', AFTER_10_10: 'myMatch.intel.stageAfter10' };
const events: Record<string, MessageKey> = { TIED: 'myMatch.intel.event.TIED', TAKE_LEAD: 'myMatch.intel.event.TAKE_LEAD', OVERTAKE: 'myMatch.intel.event.OVERTAKE', GAME_END: 'myMatch.intel.event.GAME_END' };
const translate = (locale: Locale) => (key: MessageKey, values: Record<string, string | number> = {}) => Object.entries(values).reduce((text, [name, value]) => text.replaceAll(`{${name}}`, String(value)), message(locale, key));

export function trainingQuestionText(question: TrainingQuestion, locale: Locale) {
  const t = translate(locale);
  if (question.kind === 'KEY_SCORE_RANGE') return t('report.questionKey', { stage: t(stages[question.stage_id]), first: question.first_point, last: question.last_point, n: question.sample_count, a: question.player_a_won, b: question.player_b_won });
  if (question.kind === 'SCORING_RUN') return t('report.questionRun', { player: t(question.side === 'PLAYER_A' ? 'pro.video.playerA' : 'pro.video.playerB'), first: question.first_point, last: question.last_point, n: question.length });
  if (question.kind === 'SERVE_RECEIVE') return t('report.questionServe', { n: question.sample_count });
  return t('report.questionUnknown');
}

function rateLines(report: Report, locale: Locale) {
  const t = translate(locale);
  const rates = report.calculated_results.serve_receive;
  if (rates.status !== 'AVAILABLE' || !rates.players) return [t(rates.status === 'FIRST_SERVER_UNKNOWN' ? 'myMatch.intel.serveUnknownFirst' : rates.status === 'GAME_IN_PROGRESS' ? 'myMatch.intel.serveIncompleteGame' : 'myMatch.intel.serveUnknownPoints')];
  return (['PLAYER_A', 'PLAYER_B'] as const).flatMap((side) => {
    const player = t(side === 'PLAYER_A' ? 'pro.video.playerA' : 'pro.video.playerB');
    return (['serve', 'receive'] as const).map((kind) => {
      const row = rates.players![side][kind];
      return row.rate === null ? t('myMatch.intel.noSampleRate', { player, measure: t(kind === 'serve' ? 'myMatch.intel.serve' : 'myMatch.intel.receive') })
        : t(kind === 'serve' ? 'myMatch.intel.serveRatio' : 'myMatch.intel.receiveRatio', { player, won: row.won, total: row.total, rate: Math.round(row.rate * 100) });
    });
  });
}

export function formatPersonalMatchSummary(report: Report, locale: Locale, selectedQuestionId: string | null) {
  const t = translate(locale); const result = report.calculated_results;
  return [t('report.title'), (report.source.type === 'SIMULATED_DEMO' ? 'SIMULATED DEMO · '+(locale === 'zh-CN' ? '合成记录，非本人或官方比赛；无视频。' : 'Synthetic record, not your match or an official match. No video.') : t('myMatch.manual')), t('report.scope'),
    `${t('report.facts')}: ${result.final.score.player_a}:${result.final.score.player_b} · ${t(result.final.status === 'GAME_COMPLETE' ? 'myMatch.complete' : 'myMatch.inProgress')}`,
    t('report.coverage', { n: report.data_facts.recorded_point_count, known: report.data_facts.server_confirmed_point_count }),
    ...(result.final.winner ? [t('myMatch.finalWinner', { player: t(result.final.winner === 'PLAYER_A' ? 'pro.video.playerA' : 'pro.video.playerB') })] : []),
    t('report.coverageUnknown'),
    `${t('report.calculated')}: ${result.score_progression.map((row) => `${row.point_number}→${row.score_after.player_a}:${row.score_after.player_b}${row.events.length ? ` (${row.events.map((event) => t(events[event])).join(', ')})` : ''}`).join(' · ')}`,
    t('report.stageDefinition'),
    ...result.key_stages.map((stage) => `${t(stages[stage.id])}: ${stage.sample_count === null ? t('report.notReached') : stage.sample_count === 0 ? t('myMatch.intel.reachedNoPoints') : t('report.stageResult', { first: stage.first_point!, last: stage.last_point!, n: stage.sample_count, a: stage.outcomes!.PLAYER_A.won, b: stage.outcomes!.PLAYER_B.won })}`),
    t('report.runDefinition'), ...result.longest_scoring_runs.map((run) => t('report.runFact', { player: t(run.side === 'PLAYER_A' ? 'pro.video.playerA' : 'pro.video.playerB'), first: run.first_point, last: run.last_point, n: run.length })),
    ...(result.longest_scoring_runs.length === 0 ? [t('report.noRun')] : []),
    ...rateLines(report, locale), t('report.smallSample'), t('report.questions'),
    ...report.training_questions.map((question) => `${question.question_id === selectedQuestionId ? '★ ' : ''}${trainingQuestionText(question, locale)}`),
    t('myMatch.intel.limitations'), t('report.localOnly'),
  ].join('\n');
}

export function serializePersonalReportForLocale(session: LocalVideoSession, points: readonly LocalVideoPoint[], gameContext: LocalGameContext, locale: Locale, selectedQuestionId: string | null) {
  const output = serializePersonalMatchReport(session, points, gameContext, selectedQuestionId);
  if (!output.ok) return output;
  const report = JSON.parse(output.text) as Report;
  return { ok: true as const, text: `${JSON.stringify({ ...report, presentation: {
    locale, summary_text: formatPersonalMatchSummary(report, locale, selectedQuestionId),
    training_questions: report.training_questions.map((question) => ({ question_id: question.question_id, text: trainingQuestionText(question, locale) })),
  } }, null, 2)}\n` };
}

export function PersonalMatchReportView({ report, locale, selectedQuestionId, disabled, onSelect, onCopy, onExport, onOpenJournal, onOpenPremiere, status = '', manualText = '' }: {
  report: Report; locale: Locale; selectedQuestionId: string | null; disabled: boolean;
  onSelect: (id: string) => void; onCopy?: () => void; onExport?: () => void; onOpenJournal?: () => void; onOpenPremiere?: () => void;
  status?: '' | 'copied' | 'manual' | 'downloaded' | 'error'; manualText?: string;
}) {
  const t = translate(locale); const results = report.calculated_results;
  return <details className="personal-match-report" data-personal-report data-point-intelligence>
    <summary><span>{t('report.title')}</span><strong>{results.final.score.player_a}:{results.final.score.player_b}</strong></summary>
    <div className="personal-report-body">
      <header><p className="eyebrow">{t('report.facts')}</p><h3>{t('report.title')}</h3><p>{(report.source.type === 'SIMULATED_DEMO' ? 'SIMULATED DEMO · '+(locale === 'zh-CN' ? '合成记录，非本人或官方比赛；无视频。' : 'Synthetic record, not your match or an official match. No video.') : t('myMatch.manual'))}</p><small>{t('report.scope')}</small></header>
      <div className="personal-report-score"><strong>{results.final.score.player_a}:{results.final.score.player_b}</strong><span>{t(results.final.status === 'GAME_COMPLETE' ? 'myMatch.complete' : 'myMatch.inProgress')}{results.final.winner && <b>{t('myMatch.finalWinner', { player: t(results.final.winner === 'PLAYER_A' ? 'pro.video.playerA' : 'pro.video.playerB') })}</b>}</span></div>
      <p>{t('report.coverage', { n: report.data_facts.recorded_point_count, known: report.data_facts.server_confirmed_point_count })}</p><small>{t('report.coverageUnknown')}</small>
      {disabled && <p role="status">{t('report.saveFirst')}</p>}
      <MomentumRiver report={report} locale={locale} /><section data-score-calculations><h4>{t('report.calculated')}</h4><p>{t('myMatch.intel.scorePath')}</p>
        <ol className="my-match-score-path">{results.score_progression.map((row) => <li key={row.point_number} data-intel-point={row.point_number} data-score-phase={row.phase}><span>{t('myMatch.intel.pointLabel', { point: row.point_number })}</span><strong>{row.score_after.player_a}:{row.score_after.player_b}</strong><span className="my-match-score-events">{row.events.map((event) => <small key={event} data-score-event={event}>{t(events[event])}</small>)}</span></li>)}</ol>
        <p className="personal-report-definition">{t('report.stageDefinition')}</p>
        <div className="my-match-key-stage-grid">{results.key_stages.map((stage) => <article key={stage.id} data-key-score-stage={stage.id} data-stage-status={stage.status}><strong>{t(stages[stage.id])}</strong><p>{stage.sample_count === null ? t('report.notReached') : stage.sample_count === 0 ? t('myMatch.intel.reachedNoPoints') : t('report.stageResult', { first: stage.first_point!, last: stage.last_point!, n: stage.sample_count, a: stage.outcomes!.PLAYER_A.won, b: stage.outcomes!.PLAYER_B.won })}</p></article>)}</div>
        <p className="personal-report-definition">{t('report.runDefinition')}</p>
        {results.longest_scoring_runs.map((run) => <p className="personal-report-run" key={run.first_point}>{t('report.runFact', { player: t(run.side === 'PLAYER_A' ? 'pro.video.playerA' : 'pro.video.playerB'), first: run.first_point, last: run.last_point, n: run.length })}</p>)}
        {results.longest_scoring_runs.length === 0 && <p>{t('report.noRun')}</p>}
        <div className="my-match-serve-receive" data-serve-receive-status={results.serve_receive.status}><h4>{t('myMatch.intel.serveReceive')}</h4>{rateLines(report, locale).map((line) => <p key={line}>{line}</p>)}</div>
        <p className="personal-report-caution">{t('report.smallSample')}</p>
      </section>
      <section data-training-observation="TRAINING_QUESTION"><p className="eyebrow">{t('report.questions')}</p><p>{t('report.selectQuestion')}</p>
        <fieldset disabled={disabled}><legend>{t('report.choose')}</legend>{report.training_questions.map((question) => <label className="personal-report-question" key={question.question_id}><input type="radio" name="personal-report-question" value={question.question_id} checked={selectedQuestionId === question.question_id} onChange={() => onSelect(question.question_id)} /><span>{trainingQuestionText(question, locale)}</span></label>)}</fieldset>
        <p>{t('myMatch.intel.limitations')}</p>
      </section>
      <TrainingActionLoop report={report} questionId={selectedQuestionId} locale={locale} disabled={disabled} onOpenJournal={onOpenJournal} />
      <div className="personal-report-actions">{onOpenPremiere && <button type="button" onClick={onOpenPremiere}>{locale === 'zh-CN' ? '返回我的比赛故事' : 'Back to my match story'}</button>}{onCopy && <button type="button" className="button button-secondary" onClick={onCopy} disabled={disabled}>{t('report.copy')}</button>}{onExport && <button type="button" className="button button-primary" onClick={onExport} disabled={disabled}>{t('report.export')}</button>}{onOpenJournal && <button type="button" className="button button-outline" onClick={onOpenJournal}>{t('report.journal')}</button>}</div>
      <p>{t('report.localOnly')}</p><small>{t('report.journalHint')}</small>
      {status && <p role="status" aria-live="polite">{t(status === 'copied' ? 'report.copied' : status === 'manual' ? 'report.manual' : status === 'downloaded' ? 'report.downloaded' : 'report.error')}</p>}
      {manualText && <label className="personal-report-manual">{t('report.manual')}<textarea readOnly value={manualText} rows={10} onFocus={(event) => event.currentTarget.select()} /></label>}
    </div>
  </details>;
}

export function PersonalMatchReport({ session, points, gameContext, locale, active, disabled, selection, onSelect, onOpenJournal, onOpenPremiere }: {
  session: LocalVideoSession; points: readonly LocalVideoPoint[]; gameContext: LocalGameContext; locale: Locale; active: boolean; disabled: boolean;
  selection: ReportSelection; onSelect: (value: ReportSelection) => void; onOpenJournal?: () => void; onOpenPremiere?: () => void;
}) {
  const result = useMemo(() => createPersonalMatchReport(session, points, gameContext), [session, points, gameContext]);
  const report = result.ok ? result.value : null;
  const reportKey = JSON.stringify(report);
  const selectedQuestionId = resolvePersonalReportSelection(report, selection);
  const requestKey = JSON.stringify([reportKey, selectedQuestionId, locale, disabled, active]);
  const currentRequest = useRef(requestKey); currentRequest.current = requestKey;
  const copyGuard = useRef(createWatchCopyGuard());
  const [feedback, setFeedback] = useState<{ key: string; status: 'copied' | 'manual' | 'downloaded' | 'error'; manualText?: string } | null>(null);
  useEffect(() => { copyGuard.current.invalidate(); return () => copyGuard.current.invalidate(); }, [requestKey]);
  const t = translate(locale);
  if (!report) return <p className="personal-report-empty" role="status">{t(points.length === 0 ? 'report.empty' : 'report.unavailable')}</p>;
  async function copy() {
    if (disabled || !active || !report) return;
    const key = requestKey; const text = formatPersonalMatchSummary(report, locale, selectedQuestionId);
    const status = await copyGuard.current.copy(text, async (value: string) => {
      if (!navigator.clipboard?.writeText) throw new Error('clipboard-unavailable');
      await navigator.clipboard.writeText(value);
    });
    if (status && currentRequest.current === key) setFeedback({ key, status, manualText: status === 'manual' ? text : undefined });
  }
  function download() {
    if (disabled || !active) return;
    const output = serializePersonalReportForLocale(session, points, gameContext, locale, selectedQuestionId);
    let url: string | null = null;
    try {
      if (!output.ok) throw new Error('report-invalid');
      url = URL.createObjectURL(new Blob([output.text], { type: 'application/json' }));
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'ptti-personal-match-report-v0.1.json'; anchor.click();
      setFeedback({ key: requestKey, status: 'downloaded' });
    } catch { setFeedback({ key: requestKey, status: 'error' }); }
    finally { if (url) { const release = url; window.setTimeout(() => URL.revokeObjectURL(release), 1000); } }
  }
  const currentFeedback = feedback?.key === requestKey ? feedback : null;
  return <PersonalMatchReportView report={report} locale={locale} selectedQuestionId={selectedQuestionId} disabled={disabled || !active} onSelect={(questionId) => onSelect({ key: reportKey, questionId })} onCopy={() => void copy()} onExport={download} onOpenJournal={onOpenJournal} onOpenPremiere={onOpenPremiere} status={currentFeedback?.status} manualText={currentFeedback?.manualText} />;
}
