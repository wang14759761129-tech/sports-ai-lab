import {useEffect,useState} from 'react';
import rawProjection from './sprint08-cinema-projection.json?raw';
import {loadPinnedCinema} from './pinnedCinema.mjs';
import './real-catalog.css';
export default function RealMatchCatalog({query}:{query:string}){
 const [loaded,setLoaded]=useState<Awaited<ReturnType<typeof loadPinnedCinema>>|null>(null),[failed,setFailed]=useState(false);
 useEffect(()=>{let live=true;loadPinnedCinema(rawProjection).then(value=>{if(live)setLoaded(value)}).catch(()=>{if(live)setFailed(true)});return()=>{live=false}},[]);
 if(failed)return <p role="alert">赛事目录身份校验失败，暂不可显示。</p>;
 if(!loaded)return <p role="status">正在验证赛事目录身份…</p>;
 const data=loaded.projection;const sources=data.video_sources as any[];
 const matches=loaded.matches.filter((m:any)=>[m.event.name,m.round,...m.participants.map((p:any)=>p.name_en)].join(' ').toLowerCase().includes(query.trim().toLowerCase()));
 const renderSource=(s:any)=><li key={s.source_id}><strong>{s.title}</strong><span>{s.publisher||'来源未记录'} · 身份：{s.identity_status}</span><small>页面和播放未测试 · 内嵌许可未知 · 证据：{s.evidence_source_ids.join(' / ')||'未提供'}</small><a href={s.official_url} target="_blank" rel="noopener noreferrer">前往 YouTube 官方来源 ↗</a></li>;
 return <section className="real-catalog" aria-labelledby="real-catalog-title"><h1 id="real-catalog-title">真实赛事目录</h1><p>真实赛事元数据 · 官方外链 · 播放尚未验证。以下内容不进入本机演示播放器。</p><div className="real-match-grid">{matches.map((m:any)=><article key={m.match_id} className="real-match-card"><div className="real-match-poster"><small>{m.event.name}</small><strong>{m.participants.map((p:any)=>p.name_en||'姓名未记录').join(' vs ')}</strong><span>{m.round==='UNKNOWN'?'轮次未核实':m.round}</span></div><p>赛事身份：{m.match_identity_status}</p><p>证据：{m.evidence_sources.map((e:any)=>e.source_id).join(' / ')||'未提供'}</p><ul>{m.sources.map((source:any)=>renderSource(sources.find((s:any)=>s.source_id===source.source_id)))}</ul></article>)}</div>{!matches.length&&<p>没有符合搜索条件的赛事。</p>}<details><summary>赛事级来源 · 未关联具体比赛 ({sources.filter(s=>s.match_id===null).length})</summary><p>以下来源未绑定任何单场比赛或球员。</p><ul className="real-source-list">{sources.filter(s=>s.match_id===null).map(renderSource)}</ul></details></section>
}
