import {useCallback,useEffect,useRef,useState} from 'react';
import {ReviewQueueRequests,nextCandidateAfterReview,shouldHandleReviewShortcut} from './reviewQueueRequests';

type Candidate={evidence_id:string;video_id:string;representative_ms:number;review_status:string;source:string;suggested_side?:string;disposition?:string;raw_candidate?:any;ai_provenance?:any;review_flags?:string[]};
type Page={counts:Record<string,number>;attention_counts:Record<string,number>;total:number;offset:number;limit:number;items:Candidate[]};
type Props={videoId:string;selectedId?:string;refreshKey?:string|number;reviewVersion?:number;reviewedId?:string;busy?:boolean;onSelect:(candidate:Candidate,play?:boolean)=>void;onReview:(decision:'CONFIRMED'|'REJECTED')=>Promise<boolean>};
const endpoint='/api/video-evidence';
const clock=(ms:number)=>{const s=Math.max(0,ms)/1000;return `${String(Math.floor(s/3600)).padStart(2,'0')}:${String(Math.floor(s/60)%60).padStart(2,'0')}:${(s%60).toFixed(3).padStart(6,'0')}`};
const empty:Page={counts:{},attention_counts:{},total:0,offset:0,limit:30,items:[]};

export default function HitCandidateReviewQueue({videoId,selectedId,refreshKey=0,reviewVersion=0,reviewedId='',busy=false,onSelect,onReview}:Props){
 const [status,setStatus]=useState('UNVERIFIED'),[attention,setAttention]=useState(''),[page,setPage]=useState<Page>(empty),[offset,setOffset]=useState(0),[loading,setLoading]=useState(false),[message,setMessage]=useState('');
 const selected=page.items.find(item=>item.evidence_id===selectedId)||null;
 const cursorKey=`ptti-review-cursor:${videoId}:${status}:${attention}`;
 const requests=useRef(new ReviewQueueRequests()),scope=`${videoId}:${status}:${attention}`;
 requests.current.setScope(scope);
 const previousScope=useRef(''),previousReview=useRef(reviewVersion),actionPending=useRef(false);
 const onSelectRef=useRef(onSelect);onSelectRef.current=onSelect;
 const pageRef=useRef(page);pageRef.current=page;
 const load=useCallback(async(nextOffset=offset)=>{
  if(!videoId){setPage(empty);return null}
  return requests.current.load<Page>(scope,async()=>{const query=new URLSearchParams({video_id:videoId,status,offset:String(nextOffset),limit:'30'});if(attention)query.set('attention',attention);const response=await fetch(`${endpoint}/ai-suggestions?${query}`);const result=await response.json();if(!response.ok)throw new Error(result.detail||'候选加载失败');return result},value=>{setPage(value);setOffset(value.offset);setMessage('')},setMessage,setLoading);
 },[videoId,status,attention,offset,scope]);
 useEffect(()=>{
  const changed=previousScope.current!==scope,reviewed=previousReview.current!==reviewVersion;
  previousScope.current=scope;previousReview.current=reviewVersion;
  const before=pageRef.current.items;
  let saved:any=null;
  if(changed){setPage(empty);try{saved=JSON.parse(localStorage.getItem(cursorKey)||'null')}catch{/* Ignore invalid stored cursor. */}}
  const restoredOffset=Number.isSafeInteger(saved?.offset)&&saved.offset>=0&&saved.offset<1000000?saved.offset:0;
  void load(changed?restoredOffset:offset).then(result=>{
   if(!result||!requests.current.isScope(scope))return;
   if(reviewed&&status==='UNVERIFIED'){
    const next=nextCandidateAfterReview(before,result.items,reviewedId);
    if(next)choose(next,true,result.offset);else setMessage('复核已保存；当前页后面没有候选，可查看上一页或调整筛选。');
   }else if(changed&&saved){const next=result.items.find(item=>item.evidence_id===saved.evidence_id)||result.items.find(item=>item.representative_ms>=Number(saved.timestamp_ms||0));if(next)onSelectRef.current(next,false)}
  });
 },[videoId,status,attention,refreshKey,reviewVersion]);
 function choose(item:Candidate,play=true,pageOffset=offset){if(item.video_id!==videoId||!requests.current.isScope(scope))return;try{localStorage.setItem(cursorKey,JSON.stringify({evidence_id:item.evidence_id,timestamp_ms:item.representative_ms,offset:pageOffset}))}catch{/* The queue remains usable when local storage is disabled. */}onSelectRef.current(item,play)}
 async function move(delta:number){
  if(!page.items.length||loading||busy)return;
  let index=page.items.findIndex(item=>item.evidence_id===selectedId);let target=index+delta;
  if(target<0&&offset>0){const next=await load(Math.max(0,offset-page.limit));if(next?.items.length)choose(next.items[next.items.length-1],true,next.offset);return}
  if(target>=page.items.length&&offset+page.limit<page.total){const next=await load(offset+page.limit);if(next?.items.length)choose(next.items[0],true,next.offset);return}
  target=Math.max(0,Math.min(page.items.length-1,target));choose(page.items[target]);
 }
 async function decide(decision:'CONFIRMED'|'REJECTED'){
  if(!selected||selected.review_status!=='UNVERIFIED'||busy||actionPending.current)return;
  actionPending.current=true;
  try{await onReview(decision)}finally{actionPending.current=false}
 }
 useEffect(()=>{
  const handle=(event:KeyboardEvent)=>{
   const target=event.target as HTMLElement|null;
   const editable=Boolean(target?.closest('input,textarea,select,button,[role="textbox"]')||target?.isContentEditable);
   if(!videoId||loading||busy||!shouldHandleReviewShortcut(event,editable))return;
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
  <div className="vep-ai-list" aria-label="候选列表">{page.items.map(item=><button key={item.evidence_id} className={selectedId===item.evidence_id?'active':''} onClick={()=>choose(item,true)}><b>{clock(item.representative_ms)} · 击球候选</b><small>{item.suggested_side==='NEAR'?'Near 候选':item.suggested_side==='FAR'?'Far 候选':'击球方未知'} · {item.review_status==='UNVERIFIED'?'待复核':item.review_status==='CONFIRMED'?'人工已确认':item.review_status==='REJECTED'?'已否决':'算法已过滤'}</small><small>规则证据 {Number(item.raw_candidate?.evidence_score||0).toFixed(3)} · {item.raw_candidate?.ball_quality||'球证据不足'} · {item.review_flags?.length?`优先复核：${item.review_flags.join('、')}`:'暂无额外异常标记'}</small></button>)}{!page.items.length&&<p className="vep-empty-review">{status==='UNVERIFIED'?'当前筛选没有待复核项。没有候选时，可使用人工时间标记。':'该状态下暂无记录。'}</p>}</div>
  <div className="vep-queue-footer"><span>快捷键：J 下一条 · K 上一条 · A 确认 · R 否决（焦点在输入框时不触发）</span><div><button disabled={loading||busy||offset===0} onClick={()=>{const next=Math.max(0,offset-page.limit);void load(next)}}>上一页</button><button disabled={loading||busy||offset+page.limit>=page.total} onClick={()=>{const next=offset+page.limit;void load(next)}}>下一页</button></div></div>
 </section>;
}
