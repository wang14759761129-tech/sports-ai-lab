import {useEffect,useMemo,useState,type PointerEvent as ReactPointerEvent} from 'react';
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
 const [selectedConflictId,setSelectedConflictId]=useState(''),[reviewDrawing,setReviewDrawing]=useState(false),[reviewBox,setReviewBox]=useState<number[]|null>(null),[drawStart,setDrawStart]=useState<number[]|null>(null);
 const [trackingArchitecture,setTrackingArchitecture]=useState<'DETECTION_ANCHORED_MASK_TRACKING'|'CLOSED_LOOP_SINGLE_SEED'>('DETECTION_ANCHORED_MASK_TRACKING');
 const [anchorInterval,setAnchorInterval]=useState('1.0');
 const [reacquireRole,setReacquireRole]=useState<'NEAR_PLAYER'|'FAR_PLAYER'>('FAR_PLAYER');
 const sample=useMemo(()=>samples.find(item=>item.sample_id===sampleId),[samples,sampleId]);
 const candidates:Candidate[]=detections?.detections||[];
 const events:any[]=job?.events||[];
 const anomalies=events.filter(event=>['TRACK_LOST','OUT_OF_FRAME','IDENTITY_UNCERTAIN','IDENTITY_AMBIGUOUS','AUTO_REACQUIRED','MANUAL_REACQUIRED','SCENE_RESET','MASK_SUSPECT','VISIBLE_MASK_GAP','MASK_CONFLICT'].includes(event.type)&&event.status!=='RESOLVED');
 const conflictEvents=events.filter(event=>event.type==='MASK_CONFLICT'&&event.status!=='RESOLVED');
 const selectedConflict=conflictEvents.find(event=>event.event_id===selectedConflictId)||conflictEvents[0];
 const selectedAnomaly=anomalies[selectedEvent];
 const anchors=events.filter(event=>['AUTO_ANCHOR','SAM2_REPROMPT','REVERSE_REPAIR'].includes(event.type));
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
  try{const candidate_review=Object.fromEntries(otherIds.map(id=>[id,'MARK_OTHER']));const result=await jsonRequest(`${loopApi}/jobs`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sample_id:sampleId,frame_index:frame,detection_set_id:detections.detection_set_id,near_candidate_id:near.candidate_id,far_candidate_id:far.candidate_id,near_bbox:near.bbox,far_bbox:far.bbox,candidate_review,user_confirmed:true,tracking_architecture:trackingArchitecture,anchor_interval_seconds:Number(anchorInterval)})});setJobId(result.job_id);setJob({status:result.status,stage:'等待 GPU worker 启动',processed_frames:0,frame_count:sample.frames,events:[],tracking_architecture:trackingArchitecture,anchor_interval_seconds:Number(anchorInterval)});setTab('track')}
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
  if(anomalies[next]?.type==='MASK_CONFLICT')setSelectedConflictId(anomalies[next].event_id);
 }
 function reviewPoint(event:ReactPointerEvent<HTMLImageElement>){
  const rect=event.currentTarget.getBoundingClientRect();const width=Number(sample?.width||event.currentTarget.naturalWidth);const height=Number(sample?.height||event.currentTarget.naturalHeight);
  return [Math.max(0,Math.min(width,(event.clientX-rect.left)*width/rect.width)),Math.max(0,Math.min(height,(event.clientY-rect.top)*height/rect.height))];
 }
 async function resolveConflict(choice:'FORWARD'|'REVERSE'|'NEITHER'|'REBOX'){
  if(!jobId||!selectedConflict)return;setBusy(true);setError('');
  try{
   const body:any={event_id:selectedConflict.event_id,role:selectedConflict.role,choice};
   if(choice==='REBOX'){
    if(!reviewBox||reviewBox[2]-reviewBox[0]<4||reviewBox[3]-reviewBox[1]<4)throw new Error('请在原始画面上画出完整人物框。');
    body.bbox=reviewBox;
   }
   const result=await jsonRequest(`${loopApi}/jobs/${jobId}/conflicts`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
   if(choice==='NEITHER'||result.status==='NEEDS_REBOX'){setReviewDrawing(true);setReviewBox(null);}
   else{setReviewDrawing(false);setReviewBox(null);}
   setJob(await jsonRequest(`${loopApi}/jobs/${jobId}`));
  }catch(err:any){setError(err.message)}finally{setBusy(false)}
 }
 async function confirmOutOfFrame(event:any,confirm:boolean){
  if(!jobId)return;setBusy(true);setError('');
  try{await jsonRequest(`${loopApi}/jobs/${jobId}/out-of-frame-reviews`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({event_id:event.event_id,role:event.role,confirm_out_of_frame:confirm})});setJob(await jsonRequest(`${loopApi}/jobs/${jobId}`));}
  catch(err:any){setError(err.message)}finally{setBusy(false)}
 }

 return <Card className="closed-loop-card">
  <div className="section-title"><div><h2>球员持续追踪</h2><p>先由你确认两名球员，再开始 SAM 2.1 Small 传播；身份不会因丢帧自动互换。</p></div><span className="badge muted">GPU 研究预览 · 不访问正式数据库</span></div>
  <div className="tabs closed-loop-tabs"><button className={tab==='prepare'?'active':''} onClick={()=>setTab('prepare')}>1–3 · 选择片段与确认角色</button><button className={tab==='track'?'active':''} disabled={!jobId} onClick={()=>setTab('track')}>4–8 · 追踪与异常复核</button></div>
  {tab==='prepare'?<>
   <div className="closed-loop-setup">
    <label>选择真实研究比赛<select value={sampleId} disabled={busy} onChange={e=>setSampleId(e.target.value)}>{samples.map(item=><option key={item.sample_id} value={item.sample_id}>{item.match_id.replace('game_','比赛 ')} · {item.start_seconds} 秒处起 · 10 秒研究片段 · {item.seed_screening==='SEEDS_READY'?'已有双人候选':'需重新检查'}</option>)}</select></label>
    <label>追踪方式<select value={trackingArchitecture} disabled={busy} onChange={e=>setTrackingArchitecture(e.target.value as any)}><option value="DETECTION_ANCHORED_MASK_TRACKING">检测锚点驱动 · 推荐</option><option value="CLOSED_LOOP_SINGLE_SEED">单次初始化 · 对照基线</option></select></label>
    {trackingArchitecture==='DETECTION_ANCHORED_MASK_TRACKING'&&<label>自动检测间隔<select value={anchorInterval} disabled={busy} onChange={e=>setAnchorInterval(e.target.value)}><option value="0.5">每 0.5 秒 · 更密</option><option value="1.0">每 1 秒 · 平衡</option><option value="2.0">每 2 秒 · 更稀</option></select><small>只在固定时间点重新检测；身份不明确时标记复核，不会强行绑定。</small></label>}
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
   {job&&<div className="closed-loop-job-status" role="status"><div><strong>{job.status==='RUNNING'?'追踪中':job.status==='RUNNING_REVIEW'?'局部复核处理中':job.status==='NEEDS_USER_CONFIRMATION'?'需要确认球员身份':job.status==='COMPLETE'?'追踪完成':job.status==='FAILED'?'追踪失败':job.stage}</strong><span>{job.tracking_architecture==='DETECTION_ANCHORED_MASK_TRACKING'?`检测锚点 · 每 ${job.anchor_interval_seconds||anchorInterval} 秒重新确认球员位置`:job.stage}</span></div><div className="closed-loop-progress"><span style={{width:`${job.total_steps?Math.min(100,100*(job.processed_frames||0)/job.total_steps):job.frame_count?Math.min(100,100*(job.processed_frames||0)/job.frame_count):0}%`}}/><small>{job.processed_frames||0}/{job.total_steps||job.frame_count||sample?.frames||300} {job.total_steps?'个处理步骤':'帧'} </small></div>{job.status==='FAILED'&&<button onClick={()=>setTab('prepare')}>返回种子确认并重试</button>}</div>}
   {job?.review_candidates&&<section className="closed-loop-reacquire"><div><h3>追踪中断 · 请确认对应球员</h3><p>固定身份不会自动更换。这里只显示与所选身份的时空位置相符的人物候选；确认后将以原 object ID 重新提示 SAM2 并继续。</p><label>要恢复的身份<select value={reacquireRole} onChange={e=>setReacquireRole(e.target.value as any)}><option value="NEAR_PLAYER" disabled={!candidateIdsByRole.NEAR_PLAYER?.length&&reacquireRole!=='NEAR_PLAYER'}>Near Player · 近端球员</option><option value="FAR_PLAYER" disabled={!candidateIdsByRole.FAR_PLAYER?.length&&reacquireRole!=='FAR_PLAYER'}>Far Player · 远端球员</option></select></label></div><div className="closed-loop-review-frame"><img src={`${loopApi}/jobs/${jobId}/assets/review-frames/${String(job.review_candidates.frame_index).padStart(5,'0')}.jpg`} alt="追踪异常帧与重新检测的人物候选"/><div>{reviewCandidates.map((candidate:Candidate)=><button key={candidate.candidate_id} disabled={busy} onClick={()=>reacquire(candidate)}>将此框关联到{reacquireRole==='NEAR_PLAYER'?'近端':'远端'}球员 · {candidate.detector_score?.toFixed(2)}</button>)}</div></div>{!reviewCandidates.length&&<p className="empty-state">当前身份没有几何上合理的候选。追踪会保留异常状态，不会把裁判或无关人物交给你误选。</p>}</section>}
   {selectedConflict&&<section className="closed-loop-anomalies mask-conflict-review"><div className="section-title"><div><h3>前向 / 反向遮罩冲突 · {selectedConflict.role==='NEAR_PLAYER'?'近端球员':'远端球员'}</h3><p>{((selectedConflict.start_timestamp_ms||0)/1000).toFixed(2)}–{((selectedConflict.end_timestamp_ms||0)/1000).toFixed(2)} 秒 · {selectedConflict.conflict_frames} 帧需要判断。原始两路结果会保留。</p></div><span className="badge warning">需要确认</span></div><div className="mask-conflict-comparison"><figure><figcaption>原始画面 · 可用于重新框选</figcaption><div className="mask-rebox-canvas"><img src={`${loopApi}/jobs/${jobId}/conflicts/${encodeURIComponent(selectedConflict.event_id)}/source`} alt="冲突位置原始比赛画面" onPointerDown={event=>{if(!reviewDrawing||busy)return;event.currentTarget.setPointerCapture(event.pointerId);const point=reviewPoint(event);setDrawStart(point);setReviewBox([point[0],point[1],point[0],point[1]])}} onPointerMove={event=>{if(!reviewDrawing||!drawStart)return;const point=reviewPoint(event);setReviewBox([Math.min(drawStart[0],point[0]),Math.min(drawStart[1],point[1]),Math.max(drawStart[0],point[0]),Math.max(drawStart[1],point[1])])}} onPointerUp={()=>{setDrawStart(null)}} style={{cursor:reviewDrawing?'crosshair':'default'}}/>{reviewBox&&sample&&<svg viewBox={`0 0 ${sample.width} ${sample.height}`} preserveAspectRatio="none"><rect x={reviewBox[0]} y={reviewBox[1]} width={reviewBox[2]-reviewBox[0]} height={reviewBox[3]-reviewBox[1]}/></svg>}</div></figure><figure><figcaption>A · 前向传播 · 锚点 {selectedConflict.forward_source_anchor}</figcaption><img src={`${loopApi}/jobs/${jobId}/conflicts/${encodeURIComponent(selectedConflict.event_id)}/forward`} alt="前向 SAM2 mask"/></figure><figure><figcaption>B · 反向传播 · 锚点 {selectedConflict.reverse_source_anchor}</figcaption><img src={`${loopApi}/jobs/${jobId}/conflicts/${encodeURIComponent(selectedConflict.event_id)}/reverse`} alt="反向 SAM2 mask"/></figure></div><div className="actions mask-conflict-actions"><button disabled={busy||reviewDrawing} onClick={()=>resolveConflict('FORWARD')}>选 A 并局部重跑</button><button disabled={busy||reviewDrawing} onClick={()=>resolveConflict('REVERSE')}>选 B 并局部重跑</button><button disabled={busy} onClick={()=>resolveConflict('NEITHER')}>都不对，重新框人</button><button className="secondary" disabled={busy||!reviewDrawing||!reviewBox} onClick={()=>resolveConflict('REBOX')}>使用新框局部重跑</button>{reviewDrawing&&<button disabled={busy} onClick={()=>{setReviewDrawing(false);setReviewBox(null)}}>取消画框</button>}</div><p className="small">系统会从冲突区前后最近的健康锚点，仅重跑覆盖冲突的局部窗口；不会重跑整段视频。若仍有前后向分歧，复核项会继续保留。</p></section>}
   <section className="closed-loop-anomalies"><div className="section-title"><div><h3>只检查追踪异常</h3><p>身份不明确、可见球员无可用 mask、离开画面、mask 冲突或追踪丢失。</p></div><div className="actions"><button disabled={!anomalies.length} onClick={()=>jumpToAnomaly(selectedEvent-1)}>上一异常</button><button disabled={!anomalies.length} onClick={()=>jumpToAnomaly(selectedEvent+1)}>下一异常</button></div></div>{anomalies.length?<div className="closed-loop-event-list">{anomalies.map((event,index)=><button key={`${event.type}-${event.frame}-${index}`} className={selectedEvent===index?'selected':''} onClick={()=>{setSelectedEvent(index);if(event.type==='MASK_CONFLICT')setSelectedConflictId(event.event_id);const player=document.querySelector<HTMLVideoElement>('.closed-loop-output-video');if(player)player.currentTime=(event.frame||0)/(sample?.sample_fps||30)}}><strong>{event.type==='TRACK_LOST'?'追踪丢失':event.type==='OUT_OF_FRAME'?'球员离开画面':event.type==='AUTO_REACQUIRED'?'自动重新关联':event.type==='IDENTITY_UNCERTAIN'||event.type==='IDENTITY_AMBIGUOUS'?'身份需要确认':event.type==='MASK_CONFLICT'?'前后向遮罩冲突':event.type==='VISIBLE_MASK_GAP'?'可见球员暂缺遮罩':event.type==='SCENE_RESET'?'镜头切换后重新定位':'需要复核'}</strong><span>第 {(event.frame||0)+1} 帧 · {((event.timestamp_ms||0)/1000).toFixed(2)} 秒</span><small>{event.role||event.evidence||'固定球员身份未更改'}{event.confidence_level?` · ${event.confidence_level}`:''}</small></button>)}</div>:<p className="empty-state">{job?.status==='COMPLETE'?'没有产生需复核事件。':'异常出现后会显示在这里；无需逐帧检查。'}</p>}</section>
   {selectedAnomaly?.type==='OUT_OF_FRAME'&&selectedAnomaly.status!=='CONFIRMED'&&<section className="closed-loop-anomalies"><h3>确认球员暂时离开画面？</h3><p>{selectedAnomaly.role==='NEAR_PLAYER'?'近端':'远端'}球员 · {selectedAnomaly.confidence_level||'LOW'} 证据 · {selectedAnomaly.source==='HUMAN_REVIEW'?'来自人工可见性复核':'来自组合追踪证据'}</p><div className="actions"><button disabled={busy} onClick={()=>confirmOutOfFrame(selectedAnomaly,true)}>确认离开画面</button><button disabled={busy} onClick={()=>confirmOutOfFrame(selectedAnomaly,false)}>改为身份不确定</button></div></section>}
   {!!anchors.length&&<section className="closed-loop-anomalies"><h3>自动追踪锚点</h3><p>RT-DETR 在这些时间点确认球员位置，并用相同 object ID 重新提示遮罩模型。</p><div className="closed-loop-event-list">{anchors.slice(0,24).map((event,index)=><button key={`${event.type}-${event.role}-${event.frame}-${index}`} onClick={()=>{const player=document.querySelector<HTMLVideoElement>('.closed-loop-output-video');if(player)player.currentTime=(event.frame||0)/(sample?.sample_fps||30)}}><strong>{event.type==='AUTO_ANCHOR'?'自动校正':event.type==='REVERSE_REPAIR'?'反向补全':'追踪锚点'}</strong><span>{event.role==='NEAR_PLAYER'?'近端球员':'远端球员'} · {((event.timestamp_ms||0)/1000).toFixed(2)} 秒</span><small>固定 object ID {event.object_id||'不变'}</small></button>)}</div></section>}
   {job?.status==='COMPLETE'&&<div className="closed-loop-result"><h3>Near / Far 追踪结果</h3><div className="facts"><span>Near 可见样本追踪率<strong>{job.summary?.NEAR_PLAYER?.visible_window_sample_coverage==null?'待人工标注':`${(100*job.summary.NEAR_PLAYER.visible_window_sample_coverage).toFixed(1)}%`}</strong></span><span>Far 可见样本追踪率<strong>{job.summary?.FAR_PLAYER?.visible_window_sample_coverage==null?'待人工标注':`${(100*job.summary.FAR_PLAYER.visible_window_sample_coverage).toFixed(1)}%`}</strong></span><span>自动锚定<strong>{job.recovery?.automatic_anchors??job.recovery?.auto_reacquisitions??0}</strong></span><span>SAM 重新提示<strong>{job.recovery?.sam2_reprompts??job.recovery?.re_prompts??0}</strong></span><span>反向补全<strong>{job.recovery?.reverse_mask_repairs??0}</strong></span><span>需确认<strong>{job.recovery?.ambiguous_associations??job.recovery?.review_events??0}</strong></span></div><video className="closed-loop-output-video" controls preload="metadata" src={`${loopApi}/jobs/${jobId}/assets/${job.tracking_architecture==='DETECTION_ANCHORED_MASK_TRACKING'?'anchor_guided_tracking_overlay.mp4':'player_tracking_overlay.mp4'}`}/><p className="small">{job.visibility_truth_status==='HUMAN_REVIEWED'?'覆盖率按人工复核的半秒窗口中点样本计算；这是稀疏可见性检查，不代表逐帧标注。':'可见时段真值尚未完成，因此不计算可见样本覆盖率。'} 这是视觉证据，不代表动作或战术判断；当前片段没有同时间轴 BallTrack RAW 结果。</p><details><summary>研究数据与逐帧原始统计</summary><p>检测锚点间隔：{job.anchor_interval_seconds||'—'} 秒；数据来源：Extended OpenTTGames · CC BY-NC-SA 4.0 · 仅研究/非商业。</p><p>Near 原始 mask：{job.summary?.NEAR_PLAYER?.tracked}/{job.summary?.NEAR_PLAYER?.frames}；Far 原始 mask：{job.summary?.FAR_PLAYER?.tracked}/{job.summary?.FAR_PLAYER?.frames}。人工可见样本：Near {job.summary?.NEAR_PLAYER?.visible_mask_window_samples??'—'}/{job.summary?.NEAR_PLAYER?.visible_window_samples??'—'}，Far {job.summary?.FAR_PLAYER?.visible_mask_window_samples??'—'}/{job.summary?.FAR_PLAYER?.visible_window_samples??'—'}。固定 object ID 不变；无独立身份标注，语义身份交换率未评价。</p></details><button className="primary" onClick={resetLoop}>选择另一片段继续测试</button></div>}
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
