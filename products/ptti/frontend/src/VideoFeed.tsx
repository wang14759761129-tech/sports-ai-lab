import {lazy,useEffect,useLayoutEffect,useRef,useState,type MouseEvent,type ReactNode} from 'react';
import GrandNavigation from './GrandNavigation';
import type {GrandSpace} from './GrandNavigation';
import {Empty} from './ui';
import {feedVideos,feedMediaMode,filterFeed,durationLabel,officialAction,officialWatchState,feedMatchId,isFeedFavorite,isMatchFavorite,favoriteKeysForMatch,uniqueFavoriteRows} from './feedCatalog';
import type {FeedVideo} from './feedCatalog';
import FeedCoverFallback from './FeedCoverFallback';
import OfficialVideoPlayer from './OfficialVideoPlayer';
import OfficialCardActions from './OfficialCardActions';
import WorkspaceFrame from './WorkspaceFrame';
import {loadFeedView,saveFeedView,personalShelfFilters} from './cinemaViewing.mjs';
import {openOfficialLink} from './officialPlayback.mjs';
import {persistFavoriteKeys} from './favoritePersistence.mjs';
import {unavailableFavoriteKeys} from './matchFavorites.mjs';
import MatchSourcePanel from './MatchSourcePanel';
import LegacyMatchStory from './LegacyMatchStory';
const MomentCards=lazy(()=>import('./MomentCardsPage'));
const ProLab=lazy(()=>import('./ProLab'));
const FanArena=lazy(()=>import('./FanArena'));
const FounderReview=lazy(()=>import('./FounderReviewPanel'));
import {preferredSources} from './onlinePlayers';
import {activeStoryMatch} from './storyRoute.mjs';
import './video-feed.css';

function feedContext(){try{return JSON.parse(sessionStorage.getItem('ptti-r4-feed')||'{}')}catch{return {}}}
function feedView(){try{return loadFeedView(window.sessionStorage)||{athlete:'',event:'',query:''}}catch{return {athlete:'',event:'',query:''}}}
function rememberScroll(page?:string){try{const saved=feedContext();sessionStorage.setItem('ptti-r4-feed',JSON.stringify({...saved,scroll:window.scrollY,...(page?{returnPage:page}:{})}))}catch{}}

type ThumbnailProps={video:FeedVideo;external?:boolean;coverVariant?:number};
function Thumbnail(props:ThumbnailProps){
 return <ThumbnailImage key={`${props.video.key}:${props.video.thumbnailSource||''}:${props.video.thumbnail||''}`} {...props}/>;
}
function ThumbnailImage({video,external=false,coverVariant=0}:ThumbnailProps){
 const [failed,setFailed]=useState(!video.thumbnail),[loaded,setLoaded]=useState(false);
 const internalQa=video.thumbnailSource==='YOUTUBE_INTERNAL_QA_REMOTE';
 const coverState=failed?'FALLBACK':loaded?'LOADED':'LOADING';
 const fallbackReason=!video.thumbnail?'NO_ADMITTED_THUMBNAIL':failed?'IMAGE_LOAD_FAILED':'';
 return <div className={'feed-cover'+(video.thumbnailSource==='YOUTUBE_DATA_API'?' feed-cover--youtube-api':video.thumbnailSource==='EDITORIAL_MATCH_PHOTO'?' feed-cover--editorial-photo':internalQa?' feed-cover--youtube-internal-qa':'')} data-cover-state={coverState} data-cover-source={video.thumbnailSource||'NONE'} data-cover-fallback-reason={fallbackReason||undefined} {...(internalQa?{'data-qa-thumbnail-state':coverState,'data-qa-video-id':video.source.video_id}:{})}>{failed?<FeedCoverFallback video={video} variant={coverVariant}/>:<img src={video.thumbnail} alt={video.thumbnailDescription||''} aria-hidden={video.thumbnailSource==='EDITORIAL_MATCH_PHOTO'?undefined:true} loading="lazy" decoding="async" onLoad={()=>setLoaded(true)} onError={()=>{setLoaded(false);setFailed(true)}}/>}<span className={external?'feed-external':'feed-play'} aria-hidden="true">{external?'↗':'▶'}</span>{video.thumbnailSource==='YOUTUBE_DATA_API'?null:<small>{durationLabel(video.duration)}</small>}</div>;
}
function officialProviderLabel(source:any){return source?.provider==='BILIBILI'?'Bilibili':source?.provider==='YOUTUBE'||source?.provider==='YOUTUBE_OFFICIAL'?'YouTube':'官方平台'}
export default function VideoFeed({page,revision,query,onPlay,onTools,navigate}:{page:string;revision:number;query:string;onPlay:(id:string)=>void;onTools:()=>void;navigate:(page:string)=>void}){
 const [preference,setPreference]=useState('');
 const [refreshTick,setRefreshTick]=useState(0);
 const [year,setYear]=useState(()=>feedContext().year||''),[platform,setPlatform]=useState(()=>feedContext().platform||''),[content,setContent]=useState(()=>feedContext().content||'');
 const [matchChoice,setMatchChoice]=useState(''),[mappingBusy,setMappingBusy]=useState(false);
 const [data,setData]=useState<any>(null),[error,setError]=useState(''),[failedWatchUrl,setFailedWatchUrl]=useState<string|null>(null),[category,setCategory]=useState(()=>feedContext().category||'全部'),[athlete,setAthlete]=useState(()=>feedView().athlete||''),[event,setEvent]=useState(()=>feedView().event||''),[favorites,setFavorites]=useState<string[]>([]),[official,setOfficial]=useState<any>(null),[storyRoute,setStoryRoute]=useState<{matchId:string;page:string;revision:number}|null>(null),[visibleCount,setVisibleCount]=useState(12);
 const previousPage=useRef({page,revision});
 const favoriteWriteInFlight=useRef(false),favoriteEpoch=useRef(0);
 const [favoriteBusy,setFavoriteBusy]=useState(false);
 const [space,setSpace]=useState<GrandSpace>('cinema');
 const [visited,setVisited]=useState<GrandSpace[]>([]);
 const [reviewMounted,setReviewMounted]=useState(false),[reviewOpen,setReviewOpen]=useState(false);
 const spaceScroll=useRef<Partial<Record<GrandSpace,number>>>({cinema:feedContext().scroll||0});
 const pendingRestore=useRef<number|null>(null);
 useLayoutEffect(()=>{
  const target=pendingRestore.current;if(target===null)return;
  pendingRestore.current=null;
  const frame=requestAnimationFrame(()=>{document.getElementById(`grand-panel-${space}`)?.focus({preventScroll:true});window.scrollTo(0,target)});
  return()=>cancelAnimationFrame(frame);
 },[space]);
 useEffect(()=>{let live=true;const epoch=favoriteEpoch.current;fetch('/api/video-evidence/library').then(async r=>{if(!r.ok)throw Error('比赛视频目录暂不可用');const d=await r.json();if(live){setData(d);if(epoch===favoriteEpoch.current&&!favoriteWriteInFlight.current){setFavorites(d.feed_favorites||[]);setError('')}}}).catch(()=>{if(live&&epoch===favoriteEpoch.current&&!favoriteWriteInFlight.current)setError('比赛目录暂不可用；其他空间仍可使用。')});return()=>{live=false}},[page,revision,refreshTick]);
 useEffect(()=>{
  setOfficial(null);
  setStoryRoute(null);
  pendingRestore.current=null;
  setSpace('cinema');
  const previous=previousPage.current;
  if(previous.page!==page||previous.revision!==revision){
   const context=feedContext();
   if(page==='feedFavorites'){
    requestAnimationFrame(()=>window.scrollTo(0,0));
   }else if(context.returnPage===page&&typeof context.scroll==='number'){
    requestAnimationFrame(()=>window.scrollTo(0,context.scroll));
    try{
     const {returnPage:_returnPage,...rest}=context;
     sessionStorage.setItem('ptti-r4-feed',JSON.stringify(rest));
    }catch{}
   }
   previousPage.current={page,revision};
  }
 },[page,revision]);
 useEffect(()=>{if(official){const frame=requestAnimationFrame(()=>window.scrollTo(0,0));return()=>cancelAnimationFrame(frame)}},[official]);
 useEffect(()=>{if(official)return;const timer=window.setInterval(()=>{if(document.visibilityState==='visible')setRefreshTick(n=>n+1)},300000);return()=>clearInterval(timer)},[official]);
 useEffect(()=>setVisibleCount(12),[page,revision,query,category,athlete,event,year,platform,content]);
 useEffect(()=>{try{saveFeedView(window.sessionStorage,{athlete,event,query})}catch{}},[athlete,event,query]);
 useEffect(()=>{try{sessionStorage.setItem('ptti-r4-feed',JSON.stringify({...feedContext(),category,year,platform,content}))}catch{}},[category,year,platform,content]);
 useEffect(()=>{if(data&&!official&&space==='cinema'){const frame=requestAnimationFrame(()=>window.scrollTo(0,feedContext().scroll||0));return()=>cancelAnimationFrame(frame)}},[!!data,!!official]);
 function openOfficialOnDesktop(event:MouseEvent<HTMLAnchorElement>,url:string,expectedVideoId?:string){
  setFailedWatchUrl(null);
  const api=(window as any).pywebview?.api;
  void openOfficialLink(event,url,typeof api?.open_official_video==='function'?(value,videoId)=>api.open_official_video(value,videoId):undefined,expectedVideoId).then(result=>{
   if(result==='FAILED')setFailedWatchUrl(url);
  });
 }
 function retryOfficialOnDesktop(url:string){
  setFailedWatchUrl(null);
  const api=(window as any).pywebview?.api;
  if(typeof api?.open_official_video==='function'){
   void Promise.resolve(api.open_official_video(url)).then((opened:boolean)=>{if(!opened)setFailedWatchUrl(url)}).catch(()=>setFailedWatchUrl(url));
   return;
  }
  try{const opened=window.open(url,'_blank');if(opened)opened.opener=null;else setFailedWatchUrl(url)}catch{setFailedWatchUrl(url)}
 }
 async function updateFavoriteKeys(keys:string[],saved:boolean){
  if(favoriteWriteInFlight.current)return;
  favoriteWriteInFlight.current=true;favoriteEpoch.current++;setFavoriteBusy(true);
  try{const result=await persistFavoriteKeys(keys,saved,favorites);setFavorites(result.favorites);setError(result.error)}
  finally{favoriteEpoch.current++;favoriteWriteInFlight.current=false;setFavoriteBusy(false)}
 }
 function toggleVideoFavorite(video:FeedVideo,rows:FeedVideo[]){const matchId=feedMatchId(video);const saved=isFeedFavorite(video,favorites,rows);const keys=matchId?favoriteKeysForMatch(matchId,rows,favorites):[video.key];void updateFavoriteKeys(keys,!saved)}
 function switchSpace(next:GrandSpace){
  if(next===space){
   if(next==='cinema'&&(storyRoute||official)){setStoryRoute(null);setOfficial(null);requestAnimationFrame(()=>window.scrollTo(0,feedContext().scroll||0))}
   return;
  }
  spaceScroll.current[space]=space==='cinema'&&(storyRoute||official)?feedContext().scroll||0:window.scrollY;
  if(space==='cinema'){
   if(!storyRoute&&!official)rememberScroll(page);
   setOfficial(null);setStoryRoute(null);
  }
  if(next!=='cinema')setVisited(previous=>previous.includes(next)?previous:[...previous,next]);
  pendingRestore.current=spaceScroll.current[next]??0;
  setSpace(next);
 }
 const returnToWall=()=>switchSpace('cinema');
 const all=data?feedVideos(data):[];
 function renderGrand(cinema:ReactNode){return <div className="grand-experience">
  {feedMediaMode==='INTERNAL_FOUNDER_QA'?<div className="grand-nav-shell"><GrandNavigation active={space} onChange={switchSpace}/><button className="grand-review-trigger" aria-label="Founder视觉验收" aria-haspopup="dialog" aria-expanded={reviewOpen} title="Founder视觉验收" onClick={()=>{setReviewMounted(true);setReviewOpen(true)}}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M3 7h4l2-3h6l2 3h4v13H3Z"/><circle cx="12" cy="13" r="4"/></svg></button></div>:<GrandNavigation active={space} onChange={switchSpace}/>}
  {reviewMounted&&<div className="grand-review-layer" hidden={!reviewOpen}><WorkspaceFrame name="视觉验收" onBack={()=>{setReviewOpen(false);returnToWall()}}><FounderReview open={reviewOpen} onClose={()=>setReviewOpen(false)} onVisit={switchSpace}/></WorkspaceFrame></div>}
  <section key="cinema" className="grand-space" id="grand-panel-cinema" tabIndex={-1} aria-labelledby="grand-nav-cinema" hidden={space!=='cinema'}>{cinema}</section>
  {visited.includes('moments')&&<section key="moments" className="grand-space" id="grand-panel-moments" tabIndex={-1} aria-labelledby="grand-nav-moments" hidden={space!=='moments'}><WorkspaceFrame name="时刻卡片" onBack={returnToWall}><MomentCards videos={all} failedWatchUrl={failedWatchUrl} onOpenOfficial={openOfficialOnDesktop} onBack={returnToWall}/></WorkspaceFrame></section>}
  {visited.includes('pro-lab')&&<section key="pro-lab" className="grand-space" id="grand-panel-pro-lab" tabIndex={-1} aria-labelledby="grand-nav-pro-lab" hidden={space!=='pro-lab'}><WorkspaceFrame name="Pro Lab" onBack={returnToWall}><ProLab qaMoment={feedMediaMode==='INTERNAL_FOUNDER_QA'} active={space==='pro-lab'} onBack={returnToWall}/></WorkspaceFrame></section>}
  {visited.includes('arena')&&<section key="arena" className="grand-space" id="grand-panel-arena" tabIndex={-1} aria-labelledby="grand-nav-arena" hidden={space!=='arena'}><WorkspaceFrame name="Fan Arena" onBack={returnToWall}><FanArena onBack={returnToWall}/></WorkspaceFrame></section>}
 </div>}

 if(!data)return renderGrand(error
  ?<div className="video-feed feed-error-state"><Empty title={error} text="检查本机连接后重试；已保存的收藏与视频记录不会受影响。"><button className="primary" onClick={()=>{setError('');setRefreshTick(n=>n+1)}}>重试目录</button></Empty></div>
  :<Empty title="正在打开比赛视频" text="正在读取官方来源与本机视频目录。"/>);
 const activeStoryId=activeStoryMatch(storyRoute,page,revision);
 const selectedStory=activeStoryId?data.matches.find((match:any)=>match.match_id===activeStoryId):null;
 if(selectedStory&&!official)return renderGrand(<LegacyMatchStory match={selectedStory} data={data} saved={isMatchFavorite(selectedStory.match_id,all,favorites)} saving={favoriteBusy} error={error} onBack={()=>{setStoryRoute(null);requestAnimationFrame(()=>window.scrollTo(0,feedContext().scroll||0))}} onToggleSaved={()=>{const saved=isMatchFavorite(selectedStory.match_id,all,favorites);void updateFavoriteKeys(favoriteKeysForMatch(selectedStory.match_id,all,favorites),!saved)}} onPlay={videoId=>{rememberScroll(page);onPlay(videoId)}} onOpenEmbedded={source=>{rememberScroll(page);setOfficial(source)}} onOpenOfficial={openOfficialOnDesktop}/>);
 if(official){const match=data.matches.find((m:any)=>m.match_id===official.match_id);return renderGrand(<><OfficialVideoPlayer source={official} onBack={()=>setOfficial(null)}/>{match?<MatchSourcePanel match={match} data={data} onPlay={onPlay} onRefresh={async()=>{const r=await fetch('/api/video-evidence/library');if(!r.ok)throw Error('关联刷新失败');setData(await r.json())}}/>:<details><summary>核对这条来源对应的比赛</summary><p>不能按标题或文件名自动确认，不能将研究样本关联不相干的职业比赛。</p><select aria-label="核对来源比赛" value={matchChoice} onChange={e=>setMatchChoice(e.target.value)}><option value="">选择已收录比赛</option>{data.matches.map((m:any)=><option key={m.match_id} value={m.match_id}>{m.event_name} · {m.event_date} · {m.players.player_a.canonical_name_zh} / {m.players.player_b.canonical_name_zh}</option>)}</select><button disabled={!matchChoice||mappingBusy} onClick={async()=>{if(!window.confirm('已观看并核对是同一场比赛？此操作不确认录像完整性或分析许可。'))return;setMappingBusy(true);try{const r=await fetch(`/api/video-evidence/library/matches/${encodeURIComponent(matchChoice)}/online-sources`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:official.provider==='BILIBILI'?'BILIBILI':'YOUTUBE',source_id:official.video_source.source_id,title:official.title,user_confirmed_match:true})});if(!r.ok)throw Error('关联未保存');const fresh=await fetch('/api/video-evidence/library');if(!fresh.ok)throw Error('刷新失败');setData(await fresh.json());setOfficial({...official,match_id:matchChoice})}catch(e:any){setError(e.message)}finally{setMappingBusy(false)}}}>人工核对后关联</button></details>}<button onClick={onTools}>关联本地录像以使用专业复盘</button>{error&&<p role="alert">{error}</p>}</>)};
 const filtered=preferredSources(filterFeed(all,personalShelfFilters(page,{query,category,athlete,event,view:page,favorites,year,platform,content})),preference),rows=page==='feedFavorites'?uniqueFavoriteRows(filtered,favorites):filtered;
 const unavailableFavorites=page==='feedFavorites'?unavailableFavoriteKeys(all,favorites):[];
 const coverVariantByKey=new Map<string,number>(all.map((video,index)=>[video.key,index%9] as const));
 const stars=[...new Set(all.flatMap(v=>v.athletes))].map(id=>data.athletes.find((a:any)=>a.athlete_id===id)).filter(Boolean);
 const extraNames=[...new Set(all.flatMap(v=>v.athleteNames))].filter(n=>!stars.some((a:any)=>a.feed_name===n||a.canonical_name_zh===n));
 const events=[...new Set(all.map(v=>v.event).filter(name=>name&&name!=='赛事未核实'))];
 const shelves=[{title:'',items:rows}];
 return renderGrand(<div className="video-feed">
  {feedMediaMode==='INTERNAL_FOUNDER_QA'&&<div className="founder-qa-media-notice" role="note">INTERNAL QA / FOUNDER REVIEW ONLY · YouTube 远程封面预览，不代表分发许可。</div>}
  {page!=='feedFavorites'&&page!=='feedHistory'&&<div className="r4-feed-toolbar"><div className="feed-categories" aria-label="视频分类">{['全部','男单','女单','男双','女双','混双'].map(c=><button aria-pressed={category===c} className={category===c?'selected':''} key={c} onClick={()=>setCategory(c)}>{c}</button>)}</div><details><summary>筛选</summary>
  <div className="cinema-library-filters"><label>年份<select aria-label="视频年份" value={year} onChange={e=>setYear(e.target.value)}><option value="">全部年份</option>{[...new Set(all.map(v=>v.source.personal_library?.event_year??v.source.event_year).filter(Boolean))].sort().map(y=><option key={String(y)} value={String(y)}>{String(y)}</option>)}</select></label><label>赛事<select aria-label="视频赛事" value={event} onChange={e=>setEvent(e.target.value)}><option value="">全部赛事</option>{events.map(name=><option key={name}>{name}</option>)}</select></label><label>平台<select value={platform} onChange={e=>setPlatform(e.target.value)}><option value="">全部平台</option><option value="YOUTUBE">YouTube</option><option value="BILIBILI">Bilibili</option><option value="LOCAL">本地录像</option></select></label><label>内容<select value={content} onChange={e=>setContent(e.target.value)}><option value="">全部内容</option><option value="FULL_MATCH">整场（用户记录，完整性另核）</option><option value="HIGHLIGHTS">集锦</option><option value="SESSION">直播场次</option><option value="CLIP">片段</option><option value="UNKNOWN">未知</option></select></label></div>
  </details></div>}
  {page==='home'&&<div className="cinema-discovery" aria-label="比赛发现快捷入口">
   <button type="button" onClick={()=>navigate('feedFavorites')}>★ 我的收藏</button>
   <button type="button" onClick={()=>navigate('feedHistory')}>观看记录</button>
   <details><summary>赛事专题</summary><div className="cinema-discovery-options">{events.length?events.map(name=><button type="button" key={name} onClick={e=>{setEvent(name);setAthlete('');setCategory('全部');setYear('');setPlatform('');setContent('');e.currentTarget.closest('details')?.removeAttribute('open')}}>{name}</button>):<span>暂无赛事</span>}</div></details>
   <details><summary>球星专题</summary><div className="cinema-discovery-options">{stars.length?stars.map((a:any)=><button type="button" key={a.athlete_id} onClick={e=>{setAthlete(a.athlete_id);setEvent('');setCategory('全部');setYear('');setPlatform('');setContent('');e.currentTarget.closest('details')?.removeAttribute('open')}}>{a.canonical_name_zh||a.canonical_name_en}</button>):<span>暂无球星</span>}</div></details>
   {(event||athlete)&&<><span className="cinema-discovery-current" role="status">当前专题：{event||stars.find((a:any)=>a.athlete_id===athlete)?.canonical_name_zh||stars.find((a:any)=>a.athlete_id===athlete)?.canonical_name_en||athlete}</span><button type="button" onClick={()=>{setEvent('');setAthlete('')}}>清除专题</button></>}
  </div>}
  {(page==='players'||page==='home'&&category==='关注球星')&&<div className="feed-selector"><button onClick={()=>setAthlete('')} className={!athlete?'selected':''}>全部球星</button>{stars.map((a:any)=><button className={athlete===a.athlete_id?'selected':''} key={a.athlete_id} onClick={()=>setAthlete(a.athlete_id)}>{a.canonical_name_zh||a.canonical_name_en}</button>)}{extraNames.map(n=><button className={athlete===n?'selected':''} key={n} onClick={()=>setAthlete(n)}>{n}</button>)}</div>}
  {page==='professionalMatches'&&<div className="feed-selector"><button onClick={()=>setEvent('')} className={!event?'selected':''}>全部赛事</button>{events.map(n=><button className={event===n?'selected':''} key={n} onClick={()=>setEvent(n)}>{n}</button>)}</div>}
  {(page==='feedFavorites'||page==='feedHistory')&&<p className="feed-personal-note" role="note">显示全部{page==='feedFavorites'?'收藏':'本机观看记录'}；返回首页后保留原搜索和筛选。观看记录不代表已保存播放进度。</p>}
  <div className="feed-caption"><button onClick={()=>setRefreshTick(n=>n+1)}>刷新目录</button><details className="grand-legacy-entries"><summary>快捷入口</summary><div><button onClick={()=>{switchSpace('moments')}}>时刻卡片</button><button onClick={()=>{switchSpace('pro-lab')}}>Pro Lab</button><button onClick={()=>{switchSpace('arena')}}>Fan Arena</button></div></details><span>{page==='feedFavorites'?'我的收藏':page==='feedHistory'?'本机观看历史':athlete?(stars.find((a:any)=>a.athlete_id===athlete)?.canonical_name_zh||athlete)+' · 比赛视频':event||query?'视频搜索结果':'为你发现比赛'} · {rows.length} 条</span><small>{all.filter(v=>v.kind==='LOCAL').length} 份本地录像 · {all.filter(v=>v.kind==='OFFICIAL').length} 条平台来源</small></div>
  <details className="feed-evidence-summary"><summary>来源状态与观看许可</summary><p className="feed-source-status" role="status">当前在线来源：已验证内播 {rows.filter(v=>v.kind==='OFFICIAL'&&v.source.video_source?.playback_verified&&v.source.video_source?.playback_type!=='OFFICIAL_PAGE').length} · 已验证外部播放 {rows.filter(v=>v.kind==='OFFICIAL'&&v.source.video_source?.playback_verified&&v.source.video_source?.playback_type==='OFFICIAL_PAGE').length} · 已核实完整比赛 {rows.filter(v=>v.kind==='OFFICIAL'&&v.source.video_source?.is_full_match===true).length} · 允许 Vision 分析 {rows.filter(v=>v.kind==='OFFICIAL'&&v.source.video_source?.analysis_permission==='ALLOWED').length}。其余为来源线索，完整性与播放待核验。</p></details>
  {error&&<p role="alert">{error}</p>}
  {unavailableFavorites.length>0&&<p role="status">部分收藏目前无法在目录中显示；收藏记录仍保留，请稍后刷新目录。</p>}
  {shelves.map(shelf=>{const items=showShelf(shelf.items,visibleCount);return <section className="cinema-shelf" key={shelf.title}>{shelf.title&&<h2>{shelf.title}</h2>}<div className="feed-grid">{items.map(v=>{
   const watchState=v.kind==='OFFICIAL'?officialWatchState(v.source):null;
   const visibleWatchWarning=watchState&&(watchState.state==='restricted'||watchState.state==='unavailable');
   const coverVariant=coverVariantByKey.get(v.key)??0;
    const saved=isFeedFavorite(v,favorites,all);
   const round=v.source.round_label?` · ${v.source.round_label}`:'';
   return <article className="feed-video" key={v.key}>
    {v.kind==='LOCAL'?<button className="feed-watch" aria-label={`播放：${v.title}`} onClick={()=>{rememberScroll(page);fetch(`/api/video-evidence/library/videos/${v.source.video_id}/opened`,{method:'POST'}).catch(()=>{});onPlay(v.source.video_id)}}><Thumbnail video={v} coverVariant={coverVariant}/><strong>{v.title}</strong><span>{v.event}{round}</span><em className="feed-watch-cta">本机播放 ▶</em></button>:officialAction(v)==='EMBED'?<button className="feed-watch" aria-label={`在 PTTI 内打开官方播放器：${v.title}`} onClick={()=>{rememberScroll(page);setOfficial(v.source)}}><Thumbnail video={v} coverVariant={coverVariant}/><strong>{v.title}</strong>{v.thumbnailSource==='YOUTUBE_DATA_API'&&<span className="feed-thumbnail-attribution">YouTube · {v.thumbnailPublisher}</span>}<span>{v.event}{round}</span><em className="feed-watch-cta">在 PTTI 内打开官方播放器 ▶</em></button>:v.watchUrl?<a className="feed-watch" aria-label={`前往官方页面观看：${v.title}`} href={v.watchUrl} target="_blank" rel="noopener noreferrer" title={`前往官方 ${officialProviderLabel(v.source)} 页面观看`} onClick={event=>openOfficialOnDesktop(event,v.watchUrl!)}><Thumbnail video={v} external coverVariant={coverVariant}/><strong>{v.title}</strong>{v.thumbnailSource==='YOUTUBE_DATA_API'&&<span className="feed-thumbnail-attribution">YouTube · {v.thumbnailPublisher}</span>}<span>{v.event}{round}</span><em className="feed-watch-cta">前往官方 {officialProviderLabel(v.source)} 观看 ↗</em></a>:<div className="feed-watch feed-watch--unavailable" role="group"><Thumbnail video={v} coverVariant={coverVariant}/><strong>{v.title}</strong><span>{v.event}{round}</span><em className="feed-watch-cta">官方观看链接待核实</em><span className="feed-watch-evidence" role="status">来源平台、视频 ID 与官方链接未能匹配，已阻止打开。</span><button type="button" onClick={()=>setRefreshTick(n=>n+1)}>重新检查来源</button></div>}
    {visibleWatchWarning&&<p className="feed-watch-warning" role="status" data-state={watchState?.state}>{watchState?.label}</p>}
    {v.thumbnailCredit&&<a className="feed-photo-credit" href={v.thumbnailCredit.url} target="_blank" rel="noopener noreferrer">{v.thumbnailCredit.label} ↗</a>}
    <button className="feed-save" disabled={favoriteBusy} title={saved?'取消收藏':'收藏'} aria-label={(saved?'取消收藏 ':'收藏 ')+v.title} aria-pressed={saved} onClick={()=>toggleVideoFavorite(v,all)}>{saved?'★':'☆'}</button>
    <OfficialCardActions video={v} matches={data.matches} failedWatchUrl={failedWatchUrl} onRetryWatch={retryOfficialOnDesktop} onOpenStory={matchId=>{rememberScroll(page);setStoryRoute({matchId,page,revision})}}/>
    {v.kind==='OFFICIAL'&&<details className="feed-source-details"><summary>来源与播放说明</summary><p>平台：{officialProviderLabel(v.source)} · source_id：{v.source.video_source?.source_id||v.source.video_id} · 页面：{v.source.watch_page_status||'NOT_TESTED'} · 播放：{v.source.playback_status||'NOT_TESTED'}</p><p>内嵌权限：{v.source.video_source?.embed_permission||'UNKNOWN'} · 权利：{v.source.rights_status||v.source.rights||'未获站内嵌入、下载或分发许可'}</p>{watchState&&<p>状态：{watchState.label}</p>}{v.source.playback_limitation&&<p>{v.source.playback_limitation}</p>}<p>登记来源、页面核验、实际播放、内嵌和媒体展示权限彼此独立；未在本次会话核验的来源不会标为已播放。</p>{!v.watchUrl&&<p role="status">来源平台、视频 ID 与 HTTPS 地址未能匹配，已阻止打开。</p>}</details>}
   </article>
  })}</div>{shelf.items.length>items.length&&<button className="feed-load-more" onClick={()=>setVisibleCount(n=>n+12)}>显示更多 {shelf.items.length-items.length} 条</button>}</section>})}
  {data.metadata_review&&Object.values(data.metadata_review.withheld_counts as Record<string,number>).some(count=>count>0)&&<details className="feed-source-details"><summary>部分来源需要重新核验</summary>{data.metadata_review.withheld_counts.EXPIRED>0&&<p>{data.metadata_review.withheld_counts.EXPIRED} 条来源超过 30 天未复核，暂不展示。收藏记录仍保留。</p>}{['FUTURE_TIMESTAMP','INVALID_TIMESTAMP','MISSING_TIMESTAMP'].some(key=>data.metadata_review.withheld_counts[key]>0)&&<p>部分来源核验日期缺失或无效，暂不展示，等待核对。</p>}</details>}
  {!rows.length&&<Empty title={page==='feedHistory'?'还没有本机观看记录':page==='feedFavorites'?(unavailableFavorites.length?'收藏暂不可显示':'还没有收藏的比赛'):'没有找到符合条件的比赛'} text="只展示真实来源；试试全部比赛或收录自己的录像。"/>}
  <div className="feed-end">已显示 {Math.min(rows.length,visibleCount)} / {rows.length} 条真实来源，不重复填充推荐。<details><summary>来源与播放说明</summary><p>比赛封面只在对应展示权限或合规官方 API 运行数据通过门禁后显示；封面与播放授权分别判断。未实测的来源不计入可播放数量；错误 150 表示嵌入被禁止，与区域限制分开记录。本机研究录像仅限非商业研究。官方链接不授予下载或 Vision 分析权利。</p><button onClick={onTools}>本地索引与次级比赛资料</button></details></div>
 </div>);
}
function showShelf<T>(items:T[],limit:number){return items.slice(0,limit)}
