import { MomentumRiver } from './MomentumRiver';
import { PersonalArenaChallenge } from './PersonalArenaChallenge';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { Locale } from './i18n';
import type { LocalVideoSession, LocalVideoPoint, LocalGameContext } from './local-video-review.mjs';
import { createPersonalMatchReport } from './personal-match-report.mjs';
import { premiereMoments, premiereSvg, personalArenaContext } from './premiere.mjs';

export function MyMatchPremiere({ session, points, gameContext, locale, onRecord, onPro, onReport }: {
  session: LocalVideoSession; points: readonly LocalVideoPoint[]; gameContext: LocalGameContext; locale: Locale;
  onRecord: (point: number) => void; onPro?: () => void; onReport?: () => void;
}) {
  const result = useMemo(() => createPersonalMatchReport(session, points, gameContext), [session, points, gameContext]);
  const [selection, setSelection] = useState({ key: '', index: 0 });
  const [exportStatus, setExportStatus] = useState('');
  const [confirmed, setConfirmed] = useState('');
  const simulationRef = useRef<HTMLDivElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (confirmed) simulationRef.current?.focus(); }, [confirmed]);
  const zh = locale === 'zh-CN';
  if (!result.ok) return <p role="status">{zh ? '记录可信的逐分比分后，即可开启私人比赛首映。' : 'Record a valid score sequence to open your private premiere.'}</p>;
  const report = result.value; const key = JSON.stringify(report); const moments = premiereMoments(report);
  const index = selection.key === key ? Math.min(selection.index, moments.length - 1) : 0;
  const current = moments[index];
  const arenaContext = personalArenaContext(report, current.point);
  const arenaKey = JSON.stringify([key, current.point]);
  const simulating = confirmed === arenaKey && arenaContext !== null;
  const eventNames: Record<string,string> = zh ? { TIED:'追平', TAKE_LEAD:'取得领先', OVERTAKE:'反超', GAME_END:'本局完成' } : { TIED:'Tied', TAKE_LEAD:'Take lead', OVERTAKE:'Overtake', GAME_END:'Game complete' };
  function choose(i: number) { setSelection({ key, index: Math.max(0, Math.min(moments.length - 1, i)) }); }
  function download() {
    let url: string | null = null;
    try { url = URL.createObjectURL(new Blob([premiereSvg(report)], { type:'image/svg+xml' }));
      const a = document.createElement('a'); a.href = url; a.download = 'ptti-my-match-premiere.svg'; a.click();
      setExportStatus(zh ? '已请求保存纪念卡。' : 'Souvenir save requested.');
    } catch { setExportStatus(zh ? '保存不可用，请重试。' : 'Save unavailable. Please retry.'); }
    finally { if (url) { const expired = url; window.setTimeout(() => URL.revokeObjectURL(expired), 1000); } }
  }
  return <details className="match-premiere" data-my-match-premiere>
    <summary>MY MATCH PREMIERE · {zh ? '我的比赛首映' : 'Your private score story'}</summary>
    <div className="premiere-body">
      <p className="eyebrow">DON’T JUST WATCH. EXPERIENCE THE GAME.</p>
      <h3>{zh ? '每一分，都有你的故事。' : 'Every point. Your story.'}</h3>
      <strong className="premiere-score">{report.calculated_results.final.score.player_a} : {report.calculated_results.final.score.player_b}</strong>
      <p>{report.calculated_results.final.status === 'GAME_COMPLETE' ? (zh ? '记录内本局已完成' : 'Recorded game complete') : (zh ? '记录进行中' : 'Record in progress')}</p>
      <p role="note">{zh ? '手工记录 · 未独立核验。仅呈现已保存逐分记录的比分故事，不推断打法、旋转、落点或技术原因。未提交编辑保留在原工作区，本页不修改记录。' : 'Manual record · Not independently verified. Score story from saved points only; no inferred strokes, spin, placement or technical causes. Unsaved edits remain in the workspace. This view does not change records.'}</p>
      <div hidden={simulating}><MomentumRiver report={report} locale={locale} onSelectPoint={point => { const i = moments.findIndex(moment => moment.point === point); if (i >= 0) choose(i); }} /><section aria-label={zh ? '逐分时刻卡' : 'Point moment cards'}>
        <div className="premiere-controls"><button type="button" disabled={index === 0} onClick={() => choose(index-1)}>{zh ? '上一张' : 'Previous'}</button><button type="button" disabled={index === moments.length-1} onClick={() => choose(index+1)}>{zh ? '下一张' : 'Next'}</button></div>
        <article className="premiere-moment" aria-live="polite" aria-atomic="true">
          <h4>{zh ? '第' : 'Point '}{current.point}{zh ? '分' : ''} · {current.a}:{current.b}</h4>
          <p>{current.events.map(e => eventNames[e]).join(' · ') || (zh ? '比分推进' : 'Score progression')}{current.checkpoint ? ' · '+(zh ? '关键平分' : 'Key tied score') : ''}</p>
          {current.runs.map(run => <p key={run.first_point}>{run.side === 'PLAYER_A' ? 'A' : 'B'} · {zh ? '最长连得分代表段' : 'Representative longest scoring run'}: {run.first_point}–{run.last_point} ({run.length})</p>)}
          <button type="button" onClick={() => onRecord(current.point)}>{zh ? '定位逐分记录（不跳转视频）' : 'Locate point record (no video seek)'}</button>
        </article>
        <ol className="premiere-timeline">{moments.map((m,i) => <li key={m.point}><button type="button" aria-pressed={i===index} onClick={() => choose(i)}>{m.point} · {m.a}:{m.b}{m.checkpoint ? ' ◆' : ''}{m.events.length ? ' · '+m.events.map(e => eventNames[e]).join(' / ') : ''}</button></li>)}</ol>
      </section>
      <div className="premiere-controls"><button type="button" onClick={() => onRecord(current.point)}>{zh ? '回到 My Matches' : 'Back to My Matches'}</button>{onReport && <button type="button" onClick={onReport}>{zh ? '查看个人报告与训练行动' : 'Open report and training action'}</button>}{onPro && <button type="button" onClick={onPro}>{zh ? '进入 Pro Lab' : 'Open Pro Lab'}</button>}</div>
      <section data-personal-arena-gate><h4>{zh ? '针对这个比分情境练习' : 'Practice this score situation'}</h4>
        <p>{zh ? '仅临时使用所选分的比分、序号、记录完成状态及手工未核验标记。现有 Arena 仅支持 9:9；这不是对真实技术的分析。确认后才开始，离开即丢弃模拟选择。' : 'Temporarily uses only the selected score, point index, completion and manual/unverified flags. Existing Arena supports 9:9 only. This is not analysis of actual technique. Confirm to start; leaving discards simulation choices.'}</p>
        {!arenaContext && <p role="status">{zh ? '请选择时间线上实际到达的 9:9；没有该记录时不提供此模拟。' : 'Select an actual recorded 9:9 on the timeline. Without that record this simulation is unavailable.'}</p>}
        <button ref={confirmRef} type="button" disabled={!arenaContext} onClick={() => setConfirmed(arenaKey)}>{zh ? '确认用途，进入假设模拟' : 'Confirm use and enter hypothetical simulation'}</button>
      </section>
      <section><h4>{zh ? '纪念卡字段预览' : 'Souvenir field preview'}</h4><p>{zh ? '仅导出：PTTI 标题、当前比分、完成状态、手工记录和未独立核验声明；不含身份、文件名、路径、图像或视频。卡片文字为英文。' : 'Exports only: PTTI title, score, completion status, manual/unverified notice. No identity, filenames, paths, images or video. Card text is English.'}</p><button type="button" onClick={download}>{zh ? '保存本地 SVG 纪念卡' : 'Save local SVG souvenir'}</button><p role="status">{exportStatus}</p></section>
      </div>
      {simulating && <div ref={simulationRef} tabIndex={-1}><PersonalArenaChallenge key={arenaKey} context={arenaContext} locale={locale} onBack={() => { setConfirmed(''); requestAnimationFrame(() => confirmRef.current?.focus()); }} onReport={() => { setConfirmed(''); onReport?.(); }} /></div>}
    </div>
  </details>;
}
