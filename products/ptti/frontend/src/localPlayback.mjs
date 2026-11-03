export const PROGRESS_KEY='ptti.local-video-progress/1';
const validId=id=>typeof id==='string'&&/^sha256-chunks-v1:[a-f0-9]{64}$/.test(id);
function parseProgress(raw){
 if(raw===null)return {schema:1,entries:{}};
 const all=JSON.parse(raw);
 if(!all||all.schema!==1||!all.entries||typeof all.entries!=='object'||Array.isArray(all.entries))throw Error('Invalid progress storage');
 return all;
}
function entrySeconds(all,id,duration){
 if(!Object.hasOwn(all.entries,id))return null;
 const e=all.entries[id];
 if(!e||typeof e!=='object'||Array.isArray(e)||!Number.isFinite(e.seconds)||e.seconds<0||!Number.isFinite(e.duration)||e.duration<=0||Math.abs(e.duration-duration)>0.5||e.seconds>duration)throw Error('Invalid stored progress');
 return e.seconds;
}
export function readProgress(storage,id,duration){
 if(!validId(id)||!Number.isFinite(duration)||duration<=0)throw Error('Invalid video identity');
 return entrySeconds(parseProgress(storage.getItem(PROGRESS_KEY)),id,duration);
}
export function writeProgress(storage,id,seconds,duration,displayName){
 if(!validId(id)||!Number.isFinite(seconds)||!Number.isFinite(duration)||duration<=0||seconds<0||seconds>duration)throw Error('Invalid video progress');
 const all=parseProgress(storage.getItem(PROGRESS_KEY));
 entrySeconds(all,id,duration);
 const previous=all.entries[id];const name=typeof displayName==='string'?displayName.split(/[\\/]/).pop().slice(0,200):previous?.displayName;
 all.entries[id]={seconds,duration,updatedAt:new Date().toISOString(),...(name?{displayName:name}:{})};storage.setItem(PROGRESS_KEY,JSON.stringify(all));
}
export function playbackState(video,blocked=false){
 if(blocked)return 'blocked';if(!video)return 'idle';if(video.error)return 'error';if(video.readyState<1)return 'loading';if(video.ended)return 'ended';if(!video.paused)return 'playing';return video.currentTime>0?'paused':'ready';
}

// Once playback or seeking starts, the user's current position takes precedence.
export function resumeDecision(saved,duration,interacted){
 if(interacted)return {action:'PRESERVE_CURRENT'};
 if(saved!==null&&Number.isFinite(saved)&&Number.isFinite(duration)&&saved>0&&saved<duration)return {action:'RESTORE',seconds:saved};
 return {action:'NO_RESTORE'};
}
export async function guardedPlay(video,isCurrent){
 if(!isCurrent())return 'inactive';
 try{
  await video.play();
  if(!isCurrent()){video.pause();return 'inactive'}
  return 'playing';
 }catch{
  return isCurrent()?'blocked':'inactive';
 }
}
export function timelinePosition(seconds,duration){
 if(!Number.isFinite(seconds)||!Number.isFinite(duration)||duration<=0||seconds<0||seconds>duration)throw Error('Invalid timeline position');
 return 100*seconds/duration;
}

export function recentProgress(storage,limit=20){
 if(!Number.isSafeInteger(limit)||limit<1||limit>100)throw Error('Invalid history limit');
 const all=parseProgress(storage.getItem(PROGRESS_KEY));const result=[];
 for(const [id,e] of Object.entries(all.entries)){
  if(!validId(id)||!e||typeof e!=='object'||!Number.isFinite(e.duration)||e.duration<=0||!Number.isFinite(e.seconds)||e.seconds<0||e.seconds>e.duration||typeof e.updatedAt!=='string'||!Number.isFinite(Date.parse(e.updatedAt)))continue;
  const name=typeof e.displayName==='string'?e.displayName.split(/[\\/]/).pop().slice(0,200):'';
  result.push({id,seconds:e.seconds,duration:e.duration,updatedAt:e.updatedAt,displayName:name||'未命名本机视频'});
 }
 return result.sort((a,b)=>b.updatedAt.localeCompare(a.updatedAt)).slice(0,limit);
}
export function removeProgress(storage,id){
 if(!validId(id))throw Error('Invalid video identity');
 const raw=storage.getItem(PROGRESS_KEY);if(raw===null)return false;
 const all=parseProgress(raw);if(!Object.hasOwn(all.entries,id))return false;
 const entry=all.entries[id];if(!entry||typeof entry!=='object'||!Number.isFinite(entry.duration)||entry.duration<=0)throw Error('Invalid stored progress');
 entrySeconds(all,id,entry.duration);
 delete all.entries[id];storage.setItem(PROGRESS_KEY,JSON.stringify(all));return true;
}
