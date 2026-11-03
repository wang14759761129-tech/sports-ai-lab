import {useEffect,useState} from 'react';
import {Card,Empty} from './ui';

const roleName:Record<string,string>={NEAR_PLAYER:'近端运动员候选',FAR_PLAYER:'远端运动员候选',REFEREE:'裁判',OTHER:'其他人物',UNKNOWN:'角色待确认'};
const reasonName:Record<string,string>={TABLE_MISSING:'未找到球台',NEAR_PLAYER_MISSING:'缺少近端候选',FAR_PLAYER_MISSING:'缺少远端候选',ROLE_AMBIGUITY:'人物角色不确定',TOO_MANY_PERSONS:'背景人物较多'};

async function load(){const r=await fetch('/api/vision/v2/person-detection');if(!r.ok)throw new Error('人物识别结果暂时无法读取，请重试。');return r.json()}

export default function PersonSceneGallery({research=false}:{research?:boolean}){
 const [data,setData]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [selected,setSelected]=useState(''),[setName,setSetName]=useState('development'),[onlyAbnormal,setOnlyAbnormal]=useState(false);
 const [table,setTable]=useState(true),[other,setOther]=useState(true);
 useEffect(()=>{let alive=true;load().then(v=>{if(alive)setData(v)}).catch(e=>{if(alive)setError(e.message)});return()=>{alive=false}},[]);
 async function review(action:string,candidate_id?:string,role?:string){
  if(!active||busy)return;setBusy(true);setError('');
  try{const r=await fetch('/api/vision/v2/person-detection/reviews',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({frame_id:active.frame_id,action,candidate_id,role})});if(!r.ok)throw new Error('修正没有保存，请重试。');setData(await load())}catch(e:any){setError(e.message)}finally{setBusy(false)}
 }
 const frames=(data?.frames||[]).filter((f:any)=>f.sample_set===setName);
 const abnormal=frames.filter((f:any)=>f.review.priority==='HIGH');
 const visible=onlyAbnormal?abnormal:frames;
 const active=visible.find((f:any)=>f.frame_id===selected)||visible[0];
 const imageUrl=(f:any)=>`/api/vision/v2/person-detection/assets/${f.image_asset}`;
 const both=frames.filter((f:any)=>new Set(f.detections.filter((p:any)=>p.user_correction?.status!=='REJECTED').map((p:any)=>p.effective_role)).has('NEAR_PLAYER')&&f.detections.some((p:any)=>p.effective_role==='FAR_PLAYER'&&p.user_correction?.status!=='REJECTED')).length;
 function step(delta:number){const i=abnormal.findIndex((f:any)=>f.frame_id===active?.frame_id);const next=i<0?(delta>0?0:abnormal.length-1):(i+delta+abnormal.length)%abnormal.length;const f=abnormal[next];if(f){setSelected(f.frame_id);setOnlyAbnormal(true)}}
 return <Card className="scene-bootstrap"><div className="section-title"><div><h2>人物识别</h2><p>真实比赛画面 · 球台与人物框 · 角色建议由你确认</p></div><span className="badge muted">研究预览 · 仍需审核</span></div>
  {error&&<p role="alert">{error}<button disabled={busy} onClick={()=>load().then(setData).then(()=>setError('')).catch(e=>setError(e.message))}>重试</button></p>}
  {!data&&!error&&<p role="status">正在读取画面…</p>}
  {data?.status==='NOT_RUN'&&<Empty title="人物识别尚未运行" text={data.message}/>}
  {!!data?.frames?.length&&<>
   <div className="tabs"><button className={setName==='development'?'active':''} onClick={()=>{setSetName('development');setSelected('')}}>原始 5 场样本</button><button className={setName==='validation'?'active':''} onClick={()=>{setSetName('validation');setSelected('')}}>新增 5 场检查</button></div>
   <div className="facts"><span>抽样画面<strong>{frames.length}</strong></span><span>球台粗定位<strong>{frames.filter((f:any)=>f.table_bbox).length}/{frames.length}</strong></span><span>双运动员角色候选<strong>{both}/{frames.length}</strong></span><span>需重点检查<strong>{abnormal.length} 帧</strong></span><span>你已确认<strong>{frames.filter((f:any)=>f.review.status==='USER_VERIFIED').length} 帧</strong></span></div>
   <p className="small">近远端是画面位置候选，不代表运动员身份。背景观众多、遮挡或机位变化时，请人工指定；记分牌尚未实现。</p>
   <div className="scene-review-controls"><label><input type="checkbox" checked={onlyAbnormal} onChange={e=>setOnlyAbnormal(e.target.checked)}/>只看异常帧</label><button disabled={!abnormal.length||busy} onClick={()=>step(-1)}>上一异常</button><button disabled={!abnormal.length||busy} onClick={()=>step(1)}>下一异常</button><label><input type="checkbox" checked={table} onChange={e=>setTable(e.target.checked)}/>球台</label><label><input type="checkbox" checked={other} onChange={e=>setOther(e.target.checked)}/>其他 / 未知人物</label></div>
   {!active&&<p>当前没有需要重点检查的画面，可关闭“只看异常帧”查看已确认记录。</p>}
   {active&&<><div className="section-title"><div><h3>{active.game} · {(active.timestamp_ms/1000).toFixed(2)} 秒</h3><p>{active.review.status==='USER_VERIFIED'?'你已确认当前画面':active.review.status==='LIKELY_OK'?'候选较完整，仍可人工复核':active.review.reasons.map((r:string)=>reasonName[r]||r).join(' · ')}</p></div><button className="primary" disabled={busy||active.review.status==='USER_VERIFIED'} onClick={()=>review('ACCEPT_FRAME')}>确认本帧</button></div>
    <div className="scene-frame-pair"><div><small>原始比赛画面</small><img className="scene-original-frame" src={imageUrl(active)} alt={`${active.game} 原始画面`}/></div><div><small>球台与人物候选 · 修正另存，原始结果保留</small><div className="scene-image-shell"><img src={imageUrl(active)} alt={`${active.game} 人物识别叠加`}/><svg viewBox={`0 0 ${active.width} ${active.height}`} preserveAspectRatio="none" aria-label="人物框叠加">{table&&active.table_bbox&&<rect x={active.table_bbox[0]} y={active.table_bbox[1]} width={active.table_bbox[2]-active.table_bbox[0]} height={active.table_bbox[3]-active.table_bbox[1]} fill="none" stroke="#22c88a" strokeWidth="4"/>}{active.detections.filter((p:any)=>p.user_correction?.status!=='REJECTED'&&(other||p.effective_role?.includes('PLAYER'))).map((p:any)=>{const [x0,y0,x1,y1]=p.bbox;return <g key={p.candidate_id}><rect x={x0} y={y0} width={x1-x0} height={y1-y0} fill="none" stroke={p.effective_role?.includes('PLAYER')?'#258cff':'#e89b23'} strokeWidth="4"/><text x={x0} y={Math.max(24,y0-8)} fill="#fff" stroke="#111" strokeWidth=".6" fontSize="22">{roleName[p.effective_role]}</text></g>})}</svg></div></div></div>
    <div className="scene-candidates">{active.detections.map((p:any,i:number)=><div className="scene-candidate" key={p.candidate_id}><span><strong>人物 {i+1} · {roleName[p.effective_role]}</strong><small>{p.user_correction?.status==='REJECTED'?'已删除误框，原始证据保留':p.user_correction?'已人工修正':'尚未确认角色'}</small></span><select disabled={busy||p.user_correction?.status==='REJECTED'} aria-label={`人物 ${i+1} 角色`} value={p.effective_role||'UNKNOWN'} onChange={e=>review('SET_ROLE',p.candidate_id,e.target.value)}>{Object.entries(roleName).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select><button disabled={busy||p.user_correction?.status==='REJECTED'} onClick={()=>review('REJECT',p.candidate_id)}>删除误框</button></div>)}</div></>}
   <div className="scene-frame-gallery">{visible.map((f:any)=><button key={f.frame_id} className={active?.frame_id===f.frame_id?'selected':''} onClick={()=>setSelected(f.frame_id)}><img loading="lazy" src={imageUrl(f)} alt={`${f.game} 样本 ${f.slot}`}/><span>{f.game} · {(f.timestamp_ms/1000).toFixed(1)}秒 · {f.review.status==='USER_VERIFIED'?'已确认':f.review.priority==='HIGH'?'需检查':'建议复核'}</span></button>)}</div>
   {research&&<details><summary>检测器、基线对比和复现信息</summary><p>RT-DETR R18 · 真实 CUDA 推理完成。标注是 Codex 视觉复核草稿，尚未经独立人工确认，不能声称正式准确率。</p><pre>{JSON.stringify({model:data.model,development:data.development,validation:data.validation,validation_metrics:data.validation_metrics,provenance:data.provenance,runtime:data.runtime,config_sha256:data.config_sha256,gate:data.person_gate},null,2)}</pre></details>}
  </>}
 </Card>
}
