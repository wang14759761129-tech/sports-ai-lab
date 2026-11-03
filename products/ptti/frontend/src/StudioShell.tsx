import {useState} from 'react';
import type {ReactNode} from 'react';
import './studio-shell.css';

const groups = [
  {title:'比赛与观看',items:[['home','首页','home'],['libraryTools','视频来源库','library'],['professionalMatches','比赛','match'],['players','运动员','person']]},
  {title:'专业复盘',items:[['videoEvidence','比分复盘','play'],['videoCenter','Vision','vision'],['research','研究中心','research']]},
  {title:'我的工作区',items:[['feedHistory','观看历史','history'],['feedFavorites','收藏','star'],['settings','设置','settings']]},
];
const paths:Record<string,string>={home:'M3 10 12 3l9 7v10h-6v-6H9v6H3Z',library:'M4 4h16v16H4Z M8 8h8M8 12h8M8 16h5',match:'M5 4h14v4a7 7 0 0 1-14 0Z M8 21h8M12 15v6M5 6H2v4h4M19 6h3v4h-4',person:'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-3a8 8 0 0 1 16 0v3',play:'M4 4h16v16H4Z M10 8l6 4-6 4Z',vision:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12 M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',research:'M9 3h6M10 3v6L4 19q-1 2 2 2h12q3 0 2-2L14 9V3M7 15h10',history:'M3 4v6h6M3 10a9 9 0 1 1 2 8M12 7v5l3 2',star:'m12 3 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1Z',settings:'M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8 M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1Z',menu:'M4 6h16M4 12h16M4 18h16',search:'M10 4a6 6 0 1 1 0 12 6 6 0 0 1 0-12M15 15l6 6',add:'M12 5v14M5 12h14'};
export function StudioIcon({name}:{name:string}){return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d={paths[name]||paths.play}/></svg>}

export default function StudioShell({page,navigate,query,onQueryChange,searchEnabled,buildLabel,children}:{page:string;navigate:(page:string)=>void;query:string;onQueryChange:(value:string)=>void;searchEnabled:boolean;buildLabel:string;children:ReactNode}){
  const [collapsed,setCollapsed]=useState(()=>{try{return localStorage.getItem('ptti.studio.sidebar')==='collapsed'}catch{return false}});
  const current=groups.flatMap(group=>group.items).find(([id])=>id===page)?.[1]||({playerDetail:'运动员资料',timeline:'比赛时间轴',vision:'Vision 分析',about:'关于 PTTI',demo:'开发工具'} as Record<string,string>)[page]||'比赛工作区';
  function toggle(){setCollapsed(value=>{const next=!value;try{localStorage.setItem('ptti.studio.sidebar',next?'collapsed':'expanded')}catch{/* Preference storage is optional. */}return next})}
  return <div className={`shell studio-shell${collapsed?' sidebar-collapsed':''}`}>
    <a className="studio-skip" href="#studio-main">跳到主内容</a>
    <header className="studio-topbar"><button className="studio-menu" aria-label={collapsed?'展开导航':'收起导航'} aria-expanded={!collapsed} onClick={toggle}><StudioIcon name="menu"/></button><button className="studio-brand" onClick={()=>navigate('home')} aria-label="PTTI 首页"><span className="studio-brand-mark">P</span><span>PTTI <small>DARK STUDIO</small></span></button><span className="studio-context">{current}</span>{searchEnabled&&<label className="studio-search"><StudioIcon name="search"/><input aria-label="搜索已收录比赛视频" placeholder="搜索球星、赛事、比赛视频" value={query} onChange={event=>onQueryChange(event.target.value)}/>{query&&<button aria-label="清空搜索" onClick={()=>onQueryChange('')}>×</button>}</label>}<div className="studio-top-actions"><button onClick={()=>navigate('libraryTools')}><StudioIcon name="add"/><span>收录录像</span></button><span className="studio-local">本地工作区</span></div></header>
    <aside className="studio-sidebar"><nav aria-label="PTTI 主导航">{groups.map(group=><section className="studio-nav-group" key={group.title}><h2>{group.title}</h2>{group.items.filter(([id])=>searchEnabled||!['feedHistory','feedFavorites'].includes(id)).map(([id,label,icon])=><button key={id} title={label} aria-current={page===id?'page':undefined} className={page===id?'active':''} onClick={()=>navigate(id)}><StudioIcon name={icon}/><span>{label}</span></button>)}</section>)}</nav><footer><span>{buildLabel}</span><button onClick={()=>navigate('about')}>关于 PTTI</button></footer></aside>
    <main className="studio-main" id="studio-main" tabIndex={-1}>{children}</main>
  </div>;
}
