import {useEffect,useRef,useState} from 'react';
import {freshArena,arenaStep,pendingEvent,ended} from './gex-moment/arena-events.mjs';
import {revealAt} from './arena-clock.mjs';
import './immersive-arena.css';

const DURATION=20;
export default function ImmersiveArena({onBack}:{onBack:()=>void}) {
 const [game,setGame]=useState(()=>freshArena(DURATION,'original-animation'));
 const [time,setTime]=useState(0),[playing,setPlaying]=useState(false);
 const previous=useRef<number|null>(null);
 const event=pendingEvent(game);
 useEffect(()=>{
  if(!playing)return;
  const timer=window.setInterval(()=>{const now=performance.now();const delta=previous.current===null?0:(now-previous.current)/1000;previous.current=now;setTime(t=>Math.min(DURATION,t+Math.min(delta,.2)));},50);
  return()=>{window.clearInterval(timer);previous.current=null};
 },[playing]);
 useEffect(()=>{
  if(!playing||!event||time<event.timestamp)return;
  setGame((current:any)=>revealAt(current,time));setPlaying(false);
 },[time,playing,event?.timestamp]);
 function choose(side:string){setGame((s:any)=>arenaStep(s,'choose',side));}
 function lock(){if(!game.prediction||game.locked)return;setGame((s:any)=>arenaStep(s,'lock'));setPlaying(true);}
 function next(){setGame((s:any)=>arenaStep(s,'next'));}
 function reset(){setPlaying(false);setTime(0);setGame(freshArena(DURATION,'original-animation'));}
 const phase=ended(game)?'终局':Math.max(game.score.A,game.score.B)>=10?'局点 / 加分':'关键分';
 return <div className="immersive-arena">
  <header><button onClick={onBack}>← 返回 Arena</button><span>ARENA · THE NEXT POINT</span><strong>MOCK 模拟赛事 · 非真实比赛</strong></header>
  <section className={'arena-stage'+(playing?' is-playing':'')+(game.revealed?' is-revealed':'')} aria-label="原创模拟赛事动画">
   <div className="arena-light arena-light-a"/><div className="arena-light arena-light-b"/><div className="arena-flight" aria-hidden="true"/>
   <div className="arena-stage-top"><span>{phase}</span><span>模拟画面 · 无现金</span></div>
   <div className="arena-stage-score" role="status" aria-live="polite"><span>雷霆</span><strong>{game.score.A} : {game.score.B}</strong><span>磐石</span></div>
   <div className="arena-stage-bottom" aria-live="polite">{playing?'关键分进行中…':game.revealed?(ended(game)?'模拟局结束':`本分揭晓 · ${game.records.at(-1)?.winner==='A'?'雷霆':'磐石'}得分`):'预测下一分，锁定后观看揭晓'}</div>
   <div className="arena-timeline" role="progressbar" aria-label="模拟动画进度" aria-valuemin={0} aria-valuemax={DURATION} aria-valuenow={Math.round(time)}><span style={{width:`${time/DURATION*100}%`}}/></div>
  </section>
  <p className="arena-disclaimer">画面与时间点均为原创模拟，不对应真实回合或视频事件。</p>
  {!game.revealed&&!ended(game)&&<div className="arena-choices" aria-label="预测下一分"><button aria-pressed={game.prediction==='A'} disabled={game.locked} onClick={()=>choose('A')}>雷霆得分</button><button aria-pressed={game.prediction==='B'} disabled={game.locked} onClick={()=>choose('B')}>磐石得分</button><button className="arena-lock" disabled={!game.prediction||game.locked} onClick={lock}>锁定并观看</button>{game.prediction&&!game.locked&&<button onClick={()=>setGame((s:any)=>arenaStep(s,'retry'))}>重新选择</button>}</div>}
  {game.revealed&&!ended(game)&&<button className="arena-lock" onClick={next}>继续观看下一分 →</button>}
  <div className="arena-actions"><button onClick={reset}>重置模拟局</button><button onClick={onBack}>退出并返回 Arena</button></div>
  <details className="arena-records"><summary>本轮预测记录 · {game.records.length}</summary>{game.records.length?<ol>{game.records.map((r:any)=><li key={r.eventId}>{r.scoreBefore.A}:{r.scoreBefore.B} → {r.scoreAfter.A}:{r.scoreAfter.B} · 选择 {r.prediction==='A'?'雷霆':'磐石'} · {r.predictionResult==='MATCH'?'猜中':'未猜中'}</li>)}</ol>:<p>尚无已揭晓记录。</p>}</details>
 </div>;
}
