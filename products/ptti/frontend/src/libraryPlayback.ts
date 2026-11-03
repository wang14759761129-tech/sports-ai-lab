export function requestedLibraryVideo<T extends {video_id:string}>(videos:T[],requested:string,applied:string):T|null{
 if(!requested||requested===applied)return null;
 return videos.find(video=>video.video_id===requested)||null;
}

export function savedFolderDefaults<T extends {path:string}>(scans:T[],currentPath:string):T|null{
 return currentPath||!scans.length?null:scans[0];
}
