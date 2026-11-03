import { useEffect, useMemo, useRef, useState } from 'react';
import type { Locale } from './i18n';
import { createSimulatedDemoReport } from './personal-match-report.mjs';
import { premiereMoments } from './premiere.mjs';
import { PersonalMatchReportView } from './PersonalMatchReport';
import { ArenaChallengePage } from './ArenaChallengePage';

/** Read-only synthetic experience. Never creates a local media or personal record session. */
export function FirstExperienceDemo({ locale, onBack, onReview }: { locale: Locale; onBack: () => void; onReview: () => void }) {
  const report = useMemo(createSimulatedDemoReport, []);
  const moments = useMemo(() => premiereMoments(report), [report]);
  const [point, setPoint] = useState(18);
  const [arena, setArena] = useState(false);
  const [question, setQuestion] = useState<string | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const challengeButton = useRef<HTMLButtonElement>(null);
  const reportRef = useRef<HTMLDivElement>(null);
  const zh = locale === 'zh-CN';
  useEffect(() => { heading.current?.focus(); }, [arena]);
  const current = moments.find(row => row.point === point)!;
  function returnReport() { setArena(false); requestAnimationFrame(() => { const details = reportRef.current?.querySelector('details'); if (details) details.open = true; reportRef.current?.querySelector('summary')?.focus(); }); }
  return <section className="first-demo" data-demo="SIMULATED_DEMO">
    <div className="premiere-controls"><button type="button" onClick={onBack}>{zh ? '返回 PTTI' : 'Back to PTTI'}</button><button type="button" onClick={onReview}>{zh ? '复盘我的比赛' : 'Review My Match'}</button></div>
    <p className="eyebrow">SIMULATED DEMO · {zh ? '约三分钟' : 'About three minutes'}</p>
    <h1 ref={heading} tabIndex={-1}>{zh ? '从一局比赛，找到下一次进步。' : 'One game. Your next step.'}</h1>
    <p role="note">{zh ? '合成逐分演示，不是本人比赛或官方赛事。没有视频、时间点或自动保存；不写入个人资料。PTTI 目前需要用户记录比赛数据，不会自动识别每次击球。' : 'Synthetic points, not your match or an official event. No video, timestamps or auto-save. Nothing enters your personal records. PTTI currently needs your annotations; it does not automatically recognize every stroke.'}</p>
    {arena ? <><h2>{zh ? '9:9 假设战术模拟' : '9:9 hypothetical tactics'}</h2><button type="button" onClick={returnReport}>{zh ? '返回演示报告' : 'Return to demo report'}</button><ArenaChallengePage locale={locale} onBack={() => { setArena(false); requestAnimationFrame(() => challengeButton.current?.focus()); }} /></> : <>
      <nav aria-label={zh ? '演示步骤' : 'Demo steps'} className="premiere-controls"><a href="#demo-story">1 · Premiere</a><a href="#demo-report">2 · {zh ? '报告' : 'Report'}</a><a href="#demo-arena">3 · Arena</a></nav>
      <section id="demo-story"><h2>MY MATCH PREMIERE · SIMULATED</h2><p>{zh ? '合成记录 → 比分计算 → 时刻卡。按钮只选择记录，不控制视频。' : 'Synthetic record → calculated scores → moment cards. These controls select records, never video.'}</p>
        <article className="premiere-moment" aria-live="polite"><h3>{zh ? '第' : 'Point '}{point}{zh ? '分后' : ''}</h3><strong className="premiere-score">{current.a}:{current.b}</strong><p>{current.checkpoint ? (zh ? '实际出现在本演示序列中的关键平分' : 'Key tie present in this synthetic sequence') : (zh ? '合成比分推进' : 'Synthetic score progression')}</p></article>
        <ol className="premiere-timeline">{moments.map(m => <li key={m.point}><button type="button" aria-pressed={point === m.point} onClick={() => setPoint(m.point)}>{m.point} · {m.a}:{m.b}</button></li>)}</ol>
      </section>
      <div id="demo-report" ref={reportRef}><PersonalMatchReportView report={report} locale={locale} selectedQuestionId={question} disabled={false} onSelect={setQuestion} /></div>
      <section id="demo-arena"><h2>{zh ? '把 9:9 带入假设挑战' : 'Explore a hypothetical 9:9'}</h2><p>{zh ? '只使用演示中第18分后的9:9比分。Arena 不解释这局的真实技术；挑战选择不会改变记录。' : 'Uses only the demo’s 9:9 after point 18. Arena does not explain real technique; choices never change the record.'}</p><button ref={challengeButton} type="button" onClick={() => setArena(true)}>{zh ? '确认模拟性质，进入 Arena' : 'Confirm simulation and enter Arena'}</button></section>
    </>}
  </section>;
}
