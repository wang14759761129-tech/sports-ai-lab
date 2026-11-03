/** Narrow native export boundary. Browser download remains unconfirmed. */
export async function saveReviewJSON(json, {native, bridge, browserDownload}) {
 if(typeof json!=='string'||new TextEncoder().encode(json).length>2*1024*1024) return {status:'error'};
 if(native){
  if(typeof bridge?.save_prolab_json!=='function')return {status:'unavailable'};
  try{const result=await bridge.save_prolab_json(json);return ['saved','cancelled','error'].includes(result?.status)?{status:result.status}:{status:'error'}}catch{return {status:'error'}}
 }
 try{browserDownload(json);return {status:'requested'}}catch{return {status:'error'}}
}
export function reviewDirty(marks, signature, savedSnapshot){return (marks.length>0||savedSnapshot!==null)&&signature!==savedSnapshot;}
