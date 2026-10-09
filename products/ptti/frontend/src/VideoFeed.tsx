import {useEffect,useState} from 'react';
import {Empty} from './ui';
import {feedVideos,filterFeed,durationLabel} from './feedCatalog';
import type {FeedVideo} from './feedCatalog';
import OfficialVideoPlayer from './OfficialVideoPlayer';
import MatchSourcePanel from './MatchSourcePanel';
import {preferredSources} from './onlinePlayers';
import './video-feed.css';

function Thumbnail({video}:{video:FeedVideo}){
 const [failed,setFailed]=useState(!video.thumbnail);
 return <div className="feed-cover">{failed?<span className="feed-missing">封面暂不可用</span>:<img src={video.thumbnail} alt={video.title} loading="lazy" onError={()=>setFailed(true)}/>}<span className="feed-play" aria-hidden="true">▶</span><small>{durationLabel(video.duration)}</small></div>;
}
export default function VideoFeed({page,revision,query,onPlay,onTools,navigate}:{page:string;revision:number;query:string;onPlay:(id:string)=>void;onTools:()=>void;navigate:(page:string)=>void}){
 const [preference,setPreference]=useState('');
 const [matchChoice,setMatchChoice]=useState(''),[mappingBusy,setMappingBusy]=useState(false);
 const [data,setData]=useState<any>(null),[error,setError]=useState(''),[category,setCategory]=useState('全部'),[athlete,setAthlete]=useState(''),[event,setEvent]=useState(''),[favorites,setFavorites]=useState<string[]>([]),[official,setOfficial]=useState<any>(null);
 useEffect(()=>{let live=true;setOfficial(null);setAthlete('');setEvent('');setCategory('全部');fetch('/api/video-evidence/library').then(async r=>{if(!r.ok)throw Error('比赛视频目录暂不可用');const d=await r.json();if(live){setData(d);setFavorites(d.feed_favorites||[]);setError('')}}).catch(e=>{if(live)setError(e.message)});return()=>{live=false}},[page,revision]);
 async function bookmark(key:string){try{const r=await fetch('/api/video-evidence/library/feed/favorite',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({key,saved:!favorites.includes(key)})});if(!r.ok)throw Error('收藏未保存，请重试');const d=await r.json();setFavorites(d.favorites)}catch(e:any){setError(e.message)}}
 if(!data)return <Empty title={error||'正在打开比赛视频'} text=""/>;
 if(official){const match=data.matches.find((m:any)=>m.match_id===official.match_id);return <><OfficialVideoPlayer source={official} onBack={()=>setOfficial(null)}/>{match?<MatchSourcePanel match={match} data={data} onPlay={onPlay} onRefresh={async()=>{const r=await fetch('/api/video-evidence/library');if(!r.ok)throw Error('关联刷新失败');setData(await r.json())}}/>:<details><summary>核对这条来源对应的比赛</summary><p>不能按标题或文件名自动确认，不能将研究样本关联不相干的职业比赛。</p><select aria-label="核对来源比赛" value={matchChoice} onChange={e=>setMatchChoice(e.target.value)}><option value="">选择已收录比赛</option>{data.matches.map((m:any)=><option key={m.match_id} value={m.match_id}>{m.event_name} · {m.event_date} · {m.players.player_a.canonical_name_zh} / {m.players.player_b.canonical_name_zh}</option>)}</select><button disabled={!matchChoice||mappingBusy} onClick={async()=>{if(!window.confirm('已观看并核对是同一场比赛？此操作不确认录像完整性或分析许可。'))return;setMappingBusy(true);try{const r=await fetch(`/api/video-evidence/library/matches/${encodeURIComponent(matchChoice)}/online-sources`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:official.provider==='BILIBILI'?'BILIBILI':'YOUTUBE',source_id:official.video_source.source_id,title:official.title,user_confirmed_match:true})});if(!r.ok)throw Error('关联未保存');const fresh=await fetch('/api/video-evidence/library');if(!fresh.ok)throw Error('刷新失败');setData(await fresh.json());setOfficial({...official,match_id:matchChoice})}catch(e:any){setError(e.message)}finally{setMappingBusy(false)}}}>人工核对后关联</button></details>}<button onClick={onTools}>关联本地录像以使用专业复盘</button>{error&&<p role="alert">{error}</p>}</>};
 const all=feedVideos(data),rows=preferredSources(filterFeed(all,{query,category,athlete,event,view:page,favorites}),preference);
 const stars=[...new Set(all.flatMap(v=>v.athletes))].map(id=>data.athletes.find((a:any)=>a.athlete_id===id)).filter(Boolean);
 const extraNames=[...new Set(all.flatMap(v=>v.athleteNames))].filter(n=>!stars.some((a:any)=>a.feed_name===n||a.canonical_name_zh===n));
 const events=[...new Set(all.map(v=>v.event))];
 return <div className="video-feed">
  <div className="feed-import"><button onClick={onTools}>＋ 收录本地录像</button></div>
  <label>观看偏好 <select value={preference} onChange={e=>setPreference(e.target.value)}><option value="">已验证来源优先</option><option value="BILIBILI">B 站优先（仅已验证来源）</option><option value="YOUTUBE_OFFICIAL">YouTube 优先（仅已验证来源）</option></select></label>
  <div className="feed-sections"><button className={page==='home'?'selected':''} onClick={()=>navigate('home')}>发现</button><button className={page==='players'?'selected':''} onClick={()=>navigate('players')}>球星比赛</button><button className={page==='professionalMatches'?'selected':''} onClick={()=>navigate('professionalMatches')}>赛事回放</button></div>
  <div className="feed-categories" aria-label="视频分类">{['全部','完整比赛','男单','女单','WTT','世乒赛','奥运','关注球星','本地录像'].map(c=><button aria-pressed={category===c} className={category===c?'selected':''} key={c} onClick={()=>setCategory(c)}>{c}</button>)}</div>
  {(page==='players'||category==='关注球星')&&<div className="feed-selector"><button onClick={()=>setAthlete('')} className={!athlete?'selected':''}>全部球星</button>{stars.map((a:any)=><button className={athlete===a.athlete_id?'selected':''} key={a.athlete_id} onClick={()=>setAthlete(a.athlete_id)}>{a.canonical_name_zh||a.canonical_name_en}</button>)}{extraNames.map(n=><button className={athlete===n?'selected':''} key={n} onClick={()=>setAthlete(n)}>{n}</button>)}</div>}
  {page==='professionalMatches'&&<div className="feed-selector"><button onClick={()=>setEvent('')} className={!event?'selected':''}>全部赛事</button>{events.map(n=><button className={event===n?'selected':''} key={n} onClick={()=>setEvent(n)}>{n}</button>)}</div>}
  <div className="feed-caption"><span>{page==='feedFavorites'?'我的收藏':page==='feedHistory'?'本机观看历史':athlete?(stars.find((a:any)=>a.athlete_id===athlete)?.canonical_name_zh||athlete)+' · 比赛视频':event||query?'视频搜索结果':'为你发现比赛'} · {rows.length} 条</span><small>{all.filter(v=>v.kind==='LOCAL').length} 份本地录像 · {all.filter(v=>v.kind==='OFFICIAL').length} 条平台来源</small></div>
  <p className="feed-source-status" role="status">当前在线来源：已验证内播 {rows.filter(v=>v.kind==='OFFICIAL'&&v.source.video_source?.playback_verified&&v.source.video_source?.playback_type!=='OFFICIAL_PAGE').length} · 已验证外部播放 {rows.filter(v=>v.kind==='OFFICIAL'&&v.source.video_source?.playback_verified&&v.source.video_source?.playback_type==='OFFICIAL_PAGE').length} · 已核实完整比赛 {rows.filter(v=>v.kind==='OFFICIAL'&&v.source.video_source?.is_full_match===true).length} · 允许 Vision 分析 {rows.filter(v=>v.kind==='OFFICIAL'&&v.source.video_source?.analysis_permission==='ALLOWED').length}。其余为来源线索，完整性与播放待核验。</p>
  {error&&<p role="alert">{error}</p>}
  <div className="feed-grid">{rows.map(v=><article className="feed-video" key={v.key}>
   {v.kind==='LOCAL'||v.kind==='OFFICIAL'?<button className="feed-watch" onClick={()=>{if(v.kind==='LOCAL'){fetch(`/api/video-evidence/library/videos/${v.source.video_id}/opened`,{method:'POST'}).catch(()=>{});onPlay(v.source.video_id)}else setOfficial(v.source)}}><Thumbnail video={v}/><strong>{v.title}</strong><span>{v.event}{v.source.round_label?' · '+v.source.round_label:''}</span><em>{v.subtitle}</em></button>:<a className="feed-watch" href={v.source.source_url} target="_blank" rel="noreferrer" title="打开官方来源页面；本机播放状态尚未核验"><Thumbnail video={v}/><strong>{v.title}</strong><span>{v.event}{v.source.round_label?' · '+v.source.round_label:''}</span><em>{v.subtitle} ↗</em><small>YouTube · World Table Tennis · 完整性待核验</small></a>}
   <button className="feed-save" aria-label={(favorites.includes(v.key)?'取消收藏 ':'收藏 ')+v.title} aria-pressed={favorites.includes(v.key)} onClick={()=>bookmark(v.key)}>{favorites.includes(v.key)?'★':'☆'}</button>
  </article>)}</div>
  {!rows.length&&<Empty title={page==='feedHistory'?'还没有本机观看记录':page==='feedFavorites'?'还没有收藏的比赛':'当前分类尚无已收录视频'} text="只展示真实来源；试试全部比赛或收录自己的录像。"/>}
  <div className="feed-end">已显示全部 {rows.length} 条真实来源，不重复填充推荐。<details><summary>来源与播放说明</summary><p>官方封面由官方嵌入元数据提供。未实测的来源不计入可播放数量；错误 150 表示嵌入被禁止，与区域限制分开记录。本机研究录像仅限非商业研究。官方链接不授予下载或 Vision 分析权利。</p><button onClick={onTools}>本地索引与次级比赛资料</button></details></div>
 </div>;
}
