import { useId } from 'react';
import type { Locale } from './i18n';
import type { PersonalMatchReport } from './personal-match-report.mjs';

/** Score difference by recorded point index, never a time or psychological signal. */
export function MomentumRiver({ report, locale, onSelectPoint }: { report: PersonalMatchReport; locale: Locale; onSelectPoint?: (point: number) => void }) {
  const zh = locale === 'zh-CN';
  const id = useId().replaceAll(':', '');
  const rows = report.calculated_results.score_progression;
  const synthetic = report.source.type === 'SIMULATED_DEMO';
  const scale = Math.max(2, ...rows.map(row => Math.abs(row.score_after.player_a - row.score_after.player_b)));
  const x = (index: number) => 12 + (index + 1) / Math.max(1, rows.length) * 576;
  const y = (a: number, b: number) => 70 - (a - b) / scale * 48;
  return <section className="momentum-river" data-momentum-river data-evidence={synthetic ? 'SIMULATED_DEMO' : 'MANUAL_NOT_VERIFIED'} aria-label={zh ? '比分河流' : 'Score river'}>
    <h4>MOMENTUM RIVER · {zh ? '比分轨迹' : 'Score progression'}</h4>
    <p>{synthetic ? 'SAMPLE · SIMULATED_DEMO' : 'MANUAL_NOT_VERIFIED'} · {zh ? '仅按已记录分序排列；不表示心理势头、回合时长或技术原因。' : 'Recorded point order only; no psychological momentum, rally duration or technical causality.'}</p>
    {rows.length === 0 ? <p>{zh ? '尚无逐分记录。' : 'No recorded points yet.'}</p> : <>
      <div className="river-axis-labels" aria-hidden="true"><span>A {zh ? '领先' : 'ahead'}</span><span>B {zh ? '领先' : 'ahead'}</span></div>
      <svg viewBox="0 0 600 140" role="img" aria-label={zh ? 'A 与 B 的分差，横轴为记录分序；逐分详情见下方报告。' : 'A minus B score by recorded point index. Exact scores follow in the report.'}>
        <defs><linearGradient id={`${id}-river-fill`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#d4b07a" stopOpacity=".28" /><stop offset="100%" stopColor="#d4b07a" stopOpacity=".03" /></linearGradient></defs>
        <polygon fill={`url(#${id}-river-fill)`} points={'12,70 ' + rows.map((row,index) => `${x(index)},${y(row.score_after.player_a,row.score_after.player_b)}`).join(' ') + ' 588,70'} />
        <line x1="12" y1="70" x2="588" y2="70" stroke="currentColor" opacity="0.3" />
        <polyline fill="none" stroke="#D4B07A" strokeWidth="3" points={'12,70 ' + rows.map((row, index) => `${x(index)},${y(row.score_after.player_a, row.score_after.player_b)}`).join(' ')} />
        {rows.map((row, index) => <circle key={row.point_number} cx={x(index)} cy={y(row.score_after.player_a, row.score_after.player_b)} r="3" fill="#D4B07A"><title>{`${row.point_number} · ${row.score_after.player_a}:${row.score_after.player_b}`}</title></circle>)}
      </svg>
      <div className="river-axis-labels" aria-hidden="true"><span>0</span><span>{zh ? '记录分序' : 'Recorded point index'} → {rows.length}</span></div>
      <p>{zh ? '记录样本' : 'Recorded sample'}: {rows.length} · A − B</p>
      <ul>{[7, 9, 10].map(score => { const tie = rows.find(row => row.score_after.player_a === score && row.score_after.player_b === score); return <li key={score}>{score}:{score} · {tie ? `${zh ? '第' : 'Point '}${tie.point_number}${zh ? '分后' : ''}` : (zh ? '未记录此平分' : 'Tie not recorded')}</li>; })}</ul>
      {onSelectPoint && <div className="river-point-actions" role="group" aria-label={zh ? '定位比分记录，不跳转视频' : 'Locate a score record, not video'}>{rows.filter(row => (row.score_after.player_a === row.score_after.player_b && [7,9,10].includes(row.score_after.player_a)) || row.point_number === rows.at(-1)?.point_number).map(row => <button type="button" key={row.point_number} onClick={() => onSelectPoint(row.point_number)}>{row.score_after.player_a}:{row.score_after.player_b} · {zh ? '第' : 'Point '}{row.point_number}{zh ? '分记录' : ''}</button>)}</div>}
      <p>{zh ? '最长连分（记录内）' : 'Longest scoring runs within record'}: {report.calculated_results.longest_scoring_runs.map(run => `${run.side === 'PLAYER_A' ? 'A' : 'B'} · ${run.first_point}–${run.last_point} (${run.length})`).join(' / ') || '—'}</p>
    </>}
  </section>;
}
