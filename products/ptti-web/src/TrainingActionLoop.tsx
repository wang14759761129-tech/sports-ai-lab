import { useEffect, useRef, useState } from 'react';
import type { PersonalMatchReport } from './personal-match-report.mjs';
import type { Locale } from './i18n';
import { createTrainingAction, formatTrainingAction } from './training-action';
import { createWatchCopyGuard } from './watch-copy-guard.mjs';

export function TrainingActionLoop({ report, questionId, locale, disabled, onOpenJournal }: {
  report: PersonalMatchReport; questionId: string | null; locale: Locale; disabled: boolean; onOpenJournal?: () => void;
}) {
  const plan = createTrainingAction(report, questionId, locale);
  const zh = locale === 'zh-CN';
  return <section className="training-action-loop" data-training-action>
    <h4>{zh ? '下一次训练，把观察变成行动。' : 'Turn your observation into the next practice.'}</h4>
    {!plan ? <p>{zh ? '先选择上方一条观察问题，再生成具体训练计划。' : 'Select an observation question above to build a specific practice plan.'}</p>
      : <TrainingActionCard key={JSON.stringify([plan, report.evidence_identity, disabled])} plan={plan} disabled={disabled} onOpenJournal={onOpenJournal} />}
  </section>;
}
export function TrainingActionCard({ plan, disabled, onOpenJournal }: {
  plan: NonNullable<ReturnType<typeof createTrainingAction>>; disabled: boolean; onOpenJournal?: () => void;
}) {
  const zh = plan.locale === 'zh-CN';
  const [feedback, setFeedback] = useState('');
  const [manual, setManual] = useState(false);
  const guard = useRef(createWatchCopyGuard());
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; guard.current.invalidate(); }; }, []);
  const text = formatTrainingAction(plan);
  async function copy() {
    if (disabled) return;
    const result = await guard.current.copy(text, async (value: string) => {
      if (!navigator.clipboard?.writeText) throw new Error('clipboard-unavailable');
      await navigator.clipboard.writeText(value);
    });
    if (!result || !alive.current) return;
    setManual(result === 'manual');
    setFeedback(result === 'copied' ? (zh ? '行动摘要已复制。' : 'Action summary copied.') : (zh ? '无法自动复制，请在下方手动复制。' : 'Automatic copy unavailable. Copy the text below.'));
  }
  function download() {
    if (disabled) return;
    guard.current.invalidate();
    let url: string | null = null;
    try {
      url = URL.createObjectURL(new Blob([JSON.stringify(plan, null, 2)+'\n'], { type: 'application/json' }));
      const a = document.createElement('a'); a.href = url; a.download = plan.simulated ? 'ptti-SIMULATED-training-action-v0.1.json' : 'ptti-training-action-v0.1.json'; a.click();
      setFeedback(zh ? '已请求下载行动 JSON；未自动保存到笔记。' : 'Action JSON download requested; no note was saved.');
    } catch { setFeedback(zh ? '下载失败，计划仍保留；可重试或复制。' : 'Download failed. The plan remains; retry or copy it.'); }
    finally { if (url) { const expired = url; window.setTimeout(() => URL.revokeObjectURL(expired), 1000); } }
  }
  return <article data-action-source={plan.source}>
    <p className="eyebrow">{plan.simulated ? 'SIMULATED DEMO' : 'MANUAL · NOT INDEPENDENTLY VERIFIED'}</p>
    <dl><dt>{zh ? '依据 · 已记录 / 已计算' : 'Basis · recorded / calculated'}</dt><dd>{plan.evidence.basis}</dd>
      <dt>{zh ? '观察问题' : 'Observation question'}</dt><dd>{plan.observation_question}</dd>
      <dt>{zh ? '下次训练行动' : 'Next practice action'}</dt><dd>{plan.next_training_action}</dd>
      <dt>{zh ? '验证办法' : 'How to check'}</dt><dd>{plan.verification_method}</dd>
      <dt>{zh ? '证据限制' : 'Evidence limits'}</dt><dd>{plan.limitations}</dd></dl>
    <div className="personal-report-actions"><button type="button" disabled={disabled} onClick={() => void copy()}>{zh ? '复制行动摘要' : 'Copy action summary'}</button><button type="button" disabled={disabled} onClick={download}>{zh ? '导出行动 JSON' : 'Export action JSON'}</button>{onOpenJournal && <button type="button" onClick={onOpenJournal}>{zh ? '前往 Journal，自行创建笔记' : 'Open Journal to create your own note'}</button>}</div>
    <p>{zh ? '仅当前页面会话；不自动写入 Journal 或个人资料。' : 'Current page session only. No automatic Journal or personal-data writes.'}</p>
    <p role="status" aria-live="polite">{feedback}</p>
    {manual && <label>{zh ? '手动复制行动摘要' : 'Manually copy action summary'}<textarea readOnly value={text} rows={12} onFocus={event => event.currentTarget.select()} /></label>}
  </article>;
}
