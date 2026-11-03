import type {DemoMoment} from './demoMoments';
import {timelineMarkers} from './timelineLayout';
import './moment-timeline.css';
export default function MomentTimeline({moments,duration,selected,disabled,onSelect}:{moments:DemoMoment[];duration:number;selected:string;disabled:boolean;onSelect:(m:DemoMoment)=>void}){
 const markers=timelineMarkers(moments,duration);const chosen=moments.find(m=>m.id===selected);
 return <section className="moment-timeline" aria-label="精彩时刻时间轴"><h3>精彩时刻时间轴</h3>{!Number.isFinite(duration)||duration<=0?<p>等待视频时长，暂不可定位时刻。</p>:<><div className="moment-track" style={{height:Math.max(48,(Math.max(0,...markers.map(m=>m.lane))+1)*36)}}>{markers.map(m=><button key={m.id} className={selected===m.id?'chosen':''} style={{left:`${m.percent}%`,top:m.lane*36}} disabled={disabled} aria-pressed={selected===m.id} title={`${m.time.toFixed(2)} 秒 · ${m.note||'无备注'}`} aria-label={`${m.time.toFixed(2)} 秒 · ${m.note||'无备注'}`} onClick={()=>onSelect(m)}>◆</button>)}</div><div className="moment-scale"><span>0:00</span><span>{duration.toFixed(2)} 秒</span></div>{markers.length===0&&<p>保存一个时刻后，它会出现在这里。</p>}</>}{chosen&&<p role="status">已选择 {chosen.time.toFixed(2)} 秒 · {chosen.note||'无备注'}</p>}</section>
}

