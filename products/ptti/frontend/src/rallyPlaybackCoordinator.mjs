/** One owner for Moment seeks and rally playback. Core enforces session identity. */
export function createRallyPlaybackCoordinator(core,adapter){
 let task=null,generation=0;
 function cancel(){generation++;adapter.cancelPendingSeek();if(task){task.cancel();task=null}core.pause()}
 function playRally(rally,identity,{repeat=false}={}){
  cancel();
  const snapshot=core.getSnapshot();
  if(!identity||snapshot.status!=='ready'||snapshot.video_identity!==identity)return {ok:false,error:'identity-mismatch'};
  if(!Number.isFinite(rally?.start_seconds)||!Number.isFinite(rally?.end_seconds)||rally.start_seconds<0||rally.start_seconds>=rally.end_seconds||rally.end_seconds>snapshot.duration_seconds)return {ok:false,error:'invalid-rally'};
  const current=++generation;
  const result=core.playRallyPlaylist([{point_id:rally.id,video_identity:identity,start_time:rally.start_seconds,end_time:rally.end_seconds,binding_status:'BOUND'}],{repeat_single:repeat});
  if(!result.ok)return result;
  task=result.value;const owned=task;
  const done=owned.done.then(outcome=>{if(current===generation)task=null;return outcome});
  return {ok:true,value:{done,pause:()=>{if(current===generation)owned.pause()},resume:()=>current===generation?owned.resume():Promise.resolve({ok:false,error:'cancelled'}),cancel:()=>{if(current===generation)cancel()}}};
 }
 async function seekMoment(seconds){cancel();const current=++generation;const result=await adapter.seekExact(seconds);return current===generation?result:{ok:false,error:'cancelled'};}
 return {playRally,seekMoment,cancel,dispose:cancel};
}
