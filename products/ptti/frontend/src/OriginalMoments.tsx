import {confirmMomentContent} from './confirmMomentContent.mjs';
import {momentLocalVideo} from './originalMomentRoute.mjs';
import {useState} from 'react';
import type {FeedVideo} from './feedCatalog';
import {loadMomentState,formatTimestamp} from './momentCards.mjs';
export default function OriginalMoments({videos,onBack,onPlayLocal}:{videos:FeedVideo[];onBack:()=>void;onPlayLocal:(id:string)=>void}){
 const [error,setError]=useState(''),[checking,setChecking]=useState(false);
 const [state]=useState(()=>{try{return loadMomentState(window.localStorage)}catch{return {moments:[],writable:false,error:'无法读取本机时刻，原记录未修改。'}}});
 return <section><button onClick={onBack}>← 返回收藏</button><h2>我的时刻</h2><p>本机时刻记录；打开视频后请手动定位。来源缺失的记录保留。</p>{(state.error||error)&&<p role="alert">{state.error||error}</p>}{!state.moments.length?<p>暂无时刻记录。</p>:state.moments.map(m=>{const matches=videos.filter(v=>v.key===m.videoKey);const v=matches.length===1?matches[0]:null;const local=momentLocalVideo(m,videos);return <article key={m.id}><strong>{m.title}</strong><p>{formatTimestamp(m.seconds)} · {v?v.title:'来源不可用或身份未核实'}</p>{m.note&&<p>{m.note}</p>}{local?<button disabled={checking} onClick={async()=>{setChecking(true);setError('');try{await confirmMomentContent(local.source.video_id,local.source.source_sha256);onPlayLocal(local.source.video_id)}catch(e:any){setError(e.message||'视频身份校验失败')}finally{setChecking(false)}}}>打开本机视频（手动定位到 {formatTimestamp(m.seconds)}）</button>:<span>本机视频不可用；记录未删除。</span>}</article>})}</section>;
}
