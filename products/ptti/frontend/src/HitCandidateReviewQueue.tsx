import {useCallback,useEffect,useRef,useState} from 'react';

type Candidate={evidence_id:string;video_id:string;representative_ms:number;review_status:string;source:string;suggested_side?:string;disposition?:string;raw_candidate?:any;ai_provenance?:any;review_flags?:string[]};
type Page={counts:Record<string,number>;attention_counts:Record<string,number>;total:number;offset:number;limit:number;items:Candidate[]};
type Props={videoId:string;selectedId?:string;refreshKey?:number;onSelect:(candidate:Candidate,play?:boolean)=>void;onReview:(decision:'CONFIRMED'|'REJECTED')=>Promise<void>};
const endpoint='/api/video-evidence';
const clock=(ms:number)=>{const s=Math.max(0,ms)/1000;return `${String(Math.floor(s/3600)).padStart(2,'0')}:${String(Math.floor(s/60)%60).padStart(2,'0')}:${(s%60).toFixed(3).padStart(6,'0')}`};
const empty:Page={counts:{},attention_counts:{},total:0,offset:0,limit:30,items:[]};

export default function HitCandidateReviewQueue({videoId,selectedId,refreshKey=0,onSelect,onReview}:Props){
 const [status,setStatus]=useState('UNVERIFIED'),[attention,setAttention]=useState(''),[page,setPage]=useState<Page>(empty),[offset,setOffset]=useState(0),[loading,setLoading]=useState(false),[message,setMessage]=useState('');
 const selected=page.items.find(item=>item.evidence_id===selectedId)||null;
 const cursorKey=`ptti-review-cursor:${videoId}:${status}:${attention}`;
 const restoring=useRef('');
 const load=useCallback(async(nextOffset=offset)=>{
  if(!videoId){setPage(empty);return empty}
  setLoading(true);
  try{const query=new URLSearchParams({video_id:videoId,status,offset:String(nextOffset),limit:'30'});if(attention)query.set('attention',attention);const response=await fetch(`${endpoint}/ai-suggestions?${query}`);const result=await response.json();if(!response.ok)throw new Error(result.detail||'候选加载失败');setPage(result);return result as Page}
  catch(error){setMessage((error as Error).message);return empty}
  finally{setLoading(false)}
 },[videoId,status,attention,offset]);
 useEffect(()=>{setOffset(0);setPage(empty);void load(0)},[videoId,status,attention,refreshKey]);
 useEffect(()=>{
  if(!videoId||!page.items.length||restoring.current===cursorKey)return;
  restoring.current=cursorKey;
  try{const saved=JSON.parse(localStorage.getItem(cursorKey)||'null');if(saved?.evidence_id){const found=page.items.find(item=>item.evidence_id===saved.evidence_id);const next=found||page.items.find(item=>item.representative_ms>=Number(saved.timestamp_ms||0));if(next)onSelect(next,false)}}catch{/* Ignore malformed local review cursor. */}
 },[videoId,cursorKey,page.items,onSelect]);
 function choose(item:Candidate,play=true){try{localStorage.setItem(cursorKey,JSON.stringify({evidence_id:item.evidence_id,timestamp_ms:item.representative_ms}))}catch{/* The queue remains usable when local storage is disabled. */}onSelect(item,play)}
 async function move(delta:number){
  if(!page.items.length)return;
  let index=page.items.findIndex(item=>item.evidence_id===selectedId);let target=index+delta;
  if(target<0&&offset>0){const next=await load(Math.max(0,offset-page.limit));setOffset(Math.max(0,offset-page.limit));if(next.items.length)choose(next.items[next.items.length-1]);return}
  if(target>=page.items.length&&offset+page.limit<page.total){const nextOffset=offset+page.limit;const next=await load(nextOffset);setOffset(nextOffset);if(next.items.length)choose(next.items[0]);return}
  target=Math.max(0,Math.min(page.items.length-1,target));choose(page.items[target]);
 }
 async function focusNextPending(){
  const pendingStatus='UNVERIFIED';const query=new URLSearchParams({video_id:videoId,status:pendingStatus,offset:'0',limit:'30'});if(attention)query.set('attention',attention);
  const response=await fetch(`${endpoint}/ai-suggestions?${query}`);const next=await response.json() as Page;
  if(!response.ok||!next.items?.length){setStatus(pendingStatus);setAttention('');setMessage('待复核候选已看完。');return}
  setStatus(pendingStatus);setOffset(0);setPage(next);
  const oldIndex=page.items.findIndex(item=>item.evidence_id===selectedId);const target=next.items[Math.min(Math.max(oldIndex,0),next.items.length-1)];choose(target);
 }
 async function decide(decision:'CONFIRMED'|'REJECTED'){
  if(!selected||selected.review_status!=='UNVERIFIED')return;
  await onReview(decision);await focusNextPending();
 }
 useEffect(()=>{
  const handle=(event:KeyboardEvent)=>{
   const target=event.target as HTMLElement|null;
   if(!videoId||event.altKey||event.ctrlKey||event.metaKey||event.shiftKey||
      ['INPUT','TEXTAREA','SELECT','BUTTON'].includes(target?.tagName||'')||target?.isContentEditable)return;
   const key=event.key.toLowerCase();
   if(key==='j'){event.preventDefault();void move(1)}else if(key==='k'){event.preventDefault();void move(-1)}
   else if(key==='a'&&selected?.review_status==='UNVERIFIED'){event.preventDefault();void decide('CONFIRMED')}
   else if(key==='r'&&selected?.review_status==='UNVERIFIED'){event.preventDefault();void decide('REJECTED')}
  };
  window.addEventListener('keydown',handle);return()=>window.removeEventListener('keydown',handle);
 });
 const end=page.items.length?Math.min(offset+page.items.length,page.total):offset;
 return <section className="vep-review-queue" aria-label="候选事件复核队列">
  <div className="vep-queue-heading"><div><h3>候选事件 · {page.counts?.UNVERIFIED||0} 条待复核</h3><small>规则证据用于排序，不是击球概率；AI 候选都需要你判断。</small></div><div className="vep-exports"><a href={`${endpoint}/videos/${encodeURIComponent(videoId)}/export?format=json`}>导出 JSON</a><a href={`${endpoint}/videos/${encodeURIComponent(videoId)}/export?format=csv`}>导出 CSV</a><a href={`${endpoint}/videos/${encodeURIComponent(videoId)}/export?format=html`}>中文报告</a></div></div>
  <div className="vep-queue-filters"><label>候选状态<select aria-label="候选状态" value={status} onChange={event=>setStatus(event.target.value)}><option value="UNVERIFIED">待复核 · {page.counts?.UNVERIFIED||0}</option><option value="CONFIRMED">已确认 · {page.counts?.CONFIRMED||0}</option><option value="REJECTED">已否决 · {page.counts?.REJECTED||0}</option><option value="FILTERED">算法过滤 · {page.counts?.FILTERED||0}</option></select></label><label>复核优先级<select aria-label="复核优先级" value={attention} onChange={event=>setAttention(event.target.value)}><option value="">全部</option><option value="NEEDS_REVIEW">优先查看异常 · {page.attention_counts?.NEEDS_REVIEW||0}</option><option value="EVIDENCE_GAP">证据不足 · {page.attention_counts?.EVIDENCE_GAP||0}</option></select></label></div>
  <div className="vep-queue-actions"><button disabled={!page.items.length} onClick={()=>void move(-1)}>上一候选</button><button disabled={!page.items.length} onClick={()=>void move(1)}>下一候选</button><button disabled={!page.counts?.UNVERIFIED} onClick={()=>{setStatus('UNVERIFIED');setAttention('NEEDS_REVIEW');setOffset(0)}}>只看异常</button><span>{loading?'正在更新…':page.total?`${offset+1}–${end} / ${page.total}`:'暂无候选'}</span></div>
  {message&&<p role="status">{message}</p>}
  <div className="vep-ai-list" aria-label="候选列表">{page.items.map(item=><button key={item.evidence_id} className={selectedId===item.evidence_id?'active':''} onClick={()=>choose(item,true)}><b>{clock(item.representative_ms)} · 击球候选</b><small>{item.suggested_side==='UNKNOWN'||!item.suggested_side?'击球方未知':item.suggested_side==='NEAR'?'Near 候选':'Far 候选'} · {item.review_status==='UNVERIFIED'?'待复核':item.review_status==='CONFIRMED'?'人工已确认':item.review_status==='REJECTED'?'已否决':'算法已过滤'}</small><small>规则证据 {Number(item.raw_candidate?.evidence_score||0).toFixed(3)} · {item.raw_candidate?.ball_quality||'球证据不足'} · {item.review_flags?.length?`优先复核：${item.review_flags.join('、')}`:'暂无额外异常标记'}</small></button>)}{!page.items.length&&<p className="vep-empty-review">{status==='UNVERIFIED'?'当前筛选没有待复核项。没有候选时，可使用人工时间标记。':'该状态下暂无记录。'}</p>}</div>
  <div className="vep-queue-footer"><span>快捷键：J 下一条 · K 上一条 · A 确认 · R 否决（焦点在输入框时不触发）</span><div><button disabled={offset===0} onClick={()=>{const next=Math.max(0,offset-page.limit);setOffset(next);void load(next)}}>上一页</button><button disabled={offset+page.limit>=page.total} onClick={()=>{const next=offset+page.limit;setOffset(next);void load(next)}}>下一页</button></div></div>
 </section>;
}
