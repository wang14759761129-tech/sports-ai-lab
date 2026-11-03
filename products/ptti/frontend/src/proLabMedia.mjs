export function readReadyTime(video){
 if(!video||video.error||video.readyState<1||!Number.isFinite(video.duration)||video.duration<=0||!Number.isFinite(video.currentTime)||video.currentTime<0||video.currentTime>video.duration)throw Error('MEDIA_NOT_READY');
 return video.currentTime;
}

export function requestPauseSeek(video,time){
 readReadyTime(video);
 if(!Number.isFinite(time)||time<0||time>video.duration)throw Error("INVALID_SEEK_TARGET");
 video.pause();
 video.currentTime=time;
}

export function isVerifiedSyntheticDigest(actual,expected){return typeof actual === "string" && typeof expected === "string" && /^[0-9a-f]{64}$/.test(actual) && actual === expected}
export function requireVerifiedStorage(identity,broken){if(identity !== true || broken !== false)throw Error("媒体身份未确认或存储异常，未修改记录") }
