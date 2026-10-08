/** Only the latest request in the current video/filter scope may update the UI. */
export class ReviewQueueRequests {
 private scope='';
 private generation=0;
 setScope(scope:string){if(scope!==this.scope){this.scope=scope;this.generation++}}
 isScope(scope:string){return this.scope===scope}
 async load<T>(scope:string,request:()=>Promise<T>,apply:(value:T)=>void,
               failed:(message:string)=>void,loading:(value:boolean)=>void):Promise<T|null>{
  if(scope!==this.scope)return null;
  const generation=++this.generation;
  const current=()=>generation===this.generation&&scope===this.scope;
  loading(true);
  try{const value=await request();if(!current())return null;apply(value);return value}
  catch(error){if(current())failed(error instanceof Error?error.message:'候选加载失败');return null}
  finally{if(current())loading(false)}
 }
}

export function nextCandidateAfterReview<T extends {evidence_id:string}>(previous:T[],updated:T[],reviewedId:string):T|null{
 if(updated.some(item=>item.evidence_id===reviewedId))return null;
 const index=previous.findIndex(item=>item.evidence_id===reviewedId);
 return index>=0?updated[index]??null:null;
}

export function shouldHandleReviewShortcut(event:{repeat:boolean;isComposing:boolean;altKey:boolean;ctrlKey:boolean;metaKey:boolean;shiftKey:boolean},editable:boolean){
 return !editable&&!event.repeat&&!event.isComposing&&!event.altKey&&!event.ctrlKey&&!event.metaKey&&!event.shiftKey;
}
