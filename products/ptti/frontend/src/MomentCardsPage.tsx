import {useMemo,useState,type MouseEvent} from 'react';
import type {FeedVideo} from './feedCatalog';
import OfficialLinkRecovery from './OfficialLinkRecovery';
import {buildOfficialJump,createMoment,deleteMoment,exportMoments,filterMomentsByTag,formatTimestamp,loadMomentState,parseTags,writeMoments,updateMoment,type MomentCard} from './momentCards.mjs';
import './moment-cards.css';

type MomentInput={videoKey:string;title:string;timestamp:string;note:string;tags:string};

const EMPTY:MomentInput={videoKey:'',title:'',timestamp:'',note:'',tags:''};

function initialMoments(){try{return loadMomentState(window.localStorage)}catch{return {moments:[] as MomentCard[],writable:false,error:'此浏览器存储不可用，暂不能保存时刻。'}}}
export default function MomentCards({videos,onBack,onOpenOfficial,onPlayLocal,failedWatchUrl}:{videos:FeedVideo[];onBack:()=>void;onPlayLocal?:(videoId:string)=>void;onOpenOfficial?:(event:MouseEvent<HTMLAnchorElement>,url:string,expectedVideoId?:string)=>void;failedWatchUrl?:string|null}){
 const [initial]=useState(initialMoments);
 const [moments,setMoments]=useState<MomentCard[]>(initial.moments);
 const [form,setForm]=useState<MomentInput>(EMPTY);
 const [editingId,setEditingId]=useState<string|null>(null);
 const [error,setError]=useState(initial.error);
 const [notice,setNotice]=useState('');
 const [tagFilter,setTagFilter]=useState('');
 const byKey=new Map(videos.map(v=>[v.key,v]));
 const allTags=useMemo(()=>[...new Set(moments.flatMap(m=>m.tags||[]))],[moments]);
 const shown=useMemo(()=>filterMomentsByTag(moments,tagFilter),[moments,tagFilter]);
 function startEdit(m:MomentCard){setEditingId(m.id);setForm({videoKey:m.videoKey,title:m.title,timestamp:formatTimestamp(m.seconds),note:m.note||'',tags:(m.tags||[]).join(', ')});setError(initial.error);setNotice('')}
 function cancelEdit(){setEditingId(null);setForm(EMPTY);setError(initial.error)}
 function commit(next:MomentCard[]){
  setNotice('');
  if(!initial.writable){setError(initial.error);return false}
  try{const saved=writeMoments(window.localStorage,next);if(!saved.ok){setError(saved.error);return false}}
  catch{setError('此浏览器存储不可用，时刻未保存；请保留当前输入。');return false}
  setMoments(next);if(tagFilter&&!next.some(moment=>moment.tags.includes(tagFilter)))setTagFilter('');setError('');setNotice('已保存在此浏览器');return true;
 }
 function submit(){setNotice('');const input={...form,tags:parseTags(form.tags)};
  const result=editingId?updateMoment(moments,editingId,{...input,timestamp:form.timestamp}):createMoment(moments,{...input,timestamp:form.timestamp});
  if(!byKey.has(form.videoKey)){setError('请从当前已登记来源中选择比赛');return}
  if(result.errors.length){setError(result.errors.join('；'));return}
  if(commit(result.moments))cancelEdit()}
 function exportJson(){
  setNotice('');
  try{const data=exportMoments(moments),url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),anchor=document.createElement('a');anchor.href=url;anchor.download='ptti-moment-cards-backup.json';anchor.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);setNotice(`已导出 ${data.momentCount} 张时刻卡片备份，不含视频内容。`);setError('')}
  catch{setError('备份导出失败；本机时刻记录未改变。')}
 }
 return <div className="moment-cards">
  <div className="moment-header"><button onClick={onBack}>← 返回 Cinema</button><div><h2>时刻卡片</h2><p>为已登记视频保存时间标记、备注和标签。记录仅保存在当前浏览器；个人标记不代表已经核验的视频片段或播放资格。</p></div></div>
  <form className="moment-form" aria-label="新建或编辑时刻" onSubmit={event=>{event.preventDefault();submit()}}>
   <label>比赛<select aria-label="选择比赛" value={form.videoKey} onChange={e=>setForm({...form,videoKey:e.target.value})}><option value="">选择一场比赛</option>{videos.map(v=><option key={v.key} value={v.key}>{v.event} · {v.title}</option>)}</select></label>
   <label>时间戳<input aria-label="时间戳" value={form.timestamp} onChange={e=>setForm({...form,timestamp:e.target.value})} placeholder="如 12:34 或 1:02:03" /></label>
   <label>时刻名称<input aria-label="时刻名称" value={form.title} onChange={e=>setForm({...form,title:e.target.value})} placeholder="如 关键分反手变线" maxLength={60} /></label>
   <label>个人备注<textarea aria-label="个人备注" value={form.note} onChange={e=>setForm({...form,note:e.target.value})} placeholder="当时为什么这样打？下次想改什么？" maxLength={500} /></label>
   <label>标签<input aria-label="标签" value={form.tags} onChange={e=>setForm({...form,tags:e.target.value})} placeholder="用逗号分隔，如 关键分, 发球" /></label>
   {error&&<p role="alert" className="moment-error">{error}</p>}
   {notice&&<p role="status">{notice}</p>}
   <div className="moment-actions"><button type="submit" className="primary">{editingId?'保存修改':'保存时刻'}</button>{editingId&&<button type="button" onClick={cancelEdit}>取消编辑</button>}</div>
  </form>
  <div className="moment-filter"><label>按标签筛选<select aria-label="按标签筛选" value={tagFilter} onChange={e=>setTagFilter(e.target.value)}><option value="">全部标签</option>{allTags.map(t=><option key={t} value={t}>{t}</option>)}</select></label><span>{shown.length} / {moments.length} 张</span><button onClick={exportJson}>导出时刻备份 JSON</button></div>
  <p className="small">建议定期导出备份；清除浏览器数据会移除本机时刻记录。</p>
  {!shown.length?<p className="moment-empty">还没有时刻卡片。选一场比赛，填一个时间戳和名字，先保存第一张。</p>:<div className="moment-grid">{shown.map(m=>{const video=byKey.get(m.videoKey);const jump=video?buildOfficialJump(video,m.seconds):{precise:false,url:null,reason:'比赛已不在当前目录'};return <article className="moment-card" key={m.id}>
   <div className="moment-time">{formatTimestamp(m.seconds)}</div>
   <strong>{m.title}</strong>
   <span>{video?`${video.event} · ${video.title}`:'比赛已不在当前目录'}</span>
   {m.note&&<p>{m.note}</p>}
   <div className="moment-tags">{(m.tags||[]).map((t:string)=><button key={t} onClick={()=>setTagFilter(t)}>#{t}</button>)}</div>
   <div className="moment-actions">
    {video?.kind==='LOCAL'&&onPlayLocal?<button onClick={()=>onPlayLocal(video.source.video_id)}>打开本机视频（手动定位到 {formatTimestamp(m.seconds)}）</button>:jump.url?<a href={jump.url} target="_blank" rel="noopener noreferrer" onClick={event=>onOpenOfficial?.(event,jump.url!,jump.precise?video?.source?.video_id:undefined)}>{jump.precise?'在官方页面定位此时刻 ↗':'打开官方页面 ↗'}</a>:<span>无官方观看链接</span>}
    {jump.url&&failedWatchUrl===jump.url&&<div role="status"><p>定位链接未能打开，可复制链接，或从官方页面手动定位。</p>{video?.watchUrl&&<a href={video.watchUrl} target="_blank" rel="noopener noreferrer" onClick={event=>onOpenOfficial?.(event,video.watchUrl!)}>打开原始官方页面 ↗</a>}<OfficialLinkRecovery url={jump.url} buttonLabel="复制官方定位链接"/></div>}
    {!jump.precise&&jump.reason&&<small>{jump.reason}</small>}
    <button onClick={()=>startEdit(m)}>编辑</button>
    <button onClick={()=>{if(window.confirm('确定删除这张时刻卡片吗？')&&commit(deleteMoment(moments,m.id))&&editingId===m.id)cancelEdit()}}>删除</button>
   </div>
  </article>})}</div>}
 </div>;
}
