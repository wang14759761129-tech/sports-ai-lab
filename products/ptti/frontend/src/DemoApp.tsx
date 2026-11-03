import {useState,useRef,useEffect} from 'react';
import MomentTimeline from './MomentTimeline';
import RealMatchCatalog from './RealMatchCatalog';
import type {DemoMoment} from './demoMoments';
import {arenaScene,validateReturn,type SpaceContext} from './spaceContext';
import StudioShell from './StudioShell';
import VideoFeed from './VideoFeed';
import './style.css';
import {validateDemoIdentity,sortedMoments,updateMoment,removeMoment,requireDemoResponse} from './demoMoments';
import {createMutationGuard,fetchWithTimeout,demoDiagnostics,recordDemoDiagnostic} from './demoActions';
const poster=(i:number)=>'data:image/svg+xml,'+encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360"><rect width="640" height="360" fill="${['#14242a','#282018','#192029','#28242b'][i%4]}"/><path d="M80 245 L560 245 L500 155 L140 155 Z" fill="none" stroke="#b6955c" stroke-width="3"/><path d="M140 155 L500 155 M320 155 L320 245" stroke="#b6955c"/><text x="320" y="305" text-anchor="middle" fill="#fff" font-size="23">SYNTHETIC DEMO ${i+1}</text></svg>`);
const rows=Array.from({length:8},(_,i)=>({demo_thumbnail:poster(i),video_id:`demo-${i+1}`,title:`模拟比赛 ${i+1} · 合成训练视频`,availability_status:'AVAILABLE',duration_ms:20000,athlete_ids:[],rights_status:'USER_OWNED',personal_library:{event_name:'演示赛事 · 模拟数据',match_type:i%2?'WS':'MS',content_type:'CLIP'}}));
const nativeFetch=window.fetch.bind(window);
const key='ptti-cinema-sprint02-demo-favorites';
const read=(k:string)=>{try{return JSON.parse(localStorage.getItem(k)||'[]')}catch{return []}};
export function installDemoFetch(){window.fetch=async (input,init)=>{const url=typeof input==='string'?input:input instanceof URL?input.href:input.url;const path=new URL(url,location.href);if(path.origin!==location.origin||!path.pathname.startsWith('/api/'))return new Response('DEMO: network disabled',{status:403});let value:any={};if(path.pathname==='/api/video-evidence/library')value={videos:rows,official_videos:[],athletes:[],matches:[],feed_favorites:read(key),tournament_editions:[]};else if(path.pathname==='/api/video-evidence/library/feed/favorite'&&init?.method==='PUT'){const body=JSON.parse(String(init.body));const list:string[]=read(key);value={favorites:body.saved?[...new Set([...list,body.key])]:list.filter(x=>x!==body.key)};localStorage.setItem(key,JSON.stringify(value.favorites))}else if(path.pathname.includes('/opened'))value={ok:true};else return new Response('DEMO: endpoint unavailable',{status:404});return new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}})}}
export default function DemoApp({onArena,returnContext,onReturnEnd}:{onReturnEnd?:(error?:string)=>void;onArena?:(c:SpaceContext)=>void;returnContext?:SpaceContext|null}){
 const [realCatalog,setRealCatalog]=useState(false);
 const [page,setPage]=useState('home'),[query,setQuery]=useState(''),[video,setVideo]=useState(''),[note,setNote]=useState('');
 const [error,setError]=useState(''),[notice,setNotice]=useState(''),[seekStatus,setSeekStatus]=useState('');
 const [moments,setMoments]=useState<Array<{id:string;time:number;note:string}>>([]),[identity,setIdentity]=useState('');
 const [duration,setDuration]=useState(0),[selected,setSelected]=useState('');
 const [loading,setLoading]=useState(false),[busy,setBusy]=useState(false),[refresh,setRefresh]=useState(0);
 const ref=useRef<HTMLVideoElement>(null),activeEvent=useRef(video),guard=useRef(createMutationGuard()),loadedReturn=useRef<SpaceContext|null|undefined>(null),handledReturn=useRef<SpaceContext|null>(null),pendingReturn=useRef<number|null>(null);activeEvent.current=video;
 useEffect(()=>setDuration(0),[video]);
 useEffect(()=>{if(returnContext){loadedReturn.current=null;setVideo(returnContext.cardId);setRefresh(n=>n+1)}},[returnContext]);
 useEffect(()=>{if(!returnContext){pendingReturn.current=null;return}if(handledReturn.current===returnContext||loadedReturn.current!==returnContext||loading||!identity||!duration||!ref.current)return;handledReturn.current=returnContext;try{const time=validateReturn(returnContext,identity,video,moments,duration);ref.current.pause();pendingReturn.current=time;ref.current.currentTime=time;setNotice('正在定位返回位置，等待播放器确认');setSelected(returnContext.momentId)}catch(e){const message=(e as Error).message;setError(message);onReturnEnd?.(message)}},[returnContext,identity,duration,loading]);
 useEffect(()=>{if(!returnContext)return;const timer=setTimeout(()=>{if(returnContext){pendingReturn.current=null;setError('返回定位未得到播放器确认，请手动定位');onReturnEnd?.('返回定位超时')}} ,12000);return()=>clearTimeout(timer)},[returnContext]);
 function enterArena(m:DemoMoment){const v=ref.current,sceneId=arenaScene(video);if(!onArena||!sceneId||!v||!identity||loading||busy)return;const c={sha256:identity,cardId:video,momentId:m.id,time:v.currentTime,sceneId,createdAt:Date.now(),momentTime:m.time,momentNote:m.note};try{validateReturn(c,identity,video,moments,v.duration);v.pause();onArena(c)}catch(e){setError((e as Error).message)}}
 const navigate=(p:string)=>{setPage(p);setVideo('')};
 useEffect(()=>{
  if(!video)return;let live=true;setIdentity('');setMoments([]);setNotice('');setSeekStatus('');setError('');setLoading(true);setSelected('');
  (async()=>{try{
   const [file,api]=await Promise.all([fetchWithTimeout(nativeFetch,'/demo-synthetic.mp4'),fetchWithTimeout(nativeFetch,'/demo-api/moments?event='+encodeURIComponent(video))]);
   requireDemoResponse(file.ok&&api.ok,'独立演示 API 或合成视频不可用');
   const bytes=await file.arrayBuffer();const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');
   const data=await api.json();validateDemoIdentity(hash,data.sha256,video,data.event_id);
   if(live){loadedReturn.current=returnContext;setIdentity(hash);setMoments(sortedMoments(data.moments));setError('')}
  }catch(e){if(live){setError((e as Error).message);if(returnContext)onReturnEnd?.((e as Error).message)}}finally{if(live)setLoading(false)}})();
  return()=>{live=false};
 },[video,refresh]);
 async function mutate(path:string,method:string,payload:Record<string,unknown>,success:(value:any)=>void){
  if(!guard.current.begin())return;setBusy(true);setError('');setNotice('');
  try{const response=await fetchWithTimeout(nativeFetch,path,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify({sha256:identity,event_id:video,...payload})});
   requireDemoResponse(response.ok,'操作失败，时刻未确认保存；请刷新列表后重试');const value=await response.json();if(activeEvent.current===video)success(value)
  }catch(e){if(activeEvent.current===video){setError((e as Error).message+'；如已发送请求，请先刷新列表确认结果。');setIdentity('')}}
  finally{guard.current.end();setBusy(false)}
 }
 function selectMoment(m:DemoMoment){if(loading||busy||!identity||!ref.current||ref.current.readyState<1){setError('视频或身份未就绪，无法定位');return}if(!Number.isFinite(m.time)||m.time<0||m.time>ref.current.duration){setError('时刻超出视频时长');return}try{ref.current.currentTime=m.time;setSelected(m.id);document.getElementById('moment-'+m.id)?.scrollIntoView({block:'nearest'})}catch{setError('无法定位这个时刻')}}
 return <StudioShell page={page} navigate={navigate} query={query} onQueryChange={setQuery} searchEnabled buildLabel="DEMO · 全部赛事为模拟">
  <details className="demo-info"><summary>演示说明与诊断</summary><p role="status">演示使用模拟赛事和合成视频，时刻保存在本机临时演示数据库；不连接正式 API、数据库或私人媒体。Arena 预配置场景不是视频识别结果。未迁移 5199 / 5210 的历史。</p><button onClick={()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(demoDiagnostics,null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download="cinema-diagnostics.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}}>导出本轮诊断</button></details>
  {!video&&<div className="catalog-switch" aria-label="目录类型"><button aria-pressed={!realCatalog} onClick={()=>setRealCatalog(false)}>模拟体验</button><button aria-pressed={realCatalog} onClick={()=>setRealCatalog(true)}>真实赛事目录</button></div>}
  {error&&!video&&<p role="alert">{error}</p>}
  {video?<section><button onClick={()=>setVideo('')}>返回视频墙</button><h2>合成测试视频 · {video}</h2>
   <video key={video} onLoadedMetadata={e=>setDuration(e.currentTarget.duration)} onDurationChange={e=>setDuration(e.currentTarget.duration)} ref={ref} src="/demo-synthetic.mp4" controls playsInline onSeeked={()=>{recordDemoDiagnostic("seeked",JSON.stringify({event:video,currentTime:ref.current?.currentTime}));if(pendingReturn.current!==null){const target=pendingReturn.current;pendingReturn.current=null;if(ref.current&&Math.abs(ref.current.currentTime-target)<=0.1){setNotice('播放器已确认返回位置，保持暂停；请自行播放');onReturnEnd?.()}else{setError('实际返回位置与保存位置不符');onReturnEnd?.('定位偏差超出允许范围')}}setSeekStatus(`已到达 ${ref.current?.currentTime.toFixed(2)} 秒（seeked）`)}} onError={()=>{setError('合成视频无法播放，未恢复观看位置');if(returnContext)onReturnEnd?.('合成媒体缺失或无法播放')}} style={{width:'100%',maxWidth:900}}/>
   <MomentTimeline moments={moments} duration={duration} selected={selected} disabled={loading||busy||!identity} onSelect={selectMoment}/>{onArena&&arenaScene(video)&&selected&&<button disabled={!identity||loading||busy} onClick={()=>{const m=moments.find(x=>x.id===selected);if(m)enterArena(m)}}>进入 Arena · 模拟互动</button>}
   <div><label>时刻备注 <input value={note} onChange={e=>setNote(e.target.value)}/></label>
    <button disabled={loading||busy||!identity} onClick={()=>{if(!ref.current||ref.current.readyState<1){setError('视频未加载，无法保存时刻');return}void mutate('/demo-api/moments','POST',{time:ref.current.currentTime,note},saved=>{setMoments(current=>sortedMoments([...current,saved]));setNote('');setNotice('时刻已保存到演示数据库')})}}>{busy?'正在保存…':'保存当前时刻'}</button>
   </div><p role="status">{seekStatus}</p><h3>我的演示时刻</h3>
   {loading&&<p role="status">正在核对视频并加载时刻…</p>}{!loading&&!error&&identity&&moments.length===0&&<p>当前赛事还没有演示时刻。</p>}
   {notice&&<p role="status">{notice}</p>}
   {moments.map(m=><p id={"moment-"+m.id} className={selected===m.id?"moment-selected":""} key={m.id}><button disabled={busy||loading||!identity} onClick={()=>selectMoment(m)}>{m.time.toFixed(2)} 秒 · {m.note||'无备注'}</button>
    {onArena&&arenaScene(video)&&<button disabled={busy||loading||!identity} onClick={()=>enterArena(m)}>进入 Arena · 模拟互动</button>}<button disabled={busy||loading||!identity} onClick={()=>{const value=window.prompt('修改备注',m.note);if(value===null)return;void mutate('/demo-api/moments/'+m.id,'PUT',{note:value},()=>{setMoments(current=>updateMoment(current,m.id,value));setNotice('备注已更新')})}}>编辑备注</button>
    <button disabled={busy||loading||!identity} onClick={()=>{if(!window.confirm('删除这个演示时刻？'))return;void mutate('/demo-api/moments/'+m.id,'DELETE',{},()=>{setMoments(current=>removeMoment(current,m.id));setNotice('时刻已删除');if(selected===m.id)setSelected('')})}}>删除</button></p>)}
   {error&&<div role="alert"><p>{error}</p><button disabled={busy} onClick={()=>setRefresh(v=>v+1)}>重新加载时刻</button></div>}
  </section>:realCatalog?<RealMatchCatalog query={query}/>:<VideoFeed page={page} revision={0} query={query} onPlay={setVideo} onTools={()=>setError('演示模式未启用本地导入')} navigate={navigate}/>}
 </StudioShell>
}
