import { useMemo, useRef, useState } from 'react';
import { message } from './i18n';
import type { Locale, MessageKey } from './i18n';
import { independentSourceVerification, metricPointIds, parseTrainingReviewJson } from './training-review.mjs';
import type { TrainingMetricReport, TrainingPointRecord, TrainingReviewReport } from './training-review.mjs';
import { parseTrainingHandoffJson } from './training-handoff.mjs';
import type { VerifiedTrainingHandoff } from './training-handoff.mjs';
import { TrainingQualityReviewPanel } from './TrainingQualityReviewPanel';

const metricLabels: Record<string, MessageKey> = {
  server_point_win_rate: 'pro.report.metric.serverRate',
  receiver_point_win_rate: 'pro.report.metric.receiverRate',
  third_ball_attack_rate: 'pro.report.metric.thirdAttackRate',
  third_ball_point_conversion: 'pro.report.metric.thirdConversion',
  third_ball_immediate_success: 'pro.report.metric.thirdSuccess',
  key_point_player_win_rate: 'pro.report.metric.keyPoints',
  rally_length_mean: 'pro.report.metric.rallyMean',
  serve_side: 'pro.report.distribution.serveSide',
  serve_length: 'pro.report.distribution.serveLength',
  serve_location: 'pro.report.distribution.serveLocation',
  serve_spin: 'pro.report.distribution.serveSpin',
  receive_type: 'pro.report.distribution.receiveType',
  receive_location: 'pro.report.distribution.receiveLocation',
};

const pointFieldLabels: Record<string, MessageKey> = {
  match_id: 'pro.report.field.matchId', game_number: 'pro.report.field.gameNumber', point_number: 'pro.report.field.pointNumber',
  server: 'pro.report.field.server', receiver: 'pro.report.field.receiver', server_score_before: 'pro.report.field.serverScore',
  receiver_score_before: 'pro.report.field.receiverScore', serve_side: 'pro.report.field.serveSide',
  serve_length: 'pro.report.field.serveLength', serve_location: 'pro.report.field.serveLocation',
  serve_spin: 'pro.report.field.serveSpin', receive_type: 'pro.report.field.receiveType',
  receive_location: 'pro.report.field.receiveLocation', third_ball_attack: 'pro.report.field.thirdAttack',
  third_ball_side: 'pro.report.field.thirdSide', third_ball_outcome: 'pro.report.field.thirdOutcome',
  rally_length: 'pro.report.field.rallyLength', point_winner: 'pro.report.field.winner',
  point_outcome: 'pro.report.field.outcome', video_timestamp: 'pro.report.field.timestamp', notes: 'pro.report.field.notes',
};

function percentage(value: number | null) { return value === null ? '—' : `${(value * 100).toFixed(1)}%`; }
function countLabel(metric: TrainingMetricReport) {
  return typeof metric.numerator === 'number' ? `${metric.numerator}/${metric.denominator}` : `${metric.denominator}`;
}
function metricValue(metric: TrainingMetricReport, key: string) {
  if (key === 'rally_length_mean') return metric.value === null ? '—' : metric.value.toFixed(2);
  if (typeof metric.numerator === 'object') return Object.entries(metric.numerator).map(([category, count]) => `${category}: ${count}`).join(' · ') || '—';
  return percentage(metric.value);
}

function handoffErrorKey(cause: unknown): MessageKey {
  const code = cause && typeof cause === 'object' && 'code' in cause ? String(cause.code) : '';
  if (code === 'HANDOFF_JSON_INVALID') return 'pro.quality.error.json';
  if (code === 'HANDOFF_VERSION_UNSUPPORTED') return 'pro.quality.error.version';
  if (code === 'HANDOFF_ROOT_FIELDS_INVALID') return 'pro.quality.error.fields';
  if (code === 'HANDOFF_CSV_HASH_MISMATCH') return 'pro.quality.error.hash';
  if (code === 'HANDOFF_POINT_TRACE_MISMATCH' || code === 'HANDOFF_ROW_COUNT_MISMATCH') return 'pro.quality.error.trace';
  if (code === 'HANDOFF_QUALITY_RECOMPUTATION_MISMATCH') return 'pro.quality.error.audit';
  return 'pro.quality.error.invalid';
}

export function TrainingReviewImport({ locale }: { locale: Locale }) {
  const t = (key: MessageKey) => message(locale, key);
  const inputRef = useRef<HTMLInputElement>(null);
  const [report, setReport] = useState<TrainingReviewReport | null>(null);
  const [fileName, setFileName] = useState('');
  const [error, setError] = useState<MessageKey | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null);
  const [selectedPointId, setSelectedPointId] = useState<string | null>(null);
  const [downloaded, setDownloaded] = useState(false);
  const [rawJson, setRawJson] = useState('');
  const [verifiedHandoff, setVerifiedHandoff] = useState<VerifiedTrainingHandoff | null>(null);

  const selectedRows = useMemo(() => {
    if (!report || !selectedMetric) return [];
    const ids = new Set(metricPointIds(report, selectedMetric));
    return report.point_records.filter((row) => ids.has(row.point_id));
  }, [report, selectedMetric]);
  const selectedPoint = report?.point_records.find((row) => row.point_id === selectedPointId) ?? null;
  const verification = report ? independentSourceVerification(report) : null;

  async function importFile(file?: File) {
    if (!file) return;
    setError(null);
    setDownloaded(false);
    let isHandoff = false;
    try {
      if (file.size > 10 * 1024 * 1024) throw Object.assign(new Error('too large'), { code: 'REPORT_TOO_LARGE' });
      const source = await file.text();
      let candidate: unknown;
      try { candidate = JSON.parse(source); } catch { /* the report parser below returns the localized invalid-report message */ }
      isHandoff = candidate !== null && typeof candidate === 'object' && !Array.isArray(candidate)
        && typeof (candidate as { package_version?: unknown }).package_version === 'string'
        && (candidate as { package_version: string }).package_version.startsWith('ptti.training-handoff/');
      const parsedHandoff = isHandoff ? await parseTrainingHandoffJson(source) : null;
      const parsed = parsedHandoff?.report ?? parseTrainingReviewJson(source);
      setReport(parsed);
      setVerifiedHandoff(parsedHandoff);
      setFileName(file.name);
      setRawJson(source);
      setSelectedMetric(null);
      setSelectedPointId(parsedHandoff?.quality.findings[0]?.point_id ?? parsed.point_records[0]?.point_id ?? null);
    } catch (cause) {
      setReport(null);
      setVerifiedHandoff(null);
      setFileName('');
      setRawJson('');
      setSelectedMetric(null);
      setSelectedPointId(null);
      if (cause && typeof cause === 'object' && 'code' in cause && String(cause.code).startsWith('HANDOFF_')) setError(handoffErrorKey(cause));
      else if (cause && typeof cause === 'object' && 'code' in cause && cause.code === 'REPORT_TOO_LARGE') setError('pro.report.tooLarge');
      else setError('pro.report.invalid');
    } finally {
      if (inputRef.current) inputRef.current.value = '';
    }
  }

  function downloadCopy() {
    if (!rawJson) return;
    const blob = new Blob([rawJson], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = verifiedHandoff ? 'ptti-training-quality-handoff-copy.json' : 'ptti-training-review-report-copy.json';
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setDownloaded(true);
  }

  function clearReport() {
    setReport(null); setVerifiedHandoff(null); setFileName(''); setRawJson(''); setError(null); setSelectedMetric(null); setSelectedPointId(null); setDownloaded(false);
    if (inputRef.current) inputRef.current.value = '';
  }

  function focusReportPoint(pointId: string) {
    setSelectedMetric(null);
    setSelectedPointId(pointId);
    window.setTimeout(() => {
      const detail = document.getElementById('training-report-point-detail');
      detail?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      detail?.focus({ preventScroll: true });
    }, 0);
  }

  return <section className="training-report-import" aria-labelledby="training-report-title" data-training-report-import>
    <header className="training-report-heading">
      <div><p className="eyebrow">{t('pro.report.kicker')}</p><h3 id="training-report-title">{t('pro.report.title')}</h3><p>{t('pro.report.description')}</p></div>
      <div className="training-report-actions">
        <input ref={inputRef} className="sr-only" type="file" accept="application/json,.json" aria-label={t('pro.report.fileLabel')} onChange={(event) => { void importFile(event.currentTarget.files?.[0]); }} />
        <button type="button" className="button button-primary" onClick={() => inputRef.current?.click()}>{t('pro.report.choose')}</button>
        {report && <button type="button" className="button button-secondary" onClick={clearReport}>{t('pro.report.clear')}</button>}
      </div>
    </header>
    <p className="training-report-local-note">{t('pro.report.localNote')}</p>
    {error && <p className="training-report-error" role="alert">{t('pro.report.importError')} {t(error)}</p>}
    {!report && !error && <p className="training-report-empty" role="status">{t('pro.report.empty')}</p>}
    {report && verification && <div className="training-report-content" data-training-report-version={report.report_version} data-training-handoff-version={verifiedHandoff?.package.package_version} data-report-dataset-class={report.dataset.dataset_class} data-quality-dataset-class={verifiedHandoff?.dataClass}>
      <div className="training-report-title-row">
        <div><p className="eyebrow">{report.report_version} · {fileName}</p><h4>{t('pro.report.overview')}</h4></div>
        {report.dataset.dataset_class === 'SIMULATED_ONLY'
          ? <span className="demo-status-badge">{t('pro.report.simulated')}</span>
          : <span className="training-report-human-badge">{t('pro.report.humanDeclared')}</span>}
      </div>
      {!verifiedHandoff && <div className="training-report-verification" role="status">
        <strong>{t('pro.report.cannotVerify')}</strong><span>{t('pro.report.verifyDetail')}</span>
      </div>}
      <dl className="training-report-identity">
        <dt>{t('pro.report.datasetId')}</dt><dd>{report.dataset.dataset_id}</dd>
        <dt>{t('pro.report.matchId')}</dt><dd>{report.dataset.match_id}</dd>
        <dt>{t('pro.report.sourceId')}</dt><dd>{report.dataset.source_id ?? t('pro.report.notProvided')}</dd>
        <dt>{t('pro.report.localAssetId')}</dt><dd>{report.dataset.local_asset_id ?? t('pro.report.notProvided')}</dd>
        <dt>{t('pro.report.datasetClass')}</dt><dd>{report.dataset.dataset_class}</dd>
        <dt>{t('pro.report.evidenceStatus')}</dt><dd>{report.dataset.evidence_status}</dd>
        <dt>{t('pro.report.pointCount')}</dt><dd>{report.sample.point_count} · {t('pro.report.games')} {report.sample.game_count} · {t('pro.report.knownScore')} {report.sample.known_score_count} · {t('pro.report.knownWinner')} {report.sample.known_winner_count}</dd>
        <dt>{t('pro.report.generatedAt')}</dt><dd>{report.generated_at}</dd>
        <dt>{t('pro.report.protocol')}</dt><dd>{report.dataset.protocol.id} / v{report.dataset.protocol.version} · {report.dataset.protocol.schema_revision}</dd>
        <dt>{t('pro.report.provenance')}</dt><dd>{String(report.dataset.annotation_provenance.method ?? t('pro.report.notProvided'))}</dd>
        {typeof report.dataset.annotation_provenance.parent_dataset_id === 'string' && <><dt>{t('pro.report.parentDataset')}</dt><dd>{report.dataset.annotation_provenance.parent_dataset_id}</dd></>}
        {typeof report.dataset.annotation_provenance.parent_input_sha256 === 'string' && <><dt>{t('pro.report.parentSha')}</dt><dd className="break-all">{report.dataset.annotation_provenance.parent_input_sha256}</dd></>}
        {report.dataset.annotation_provenance.edit !== undefined && <><dt>{t('pro.report.simulatedEdit')}</dt><dd className="break-all">{JSON.stringify(report.dataset.annotation_provenance.edit)}</dd></>}
        <dt>{t('pro.report.matchLink')}</dt><dd>{report.dataset.match_link_status}</dd>
        <dt>{t('pro.report.permission')}</dt><dd>{report.dataset.local_analysis_permission} · {t('pro.report.notRightsGrant')}</dd>
        <dt>{t('pro.report.rightsBasis')}</dt><dd>{report.dataset.rights_basis_ref ?? t('pro.report.notProvided')}</dd>
        <dt>{t('pro.report.vision')}</dt><dd>{report.dataset.vision_status}</dd>
        <dt>{t('pro.report.videoTimeline')}</dt><dd>{report.dataset.video_timeline.status} · {t('pro.report.timestampUnbound')}</dd>
        <dt>{t('pro.report.csvHash')}</dt><dd className="break-all">{report.dataset.annotation_csv_sha256}</dd>
        <dt>{t('pro.report.bundleHash')}</dt><dd className="break-all">{report.dataset.annotation_bundle_sha256}</dd>
        <dt>{t('pro.report.videoHash')}</dt><dd className="break-all">{report.dataset.source_video_sha256 ?? t('pro.report.notProvided')}</dd>
      </dl>
      {!verifiedHandoff && <p className="training-report-source-caution">{t('pro.report.shaCaution')}</p>}

      {verifiedHandoff && <TrainingQualityReviewPanel key={`${report.dataset.dataset_id}:${verifiedHandoff.actualCsvSha256}:${report.generated_at}`} locale={locale} verified={verifiedHandoff} onFocusPoint={focusReportPoint} />}

      <section className="training-report-metrics" aria-labelledby="training-report-metrics-title">
        <div className="pro-stats-heading"><div><p className="eyebrow">{t('pro.report.metricsKicker')}</p><h4 id="training-report-metrics-title">{t('pro.report.metricsTitle')}</h4></div><span>{t('pro.report.clickMetric')}</span></div>
        <div className="training-report-metric-grid">
          {Object.entries(report.metrics).map(([key, metric]) => <button key={key} type="button" className={`training-report-metric${selectedMetric === key ? ' selected' : ''}`} data-report-metric={key} aria-pressed={selectedMetric === key} onClick={() => { setSelectedMetric(key); setSelectedPointId(null); }}>
            <span>{t(metricLabels[key] ?? 'pro.report.metricsTitle')}</span>
            <strong>{metricValue(metric, key)}</strong>
            <small>{t('pro.report.numeratorDenominator')} {countLabel(metric)} · {t('pro.report.eligible')} {metric.sample_count} · {t('pro.report.missing')} {metric.missing_count}</small>
            <small>{metric.evidence_status} · {t(`pro.report.sample.${metric.sample_status}` as MessageKey)}</small>
          </button>)}
        </div>
        <details className="training-report-distributions"><summary>{t('pro.report.distributionTitle')}</summary><div className="training-report-distribution-grid">
          {Object.entries(report.distributions).map(([key, metric]) => <button key={key} type="button" className={`training-report-metric compact${selectedMetric === key ? ' selected' : ''}`} data-report-metric={key} aria-pressed={selectedMetric === key} onClick={() => { setSelectedMetric(key); setSelectedPointId(null); }}>
            <span>{t(metricLabels[key])}</span><strong>{metricValue(metric, key)}</strong>
            <small>{t('pro.report.observed')} {metric.denominator} · {t('pro.report.eligible')} {metric.sample_count} · {t('pro.report.missing')} {metric.missing_count}</small>
          </button>)}
        </div></details>
      </section>

      <section className="training-report-drilldown" aria-labelledby="training-report-drill-title">
        <div className="pro-stats-heading"><div><p className="eyebrow">{t('pro.report.traceKicker')}</p><h4 id="training-report-drill-title">{t('pro.report.traceTitle')}</h4></div><div className="training-report-trace-controls"><span>{selectedMetric ? t(metricLabels[selectedMetric] ?? 'pro.report.traceTitle') : t('pro.report.allPoints')}</span><button type="button" className="training-report-point-button" aria-pressed={selectedMetric === null} onClick={() => { setSelectedMetric(null); setSelectedPointId(null); }}>{t('pro.report.showAllPoints')}</button></div></div>
        {selectedMetric && <p className="training-report-rule">{t('pro.report.rule')} {report.metrics[selectedMetric]?.computation_rule ?? report.distributions[selectedMetric]?.computation_rule}</p>}
        <div className="training-report-table-scroll" role="region" aria-label={t('pro.report.traceTitle')} tabIndex={0}>
          <table className="training-report-table"><thead><tr><th>{t('pro.report.pointId')}</th><th>{t('pro.report.gamePoint')}</th><th>{t('pro.report.csvRecord')}</th><th>{t('pro.report.evidenceStatus')}</th><th>{t('pro.report.timestamp')}</th><th><span className="sr-only">{t('pro.report.openPoint')}</span></th></tr></thead>
            <tbody>{(selectedMetric ? selectedRows : report.point_records).map((row) => <PointRow key={row.point_id} locale={locale} row={row} report={report} selected={selectedPointId === row.point_id} onSelect={() => setSelectedPointId(row.point_id)} />)}</tbody>
          </table>
        </div>
        {selectedMetric && selectedRows.length === 0 && <p role="status">{t('pro.report.noRows')}</p>}
        {selectedPoint && <PointDetail locale={locale} row={selectedPoint} evidenceStatus={report.dataset.evidence_status} />}
      </section>

      <section className="training-report-key-points" aria-labelledby="training-report-key-title">
        <h4 id="training-report-key-title">{t('pro.report.keyPointList')} · {report.key_points.length}</h4>
        {report.key_points.length === 0 ? <p>{t('pro.report.noKeyPoints')}</p> : <div className="training-report-key-list">{report.key_points.map((item) => <button key={item.point_id} type="button" onClick={() => { setSelectedMetric(null); setSelectedPointId(item.point_id); document.getElementById('training-report-drill-title')?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }}><strong>{item.score_before.player} – {item.score_before.opponent}</strong><span>{item.point_id}</span></button>)}</div>}
      </section>

      <details className="training-report-limitations"><summary>{t('pro.report.limitations')} ({report.limitations.length})</summary><ul>{report.limitations.map((item) => <li key={item}>{item}</li>)}</ul></details>
      <div className="training-report-footer"><p>{t('pro.report.csvReadOnly')}</p><button type="button" className="button button-secondary" onClick={downloadCopy}>{t(verifiedHandoff ? 'pro.report.downloadHandoffCopy' : 'pro.report.downloadCopy')}</button></div>
      <p className="pro-save-status" role="status" aria-live="polite">{downloaded ? t(verifiedHandoff ? 'pro.report.downloadedHandoff' : 'pro.report.downloaded') : ''}</p>
    </div>}
  </section>;
}

function PointRow({ locale, row, report, selected, onSelect }: { locale: Locale; row: TrainingPointRecord; report: TrainingReviewReport; selected: boolean; onSelect: () => void }) {
  const t = (key: MessageKey) => message(locale, key);
  const ref = report.point_refs.find((item) => item.point_id === row.point_id)!;
  return <tr className={selected ? 'selected' : undefined} data-report-point-id={row.point_id}>
    <th scope="row"><code>{row.point_id}</code></th>
    <td>{row.fields.game_number} / {row.fields.point_number}</td><td>{row.csv_record_number}</td>
    <td>{report.dataset.evidence_status}</td><td>{String(ref.video_timestamp_text)} · {t('pro.report.unbound')}</td>
    <td><button type="button" className="training-report-point-button" aria-label={`${t('pro.report.openPoint')} ${row.point_id}`} onClick={onSelect}>{t('pro.report.openPoint')}</button></td>
  </tr>;
}

function PointDetail({ locale, row, evidenceStatus }: { locale: Locale; row: TrainingPointRecord; evidenceStatus: string }) {
  const t = (key: MessageKey) => message(locale, key);
  return <aside id="training-report-point-detail" className="training-report-point-detail" tabIndex={-1} aria-label={t('pro.report.pointDetail')} data-selected-report-point={row.point_id}>
    <div><p className="eyebrow">{t('pro.report.pointDetail')}</p><h5><code>{row.point_id}</code></h5></div>
    <dl><dt>{t('pro.report.csvRecord')}</dt><dd>{row.csv_record_number}</dd><dt>{t('pro.report.evidenceStatus')}</dt><dd>{evidenceStatus}</dd><dt>{t('pro.report.rowHash')}</dt><dd className="break-all">{row.annotation_row_sha256}</dd></dl>
    <div className="training-report-fields">{Object.entries(row.fields).map(([key, value]) => <div key={key}><span>{t(pointFieldLabels[key] ?? 'pro.report.pointDetail')}</span><code>{String(value)}</code></div>)}</div>
  </aside>;
}
