export function readReadyTime(video){
 if(!video||video.error||video.readyState<1||!Number.isFinite(video.duration)||video.duration<=0||!Number.isFinite(video.currentTime)||video.currentTime<0||video.currentTime>video.duration)throw Error('MEDIA_NOT_READY');
 return video.currentTime;
}
