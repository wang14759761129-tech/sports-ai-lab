import {useEffect,useRef,useState} from 'react';
import {REVIEW_VIEWS,createReviewReceipt,type ReviewVerdict,type ReviewSpace} from './founderReview.mjs';
import './founder-review.css';

export default function FounderReview({open,onClose,onVisit}:{open:boolean;onClose:()=>void;onVisit:(space:ReviewSpace)=>void}){
 const dialog=useRef<HTMLDialogElement>(null);
 const [views,setViews]=useState<Record<string,ReviewVerdict>>({});
 const [feedback,setFeedback]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState('');
 useEffect(()=>{const node=dialog.current;if(!node)return;if(open&&!node.open)node.showModal();else if(!open&&node.open)node.close()},[open]);
 function exportReview(){
  setNotice('');setError('');
  try{
   const data=createReviewReceipt({views,feedback},{width:innerWidth,height:innerHeight,devicePixelRatio,reducedMotion:matchMedia('(prefers-reduced-motion: reduce)').matches});
   const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),link=document.createElement('a');
   link.href=url;link.download='ptti-founder-visual-review.json';link.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
   setNotice('已请求浏览器下载反馈 JSON，请确认下载完成。请手动附上你选择的截图；没有上传任何内容。');
  }catch(e){setError(e instanceof Error?e.message:'导出失败，当前反馈仍保留。')}
 }
 return <dialog ref={dialog} className="founder-review" aria-labelledby="founder-review-title" onCancel={event=>{event.preventDefault();onClose()}}>
  <header><div><small>FOUNDER REVIEW · INTERNAL QA</small><h2 id="founder-review-title">四张图，一轮真实反馈</h2></div><button onClick={onClose} aria-label="关闭视觉验收">关闭</button></header>
  <p>逐项打开目标页面，使用 Windows 截图工具选择浏览器窗口。桌面图可先按 F11 全屏，再按 Win + Shift + S 截图；操作由你亲自完成。</p>
  <ol>{REVIEW_VIEWS.map(view=><li key={view.id}><div><strong>{view.label}</strong><p>{view.hint}</p></div><div className="founder-review-actions"><button onClick={()=>{dialog.current?.close();onClose();onVisit(view.space)}}>查看{view.label}</button><label>人工结论<select aria-label={`${view.label}人工结论`} value={views[view.id]??'NOT_REVIEWED'} onChange={event=>{setViews(current=>({...current,[view.id]:event.target.value as ReviewVerdict}));setNotice('')}}><option value="NOT_REVIEWED">尚未验收</option><option value="APPROVED">认可</option><option value="NEEDS_CHANGE">需要修改</option></select></label></div></li>)}</ol>
  <label className="founder-review-feedback">最想保留或修改什么？<textarea aria-label="Founder视觉反馈" value={feedback} maxLength={2000} onChange={event=>{setFeedback(event.target.value);setNotice('')}} placeholder="例如：封面够醒目；导航希望更紧凑；局点文字需要更清楚。"/></label>
  <p className="founder-review-private">反馈仅暂存在本页，刷新前请导出。仅导出你填写的结论、反馈和窗口尺寸，不读取录像、笔记、收藏或文件路径。开发页面的精确源码版本需与本轮 Git 回执配对。</p>
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  <footer><button onClick={exportReview}>导出本地视觉反馈 JSON</button><button onClick={onClose}>继续体验</button></footer>
 </dialog>;
}
