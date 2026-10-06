import {useEffect,useMemo,useState} from 'react';
import {Card} from './ui';
import './player-tracking-closed-loop.css';

const legacyApi='/api/vision/v2/player-tracking';
const loopApi=`${legacyApi}/closed-loop`;
const legacyAsset=(name:string)=>`${legacyApi}/assets/${encodeURIComponent(name)}`;
const legacyFrame=(frame:number,view:'source'|'overlay')=>`${legacyApi}/frames/${frame}/${view}`;
type Candidate={candidate_id:string;bbox:number[];detector_score:number;detector?:string;role?:string;status?:string};

async function jsonRequest(url:string,options?:RequestInit){
 const response=await fetch(url,options);
 let value:any={};
 try{value=await response.json()}catch{}
 if(!response.ok)throw new Error(value.detail||'请求没有完成，请检查本机视觉 worker。');
 return value;
}

function ClosedLoopWorkspace(){
 const [samples,setSamples]=useState<any[]>([]),[sampleId,setSampleId]=useState(''),[frame,setFrame]=useState(0);
 const [detections,setDetections]=useState<any>(null),[near,setNear]=useState<Candidate|null>(null),[far,setFar]=useState<Candidate|null>(null);
 const [otherIds,setOtherIds]=useState<string[]>([]),[confirmed,setConfirmed]=useState(false),[jobId,setJobId]=useState(''),[job,setJob]=useState<any>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[tab,setTab]=useState<'prepare'|'track'>('prepare'),[selectedEvent,setSelectedEvent]=useState(0);
 const [reacquireRole,setReacquireRole]=useState<'NEAR_PLAYER'|'FAR_PLAYER'>('FAR_PLAYER');
 const sample=useMemo(()=>samples.find(item=>item.sample_id===sampleId),[samples,sampleId]);
 const candidates:Candidate[]=detections?.detections||[];
 const events:any[]=job?.events||[];
 const anomalies=events.filter(event=>['TRACK_LOST','OUT_OF_FRAME','IDENTITY_UNCERTAIN','AUTO_REACQUIRED','MANUAL_REACQUIRED','SCENE_RESET','MASK_SUSPECT'].includes(event.type));
 const candidateIdsByRole:Record<string,string[]>=job?.review_candidates?.candidate_ids_by_role||{};
 const reviewCandidates:Candidate[]=(job?.review_candidates?.detections||[]).filter((candidate:Candidate)=>
  (candidateIdsByRole[reacquireRole]||[]).includes(candidate.candidate_id));

 useEffect(()=>{jsonRequest(`${loopApi}/samples`).then(data=>{
  setSamples(data.samples||[]);setSampleId((data.samples||[]).find((item:any)=>item.sample_id==='game_4-t30')?.sample_id||(data.samples||[])[0]?.sample_id||'');
 }).catch(err=>setError(err.message));},[]);
 useEffect(()=>{if(!jobId)return;let stopped=false;const refresh=async()=>{
  try{const value=await jsonRequest(`${loopApi}/jobs/${jobId}`);if(!stopped){setJob(value);const requested=value.review_candidates?.requested_role;if(requested==='NEAR_PLAYER'||requested==='FAR_PLAYER')setReacquireRole(requested);setTab('track')}}
  catch(err:any){if(!stopped)setError(err.message)}
 };
 refresh();const timer=window.setInterval(refresh,1200);return()=>{stopped=true;window.clearInterval(timer)};
 },[jobId]);
 useEffect(()=>{setFrame(0);setDetections(null);setNear(null);setFar(null);setOtherIds([]);setConfirmed(false)},[sampleId]);

 async function runDetection(){
  if(!sampleId)return;setBusy(true);setError('');setDetections(null);setNear(null);setFar(null);setOtherIds([]);setConfirmed(false);
  try{const result=await jsonRequest(`${loopApi}/seed-detections`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sample_id:sampleId,frame_index:frame})});setDetections(result)}
  catch(err:any){setError(err.message)}finally{setBusy(false)}
 }
 function setRole(role:'NEAR_PLAYER'|'FAR_PLAYER',candidate:Candidate){
  setError('');setConfirmed(false);setOtherIds(old=>old.filter(id=>id!==candidate.candidate_id));
  const corrected={...candidate,bbox:[...candidate.bbox]};
  if(role==='NEAR_PLAYER'){if(far?.candidate_id===candidate.candidate_id)setFar(null);setNear(corrected)}
  else{if(near?.candidate_id===candidate.candidate_id)setNear(null);setFar(corrected)}
 }
 function markOther(candidate:Candidate){
  if(near?.candidate_id===candidate.candidate_id)setNear(null);if(far?.candidate_id===candidate.candidate_id)setFar(null);
  setOtherIds(old=>old.includes(candidate.candidate_id)?old.filter(id=>id!==candidate.candidate_id):[...old,candidate.candidate_id]);setConfirmed(false);
 }
 function updateBox(role:'NEAR_PLAYER'|'FAR_PLAYER',index:number,value:number){
  const setter=role==='NEAR_PLAYER'?setNear:setFar;const current=role==='NEAR_PLAYER'?near:far;if(!current)return;
  const bbox=[...current.bbox];bbox[index]=value;setter({...current,bbox});setConfirmed(false);
 }
 async function startTracking(){
  if(!sample||!detections||!near||!far||near.candidate_id===far.candidate_id||!confirmed)return;
  setBusy(true);setError('');
  try{const candidate_review=Object.fromEntries(otherIds.map(id=>[id,'MARK_OTHER']));const result=await jsonRequest(`${loopApi}/jobs`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sample_id:sampleId,frame_index:frame,detection_set_id:detections.detection_set_id,near_candidate_id:near.candidate_id,far_candidate_id:far.candidate_id,near_bbox:near.bbox,far_bbox:far.bbox,candidate_review,user_confirmed:true})});setJobId(result.job_id);setJob({status:result.status,stage:'等待 GPU worker 启动',processed_frames:0,frame_count:sample.frames,events:[]});setTab('track')}
  catch(err:any){setError(err.message)}finally{setBusy(false)}
 }
 function resetLoop(){setJobId('');setJob(null);setDetections(null);setNear(null);setFar(null);setOtherIds([]);setConfirmed(false);setFrame(0);setError('');setTab('prepare');setSelectedEvent(0)}
 async function reacquire(candidate:Candidate){
  if(!jobId)return;setBusy(true);setError('');
  try{await jsonRequest(`${loopApi}/jobs/${jobId}/reacquisitions`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({role:reacquireRole,candidate_id:candidate.candidate_id})});const value=await jsonRequest(`${loopApi}/jobs/${jobId}`);setJob(value)}
  catch(err:any){setError(err.message)}finally{setBusy(false)}
 }
 function jumpToAnomaly(index:number){
  if(!anomalies.length)return;const next=(index+anomalies.length)%anomalies.length;setSelectedEvent(next);
  const frameIndex=Number(anomalies[next]?.frame);const player=document.querySelector<HTMLVideoElement>('.closed-loop-output-video');
  if(player&&Number.isFinite(frameIndex))player.currentTime=Math.max(0,frameIndex/(sample?.sample_fps||30));
 }

 return <Card className="closed-loop-card">
  <div className="section-title"><div><h2>球员持续追踪</h2><p>先由你确认两名球员，再开始 SAM 2.1 Small 传播；身份不会因丢帧自动互换。</p></div><span className="badge muted">GPU 研究预览 · 不访问正式数据库</span></div>
  <div className="tabs closed-loop-tabs"><button className={tab==='prepare'?'active':''} onClick={()=>setTab('prepare')}>1–3 · 选择片段与确认角色</button><button className={tab==='track'?'active':''} disabled={!jobId} onClick={()=>setTab('track')}>4–8 · 追踪与异常复核</button></div>
  {tab==='prepare'?<>
   <div className="closed-loop-setup">
    <label>选择真实研究比赛<select value={sampleId} disabled={busy} onChange={e=>setSampleId(e.target.value)}>{samples.map(item=><option key={item.sample_id} value={item.sample_id}>{item.match_id.replace('game_','比赛 ')} · {item.start_seconds} 秒处起 · 10 秒研究片段 · {item.seed_screening==='SEEDS_READY'?'已有双人候选':'需重新检查'}</option>)}</select></label>
    <div className="closed-loop-frame-select"><label>确认画面 <strong>{frame+1}/{sample?.frames||300}</strong><input type="range" min="0" max={Math.max(0,(sample?.frames||300)-1)} value={frame} disabled={busy} onChange={e=>{setFrame(Number(e.target.value));setDetections(null);setNear(null);setFar(null);setOtherIds([]);setConfirmed(false)}}/></label><button disabled={!sample||busy} onClick={runDetection}>{busy?'正在检测…':'重新运行 RT-DETR 人物检测'}</button></div>
   </div>
   {sample&&<p className="small closed-loop-provenance">{sample.dataset} · {sample.rights} · 仅研究/非商业 · 来源 SHA256 已校验。请选择真实球员框，裁判不得作为球员种子。</p>}
   {detections&&<>
    <div className="closed-loop-seed-gallery"><div className="closed-loop-seed-image"><img src={detections.image_url} alt="真实比赛画面与 RT-DETR 人物候选框"/><div><span>检测分数是模型输出，不是校准概率</span><span>{detections.runtime?.device} · 推理 {detections.runtime?.inference_seconds}s</span></div></div>
     <div className="closed-loop-candidates"><h3>检测候选 · {candidates.length}</h3>{candidates.map((candidate,index)=>{
      const selectedRole=near?.candidate_id===candidate.candidate_id?'NEAR_PLAYER':far?.candidate_id===candidate.candidate_id?'FAR_PLAYER':'';
      const ignored=otherIds.includes(candidate.candidate_id);
      return <article key={candidate.candidate_id} className={selectedRole?'selected':''}><div><strong>{selectedRole==='NEAR_PLAYER'?'近端球员':selectedRole==='FAR_PLAYER'?'远端球员':ignored?'其他 / 忽略':`人物候选 ${index+1}`}</strong><span>{candidate.detector_score?.toFixed(3)} · {candidate.candidate_id}</span><small>框坐标 {candidate.bbox.map((v:number)=>Math.round(v)).join(' · ')}</small></div><div className="actions"><button disabled={busy} onClick={()=>setRole('NEAR_PLAYER',candidate)}>设为 Near</button><button disabled={busy} onClick={()=>setRole('FAR_PLAYER',candidate)}>设为 Far</button><button disabled={busy} onClick={()=>markOther(candidate)}>{ignored?'取消标记':'标为其他 / 忽略'}</button></div></article>
     })}{!candidates.length&&<p className="empty-state">本帧没有人物候选。可换一帧后重新检测。</p>}</div></div>
    <div className="closed-loop-selected-grid">{(['NEAR_PLAYER','FAR_PLAYER'] as const).map(role=>{const selected=role==='NEAR_PLAYER'?near:far;return <section key={role}><h3>{role==='NEAR_PLAYER'?'Near Player · 近端球员':'Far Player · 远端球员'}</h3>{selected?<><p>{selected.candidate_id} · detector score {selected.detector_score?.toFixed(3)}</p><div className="bbox-edit">{['x₁','y₁','x₂','y₂'].map((label,index)=><label key={label}>{label}<input type="number" value={Math.round(selected.bbox[index])} onChange={e=>updateBox(role,index,Number(e.target.value))}/></label>)}</div><small>可小幅修正框；RAW 检测仍保留。</small></>:<p className="empty-state">请选择上方一个人物候选。</p>}</section>})}</div>
    <label className="closed-loop-confirm"><input type="checkbox" checked={confirmed} disabled={!near||!far||near.candidate_id===far.candidate_id||busy} onChange={e=>setConfirmed(e.target.checked)}/><span>我已检查当前画面，确认 Near 和 Far 是两名不同的场上运动员；裁判/其他人物没有被当作球员。</span></label>
    <button className="primary closed-loop-start" disabled={busy||!confirmed||!near||!far||near.candidate_id===far.candidate_id} onClick={startTracking}>确认种子并开始追踪</button>
   </>}
  </>:<>
   {job&&<div className="closed-loop-job-status" role="status"><div><strong>{job.status==='RUNNING'?'追踪中':job.status==='NEEDS_USER_CONFIRMATION'?'需要确认球员身份':job.status==='COMPLETE'?'追踪完成':job.status==='FAILED'?'追踪失败':job.stage}</strong><span>{job.stage}</span></div><div className="closed-loop-progress"><span style={{width:`${job.frame_count?Math.min(100,100*(job.processed_frames||0)/job.frame_count):0}%`}}/><small>{job.processed_frames||0}/{job.frame_count||sample?.frames||300} 帧</small></div>{job.status==='FAILED'&&<button onClick={()=>setTab('prepare')}>返回种子确认并重试</button>}</div>}
   {job?.review_candidates&&<section className="closed-loop-reacquire"><div><h3>追踪中断 · 请确认对应球员</h3><p>固定身份不会自动更换。这里只显示与所选身份的时空位置相符的人物候选；确认后将以原 object ID 重新提示 SAM2 并继续。</p><label>要恢复的身份<select value={reacquireRole} onChange={e=>setReacquireRole(e.target.value as any)}><option value="NEAR_PLAYER" disabled={!candidateIdsByRole.NEAR_PLAYER?.length&&reacquireRole!=='NEAR_PLAYER'}>Near Player · 近端球员</option><option value="FAR_PLAYER" disabled={!candidateIdsByRole.FAR_PLAYER?.length&&reacquireRole!=='FAR_PLAYER'}>Far Player · 远端球员</option></select></label></div><div className="closed-loop-review-frame"><img src={`${loopApi}/jobs/${jobId}/assets/review-frames/${String(job.review_candidates.frame_index).padStart(5,'0')}.jpg`} alt="追踪异常帧与重新检测的人物候选"/><div>{reviewCandidates.map((candidate:Candidate)=><button key={candidate.candidate_id} disabled={busy} onClick={()=>reacquire(candidate)}>将此框关联到{reacquireRole==='NEAR_PLAYER'?'近端':'远端'}球员 · {candidate.detector_score?.toFixed(2)}</button>)}</div></div>{!reviewCandidates.length&&<p className="empty-state">当前身份没有几何上合理的候选。追踪会保留异常状态，不会把裁判或无关人物交给你误选。</p>}</section>}
   <section className="closed-loop-anomalies"><div className="section-title"><div><h3>只检查追踪异常</h3><p>丢失、画外、重新关联和需要确认的事件。</p></div><div className="actions"><button disabled={!anomalies.length} onClick={()=>jumpToAnomaly(selectedEvent-1)}>上一异常</button><button disabled={!anomalies.length} onClick={()=>jumpToAnomaly(selectedEvent+1)}>下一异常</button></div></div>{anomalies.length?<div className="closed-loop-event-list">{anomalies.map((event,index)=><button key={`${event.type}-${event.frame}-${index}`} className={selectedEvent===index?'selected':''} onClick={()=>{setSelectedEvent(index);const player=document.querySelector<HTMLVideoElement>('.closed-loop-output-video');if(player)player.currentTime=(event.frame||0)/(sample?.sample_fps||30)}}><strong>{event.type==='TRACK_LOST'?'追踪丢失':event.type==='OUT_OF_FRAME'?'球员离开画面':event.type==='AUTO_REACQUIRED'?'自动重新关联':event.type==='MANUAL_REACQUIRED'?'人工确认后继续':'身份需要复核'}</strong><span>第 {(event.frame||0)+1} 帧 · {((event.timestamp_ms||0)/1000).toFixed(2)} 秒</span><small>{event.role||event.evidence||'固定对象 ID 未更改'}</small></button>)}</div>:<p className="empty-state">{job?.status==='COMPLETE'?'没有产生需复核事件。':'异常出现后会显示在这里；无需逐帧检查。'}</p>}</section>
   {job?.status==='COMPLETE'&&<div className="closed-loop-result"><h3>Near / Far 视觉证据</h3><div className="facts"><span>Near mask<strong>{job.summary?.NEAR_PLAYER?.tracked}/{job.summary?.NEAR_PLAYER?.frames}</strong></span><span>Far mask<strong>{job.summary?.FAR_PLAYER?.tracked}/{job.summary?.FAR_PLAYER?.frames}</strong></span><span>自动重连<strong>{job.recovery?.auto_reacquisitions||0}</strong></span><span>人工重连<strong>{job.recovery?.manual_reacquisitions||0}</strong></span><span>追丢事件<strong>{job.recovery?.track_lost_events||0}</strong></span><span>身份互换<strong>0 · object ID 固定</strong></span></div><video className="closed-loop-output-video" controls preload="metadata" src={`${loopApi}/jobs/${jobId}/assets/player_tracking_overlay.mp4`}/><p className="small">这是球员 mask 与固定 object ID 的视觉结果。此研究片段没有同时间轴 BallTrack RAW 结果，因此未生成 Ball + Player 合成视频。</p><button className="primary" onClick={resetLoop}>选择另一片段继续测试</button></div>}
   {job?.status==='FAILED'&&<p role="alert" className="error-banner">处理失败：{job.error||'请查看 worker 状态后重试。'}</p>}
  </>}
  {error&&<p role="alert" className="error-banner">{error}</p>}
  <details><summary>实验来源、身份规则与运行状态</summary><p>RT-DETR R18 与 SAM 2.1 Hiera Small 运行在隔离 GPU worker；只使用 Extended OpenTTGames 官方训练集研究片段（CC BY-NC-SA 4.0，非商业用途）。</p><p>OBJECT_1 固定为 Near Player，OBJECT_2 固定为 Far Player。重新检测只可关联到原 object ID；不明确时暂停等待人工确认。</p><p>BallTrack RAW 保持独立，不由本工作流修改。正式数据库：NOT ACCESSED。</p></details>
 </Card>;
}

function HistoricalPreview(){
 const [data,setData]=useState<any>(null),[error,setError]=useState(''),[near,setNear]=useState(true),[far,setFar]=useState(true),[selected,setSelected]=useState(0);
 useEffect(()=>{jsonRequest(legacyApi).then(setData).catch(err=>setError(err.message))},[]);
 const available=new Set((data?.available_assets||[]).map((item:any)=>item.name));
 const videoName=near&&far?'player_tracking_overlay.mp4':near?'player_tracking_near.mp4':far?'player_tracking_far.mp4':'player_tracking_original.mp4';
 if(error)return <Card><h2>历史静态追踪结果</h2><p role="alert">{error}</p></Card>;
 if(!data)return <Card><h2>历史静态追踪结果</h2><p>正在读取研究结果…</p></Card>;
 if(data.status==='NOT_RUN')return <Card><h2>历史静态追踪结果</h2><p>{data.message}</p></Card>;
 const nearSummary=data.role_summary?.NEAR_PLAYER||{},farSummary=data.role_summary?.FAR_PLAYER||{};
 return <Card className="sam2-tracking-preview"><div className="section-title"><div><h2>历史静态追踪结果</h2><p>既有结果只读保留；新闭环任务不会覆盖它。</p></div><span className="badge muted">历史研究记录</span></div><div className="facts"><span>追踪时长<strong>{Number(data.duration_seconds).toFixed(0)} 秒</strong></span><span>采样帧<strong>{data.frames}</strong></span><span>近端连续<strong>{nearSummary.tracked}/{nearSummary.frames}</strong></span><span>远端连续<strong>{farSummary.tracked}/{farSummary.frames}</strong></span><span>身份不确定<strong>{data.identity_uncertain_events?.length||0}</strong></span><span>丢失帧<strong>{(nearSummary.track_lost||0)+(farSummary.track_lost||0)}</strong></span></div><div className="sam2-layer-switches"><label><input type="checkbox" checked={near} onChange={e=>setNear(e.target.checked)} disabled={!available.has('player_tracking_near.mp4')}/>近端球员 mask</label><label><input type="checkbox" checked={far} onChange={e=>setFar(e.target.checked)} disabled={!available.has('player_tracking_far.mp4')}/>远端球员 mask</label></div>{available.has(videoName)?<video className="sam2-preview-video" controls preload="metadata" src={legacyAsset(videoName)}/>:<p className="empty-state">当前图层的预览文件尚未生成。</p>}<div className="sam2-frame-gallery">{(data.samples||[]).map((item:any)=><button key={item.frame} className={selected===item.frame?'selected':''} onClick={()=>setSelected(item.frame)}><img loading="lazy" src={legacyFrame(item.frame,'overlay')} alt={`追踪叠加，第 ${item.frame+1} 帧`}/><span>{(item.timestamp_ms/1000).toFixed(1)} 秒 · 近端 {item.statuses.NEAR_PLAYER||'未知'} · 远端 {item.statuses.FAR_PLAYER||'未知'}</span></button>)}</div>{(data.samples||[]).some((item:any)=>item.frame===selected)&&<div className="sam2-frame-pair"><div><small>原始画面</small><img src={legacyFrame(selected,'source')} alt="原始比赛画面"/></div><div><small>人物 mask · 可用于人工检查</small><img src={legacyFrame(selected,'overlay')} alt="两名球员 mask 叠加"/></div></div>}<details><summary>历史运行来源与限制</summary><p>{data.dataset} · {data.rights} · 不用于商业用途。</p><code>{data.sam2?.checkpoint_sha256}</code><p>传播速度 {data.runtime?.effective_fps} 帧/秒 · 峰值显存 {((data.runtime?.peak_vram_allocated_bytes||0)/1024**2).toFixed(0)} MiB。</p>{data.limitations?.map((item:string)=><p key={item}>{item}</p>)}</details></Card>;
}

export default function PlayerTrackingPreview(){
 const [view,setView]=useState<'loop'|'history'>('loop');
 return <><div className="tabs"><button className={view==='loop'?'active':''} onClick={()=>setView('loop')}>球员追踪 · 闭环流程</button><button className={view==='history'?'active':''} onClick={()=>setView('history')}>历史静态研究结果</button></div>{view==='loop'?<ClosedLoopWorkspace/>:<HistoricalPreview/>}</>;
}
