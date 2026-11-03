import {useState} from 'react';
import {Empty,PageHeader} from './ui';
import './video-discovery.css';
import OfficialVideoPlayer from './OfficialVideoPlayer';

export default function VideoDiscovery({data,onPlay,onTools,onLibrary}:{data:any;onPlay:(id:string)=>void;onTools:()=>void;onLibrary:()=>void}){
 const [official,setOfficial]=useState<any>(null);
 const [query,setQuery]=useState(''),[category,setCategory]=useState('全部'),[athlete,setAthlete]=useState('');
 const videos=data.videos.filter((v:any)=>v.availability_status==='AVAILABLE'&&(!athlete||v.athlete_ids?.includes(athlete))&&(!query||v.title.toLowerCase().includes(query.toLowerCase()))&&(category!=='最近观看'||v.last_opened_at)&&(category!=='比赛录像'||v.match_id)&&(category!=='研究素材'||v.rights_status==='RESEARCH_NONCOMMERCIAL'));
 if(official)return <OfficialVideoPlayer source={official} onBack={()=>setOfficial(null)}/>;
 return <div className="video-discovery"><PageHeader title="打开比赛，开始复盘" text="只把可访问的本机录像展示为可播放视频。比赛资料与播放权限分开保存。"><button onClick={onTools}>导入本地录像</button><button onClick={onLibrary}>比赛资料与来源</button></PageHeader>
 <div className="discovery-search"><input aria-label="搜索视频" placeholder="搜索已收录的比赛录像" value={query} onChange={e=>setQuery(e.target.value)}/><select aria-label="运动员视频" value={athlete} onChange={e=>setAthlete(e.target.value)}><option value="">全部运动员</option>{data.athletes.map((a:any)=><option key={a.athlete_id} value={a.athlete_id}>{a.canonical_name_zh||a.canonical_name_en}</option>)}</select></div>
 <div className="discovery-categories">{['全部','比赛录像','研究素材','最近观看'].map(c=><button aria-pressed={category===c} className={category===c?'primary':''} key={c} onClick={()=>setCategory(c)}>{c}</button>)}</div>
 <p className="small">当前筛选 {videos.length} 条可播放录像 · 不包含仅有资料或失去访问权限的视频</p>
 {videos.length?<div className="discovery-grid">{videos.map((v:any)=><button className="discovery-video" key={v.video_id} onClick={()=>onPlay(v.video_id)}><div className="discovery-thumbnail"><img loading="lazy" alt="录像首帧" src={`/api/video-evidence/library/videos/${v.video_id}/thumbnail`} onError={e=>{e.currentTarget.style.display="none"}}/><span aria-hidden="true">▶</span><small>{Math.floor(v.duration_ms/60000)}:{String(Math.floor(v.duration_ms/1000)%60).padStart(2,'0')}</small></div><strong>{v.title}</strong><span>{v.rights_status==='RESEARCH_NONCOMMERCIAL'?'研究素材 · 非商业使用':'本地授权录像'}</span><span>{v.match_id?'比赛关联已确认':'运动员身份尚未关联'} · {v.width} × {v.height}</span></button>)}</div>:<Empty title="当前没有可播放的录像" text="导入你有权使用的本地视频即可开始。官方赛事资料仍可查看，但不会伪装成已授权录像。"><button onClick={onTools}>导入录像</button></Empty>}
 <h2>官方完整比赛 · 嵌入播放待验证</h2><div className="discovery-grid">{(data.official_videos||[]).filter((v:any)=>(!athlete||v.athlete_ids.includes(athlete))&&(!query||v.title.toLowerCase().includes(query.toLowerCase()))).map((v:any)=><button className="discovery-video" key={v.video_id} onClick={()=>setOfficial(v)}><div className="discovery-thumbnail"><img loading="lazy" alt={v.title} src={v.thumbnail_url}/><span aria-hidden="true">▶</span></div><strong>{v.title}</strong><span>World Table Tennis · 官方来源已核验</span><span>点击尝试官方嵌入 · 不支持本地 Vision 分析</span></button>)}</div>
 <p className="privacy-note">官方视频能否播放取决于网络、地区与作者嵌入设置。未经实际播放不会计为可内播；PTTI 不下载视频。</p></div>
}
