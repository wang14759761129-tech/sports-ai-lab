import {useEffect,useMemo,useState} from 'react';
import {Card} from './ui';

const api='/api/vision/v2/player-tracking';
const asset=(name:string)=>`${api}/assets/${encodeURIComponent(name)}`;
const frameAsset=(frame:number,view:'source'|'overlay')=>`${api}/frames/${frame}/${view}`;

export default function PlayerTrackingPreview(){
 const [data,setData]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[note,setNote]=useState('');
 const [near,setNear]=useState(true),[far,setFar]=useState(true),[selected,setSelected]=useState(0);
 const load=async()=>{const response=await fetch(api);if(!response.ok)throw new Error('读取球员追踪结果失败');setData(await response.json())};
 useEffect(()=>{load().catch(e=>setError(e.message))},[]);
 const available=new Set((data?.available_assets||[]).map((item:any)=>item.name));
 const videoName=useMemo(()=>{
  if(near&&far)return 'player_tracking_overlay.mp4';
  if(near)return 'player_tracking_near.mp4';
  if(far)return 'player_tracking_far.mp4';
  return 'player_tracking_original.mp4';
 },[near,far]);
 async function review(action:string){setBusy(true);setError('');try{const response=await fetch(`${api}/reviews`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,note})});if(!response.ok)throw new Error('复核记录没有保存，请重试');await load()}catch(e:any){setError(e.message||'复核记录没有保存，请重试')}finally{setBusy(false)}}
 if(!data)return <Card><h2>球员持续追踪</h2><p>正在读取本机研究结果…</p></Card>;
 if(data.status==='NOT_RUN')return <Card><h2>球员持续追踪</h2><p>{data.message}</p></Card>;
 const nearSummary=data.role_summary?.NEAR_PLAYER||{},farSummary=data.role_summary?.FAR_PLAYER||{};
 const crossMatch=data.multi_match_validation;
 const crossVideos=crossMatch?.videos||[];
 const videoAvailable=available.has(videoName);
 return <Card className="sam2-tracking-preview">
  <div className="section-title"><div><h2>球员持续追踪</h2><p>真实比赛 · SAM 2.1 Small · 双球员分割候选</p></div><span className="badge muted">研究预览 · 单场 10 秒</span></div>
  <div className="facts"><span>追踪时长<strong>{Number(data.duration_seconds).toFixed(0)} 秒</strong></span><span>采样帧<strong>{data.frames}</strong></span><span>近端连续<strong>{nearSummary.tracked}/{nearSummary.frames}</strong></span><span>远端连续<strong>{farSummary.tracked}/{farSummary.frames}</strong></span><span>身份不确定<strong>{data.identity_uncertain_events?.length||0}</strong></span><span>丢失帧<strong>{(nearSummary.track_lost||0)+(farSummary.track_lost||0)}</strong></span></div>
  <div className="sam2-layer-switches"><label><input type="checkbox" checked={near} onChange={e=>setNear(e.target.checked)} disabled={!available.has('player_tracking_near.mp4')}/>近端球员 mask</label><label><input type="checkbox" checked={far} onChange={e=>setFar(e.target.checked)} disabled={!available.has('player_tracking_far.mp4')}/>远端球员 mask</label></div>
  {videoAvailable?<video key={videoName} className="sam2-preview-video" controls preload="metadata" src={asset(videoName)}/>:<p className="empty-state">当前图层的预览文件尚未生成。</p>}
  <div className="sam2-frame-gallery">{(data.samples||[]).map((item:any)=><button key={item.frame} className={selected===item.frame?'selected':''} onClick={()=>setSelected(item.frame)}><img loading="lazy" src={frameAsset(item.frame,'overlay')} alt={`追踪叠加，第 ${item.frame+1} 帧`}/><span>{(item.timestamp_ms/1000).toFixed(1)} 秒 · 近端 {item.statuses.NEAR_PLAYER||'未知'} · 远端 {item.statuses.FAR_PLAYER||'未知'}</span></button>)}</div>
  {(data.samples||[]).some((item:any)=>item.frame===selected)&&<div className="sam2-frame-pair"><div><small>原始画面</small><img src={frameAsset(selected,'source')} alt="原始比赛画面"/></div><div><small>人物 mask · 可用于人工检查</small><img src={frameAsset(selected,'overlay')} alt="两名球员 mask 叠加"/></div></div>}
  <div className="sam2-review"><div><h3>角色复核</h3><p>{data.review_status==='USER_REVIEWED'?'已有桌面复核记录。': '起始 Near / Far 角色由实验操作员预置；请核对本段身份是否正确。'}</p><small>复核只新增用户记录，不覆盖 RAW mask 或模型输出。</small></div><label>备注（可选）<input value={note} maxLength={500} onChange={e=>setNote(e.target.value)} placeholder="例如：第 6 秒遮挡时需要复核"/></label><div className="actions"><button className="primary" disabled={busy||data.review_status==='USER_REVIEWED'} onClick={()=>review('CONFIRM_ROLE_ASSIGNMENT')}>确认本段角色</button><button disabled={busy} onClick={()=>review('FLAG_ROLE_ASSIGNMENT')}>标记需要复核</button></div></div>
  {crossMatch&&<section className="hybrid-scene-summary sam2-cross-match"><div className="section-title"><div><h3>跨比赛连续性检查</h3><p>锁定配置 · 官方训练集 · 研究用途</p></div><span className="badge muted">{crossMatch.propagated_video_count}/{crossMatch.declared_video_count} 段完成传播</span></div><div className="scene-multimatch-grid">{crossVideos.map((item:any)=>{const status=item.sam2_run_status||item.status;return <article key={item.video_id}><strong>{item.match_id}</strong><span>{status==='PROPAGATED'?'已完成传播':status==='NOT_RUN_NO_VALID_TWO_PLAYER_SEEDS'||status==='INITIALIZATION_FAILED'?'双球员初始化失败':'未运行'}</span>{item.near&&<small>近端 {item.near.tracked}/{item.near.frames} 帧 · 丢失 {item.near.track_lost}</small>}{item.far&&<small>远端 {item.far.tracked}/{item.far.frames} 帧 · 丢失 {item.far.track_lost}</small>}{item.seed_screening?.note&&<small>{item.seed_screening.note}</small>}{item.visual_review_note&&<small>{item.visual_review_note}</small>}</article>})}</div><p className="sam2-cross-match-note">{crossMatch.interpretation||'未能初始化的比赛仍计入覆盖范围；此结果不是跨比赛泛化通过证明。'}</p></section>}
  {error&&<p role="alert" className="error-banner">{error}</p>}
  <details><summary>运行来源与限制</summary><p>{data.dataset} · {data.rights} · 不用于商业用途。</p><p>checkpoint SHA256：<code>{data.sam2?.checkpoint_sha256}</code></p><p>传播速度 {data.runtime?.effective_fps} 帧/秒 · 峰值显存 {((data.runtime?.peak_vram_allocated_bytes||0)/1024**2).toFixed(0)} MiB。</p><p>{data.limitations?.join(' ')}</p><p>原始研究视频路径不会通过桌面接口暴露。</p></details>
 </Card>;
}
