export function momentLocalVideo(moment,videos){
 const found=Array.isArray(videos)?videos.filter(v=>v.key===moment?.videoKey):[];
 const v=found.length===1?found[0]:null;
 return v?.kind==='LOCAL'&&v.source?.availability_status==='AVAILABLE'&&typeof v.source.video_id==='string'&&v.key==='local:'+v.source.video_id?v:null;
}
