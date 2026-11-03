import {useState} from 'react';
import {advancePoint,advanceToCriticalResolved,createMatch,createPrediction,readArenaSnapshot,matchStatus,resolvePredictions,saveArenaState,scoreHistory} from './fanArenaEngine.mjs';
import './fan-arena.css';

const TYPE_LABEL:Record<string,string>={NEXT_POINT:'下一分由谁获得？',FIRST_TO_GAME_POINT:'本局谁先拿到局点？',GAME_WINNER:'这一局谁获胜？'};

function initialArena(){
 try{return readArenaSnapshot(window.localStorage)}catch{return readArenaSnapshot(null)}
}

export default function FanArena({onBack}:{onBack?:()=>void}){
 const [arena,setArena]=useState(initialArena);
 const {match,predictions,history}=arena;
 const [type,setType]=useState('NEXT_POINT');
 const [choice,setChoice]=useState('A');
 const [message,setMessage]=useState('');
 const [saveError,setSaveError]=useState(arena.error);
 const status=matchStatus(match);
 const current=predictions.filter(p=>p.matchId===match.id);
 const stats=scoreHistory(history);
 function commit(next:{match:any;predictions:any[];history:any[]},notice:string){
  setMessage('');
  if(!arena.writable){setSaveError(arena.error||'本机存储不可用，操作未保存。');return;}
  try{if(!saveArenaState(window.localStorage,next))throw Error('write failed')}
  catch{setSaveError('保存失败：操作未生效，比分和历史保持上次保存状态；请重试。');return;}
  setArena({...next,writable:true,error:''});setSaveError('');setMessage(notice);
 }
 function applyResolved(nextMatch:any,resolvedPreds:any[],newly:any[]){
  const nextHistory=[...history,...newly.filter(n=>!history.some(x=>x.id===n.id))];
  const notice=newly.length?newly.map(p=>`${TYPE_LABEL[p.type]} ${p.correct?'预测正确 ✓':'预测错误 ✗'}`).join('；'):nextMatch.lastPoint?`第 ${nextMatch.pointIndex} 分：${nextMatch.lastPoint.winner==='A'?'雷霆':'磐石'}得分 · ${nextMatch.lastPoint.rally}`:'';
  commit({match:nextMatch,predictions:resolvedPreds,history:nextHistory},notice);
 }
 function advance(){const r=advancePoint(match);if(!r.advanced){setMessage('比赛已结束，请开始新比赛');return}const out=resolvePredictions(current,r.match,match);const newly=out.predictions.filter(p=>p.status==='RESOLVED'&&!current.find(c=>c.id===p.id&&c.status==='RESOLVED'));applyResolved(r.match,out.predictions,newly)}
 function advanceCritical(){
  // P0-2: stepwise reduction, not a single resolve against the final score.
  const out=advanceToCriticalResolved(match,current);
  if(out.match===match&&!out.resolved.length){setMessage('比赛已结束，请开始新比赛');return}
  applyResolved(out.match,out.predictions,out.resolved);
 }
 function lock(){const r=createPrediction(current,match,type,choice);if(r.errors.length){setMessage(r.errors.join('；'));return}commit({match,predictions:r.predictions,history},'预测已锁定，结果揭晓后不能修改')}
 function newMatch(){commit({match:createMatch(),predictions:[],history},'新模拟局已开始，已结算历史保留，不复用旧局预测')}
 return <div className="fan-arena">
  <div className="fan-arena-head"><div><h2>Fan Arena · 模拟比赛</h2><p>SIMULATED_ONLY · 虚构球员的单局演示，非真实比赛，无现金价值奖励或博彩功能。</p></div><div className="fan-actions">{onBack&&<button onClick={onBack}>返回 Cinema</button>}<button onClick={newMatch} disabled={!arena.writable}>开始新比赛</button></div></div>
  <section className="fan-scoreboard" aria-label="模拟比分" data-phase={status.kind}>
   <div className="fan-player fan-player--red"><strong>雷霆</strong><span>模拟球员</span></div>
   <div className="fan-score" role="status" aria-live="polite">{match.scoreA} : {match.scoreB}</div>
   <div className="fan-player fan-player--blue"><strong>磐石</strong><span>模拟球员</span></div>
  </section>
  <p className="fan-status" role="status" data-phase={status.kind}><strong>{status.label}</strong><span>已进行 {match.pointIndex} 分{match.lastPoint?` · 上一分：${match.lastPoint.winner==='A'?'雷霆':'磐石'} · ${match.lastPoint.rally}`:''}</span></p>
  <div className="fan-actions"><button className="primary" onClick={advance} disabled={!arena.writable||match.status==='FINISHED'}>推进一分</button><button onClick={advanceCritical} disabled={!arena.writable||match.status==='FINISHED'}>推进到下一关键分</button></div>
  <section className="fan-predict" aria-label="做预测">
   <label>预测类型<select aria-label="预测类型" value={type} onChange={e=>setType(e.target.value)}>{Object.entries(TYPE_LABEL).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
   <label>你的选择<select aria-label="你的选择" value={choice} onChange={e=>setChoice(e.target.value)}><option value="A">雷霆</option><option value="B">磐石</option></select></label>
   <button onClick={lock} disabled={!arena.writable||match.status==='FINISHED'}>锁定预测</button>
   <p>锁定后不能修改；结果按唯一预测 ID 揭晓，重复揭晓不会重复计分。局点：下一分赢下即赢本局；单局演示中，局点即本场赛点，但不作为多局赛事的赛点使用。</p>
  </section>
  {message&&<p className="fan-message" role="status">{message}</p>}
  {saveError&&<p className="fan-error" role="alert">{saveError}</p>}
  <section className="fan-current" aria-label="本场比赛预测">
   <h3>本场比赛预测</h3>
   {!current.length?<p>还没有预测。先选类型和球员，点“锁定预测”。</p>:<ul>{current.map(p=><li key={p.id}>{TYPE_LABEL[p.type]} · 选择：{p.choice==='A'?'雷霆':'磐石'} · {p.status==='RESOLVED'?(p.correct?'正确 ✓':'错误 ✗'):'已锁定，等待揭晓'}</li>)}</ul>}
  </section>
  <section className="fan-history" aria-label="个人记录">
   <h3>个人记录</h3>
   <p>已揭晓 {stats.total} 次 · 正确 {stats.correct} 次 · 正确率 {stats.accuracy}% · 连对 {stats.streak} 次</p>
   {!history.length?<p>还没有已揭晓的预测。</p>:<ul>{history.map(p=><li key={p.id}>{TYPE_LABEL[p.type]} · 选择：{p.choice==='A'?'雷霆':'磐石'} · {p.correct?'正确 ✓':'错误 ✗'}</li>)}</ul>}
  </section>
  <p><small>返回 Cinema 时，本页状态保存在浏览器隔离存储里，不写正式数据库。比赛结束总结：{match.status==='FINISHED'?`${match.winner==='A'?'雷霆':'磐石'} 以 ${match.scoreA}:${match.scoreB} 赢下本局（单局演示）`: '比赛进行中，结束后再看总结。'}</small></p>
 </div>;
}
