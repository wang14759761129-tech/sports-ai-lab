import {useEffect,useRef,useState} from 'react';
import {identifyLocalVideo} from './localVideoIdentity.mjs';
import {createReviewV2,type ReviewMark} from './manualReviewV2.mjs';
import {LocalVideoPlaybackController} from './vendor/playback/index';
import {MomentPlaybackAdapter} from './vendor/playback/momentPlaybackAdapter';

export default function LocalManualLab({onDirty}:{onDirty:(dirty:boolean)=>void}){
 const video=useRef<HTMLVideoElement>(null),controller=useRef<LocalVideoPlaybackController|null>(null),adapter=useRef<MomentPlaybackAdapter|null>(null),abort=useRef<AbortController|null>(null),generation=useRef(0);
 const [identity,setIdentity]=useState(''),[session,setSession]=useState(''),[duration,setDuration]=useState(0),[ready,setReady]=useState(false),[busy,setBusy]=useState(false),[marks,setMarks]=useState<ReviewMark[]>([]),[tag,setTag]=useState<ReviewMark['tag']>('serve'),[note,setNote]=useState(''),[message,setMessage]=useState(''),[editing,setEditing]=useState<string|null>(null);
 useEffect(()=>{onDirty(marks.length>0);return()=>onDirty(false)},[marks,onDirty]);
 useEffect(()=>()=>{generation.current++;abort.current?.abort();adapter.current?.cancelPendingSeek();controller.current?.release()},[]);
 async function select(file:File|null){
  if(!file)return;
  if(marks.length&&!window.confirm('标注仅保留在当前会话。切换视频会清除记录，请先导出。继续吗？'))return;
  const n=++generation.current;abort.current?.abort();abort.current=new AbortController();adapter.current?.cancelPendingSeek();controller.current?.release();adapter.current=null;controller.current=null;setReady(false);setIdentity('');setSession('');setMarks([]);setDuration(0);setBusy(true);setMessage('正在分块计算本机视频身份，请稍候。');
  try{
   if(!video.current)throw Error('播放器未就绪');
   if(file.type&&(!file.type.startsWith('video/')||!video.current.canPlayType(file.type)))throw Error('浏览器不支持此视频格式');
   const id=await identifyLocalVideo(file,{signal:abort.current.signal});if(n!==generation.current)return;
   const sessionId=crypto.randomUUID();const core=new LocalVideoPlaybackController(video.current,{createVideoIdentity:()=>id.digest});const play=new MomentPlaybackAdapter(core,video.current);controller.current=core;adapter.current=play;
   core.subscribe(s=>{if(n!==generation.current)return;if(s.status==='ready'){const result=play.load(id.digest);if(result.ok&&s.duration_seconds){setDuration(s.duration_seconds);setReady(true);setMessage('视频已载入。标注仅在此页面会话内保存，请主动导出。')}else setMessage('无法绑定视频身份')}else if(s.status==='error'){setReady(false);setMessage('视频无法解码或播放，请选择浏览器支持的文件。')}});
   const result=core.loadFile(file);if(!result.ok)throw Error(result.error.message);setIdentity(id.digest);setSession(sessionId);
  }catch(e){if(n===generation.current)setMessage('视频载入失败：'+(e as Error).message)}finally{if(n===generation.current)setBusy(false)}
 }
 function save(){const time=adapter.current?.getCurrentTime();if(!time?.ok||!session){setMessage('视频尚未就绪，无法记录。');return}try{const next:ReviewMark={id:editing||crypto.randomUUID(),seconds:editing?marks.find(m=>m.id===editing)!.seconds:time.value,tag,note};const nextMarks=editing?marks.map(m=>m.id===editing?next:m):[...marks,next];createReviewV2({identity:{kind:'SESSION',value:session},duration_seconds:duration},nextMarks);setMarks(nextMarks.sort((a,b)=>a.seconds-b.seconds));setNote('');setEditing(null);setMessage('标注已更新；离开前请导出。')}catch{setMessage('标注无效，请检查时间和备注。')}}
 function download(){try{const out=createReviewV2({identity:{kind:'SESSION',value:session},duration_seconds:duration},marks);const url=URL.createObjectURL(new Blob([JSON.stringify({...out,local_content_fingerprint:{algorithm:'ptti-local-video-chunks-sha256-v1',digest:identity}},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='ptti-local-manual-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);setMessage('已请求导出，请检查下载；记录仍只在当前会话。')}catch{setMessage('导出失败，请确认视频和标注有效。')}}
 return <section className="manual-review"><h2>Pro Lab · 本机手动复盘</h2><p>请选择您有权使用的视频。文件仅在本机处理，不自动上传；记录只保留在页面会话，离开或切换视频前请导出。动作标签由您手动填写，不是 AI 识别。</p><label>选择本地视频 <input type="file" accept="video/*" disabled={busy} onChange={e=>{const f=e.currentTarget.files?.[0]||null;e.currentTarget.value='';void select(f)}}/></label><video ref={video} controls playsInline style={{width:'100%',maxWidth:900}}/><p role="status">{message}</p><p>视频身份：{identity?'分块 SHA-256 指纹（不是原文件 SHA-256）':'尚未确认'}</p><div className="manual-review-actions"><label>分类 <select value={tag} onChange={e=>setTag(e.target.value as ReviewMark['tag'])}><option value="serve">发球</option><option value="receive">接发球</option><option value="rally">回合</option><option value="other">其他</option></select></label><label>教练笔记 <input maxLength={2000} value={note} onChange={e=>setNote(e.target.value)}/></label><button disabled={!ready} onClick={save}>{editing?'保存修改':'记录当前时间'}</button>{editing&&<button onClick={()=>{setEditing(null);setNote('')}}>取消编辑</button>}<button disabled={!ready||!marks.length} onClick={download}>导出 JSON</button></div>{!marks.length?<p>暂无标注。</p>:<ol>{marks.map(m=><li key={m.id}><button disabled={!ready} onClick={()=>{void adapter.current?.seekExact(m.seconds).then(r=>setMessage(r.ok?`已确认定位至 ${r.value.toFixed(2)} 秒`:'定位失败：'+r.error))}}>{m.seconds.toFixed(2)} 秒 · {m.tag} · {m.note||'无备注'}</button><button onClick={()=>{setEditing(m.id);setTag(m.tag);setNote(m.note)}}>编辑</button><button onClick={()=>{setMarks(old=>old.filter(x=>x.id!==m.id));if(editing===m.id){setEditing(null);setNote('')}setMessage('标注已删除，请重新导出。')}}>删除</button></li>)}</ol>}</section>
}
