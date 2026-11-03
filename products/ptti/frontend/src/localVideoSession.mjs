/** Owns exactly one local-media session; a newer selection invalidates older work. */
export function createLocalVideoSessionManager({open, bind}) {
 let generation=0, pending=null, active=null, closed=false;
 const disposeActive=()=>{if(active){const previous=active;active=null;previous.release();}};
 function cancel(){generation++;pending?.abort();pending=null;disposeActive();}
 async function select(file){
  if(closed) throw new Error('Video session manager is closed');
  cancel(); const current=generation; const controller=new AbortController();pending=controller;
  let candidate;
  try {
   candidate=await open(file,{signal:controller.signal});
   if(closed||current!==generation||controller.signal.aborted){candidate.release();return {status:'cancelled'};}
   let binding;
   try { binding=await bind(candidate); } catch(error) {candidate.release();throw error;}
   if(closed||current!==generation||controller.signal.aborted){binding?.release?.();candidate.release();return {status:'cancelled'};}
   let released=false;
   active={identity:candidate.identity,release(){if(released)return;released=true;try{binding?.release?.();}finally{candidate.release();}}};
   return {status:'ready',identity:candidate.identity};
  } catch(error) {
   if(closed||current!==generation||controller.signal.aborted)return {status:'cancelled'};
   throw error;
  } finally {if(current===generation)pending=null;}
 }
 return {select,cancel,close(){if(closed)return;closed=true;cancel();},isCurrent(identity){return !!active&&active.identity===identity;}};
}
