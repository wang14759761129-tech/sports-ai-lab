// A communication timeout is not a failed scan: never POST or alter task state.
export async function readScanPreviews(signal?: AbortSignal, timeoutMs=15000): Promise<any[]> {
 const controller=new AbortController();
 let timer:ReturnType<typeof setTimeout>,rejectWait:(reason:Error)=>void=()=>{};
 const abort=()=>{controller.abort();const e=new Error('已离开预览页面');e.name='AbortError';rejectWait(e)};
 if(signal?.aborted){const e=new Error('已离开预览页面');e.name='AbortError';throw e}
 const deadline=new Promise<never>((_,reject)=>{
  rejectWait=reject;
  timer=setTimeout(()=>{controller.abort();const e=new Error('读取扫描进度超时（15秒）。后台可能仍在运行，正在重新读取；请勿重复导入。');e.name='ScanPreviewTimeoutError';reject(e)},timeoutMs);
 });
 signal?.addEventListener('abort',abort,{once:true});
 try{
  const response=(async()=>{
   const r=await fetch('/api/video-evidence/library/folders',{signal:controller.signal,cache:'no-store'});
   const rows=await r.json();
   if(!r.ok)throw new Error(typeof rows.detail==='string'?rows.detail:`读取预览失败（HTTP ${r.status}）`);
   if(!Array.isArray(rows))throw new Error('预览列表格式异常，请重新读取');
   return rows;
  })();
  return await Promise.race([response,deadline]);
 }finally{clearTimeout(timer!);signal?.removeEventListener('abort',abort)}
}
