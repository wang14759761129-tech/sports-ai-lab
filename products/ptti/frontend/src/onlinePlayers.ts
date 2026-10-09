// Official page fallback is always available; permission is never inferred from region.
export interface OnlinePlayerAdapter {name:string; watchURL:(id:string)=>string; embedURL:(id:string)=>string|null}
export const BilibiliPlayerAdapter:OnlinePlayerAdapter={name:'Bilibili',watchURL:id=>`https://www.bilibili.com/video/${id}/`,embedURL:id=>/^BV[0-9A-Za-z]{10}$/.test(id)?`https://player.bilibili.com/player.html?bvid=${id}&autoplay=0`:null};
export const YouTubePlayerAdapter:OnlinePlayerAdapter={name:'YouTube',watchURL:id=>`https://www.youtube.com/watch?v=${id}`,embedURL:id=>/^[A-Za-z0-9_-]{11}$/.test(id)?`https://www.youtube.com/embed/${id}`:null};
export function onlineAdapter(provider:string){return provider==='BILIBILI'?BilibiliPlayerAdapter:provider==='YOUTUBE'||provider==='YOUTUBE_OFFICIAL'?YouTubePlayerAdapter:null}
export function allowedEmbed(source:any){const s=source.video_source;const adapter=onlineAdapter(s?.provider||source.provider);return s?.embed_permission==='ALLOWED'&&s?.playback_type==='OFFICIAL_EMBED'&&adapter?adapter.embedURL(s.source_id):null}
export function preferredSources(rows:any[],preference:string){return [...rows].sort((a,b)=>{const rank=(r:any)=>r.kind==='LOCAL'?4:r.source.video_source?.playback_verified?(r.source.provider===preference?3:2):0;return rank(b)-rank(a)})}
