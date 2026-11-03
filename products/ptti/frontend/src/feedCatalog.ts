import {reviewedOfficialSource} from './reviewedOfficialEmbed.mjs';
import {isFeedFavorite} from './matchFavorites.mjs';
import {approvedOfficialThumbnail,resolveEditorialMatchPhoto,resolveInternalFounderQaThumbnail} from './thumbnailPermission.mjs';
import {resolveYoutubeThumbnail, youtubeThumbnailSourceId} from './youtubeThumbnailRuntime.mjs';
import {allowedEmbed} from './onlinePlayers.js';
export {feedMatchId, favoriteKeysForMatch, isFeedFavorite, isMatchFavorite, matchFavoriteKey, uniqueFavoriteRows} from './matchFavorites.mjs';
export {approvedOfficialThumbnail} from './thumbnailPermission.mjs';

export type FeedMediaMode='DISTRIBUTABLE'|'INTERNAL_FOUNDER_QA';
declare const __PTTI_MEDIA_MODE__:FeedMediaMode;
export const feedMediaMode:FeedMediaMode=typeof __PTTI_MEDIA_MODE__==='undefined'?'DISTRIBUTABLE':__PTTI_MEDIA_MODE__;
export type FeedVideo = {key:string; kind:'LOCAL'|'OFFICIAL'; title:string; subtitle:string; thumbnail:string; thumbnailFallbackLabel?:string; thumbnailSource?:'YOUTUBE_DATA_API'|'EDITORIAL_MATCH_PHOTO'|'YOUTUBE_INTERNAL_QA_REMOTE'; thumbnailPublisher?:string; thumbnailCredit?:{label:string;url:string}; thumbnailDescription?:string; watchUrl:string|null; duration:number|null; athletes:string[]; athleteNames:string[]; event:string; category:string; opened:string|null; searchText?:string; source:any};
export function feedVideos(data:any,mediaMode:FeedMediaMode=feedMediaMode):FeedVideo[]{
 const local:FeedVideo[]=(data.videos||[]).filter((v:any)=>v.availability_status==='AVAILABLE').map((v:any)=>{const metadata=v.personal_library||{};return {key:'local:'+v.video_id,kind:'LOCAL',title:v.title,subtitle:`本地引用 · ${rightsLabel(v.rights_status)} · ${metadata.completeness_status==='HUMAN_VERIFIED_COMPLETE'?'完整性已人工核实':'完整性未核实'}`,thumbnail:`/api/video-evidence/library/videos/${v.video_id}/thumbnail`,thumbnailFallbackLabel:'本地封面暂不可用',watchUrl:null,duration:v.duration_ms/1000,athletes:v.athlete_ids||[],athleteNames:[metadata.player_a,metadata.player_b].filter(Boolean),event:metadata.event_name||v.match_id&&data.matches.find((m:any)=>m.match_id===v.match_id)?.event_name||'赛事未核实',category:metadata.match_type||'UNKNOWN',opened:v.last_opened_at,source:v}});
 const seen=new Set<string>();
 const official:FeedVideo[]=(data.official_videos||[]).filter((v:any)=>{const key=(v.provider||'UNKNOWN')+':'+v.video_id;if(seen.has(key))return false;seen.add(key);return v.full_match===true||!!v.source_key}).map(reviewedOfficialSource).map((v:any)=>{
  const youtubeThumbnail=resolveYoutubeThumbnail(v,data.youtube_thumbnail_runtime?.[youtubeThumbnailSourceId(v)]);
  const apiThumbnail=youtubeThumbnail.status==='CURRENT'?youtubeThumbnail.thumbnail:null;
  const explicitlyApproved=approvedOfficialThumbnail(v);
  const editorialPhoto=resolveEditorialMatchPhoto(v);
  const internalQaThumbnail=resolveInternalFounderQaThumbnail(v,mediaMode);
  return {key:'official:'+v.video_id,kind:'OFFICIAL',title:apiThumbnail?youtubeThumbnail.title||v.title:(v.display_title||v.title),subtitle:(v.source_publisher||v.channel||v.provenance?.publisher||'发布者未记录')+' · '+(v.playback_limitation|| (v.video_source?.playback_type==='OFFICIAL_EMBED'&&v.video_source?.playback_verified?'官方内嵌已验证':v.video_source?.playback_verified?'本次记录曾在官方页播放':v.playback_status==='RESTRICTED'?'官方页面访问受限':'在官方平台观看 · 实际播放待核验')),thumbnail:internalQaThumbnail||(apiThumbnail?apiThumbnail.url:(editorialPhoto?editorialPhoto.display_url:explicitlyApproved?v.thumbnail_url:'')),thumbnailSource:internalQaThumbnail?'YOUTUBE_INTERNAL_QA_REMOTE':apiThumbnail?'YOUTUBE_DATA_API':editorialPhoto?'EDITORIAL_MATCH_PHOTO':undefined,thumbnailPublisher:apiThumbnail?youtubeThumbnail.channel_title:undefined,thumbnailCredit:editorialPhoto?{label:editorialPhoto.attribution,url:editorialPhoto.photo_page_url}:undefined,thumbnailDescription:editorialPhoto?.caption,thumbnailFallbackLabel:v.thumbnail_url&&!explicitlyApproved&&!apiThumbnail?'官方封面展示许可未核实':'暂无官方封面',watchUrl:officialWatchUrl(v),duration:v.duration_seconds,athletes:v.athlete_ids||[],athleteNames:v.athlete_names||[],event:v.event_name||'赛事未核实',category:v.discipline||'UNKNOWN',opened:null,source:v};
 });
 const names:Record<string,string>={MS:"男单",WS:"女单",MD:"男双",WD:"女双",XD:"混双"};
 for(const row of [...local,...official]){const linked=(data.athletes||[]).filter((a:any)=>row.athletes.includes(a.athlete_id));const aliases=linked.flatMap((a:any)=>[a.canonical_name_en,a.canonical_name_zh,...(Array.isArray(a.aliases)?a.aliases.filter((v:any)=>typeof v==='string'):[])]).filter(Boolean);row.searchText=[row.title,row.event,...row.athleteNames,...aliases,names[row.category]||row.category,row.source.event_year??row.source.personal_library?.event_year??''].join(' ').toLowerCase()}
 return [...local,...official.sort((a,b)=>Number(!!b.source.video_source?.playback_verified)-Number(!!a.source.video_source?.playback_verified))];
}
function rightsLabel(status:string){return ({USER_SELF_CAPTURED:'本人拍摄',USER_OWNED:'本人拥有使用权',LICENSED:'许可待核对',LICENSED_FOR_ANALYSIS:'获准本机分析',PERSONAL_VIEW_ONLY:'仅个人观看',PENDING_REVIEW:'授权待核实',RESEARCH_NONCOMMERCIAL:'研究素材·非商业'})[status]||'授权待核实'}
export function filterFeed(rows:FeedVideo[],{query='',category='全部',athlete='',event='',view='home',favorites=[],year='',platform='',content=''}:{query?:string;category?:string;athlete?:string;event?:string;view?:string;favorites?:string[];year?:string;platform?:string;content?:string}):FeedVideo[]{
  return rows.filter(v=>{const contentType=v.kind==='LOCAL'?(v.source.personal_library?.content_type||'UNKNOWN'):(v.source.content_type||(v.source.full_match===true?'FULL_MATCH':'UNKNOWN'));const eventYear=v.source.personal_library?.event_year??v.source.event_year;const complete=v.kind==='LOCAL'?v.source.personal_library?.completeness_status==='HUMAN_VERIFIED_COMPLETE':v.source.video_source?.is_full_match===true;return (!year||String(eventYear)===year)&&(!platform||(v.kind==='LOCAL'?'LOCAL':v.source.provider?.replace('_OFFICIAL',''))===platform)&&(!content||contentType===content)&&(!query||query.trim().toLowerCase().split(/\s+/).filter(Boolean).every(token=>(v.searchText||[v.title,v.event,...v.athleteNames].join(' ').toLowerCase()).includes(token)))&&(!athlete||v.athletes.includes(athlete)||v.athleteNames.includes(athlete))&&(!event||v.event===event)&&(view!=='feedHistory'||!!v.opened)&&(view!=='feedFavorites'||isFeedFavorite(v,favorites,rows))&&(category==='全部'||category==='完整比赛'&&complete||category==='关注球星'&&!!athlete||category==='本地录像'&&v.kind==='LOCAL'||category==='男单'&&v.category==='MS'||category==='女单'&&v.category==='WS'||category==='男双'&&v.category==='MD'||category==='女双'&&v.category==='WD'||category==='混双'&&v.category==='XD'||category==='WTT'&&v.kind==='OFFICIAL'&&/WTT|Smash/i.test(v.event)||category==='世乒赛'&&/Worlds/i.test(v.event)||category==='奥运'&&/Olympic/i.test(v.event))});
}
function providerFamily(provider:any){return provider==='YOUTUBE'||provider==='YOUTUBE_OFFICIAL'?'YOUTUBE':provider==='BILIBILI'?'BILIBILI':null}
export function officialWatchUrl(source:any):string|null{
 if(!source||typeof source.video_id!=='string'||typeof source.source_url!=='string')return null;
 const provider=providerFamily(source.provider),nestedProvider=source.video_source?.provider;
 if(!provider||source.video_source?.source_id&&source.video_source.source_id!==source.video_id||nestedProvider&&providerFamily(nestedProvider)!==provider)return null;
 try{
  const url=new URL(source.source_url);
  if(url.protocol!=='https:'||url.username||url.password||url.hash)return null;
  if(provider==='YOUTUBE'){
   if(!/^[A-Za-z0-9_-]{11}$/.test(source.video_id))return null;
   if(['youtube.com','www.youtube.com','m.youtube.com'].includes(url.hostname))return url.pathname==='/watch'&&url.searchParams.getAll('v').length===1&&url.searchParams.get('v')===source.video_id?source.source_url:null;
   if(url.hostname==='youtu.be')return url.pathname.replace(/^\//,'')===source.video_id&&!url.search?source.source_url:null;
   return null;
  }
  if(!/^BV[A-Za-z0-9]{10}$/.test(source.video_id)||!['bilibili.com','www.bilibili.com'].includes(url.hostname)||url.search)return null;
  return url.pathname===`/video/${source.video_id}`||url.pathname===`/video/${source.video_id}/`?source.source_url:null;
 }catch{return null}
}
export function officialAction(v:FeedVideo){const source=v.source,s=source.video_source;if(!officialWatchUrl(source)||s?.source_id!==source.video_id||providerFamily(s.provider||source.provider)!==providerFamily(source.provider))return 'SOURCE_LINK';return allowedEmbed(source)?'EMBED':'SOURCE_LINK';}
export function findOfficialFeedVideo(data:any,matchId:string,source:any):FeedVideo|null{
 if(!source||source.match_id!==matchId||typeof source.source_key!=='string'||typeof source.video_id!=='string'||typeof source.provider!=='string'||typeof source.source_url!=='string'||typeof source.video_source?.source_id!=='string')return null;
 return feedVideos(data).find(video=>video.kind==='OFFICIAL'&&video.source.match_id===matchId&&video.source.source_key===source.source_key&&video.source.video_id===source.video_id&&video.source.provider===source.provider&&video.source.source_url===source.source_url&&video.source.video_source?.source_id===source.video_source.source_id)??null;
}
export function officialWatchState(source:any):{state:'restricted'|'no-embed'|'observed'|'page-verified'|'unavailable'|'unverified';label:string}{
 const limitation=String(source?.playback_limitation||'');
  const review=source?.official_embed_review||source?.video_source?.provenance?.official_embed_review;
 const observed=source?.watch_page_status==='PLAYBACK_VERIFIED'||source?.video_source?.playback_verified===true&&source?.video_source?.playback_type==='OFFICIAL_PAGE'||/画面播放已验证/.test(limitation);
 if(source?.watch_page_status==='LOGIN_REQUIRED'||source?.playback_status==='RESTRICTED'||/登录|试看|区域|地区/.test(limitation))return {state:'restricted',label:observed?'受限 · 曾记录播放，当前未核验':'官方平台受限 · 播放未核验'};
 if(source?.watch_page_status==='UNAVAILABLE'||source?.playback_status==='UNAVAILABLE')return {state:'unavailable',label:'页面记录不可用 · 可尝试官方链接'};
  if(source?.playback_status==='EMBED_BLOCKED'||source?.video_source?.embed_permission==='DENIED'||source?.native_playback_test?.error_class==='EMBEDDING_DISALLOWED'||(review&&!allowedEmbed(source)))return {state:'no-embed',label:observed?'不可内嵌 · 曾记录播放，当前未核验':'不可内嵌 · 外链播放未核验'};
 if(observed)return {state:'observed',label:'曾记录播放 · 当前状态未核验'};
 if(source?.watch_page_status==='PAGE_VERIFIED')return {state:'page-verified',label:'页面已核验 · 播放未验证'};
 return {state:'unverified',label:'来源已登记 · 页面/播放未核验'};
}
export function durationLabel(seconds:number|null){if(seconds==null)return '时长未核实';return `${Math.floor(seconds/60)}:${String(Math.floor(seconds)%60).padStart(2,'0')}`;}
