import { useRef, useState } from 'react';
import { message } from './i18n';
import type { Locale, MessageKey } from './i18n';
import { metricPointIds } from './training-review.mjs';
import { parseAnnotationReviewReceiptJson } from './training-handoff.mjs';
import type { AnnotationReviewReceipt, VerifiedTrainingHandoff } from './training-handoff.mjs';

const handoffFieldLabels: Record<string, MessageKey> = {
  match_id: 'pro.report.field.matchId', game_number: 'pro.report.field.gameNumber', point_number: 'pro.report.field.pointNumber',
  server: 'pro.report.field.server', receiver: 'pro.report.field.receiver', server_score_before: 'pro.report.field.serverScore',
  receiver_score_before: 'pro.report.field.receiverScore', serve_side: 'pro.report.field.serveSide', serve_length: 'pro.report.field.serveLength',
  serve_location: 'pro.report.field.serveLocation', serve_spin: 'pro.report.field.serveSpin', receive_type: 'pro.report.field.receiveType',
  receive_location: 'pro.report.field.receiveLocation', third_ball_attack: 'pro.report.field.thirdAttack', third_ball_side: 'pro.report.field.thirdSide',
  third_ball_outcome: 'pro.report.field.thirdOutcome', rally_length: 'pro.report.field.rallyLength', point_winner: 'pro.report.field.winner',
  point_outcome: 'pro.report.field.outcome', video_timestamp: 'pro.report.field.timestamp', notes: 'pro.report.field.notes',
};

const handoffMetricLabels: Record<string, MessageKey> = {
  server_point_win_rate: 'pro.report.metric.serverRate', receiver_point_win_rate: 'pro.report.metric.receiverRate',
  third_ball_attack_rate: 'pro.report.metric.thirdAttackRate', third_ball_point_conversion: 'pro.report.metric.thirdConversion',
  third_ball_immediate_success: 'pro.report.metric.thirdSuccess', key_point_player_win_rate: 'pro.report.metric.keyPoints',
  rally_length_mean: 'pro.report.metric.rallyMean',
};

function issueLabel(code: string, t: (key: MessageKey) => string) {
  const keys: Record<string, MessageKey> = {
    UNCERTAINTY_REVIEW: 'pro.quality.issue.uncertainty',
    TIMESTAMP_UNBOUND: 'pro.quality.issue.timestamp',
    SCORE_CONTINUITY_REVIEW: 'pro.quality.issue.score',
  };
  return t(keys[code] ?? 'pro.quality.issue.unknown');
}

export function TrainingQualityReviewPanel({
  locale,
  verified,
  onFocusPoint,
}: {
  locale: Locale;
  verified: VerifiedTrainingHandoff;
  onFocusPoint: (pointId: string) => void;
}) {
  const t = (key: MessageKey) => message(locale, key);
  const receiptInput = useRef<HTMLInputElement>(null);
  const [receipt, setReceipt] = useState<AnnotationReviewReceipt | null>(null);
  const [receiptError, setReceiptError] = useState(false);
  const [receiptName, setReceiptName] = useState('');
  const { report, quality } = verified;

  async function importReceipt(file?: File) {
    if (!file) return;
    setReceiptError(false);
    try {
      if (file.size > 1024 * 1024) throw new Error('too large');
      const parsed = await parseAnnotationReviewReceiptJson(await file.text(), verified);
      setReceipt(parsed);
      setReceiptName(file.name);
    } catch {
      setReceipt(null);
      setReceiptName('');
      setReceiptError(true);
    } finally {
      if (receiptInput.current) receiptInput.current.value = '';
    }
  }

  function focusPoint(pointId: string) {
    onFocusPoint(pointId);
  }

  return <section className="training-handoff-panel" aria-labelledby="training-quality-title" data-training-quality-review data-quality-dataset-class={verified.dataClass}>
    <div className="training-handoff-section-heading">
      <div><p className="eyebrow">{t('pro.quality.kicker')}</p><h4 id="training-quality-title">{t('pro.quality.title')}</h4></div>
      <span>{verified.package.package_version} · {quality.status}</span>
    </div>
    <div className="training-handoff-alert" role="status">
      <strong>{t('pro.quality.internalValidated')}</strong>
      <span>{t('pro.quality.verifyExplanation')}</span>
    </div>
    <div className="training-handoff-alert source-unverified" role="status">
      <strong>{t('pro.quality.cannotVerify')}</strong>
      <span>{t('pro.quality.sourceNotIndependent')}</span>
    </div>
    <dl className="training-handoff-identity">
      <dt>{t('pro.quality.csvHash')}</dt><dd className="break-all"><code>{verified.actualCsvSha256}</code> · {t('pro.quality.hashMatched')}</dd>
      <dt>{t('pro.quality.qualityContractStatus')}</dt><dd>{quality.status}</dd>
      <dt>{t('pro.quality.auditReceipt')}</dt><dd>{receipt ? t('pro.quality.receipt.loaded') : t('pro.quality.receipt.missing')}</dd>
    </dl>
    <p className="training-handoff-readonly-note">{t('pro.quality.csvReadOnly')}</p>

    <section className="training-handoff-summary" aria-labelledby="training-quality-summary-title">
      <div><p className="eyebrow">{t('pro.quality.summaryKicker')}</p><h5 id="training-quality-summary-title">{t('pro.quality.summaryTitle')}</h5></div>
      <div className="training-handoff-summary-grid">
        <article><span>{t('pro.quality.auditStatus')}</span><strong>{t('pro.quality.statusReadable')}</strong></article>
        <article><span>{t('pro.quality.findingCount')}</span><strong>{quality.findings.length}</strong></article>
        <article><span>{t('pro.quality.metricsWithFlags')}</span><strong>{quality.metric_flags.length}</strong></article>
        <article><span>{t('pro.quality.auditReceipt')}</span><strong>{receipt ? t('pro.quality.receipt.loaded') : t('pro.quality.receipt.missing')}</strong></article>
      </div>
      <div className="training-handoff-flags">
        {quality.metric_flags.map((flag) => {
          const ids = metricPointIds(report, flag.key);
          return <button key={flag.key} type="button" className="training-handoff-flag" onClick={() => {
            const pointId = report.point_records.find((point) => ids.includes(point.point_id))?.point_id;
            if (pointId) focusPoint(pointId);
          }}>
            <strong>{t(handoffMetricLabels[flag.key] ?? 'pro.quality.metricsWithFlags')}</strong>
            <span>{t('pro.quality.denominator')} {flag.denominator} · {t('pro.quality.missing')} {flag.missing_count} · {t(`pro.report.sample.${flag.sample_status}` as MessageKey)}</span>
          </button>;
        })}
      </div>
    </section>

    <section className="training-handoff-coverage" aria-labelledby="training-quality-coverage-title">
      <div><p className="eyebrow">{t('pro.quality.coverageKicker')}</p><h5 id="training-quality-coverage-title">{t('pro.quality.coverageTitle')}</h5></div>
      <div className="training-handoff-table-scroll" role="region" aria-label={t('pro.quality.coverageTitle')} tabIndex={0}>
        <table className="training-handoff-table"><thead><tr><th>{t('pro.quality.field')}</th><th>{t('pro.quality.known')}</th><th>{t('pro.quality.unknown')}</th><th>{t('pro.quality.unclear')}</th><th>{t('pro.quality.notApplicable')}</th></tr></thead>
          <tbody>{Object.entries(quality.coverage).map(([field, counts]) => <tr key={field}>
            <th scope="row">{t(handoffFieldLabels[field] ?? 'pro.quality.field')}</th><td>{counts.known}</td><td>{counts.unknown}</td><td>{counts.unclear}</td><td>{counts.not_applicable}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </section>

    <section className="training-handoff-findings" aria-labelledby="training-quality-findings-title">
      <div className="training-handoff-section-heading"><div><p className="eyebrow">{t('pro.quality.findingsKicker')}</p><h5 id="training-quality-findings-title">{t('pro.quality.findingsTitle')} · {quality.findings.length}</h5></div><span>{t('pro.quality.findingsHelp')}</span></div>
      {quality.findings.length === 0 ? <p className="training-handoff-empty">{t('pro.quality.noFindings')}</p> : <ul className="training-handoff-finding-list">
        {quality.findings.map((finding, index) => {
          const rowExists = report.point_records.some((candidate) => candidate.point_id === finding.point_id);
          if (!rowExists) return null;
          return <li key={`${finding.point_id}-${finding.code}-${index}`}>
            <button type="button" className="training-handoff-finding" data-quality-finding-point={finding.point_id} onClick={() => focusPoint(finding.point_id)}>
              <strong>{issueLabel(finding.code, t)}</strong>
              <span><code>{finding.point_id}</code></span>
              <small>{t('pro.quality.csvRecord')} {finding.csv_record_number} · {finding.fields.map((field) => t(handoffFieldLabels[field] ?? 'pro.quality.field')).join('、')}</small>
            </button>
          </li>;
        })}
      </ul>}
    </section>

    <section className="training-handoff-receipt" aria-labelledby="training-quality-receipt-title">
      <div className="training-handoff-section-heading"><div><p className="eyebrow">{t('pro.quality.receiptKicker')}</p><h5 id="training-quality-receipt-title">{t('pro.quality.auditReceipt')}</h5></div>
        <div className="training-handoff-actions">
          <input ref={receiptInput} className="sr-only" type="file" accept="application/json,.json" aria-label={t('pro.quality.receipt.fileLabel')} onChange={(event) => { void importReceipt(event.currentTarget.files?.[0]); }} />
          <button type="button" className="button button-secondary" onClick={() => receiptInput.current?.click()}>{t('pro.quality.receipt.choose')}</button>
        </div>
      </div>
      {receiptError && <p className="training-handoff-error" role="alert">{t('pro.quality.receipt.invalid')}</p>}
      {!receipt && <p className="training-handoff-empty" role="status">{t('pro.quality.receipt.missingDetail')}</p>}
      {receipt && <div className="training-handoff-receipt-card" data-review-receipt={receipt.receipt_version}>
        <p className="eyebrow">{receipt.receipt_version} · {receiptName}</p>
        <dl><dt>{t('pro.quality.receipt.status')}</dt><dd>{receipt.status}</dd><dt>{t('pro.quality.receipt.datasetClass')}</dt><dd>{receipt.dataset_class}</dd>
          <dt>{t('pro.quality.receipt.reviewer')}</dt><dd>{receipt.review.reviewer_ref}</dd><dt>{t('pro.quality.receipt.reviewedAt')}</dt><dd>{receipt.review.reviewed_at}</dd>
          <dt>{t('pro.quality.receipt.decisions')}</dt><dd>{receipt.review.decisions.length}</dd><dt>{t('pro.quality.receipt.unchanged')}</dt><dd>{receipt.source_annotations_changed ? t('pro.quality.receipt.changed') : t('pro.quality.receipt.unchangedValue')}</dd>
          <dt>{t('pro.quality.receipt.packageHash')}</dt><dd className="break-all"><code>{receipt.package_content_sha256}</code></dd></dl>
        <p>{t('pro.quality.receipt.disclaimer')}</p>
      </div>}
    </section>
  </section>;
}
