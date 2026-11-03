import {createMoment,loadMomentState,writeMoments} from './momentCards.mjs';
export function savePlaybackMoment(storage,video,seconds,title,note){
 if(!video||video.availability_status!=='AVAILABLE'||video.hash_status!=='VERIFIED'||!/^[a-f0-9]{64}$/i.test(video.source_sha256||'')||typeof video.video_id!=='string'||!video.video_id||!Number.isFinite(seconds)||seconds<0||!Number.isFinite(video.duration_ms)||seconds*1000>video.duration_ms)return {ok:false,error:'视频身份、可用性或时间尚未核验，未保存。'};
 const state=loadMomentState(storage);if(!state.writable)return {ok:false,error:state.error};
 const created=createMoment(state.moments,{videoKey:'local:'+video.video_id,title,timestamp:seconds,note,tags:[]});if(created.errors.length)return {ok:false,error:created.errors.join('；')};
 const moment={...created.moment,sourceSha256:video.source_sha256.toLowerCase()};const records=created.moments.map(m=>m.id===moment.id?moment:m);const saved=writeMoments(storage,records);return saved.ok?{ok:true,error:'',moment}:saved;
}
