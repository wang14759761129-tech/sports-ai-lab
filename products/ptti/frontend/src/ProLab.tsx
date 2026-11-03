import {useEffect,useRef,useState} from 'react';
import {PRO_LAB_TACTICAL_TAGS,bindLegacyNote,createNote,createVideoIdentity,deleteNote,exportNotes,filterNotesByVideo,formatTimestamp,legacyNotes,loadNotesState,parseTags,parseTimestamp,resolveSeek,saveNotes,updateNote,isNoteBoundToVideo} from './proLabNotes.mjs';
import type {LocalVideoIdentity,ProLabNote} from './proLabNotes.mjs';
import './pro-lab.css';
import GexMomentRestore from './GexMomentRestore';
import {downloadJsonBlob} from './downloadBlob.mjs';
import {identify} from './gex-moment/evidence.mjs';
import {readProgress,writeProgress,playbackState,resumeDecision,guardedPlay,recentProgress,removeProgress} from './localPlayback.mjs';

type StorageState={notes:ProLabNote[];writable:boolean;error:string};
type Selection={identity:LocalVideoIdentity;url:string;file:File};
function initialStorageState():StorageState{
 try{return loadNotesState(window.localStorage)}catch{return {notes:[],writable:false,error:'本机存储不可用；已有笔记未修改。'}}
}

export default function ProLab({onBack,active=true,qaMoment=false}:{onBack:()=>void;active?:boolean;qaMoment?:boolean}){
 const videoRef=useRef<HTMLVideoElement|null>(null);const activeRef=useRef(active);activeRef.current=active;
 const loadedIdentityKey=useRef<string|null>(null);
 const fileName=useRef('');const interacted=useRef(false);const contentId=useRef<string|null>(null);const progressClock=useRef(0);const generation=useRef(0);
 const [playerState,setPlayerState]=useState('idle');
 const [progressState,setProgressState]=useState<'idle'|'identifying'|'ready'|'unavailable'>('idle');
 const [selection,setSelection]=useState<Selection|null>(null);
 const [history,setHistory]=useState<ReturnType<typeof recentProgress>>(()=>{try{return recentProgress(window.localStorage)}catch{return []}});
 const [storage,setStorage]=useState<StorageState>(initialStorageState);
 const [timestamp,setTimestamp]=useState('');
 const [tags,setTags]=useState('');
 const [coachNote,setCoachNote]=useState('');
 const [editingId,setEditingId]=useState<string|null>(null);
 const [error,setError]=useState(storage.error);
 const [status,setStatus]=useState('');
 const [tagFilter,setTagFilter]=useState('');

 useEffect(()=>{const video=videoRef.current;return()=>{generation.current++;video?.pause();if(selection?.url)URL.revokeObjectURL(selection.url)}},[selection?.url]);
 useEffect(()=>{if(!active){videoRef.current?.pause();recordProgress(true)}},[active]);
 useEffect(()=>{const save=()=>recordProgress(true);window.addEventListener('pagehide',save);return()=>window.removeEventListener('pagehide',save)},[]);

 function pickFile(file:File|undefined){
  if(!file)return;
  const identity=createVideoIdentity(file);
  if(!identity){setError('无法建立安全的本机文件身份，请重新选择视频。');return;}
  let url:string;
  try{url=URL.createObjectURL(file)}catch{setError('无法在本机打开该视频文件。');return;}
  videoRef.current?.pause();recordProgress(true);generation.current++;
  loadedIdentityKey.current=null;contentId.current=null;fileName.current=file.name;interacted.current=false;setPlayerState('loading');setProgressState('identifying');
  setSelection({identity,url,file});
  setEditingId(null);setTimestamp('');setTags('');setCoachNote('');setTagFilter('');setError('');setStatus('');
 }

 async function prepareProgress(video:HTMLVideoElement,selected:Selection){
  const n=++generation.current;setProgressState('identifying');
  try{const id=await identify(selected.file,()=>{},()=>generation.current===n);
   if(n!==generation.current||videoRef.current!==video||video.currentSrc!==selected.url)return;
   const saved=readProgress(window.localStorage,id,video.duration);contentId.current=id;setProgressState('ready');
   const decision=resumeDecision(saved,video.duration,interacted.current||!video.paused||video.currentTime>=0.1);
   if(decision.action==='RESTORE'){video.currentTime=decision.seconds;setStatus(`已恢复本机观看位置 ${formatTimestamp(decision.seconds)}。`)}
   else if(decision.action==='PRESERVE_CURRENT')recordProgress(true);
  }catch{if(n===generation.current){setProgressState('unavailable');setError('无法读取观看进度；视频仍可播放，已有数据未修改。')}}
 }
 function recordProgress(force=false){const video=videoRef.current,id=contentId.current;
  if(!video||!id||!Number.isFinite(video.duration)||video.duration<=0||!Number.isFinite(video.currentTime))return;
  const now=Date.now();if(!force&&now-progressClock.current<5000)return;
  try{writeProgress(window.localStorage,id,Math.min(video.currentTime,video.duration),video.duration,fileName.current);progressClock.current=now;setProgressState('ready');setHistory(recentProgress(window.localStorage))}
  catch{setProgressState('unavailable');setError('观看进度无法保存；已有记录未覆盖。')}
 }
 function removeHistory(id:string){if(!window.confirm('删除这条本机观看记录？不会删除视频或 Moment；如果继续观看该视频，进度会重新记录。'))return;try{removeProgress(window.localStorage,id);setHistory(recentProgress(window.localStorage));setStatus('观看记录已删除。')}catch{setError('无法删除观看记录；原数据未修改。')}}
 function changeRate(rate:number){if(videoRef.current)videoRef.current.playbackRate=rate}
 function fullscreen(){const v=videoRef.current;if(!v?.requestFullscreen){setError('当前环境不支持全屏，请使用播放器原生控件。');return}void v.requestFullscreen().catch(()=>setError('无法进入全屏，请使用播放器原生控件。'))}
 function playSafely(video:HTMLVideoElement){
  if(!activeRef.current||videoRef.current!==video)return;
  setError('');
  void guardedPlay(video,()=>activeRef.current&&videoRef.current===video).then(result=>{
   if(result==='playing')setPlayerState(playbackState(video));
   else if(result==='blocked'){setPlayerState('blocked');setError('播放被浏览器阻止，请使用播放器原生控件。')}
  });
 }
 function retryPlayback(){const v=videoRef.current;if(v)playSafely(v)}
 function retryVideo(){const video=videoRef.current;if(!video)return;setError('');setPlayerState('loading');video.load()}
 function persist(next:ProLabNote[],success:string){
  if(!storage.writable){setError(storage.error||'本机存储不可用，笔记未保存。');return false;}
  let localStorage:Storage;try{localStorage=window.localStorage}catch{setError('本机存储不可用，笔记未保存；请保留当前输入。');setStatus('');return false;}
  const result=saveNotes(localStorage,next);
  if(!result.ok){setError(result.error);setStatus('');return false;}
  setStorage(current=>({...current,notes:next,error:''}));
  setError('');setStatus(success);return true;
 }

 function captureCurrent(){
  const video=videoRef.current;
  if(!selection||!video||loadedIdentityKey.current!==selection.identity.key||video.readyState<1||!Number.isFinite(video.currentTime)){
   setError('请先选择并加载一段本机视频，再记录播放时间点。');setStatus('');return;
  }
  video.pause();
  const seconds=video.currentTime;
  if(!Number.isFinite(seconds)||seconds<0){setError('当前视频时间无效，未创建记录。');setStatus('');return;}
  setTimestamp(formatTimestamp(seconds));setError('');setStatus('');
 }

 function submit(){
  setStatus('');
  if(!selection){setError('请先选择一段你有权在本机使用的视频。');return;}
  const seconds=parseTimestamp(timestamp),video=videoRef.current;
  if(!video||loadedIdentityKey.current!==selection.identity.key||video.readyState<1||!Number.isFinite(video.duration)||video.duration<=0){setError('请等待当前视频成功加载后再保存；输入已保留。');setStatus('');return;}
  if(seconds!==null&&loadedIdentityKey.current===selection.identity.key&&video&&Number.isFinite(video.duration)&&seconds>video.duration){setError('时间点超出当前视频长度。');return;}
  const input={videoIdentity:selection.identity,timestamp,tags:parseTags(tags),coachNote};
  const result=editingId?updateNote(storage.notes,editingId,input):createNote(storage.notes,input);
  if(result.errors.length){setError(result.errors.join('；'));setStatus('');return;}
  if(persist(result.notes,'笔记已保存在本机。')){setEditingId(null);setTimestamp('');setTags('');setCoachNote('');}
 }

 function startEdit(note:ProLabNote){
  if(!selection||!isNoteBoundToVideo(note,selection.identity)){setError('当前文件与这条笔记不匹配，未打开编辑。');return;}
  setEditingId(note.id);setTimestamp(formatTimestamp(note.seconds));setTags(note.tags.join(', '));setCoachNote(note.coachNote);setError('');setStatus('');
 }

 function seek(note:ProLabNote){
  const video=videoRef.current;
  if(!selection||!isNoteBoundToVideo(note,selection.identity)||loadedIdentityKey.current!==selection.identity.key||!video){setError('请重新选择与笔记身份一致的视频，未执行跳转。');return;}
  const target=resolveSeek(note.seconds,video.duration);
  if(target===null){setError('该时间点超出视频范围。');return;}
  if(Number.isFinite(video.duration)&&video.duration>0&&note.seconds>video.duration){setError('该笔记时间点超出当前文件长度，未跳转。');return;}
  video.currentTime=target;
  playSafely(video);
  setError('');setStatus('');
 }

 function rebindLegacy(note:ProLabNote){
  if(!selection){setError('先选择要明确关联的本机视频。');return;}
  if(!window.confirm(`将旧笔记“${note.videoName}”明确关联到当前所选文件？此操作只更新这条笔记。`))return;
  const result=bindLegacyNote(storage.notes,note.id,selection.identity);
  if(result.errors.length){setError(result.errors.join('；'));return;}
  persist(result.notes,'旧笔记已按你的确认关联到当前文件。');
 }

 function remove(note:ProLabNote){
  if(!window.confirm('确定删除这条本机笔记吗？'))return;
  const next=deleteNote(storage.notes,note.id);
  if(persist(next,'笔记已删除。')){if(tagFilter&&!next.some(item=>selection&&isNoteBoundToVideo(item,selection.identity)&&item.tags.includes(tagFilter)))setTagFilter('');if(editingId===note.id){setEditingId(null);setTimestamp('');setTags('');setCoachNote('');}}
 }

 function exportJson(){
  try{
   const data=exportNotes(storage.notes);
   const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
   downloadJsonBlob(blob,`ptti-pro-lab-notes-${new Date().toISOString().slice(0,10)}.json`,{url:URL,document,defer:window.setTimeout.bind(window)});
   setStatus(`已导出 ${data.noteCount} 条结构化笔记，不含视频内容。`);setError('');
  }catch{setError('导出失败；本机笔记未改变。');setStatus('');}
 }

 const matched=selection?filterNotesByVideo(storage.notes,selection.identity):[];
 const shown=tagFilter?matched.filter(note=>note.tags.includes(tagFilter)):matched;
 const oldNotes=legacyNotes(storage.notes);
 const allTags=[...new Set(matched.flatMap(note=>note.tags))];

 return <section className="pro-lab" aria-label="Pro Lab 本机比赛笔记">
  <header className="pro-lab-header"><div><p className="pro-lab-kicker">PTTI · PRO LAB</p><h2>本机视频战术笔记</h2></div><button type="button" onClick={onBack}>返回 Cinema</button></header>
  <p>选择你有权使用的本机录像，暂停、标注并回看。视频不上传，笔记保存在当前浏览器。</p>
  <details><summary>本机文件与证据说明</summary><p>文件关联使用文件名、大小、修改时间与类型元数据，不计算内容哈希；元数据完全相同的文件仍可能无法区分。人工笔记不代表 AI 识别结果，也不会写入正式数据库。</p></details>
  <details><summary>最近观看的本机视频 · {history.length}</summary><p>仅在当前浏览器保存文件名和进度；重新选择相同视频后继续，视频不会上传。</p>{history.length===0?<p>暂无观看记录。</p>:<ol>{history.map(item=><li key={item.id}>{item.displayName} · {formatTimestamp(item.seconds)} / {formatTimestamp(item.duration)} <button type="button" onClick={()=>removeHistory(item.id)} aria-label={`删除 ${item.displayName} 的观看记录`}>删除记录</button></li>)}</ol>}</details>
  <label className="pro-lab-file">选择本机训练视频<input type="file" accept="video/*" onChange={event=>{pickFile(event.target.files?.[0]);event.target.value=''}}/></label>
  {selection?<><p className="pro-lab-current">当前视频：<strong>{selection.identity.name}</strong> · {selection.identity.size.toLocaleString()} bytes · {selection.identity.type||'媒体类型未提供'}</p>
   <video key={selection.url} ref={videoRef} src={selection.url} controls preload="metadata" onLoadStart={()=>{loadedIdentityKey.current=null}} onLoadedMetadata={event=>{loadedIdentityKey.current=selection.identity.key;setError('');setPlayerState('ready');void prepareProgress(event.currentTarget,selection)}} onPlay={event=>{interacted.current=true;setPlayerState(playbackState(event.currentTarget))}} onSeeking={()=>{interacted.current=true}} onPause={event=>{setPlayerState(playbackState(event.currentTarget));recordProgress(true)}} onTimeUpdate={()=>recordProgress()} onSeeked={()=>recordProgress(true)} onEnded={event=>{setPlayerState('ended');recordProgress(true)}} onError={()=>{loadedIdentityKey.current=null;setPlayerState('error');setError('所选视频无法由当前浏览器解码；本机笔记未改变。')}} />
   <p role="status">播放器状态：{playerState}</p><p role="status">{progressState==='identifying'?'正在核对视频内容；完成前退出或切换可能无法保存当前进度。':progressState==='ready'?'可按视频内容在本机保存观看进度。':progressState==='unavailable'?'观看进度当前不可保存，请检查本机存储。':''}</p>{playerState==='error'&&<button type="button" onClick={retryVideo}>重试加载当前视频</button>}{playerState==='blocked'&&<button type="button" onClick={retryPlayback}>重试播放</button>}<div aria-label="播放速度">{[0.25,0.5,1].map(rate=><button type="button" key={rate} onClick={()=>changeRate(rate)}>{rate}×</button>)}<button type="button" onClick={fullscreen}>全屏</button></div>
  </>:<p className="pro-lab-empty">尚未选择本机视频。选择后可播放并记录时间点。</p>}

  {selection&&<GexMomentRestore file={selection.file} videoUrl={selection.url} videoRef={videoRef} onPlayRequested={playSafely}/>}
  <form className="pro-lab-form" aria-label="新建或编辑笔记" onSubmit={event=>{event.preventDefault();submit()}}>
   <button type="button" disabled={!selection} onClick={captureCurrent}>暂停并记录当前时间点</button>
   <label>时间点<input aria-label="时间点" value={timestamp} onChange={event=>setTimestamp(event.target.value)} placeholder="如 12:34"/></label>
   <label>技战术标签<input aria-label="技战术标签" value={tags} onChange={event=>setTags(event.target.value)} placeholder="如 发球, 接发球, 第三板"/></label>
   <div className="pro-lab-presets">{PRO_LAB_TACTICAL_TAGS.map(tag=><button type="button" key={tag} onClick={()=>setTags(value=>[...new Set([...parseTags(value),tag])].join(', '))}>{tag}</button>)}</div>
   <label>观察备注<textarea aria-label="观察备注" value={coachNote} maxLength={500} onChange={event=>setCoachNote(event.target.value)} placeholder="记录可回看的观察，不自动推断技术或原因。"/></label>
   {error&&<p role="alert" className="pro-lab-error">{error}</p>}
   {status&&<p role="status" className="pro-lab-status">{status}</p>}
   <div className="pro-lab-form-actions"><button type="submit" className="primary" disabled={!selection||!storage.writable}>{editingId?'保存修改':'保存笔记'}</button>{editingId&&<button type="button" onClick={()=>{setEditingId(null);setTimestamp('');setTags('');setCoachNote('');setError('');setStatus('')}}>取消编辑</button>}<button type="button" onClick={exportJson}>导出我的笔记 JSON</button></div>
  </form>

  <p className="small">建议定期导出笔记 JSON 备份。清除浏览器数据会移除本机笔记；JSON 不包含视频内容。</p>
  <section className="pro-lab-notes" aria-label="当前视频的笔记">
   <div className="pro-lab-list-heading"><h3>当前视频笔记 · {shown.length}</h3><label>按标签筛选<select value={tagFilter} onChange={event=>setTagFilter(event.target.value)}><option value="">全部标签</option>{allTags.map(tag=><option key={tag}>{tag}</option>)}</select></label></div>
   {!selection?<p>选择对应本机文件后显示已绑定笔记。</p>:!shown.length?<p>这段视频还没有已绑定的笔记。</p>:<div className="pro-lab-list">{shown.map(note=><article className="pro-lab-note" key={note.id}>
    <button type="button" className="pro-lab-time" onClick={()=>seek(note)} aria-label={`回到 ${formatTimestamp(note.seconds)}`}>{formatTimestamp(note.seconds)} ▶</button>
    <div>{note.tags.map(tag=><span className="pro-lab-tag" key={tag}>#{tag}</span>)}</div>
    {note.coachNote&&<p>{note.coachNote}</p>}
    <div className="pro-lab-note-actions"><button type="button" onClick={()=>startEdit(note)}>编辑</button><button type="button" onClick={()=>remove(note)}>删除</button></div>
   </article>)}</div>}
  </section>

  {oldNotes.length>0&&<details className="pro-lab-legacy"><summary>旧版未绑定文件身份笔记 · {oldNotes.length}</summary><p>这些笔记仅有旧版文件名，不能自动关联到同名录像。选择正确文件后，可逐条确认绑定；否则它们保持未绑定并继续保存在本机。</p>{oldNotes.map(note=><article key={note.id}><strong>{note.videoName} · {formatTimestamp(note.seconds)}</strong><p>{note.tags.map(tag=>`#${tag}`).join(' ')} {note.coachNote}</p><button type="button" disabled={!selection||!storage.writable} onClick={()=>rebindLegacy(note)}>确认关联到当前文件</button><button type="button" onClick={()=>remove(note)}>删除</button></article>)}</details>}
 </section>;
}
