import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {Card} from './ui';
import './player-motion.css';

const API='/api/vision/v2';
const BONES:[string,string][]=[
 ['left_shoulder','right_shoulder'],['left_shoulder','left_elbow'],['left_elbow','left_wrist'],
 ['right_shoulder','right_elbow'],['right_elbow','right_wrist'],['left_shoulder','left_hip'],
 ['right_shoulder','right_hip'],['left_hip','right_hip'],['left_hip','left_knee'],
 ['left_knee','left_ankle'],['right_hip','right_knee'],['right_knee','right_ankle'],
];
const ROLES=['NEAR_PLAYER','FAR_PLAYER'] as const;
type Role=typeof ROLES[number];

async function request(path:string,options?:RequestInit){
 const response=await fetch(`${API}${path}`,options);let data:any={};try{data=await response.json()}catch{}
 if(!response.ok)throw new Error(data.detail||'本机动作分析请求没有完成。');return data;
}

function CanvasOverlay({jobId,result,showBoxes,showNear,showFar,showConfidence,showTrail,mask,videoRef,hitData,hitEvents,showBall,showHits}:any){
 const canvas=useRef<HTMLCanvasElement>(null);
 const video=videoRef as {current:HTMLVideoElement|null};
 const [videoError,setVideoError]=useState('');
 const fps=Number(result?.video?.fps)||30;
 const rows=useMemo(()=>new Map((result?.records||[]).map((row:any)=>[`${row.frame}-${row.player_role}`,row])),[result]);
 const ballRows=useMemo(()=>new Map((hitData?.ball_observations||[]).map((row:any)=>[Number(row.frame),row])),[hitData]);
 const draw=useCallback(()=>{
  const v=video.current,c=canvas.current;if(!v||!c||!v.videoWidth||!v.videoHeight)return;
  if(c.width!==v.videoWidth||c.height!==v.videoHeight){c.width=v.videoWidth;c.height=v.videoHeight;}
  const ctx=c.getContext('2d');if(!ctx)return;ctx.clearRect(0,0,c.width,c.height);
  const frame=Math.min(Math.max(0,Math.floor(v.currentTime*fps)),(result?.video?.frame_count||1)-1);
  if(showBall){const ball:any=ballRows.get(frame);if(ball?.visible&&Number.isFinite(ball.x)&&Number.isFinite(ball.y)){ctx.beginPath();ctx.arc(ball.x,ball.y,Math.max(8,c.width/180),0,Math.PI*2);ctx.strokeStyle='#ffe36e';ctx.lineWidth=Math.max(3,c.width/500);ctx.stroke();ctx.fillStyle='#ffe36e';ctx.font=`600 ${Math.max(16,c.width/100)}px Microsoft YaHei UI, sans-serif`;ctx.fillText('球',ball.x+12,ball.y-10)}}
  if(showHits){const event=hitEvents.find((item:any)=>item.review?.action!=='REJECT'&&Math.abs((Number(item.review?.timestamp_ms??item.timestamp_ms)-Number(hitData?.clip_start_timestamp_ms||0))/1000-v.currentTime)<.20);if(event){const player=event.review?.player||event.candidate_player||'UNKNOWN';ctx.fillStyle='#fff';ctx.font=`700 ${Math.max(18,c.width/80)}px Microsoft YaHei UI, sans-serif`;ctx.fillText(`击球候选？${player==='NEAR_PLAYER'?'近端':player==='FAR_PLAYER'?'远端':'身份待确认'}`,14,32)}}
  const roleColors:Record<Role,string>={NEAR_PLAYER:'#36d6bd',FAR_PLAYER:'#ffac4b'};
  for(const role of ROLES){
   if((role==='NEAR_PLAYER'&&!showNear)||(role==='FAR_PLAYER'&&!showFar))continue;
   const current:any=rows.get(`${frame}-${role}`);if(!current)continue;
   const color=roleColors[role],points=current.keypoints||{};
   if(showBoxes&&current.bbox){const [x0,y0,x1,y1]=current.bbox;ctx.strokeStyle=color;ctx.lineWidth=Math.max(2,c.width/800);ctx.strokeRect(x0,y0,x1-x0,y1-y0);}
   if(!['GOOD','PARTIAL'].includes(current.pose_quality))continue;
   if(showTrail){
    const trail=[] as any[];
    for(let prior=Math.max(0,frame-Math.round(fps));prior<=frame;prior++){
     const item:any=rows.get(`${prior}-${role}`),wrist=item?.keypoints?.right_wrist;
     if(wrist&&wrist.score>=.35)trail.push(wrist);
    }
    if(trail.length>1){ctx.beginPath();trail.forEach((p,index)=>index?ctx.lineTo(p.x_global,p.y_global):ctx.moveTo(p.x_global,p.y_global));ctx.strokeStyle=color;ctx.globalAlpha=.58;ctx.lineWidth=Math.max(2,c.width/700);ctx.stroke();ctx.globalAlpha=1;}
   }
   ctx.lineCap='round';ctx.lineJoin='round';ctx.strokeStyle=color;ctx.lineWidth=Math.max(3,c.width/640);
   for(const [a,b] of BONES){const p=points[a],q=points[b];if(p&&q&&p.score>=.35&&q.score>=.35){ctx.beginPath();ctx.moveTo(p.x_global,p.y_global);ctx.lineTo(q.x_global,q.y_global);ctx.stroke();}}
   for(const point of Object.values(points) as any[]){if(point.score<.35)continue;ctx.beginPath();ctx.arc(point.x_global,point.y_global,showConfidence?Math.max(3,point.score*7):4,0,Math.PI*2);ctx.fillStyle=color;ctx.globalAlpha=showConfidence?Math.max(.2,point.score):1;ctx.fill();ctx.globalAlpha=1;}
   const label=role==='NEAR_PLAYER'?'近端':'远端';ctx.font=`600 ${Math.max(18,c.width/90)}px Microsoft YaHei UI, sans-serif`;ctx.fillStyle=color;ctx.fillText(`${label} · ${current.pose_quality}`,current.bbox?.[0]||10,Math.max(26,(current.bbox?.[1]||30)-8));
  }
 },[ballRows,fps,hitData,hitEvents,mask,result,rows,showBall,showBoxes,showConfidence,showFar,showHits,showNear,showTrail]);
 useEffect(()=>{const v=video.current;if(!v)return;const events=['timeupdate','seeked','loadeddata','play'];events.forEach(event=>v.addEventListener(event,draw));let raf=0;const tick=()=>{if(v&&!v.paused&&!v.ended)draw();raf=requestAnimationFrame(tick)};raf=requestAnimationFrame(tick);return()=>{events.forEach(event=>v.removeEventListener(event,draw));cancelAnimationFrame(raf)}},[draw]);
 const source=mask?`${API}/player-tracking/closed-loop/jobs/${jobId}/assets/anchor_guided_tracking_overlay.mp4`:`${API}/player-motion/jobs/${jobId}/source`;
 return <div className="motion-video-shell"><video ref={video} controls preload="metadata" src={source} onError={()=>setVideoError(mask?'这段视频没有可用的人物 Mask 预览。':'来源视频暂时无法播放，请重新读取追踪文件。')}/><canvas ref={canvas}/>{videoError&&<span className="motion-video-error">{videoError}</span>}</div>;
}

export default function PlayerMotionPanel(){
 const [snapshot,setSnapshot]=useState<any>(null),[selected,setSelected]=useState(''),[result,setResult]=useState<any>(null),[progress,setProgress]=useState<any>(null);
 const [hitData,setHitData]=useState<any>(null),[selectedHit,setSelectedHit]=useState(''),[hitTimeDraft,setHitTimeDraft]=useState(''),[hitPlayer,setHitPlayer]=useState<Role>('NEAR_PLAYER'),[showBall,setShowBall]=useState(true),[showHits,setShowHits]=useState(true);
 const [error,setError]=useState(''),[busy,setBusy]=useState(false),[showBoxes,setShowBoxes]=useState(true),[showNear,setShowNear]=useState(true),[showFar,setShowFar]=useState(true),[showConfidence,setShowConfidence]=useState(false),[showTrail,setShowTrail]=useState(false),[mask,setMask]=useState(false),[qualityOnly,setQualityOnly]=useState(true);
 const [reviewRole,setReviewRole]=useState<Role>('NEAR_PLAYER'),[visibility,setVisibility]=useState('VISIBLE'),[identity,setIdentity]=useState<Role|'UNCERTAIN'>('NEAR_PLAYER'),[trackQuality,setTrackQuality]=useState('GOOD'),[reviewCount,setReviewCount]=useState(0);
 const video=useRef<HTMLVideoElement>(null);
 const jobs:any[]=snapshot?.jobs||[];
 const activeJob=jobs.find(job=>job.tracking_job_id===selected);
 const fps=Number(result?.video?.fps)||30;
 const qualityWindows=useMemo(()=>{
  const windows=result?.windows||[];
  return windows.flatMap((window:any)=>ROLES.flatMap(role=>{
   const state=window.players?.[role]?.status;
   return [{role,state,start_frame:window.start_frame,end_frame:window.end_frame,start_seconds:window.start_timestamp_seconds,
    goodFrames:(result.records||[]).filter((row:any)=>row.player_role===role&&row.frame>=window.start_frame&&row.frame<window.end_frame&&['GOOD','PARTIAL'].includes(row.pose_quality)).length}];
  }));
 },[result]);

 const refreshSnapshot=useCallback(async()=>{const value=await request('/player-motion');setSnapshot(value);setReviewCount(value.validation_reviews||0);if(!selected&&value.jobs?.length)setSelected(value.jobs.find((j:any)=>j.sample_id==='game_4-t30')?.tracking_job_id||value.jobs[0].tracking_job_id)},[selected]);
 useEffect(()=>{refreshSnapshot().catch(e=>setError(e.message));const timer=window.setInterval(()=>refreshSnapshot().catch(()=>{}),5000);return()=>window.clearInterval(timer)},[refreshSnapshot]);
 const refreshResult=useCallback(async(id:string)=>{const value=await request(`/player-motion/jobs/${id}/result`);setResult(value);return value},[]);
 const refreshHitEvents=useCallback(async(id:string)=>{const value=await request(`/player-motion/jobs/${id}/hit-events`);setHitData(value);if(value.events?.length){setSelectedHit((current:string)=>value.events.some((item:any)=>item.event_id===current)?current:value.events[0].event_id)}return value},[]);
 useEffect(()=>{setResult(null);setProgress(null);if(!selected)return;let stopped=false,finished=false;const poll=async()=>{if(finished)return;try{const value=await request(`/player-motion/jobs/${selected}`);if(stopped)return;setProgress(value);if(value.status==='COMPLETE'){finished=true;await refreshResult(selected);await refreshSnapshot();}else if(value.status==='FAILED'){finished=true;setError(value.error||'姿态分析失败。')}}catch(e:any){if(!stopped&&e?.message?.includes('尚未找到'))setProgress({status:'NOT_RUN'});else if(!stopped)setError(e.message)}};const timer=window.setInterval(poll,1600);poll();return()=>{stopped=true;window.clearInterval(timer)}},[selected,refreshResult,refreshSnapshot]);
 useEffect(()=>{setHitData(null);setSelectedHit('');if(!selected)return;let stopped=false;refreshHitEvents(selected).catch(()=>{if(!stopped)setHitData(null)});return()=>{stopped=true}},[selected,refreshHitEvents]);

 async function start(){if(!selected)return;setBusy(true);setError('');try{const value=await request(`/player-motion/jobs/${selected}`,{method:'POST'});setProgress(value);await refreshSnapshot()}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 async function excludeCurrent(){if(!selected||!result)return;const current=video.current?.currentTime||0,start=Math.floor(current*fps/fps)*fps,end=Math.min(Number(result.video.frame_count),start+fps);try{await request(`/player-motion/jobs/${selected}/exclusions`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({start_frame:start,end_frame:end,role:reviewRole})});await refreshResult(selected)}catch(e:any){setError(e.message)}}
 async function reviewCurrent(){if(!selected)return;const current=video.current?.currentTime||0,start=Math.floor(current*fps),end=Math.min(Number(activeJob?.frames)||start+fps,start+fps);try{await request('/tracking-validation-workbench/reviews',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tracking_job_id:selected,start_frame:start,end_frame:Math.max(start+1,end),role:reviewRole,visibility,identity,track_quality:trackQuality})});await refreshSnapshot()}catch(e:any){setError(e.message)}}
 function jump(seconds:number){if(video.current)video.current.currentTime=seconds}

 const hitEvents:any[]=hitData?.events||[];
 const selectedHitEvent=hitEvents.find((item:any)=>item.event_id===selectedHit);
 const effectiveHitTime=(item:any)=>Number(item.review?.timestamp_ms??item.timestamp_ms);
 const clipStartMs=Number(hitData?.clip_start_timestamp_ms)||0;
 const clipDurationMs=Number(hitData?.clip_duration_ms)||Number(result?.video?.duration||0)*1000;
 useEffect(()=>{if(!selectedHitEvent)return;setHitTimeDraft(((effectiveHitTime(selectedHitEvent)-clipStartMs)/1000).toFixed(3));setHitPlayer((selectedHitEvent.review?.player||selectedHitEvent.candidate_player||'NEAR_PLAYER') as Role)},[selectedHit,hitData]);
 const latestReviewCount=(action:string)=>hitEvents.filter((item:any)=>item.review?.action===action).length;
 const saveHitReview=async(action:string,item:any,atMs?:number)=>{if(!selected||!hitData)return;const timestamp=action==='CONFIRM'||action==='REJECT'?Number(item?.timestamp_ms):Number(atMs);try{await request(`/player-motion/jobs/${selected}/hit-events/reviews`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,event_id:item?.event_id,timestamp_ms:timestamp,player:hitPlayer})});await refreshHitEvents(selected)}catch(e:any){setError(e.message)}};
 const hitState=(item:any)=>item.review?.action==='CONFIRM'?'已确认':item.review?.action==='REJECT'?'已标记误报':item.review?.action==='ADJUST'?'时间已修正':item.review?.action==='ADD'?'人工补充':'待复核';
 const hitEvidence=(item:any)=>item?.evidence_components||{};
 const isEvidence=(item:any,key:string)=>hitEvidence(item)[key]!=null;

 const runtime=snapshot?.runtime||{},state=result?.status||progress?.status||activeJob?.status||'NOT_RUN';
 const effective=result?.effective_metrics_after_user_exclusions||{};
 const metricFor=(role:Role)=>effective[role]||result?.summary?.[role]?.metrics;
 const shownSegments=qualityWindows.filter((segment:any)=>!qualityOnly||(segment.state==='POSE_READY'&&segment.goodFrames>0));

 return <Card className="player-motion-panel">
  <div className="section-title"><div><h2>人体动作 · 2D 观察</h2><p>只对通过追踪质量检查的时间窗运行姿态识别；结果是画面平面估计，不代表技术或生物力学判断。</p></div><span className={'badge '+(state==='COMPLETE'?'':'muted')}>{state==='COMPLETE'?'分析完成':state==='RUNNING'?'分析中':state==='FAILED'?'运行失败':'实验预览'}</span></div>
  {!snapshot?<p>正在读取隔离姿态环境…</p>:<div className="motion-runtime-note">隔离运行环境：{snapshot.status==='READY'?'可用':'尚未就绪'} · RTMPose-m Halpe26 · {runtime.cuda_provider_available?'CUDA 可用':'等待 GPU 运行时'} · 研究预览</div>}
  <div className="motion-job-row"><label>选择已完成的追踪片段<select value={selected} onChange={e=>setSelected(e.target.value)}><option value="">选择片段</option>{jobs.map(job=><option key={job.tracking_job_id} value={job.tracking_job_id}>{job.sample_id} · {job.status==='COMPLETE'?'动作已生成':job.status==='RUNNING'?'分析中':job.status==='FAILED'?'上次失败':'待分析'}</option>)}</select></label><button className="primary" disabled={!selected||busy||!!result||state==='RUNNING'||snapshot?.status!=='READY'} onClick={start}>{busy?'正在启动…':result?'已生成姿态结果':'开始动作分析'}</button></div>
  {activeJob&&<p className="small">Extended OpenTTGames 训练集 · {activeJob.rights} · 仅研究 / 非商业 · 视频 SHA256 已核验 · 正式数据库未访问</p>}
  {progress?.stage&&<p className="motion-progress">{progress.stage}{progress.total_frames?` · ${progress.processed_frames||0}/${progress.total_frames} 帧`:''}</p>}
  {result&&<>
   <div className="facts motion-facts">{ROLES.map(role=><span key={role}>{role==='NEAR_PLAYER'?'近端':'远端'}骨架<strong>{result.summary?.[role]?.good||0} 较完整 · {result.summary?.[role]?.partial||0} 部分 · {result.summary?.[role]?.no_pose||0} 跳过</strong></span>)}<span>来源画面<strong>{result.video?.width} × {result.video?.height} · {result.video?.fps} FPS</strong></span><span>推理<strong>{result.runtime?.pose_inferences} 人帧 · {result.runtime?.mean_pose_inference_ms_per_person??'—'} ms / 人</strong></span></div>
   <div className="motion-layers"><label><input type="checkbox" checked={showBoxes} onChange={e=>setShowBoxes(e.target.checked)}/>人物框</label><label><input type="checkbox" checked={mask} onChange={e=>setMask(e.target.checked)}/>人物 Mask</label><label><input type="checkbox" checked={showNear} onChange={e=>setShowNear(e.target.checked)}/>近端骨架</label><label><input type="checkbox" checked={showFar} onChange={e=>setShowFar(e.target.checked)}/>远端骨架</label><label><input type="checkbox" checked={showConfidence} onChange={e=>setShowConfidence(e.target.checked)}/>关节置信</label><label><input type="checkbox" checked={showTrail} onChange={e=>setShowTrail(e.target.checked)}/>手腕轨迹</label>{hitData&&<><label><input type="checkbox" checked={showBall} onChange={e=>setShowBall(e.target.checked)}/>BallTrack 原始球点</label><label><input type="checkbox" checked={showHits} onChange={e=>setShowHits(e.target.checked)}/>击球候选标记</label></>}</div>
   <CanvasOverlay jobId={selected} result={result} showBoxes={showBoxes} showNear={showNear} showFar={showFar} showConfidence={showConfidence} showTrail={showTrail} mask={mask} videoRef={video} hitData={hitData} hitEvents={hitEvents} showBall={showBall} showHits={showHits}/>
   <section className="hit-event-workspace" aria-label="击球候选时间轴">
    <div className="section-title"><div><h3>击球候选时间轴</h3><p>候选由球轨迹与球员观察共同支持；所有原始结果均待人工确认。</p></div><span className="badge muted">{hitData?.phase==='validation'?'TRAIN 内部验证':'研究预览'}</span></div>
    {hitData?<>
     <div className="hit-event-summary"><span>候选<strong>{hitEvents.filter((item:any)=>item.raw_status==='SUGGESTED').length}</strong></span><span>已确认<strong>{latestReviewCount('CONFIRM')}</strong></span><span>需复核<strong>{hitEvents.filter((item:any)=>!item.review||item.review.action==='ADJUST').length}</strong></span><span>已排除<strong>{latestReviewCount('REJECT')}</strong></span></div>
     <div className="hit-timeline" role="group" aria-label="点击击球候选跳转视频时间"><div className="hit-timeline-line"/>{hitEvents.map((item:any,index:number)=>{const local=(effectiveHitTime(item)-clipStartMs)/1000;const left=clipDurationMs?Math.max(0,Math.min(100,local*1000/clipDurationMs*100)):0;const rejected=item.review?.action==='REJECT';const confirmed=item.review?.action==='CONFIRM';return <button key={item.event_id} type="button" className={`hit-marker${confirmed?' confirmed':''}${rejected?' rejected':''}${item.event_id===selectedHit?' selected':''}`} style={{left:`${left}%`}} title={`Hit ${index+1} · ${(local).toFixed(3)} 秒 · ${item.candidate_player||item.review?.player||'身份待确认'}`} aria-label={`第 ${index+1} 个击球候选，${local.toFixed(3)} 秒，${hitState(item)}`} onClick={()=>{setSelectedHit(item.event_id);setHitTimeDraft(local.toFixed(3));setHitPlayer((item.review?.player||item.candidate_player||'NEAR_PLAYER') as Role);jump(local)}}><span>{index+1}</span></button>})}</div>
     {hitEvents.length?<div className="hit-event-review-grid"><div className="hit-event-list">{hitEvents.map((item:any,index:number)=>{const local=(effectiveHitTime(item)-clipStartMs)/1000;const player=item.review?.player||item.candidate_player;return <button key={item.event_id} className={`hit-event-row${selectedHit===item.event_id?' active':''}${item.review?.action==='REJECT'?' rejected':''}`} onClick={()=>{setSelectedHit(item.event_id);setHitTimeDraft(local.toFixed(3));setHitPlayer((player||'NEAR_PLAYER') as Role);jump(local)}}><strong>Hit {index+1} · {player==='NEAR_PLAYER'?'近端':player==='FAR_PLAYER'?'远端':'待确认'}</strong><span>{local.toFixed(3)} 秒 · {hitState(item)}{item.interval_from_previous_ms!=null?` · 距上一候选 ${(Number(item.interval_from_previous_ms)/1000).toFixed(2)} 秒`:''}</span></button>})}</div>
      {selectedHitEvent&&<div className="hit-evidence-panel"><h4>候选依据</h4><p className="small">规则证据评分 {Number(selectedHitEvent.evidence_score||0).toFixed(2)} · 不是概率；手腕距离仅为“球拍侧手腕代理”。</p><div className="hit-evidence-grid">{[["ball_player_proximity","球靠近球员"],["wrist_proximity_proxy","球靠近手腕代理"],["trajectory_direction_change","球轨迹方向变化"],["ball_speed_change","球速变化"],["wrist_speed_peak","手腕局部速度峰值"],["pose_quality","姿态质量"],["track_health","追踪状态"]].map(([key,label])=>{const component=hitEvidence(selectedHitEvent)[key];return <span key={key}>{label}<strong>{!component?'暂无证据':key==='wrist_proximity_proxy'&&component.distance_px!=null?`${Number(component.distance_px).toFixed(0)} px`:key==='pose_quality'?'可用':key==='track_health'?'可用':Number(component.value)>=.65?'明显':Number(component.value)>=.35?'部分':'较弱'}</strong></span>})}</div><label className="hit-review-time">候选时间（片段内秒）<input type="number" min="0" max={(clipDurationMs/1000).toFixed(3)} step="0.001" value={hitTimeDraft} onChange={e=>setHitTimeDraft(e.target.value)}/></label><label className="hit-review-player">击球方<select value={hitPlayer} onChange={e=>setHitPlayer(e.target.value as Role)}><option value="NEAR_PLAYER">近端</option><option value="FAR_PLAYER">远端</option><option value="UNKNOWN">待确认</option></select></label><div className="hit-review-actions"><button onClick={()=>saveHitReview('CONFIRM',selectedHitEvent)}>确认击球</button><button onClick={()=>saveHitReview('REJECT',selectedHitEvent)}>标记误报</button><button onClick={()=>saveHitReview('ADJUST',selectedHitEvent,clipStartMs+Number(hitTimeDraft||0)*1000)}>保存时间 / 击球方修正</button><button onClick={()=>saveHitReview('ADD',null,clipStartMs+(video.current?.currentTime||0)*1000)}>在当前播放位置新增</button></div><p className="small">人工修正追加保存，原始候选保持不变。</p></div>}
     </div>:<p className="empty-state">这段视频当前没有击球候选。可在播放到击球位置时手动新增一条复核记录。</p>}
     <details className="hit-research-metrics"><summary>研究评估指标 · 不代表产品准确率</summary><p>Extended OpenTTGames 官方 TRAIN · {hitData.sample_id} · {hitData.official_split} · {hitData.phase}</p><pre>{JSON.stringify(hitData.research_metrics,null,2)}</pre></details>
    </>:<p className="empty-state">该片段尚无同一视频来源的 BallTrack 与球员 / 姿态融合结果。请先完成对应研究分析。</p>}
   </section>
   <div className="motion-sections"><div className="motion-quality"><div className="section-title"><div><h3>动作片段</h3><p>可按质量筛选；冲突和离画窗口会保留在待复核列表。</p></div><label><input type="checkbox" checked={qualityOnly} onChange={e=>setQualityOnly(e.target.checked)}/>只看高质量</label></div>{shownSegments.length?<div className="motion-segment-list">{shownSegments.map((segment:any,index:number)=><button key={`${segment.role}-${segment.start_frame}-${index}`} onClick={()=>jump(segment.start_seconds)}><strong>{segment.role==='NEAR_PLAYER'?'近端':'远端'} · {segment.state==='POSE_READY'&&segment.goodFrames?'可分析':segment.state==='REVIEW'?'需复核':'跳过'}</strong><span>{segment.start_seconds.toFixed(1)}–{(segment.end_frame/fps).toFixed(1)} 秒 · {segment.goodFrames} 帧可用</span></button>)}</div>:<p className="empty-state">当前区间动作数据不足</p>}</div>
    <div className="motion-metrics"><h3>基础运动观察</h3><p>以下均为 2D estimate / proxy，动作分析会按人工排除区间更新。</p>{ROLES.map(role=>{const m=metricFor(role);return <div className="motion-metric-row" key={role}><strong>{role==='NEAR_PLAYER'?'近端':'远端'}</strong>{m?.status==='AVAILABLE'?<span>身体中心横向变化 {m.lateral_movement_proxy_px} px · 站距 {m.stance_width_proxy_px??'—'} px · 膝角 {m.knee_angle_2d_estimate_degrees??'—'}° · 手腕点 {m.wrist_observations}</span>:<span>当前区间动作数据不足</span>}</div>})}</div></div>
   <div className="motion-review-row"><label>复核对象<select value={reviewRole} onChange={e=>{const value=e.target.value as Role;setReviewRole(value);setIdentity(value)}}><option value="NEAR_PLAYER">近端球员</option><option value="FAR_PLAYER">远端球员</option></select></label><button onClick={excludeCurrent}>排除当前 1 秒动作区间</button><div className="motion-review-form"><strong>追踪人工复核</strong><select value={visibility} onChange={e=>setVisibility(e.target.value)}><option value="VISIBLE">可见</option><option value="PARTIAL">部分可见</option><option value="OUT_OF_FRAME">离开画面</option><option value="UNKNOWN">未知</option></select><select value={identity} onChange={e=>setIdentity(e.target.value as any)}><option value="NEAR_PLAYER">近端身份</option><option value="FAR_PLAYER">远端身份</option><option value="UNCERTAIN">身份不确定</option></select><select value={trackQuality} onChange={e=>setTrackQuality(e.target.value)}><option value="GOOD">追踪良好</option><option value="BAD">追踪有误</option><option value="UNKNOWN">未知</option></select><button onClick={reviewCurrent}>保存复核</button></div></div>
   <details><summary>来源、模型与限制</summary><p>原始 RTMPose 关键点全部保留；低置信关节不会画出。姿态推理不运行人物检测器。官方测试集未访问。Checkpoint 单独许可尚未明确，因此模型与数据不进入安装包或发布资产。</p><p>人工排除只影响派生动作指标；原始骨架、追踪结果和视频文件不被覆盖。追踪验证复核记录：{reviewCount}。</p><pre>{JSON.stringify(result.runtime,null,2)}</pre></details>
  </>}
  {!result&&selected&&state==='NOT_RUN'&&<p className="empty-state">选好片段后点击“开始动作分析”。冲突、身份不确定、追踪丢失或离画窗口会自动跳过或标为待复核。</p>}
  {error&&<p className="error-banner" role="alert">{error}</p>}
 </Card>;
}
