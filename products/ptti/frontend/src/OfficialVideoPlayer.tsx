import {useEffect,useRef,useState,type MouseEvent} from 'react';
import {allowedEmbed,embeddingMode,onlineAdapter} from './onlinePlayers';
import OfficialLinkRecovery from './OfficialLinkRecovery';
import {openOfficialLink} from './officialPlayback.mjs';

let apiPromise:Promise<void>|null=null;
function loadOfficialAPI(){
 if((window as any).YT?.Player)return Promise.resolve();
 if(!apiPromise)apiPromise=new Promise((resolve,reject)=>{
  (window as any).onYouTubeIframeAPIReady=()=>resolve();
  const script=document.createElement('script');script.src='https://www.youtube.com/iframe_api';script.referrerPolicy='strict-origin-when-cross-origin';
  script.onerror=()=>{apiPromise=null;reject(Error('官方播放器暂无法连接'))};document.head.appendChild(script);
 });
 return apiPromise;
}
export default function OfficialVideoPlayer({source,onBack}:{source:any;onBack:()=>void}){
 const mount=useRef<HTMLDivElement>(null),[status,setStatus]=useState('等待官方播放器加载 · 尚未验证播放'),[handoffStatus,setHandoffStatus]=useState('');
 const embed=allowedEmbed(source);
 const httpContext=typeof window!=='undefined'&&['http:','https:'].includes(window.location.protocol);
 const iframeUrl=embed&&httpContext?(embeddingMode(source)==='BILIBILI_IFRAME'?embed:embed+(embed.includes('?')?'&':'?')+'autoplay=0&controls=1&enablejsapi=1&origin='+encodeURIComponent(window.location.origin)):null;
 function openOfficial(event:MouseEvent<HTMLAnchorElement>){
  const api=(window as any).pywebview?.api;
  void openOfficialLink(event,source.source_url,typeof api?.open_official_video==='function'?url=>api.open_official_video(url):undefined).then(result=>{
   if(result==='FAILED')setHandoffStatus('系统浏览器未能打开官方页面，请复制官方链接后手动打开');
  });
 }
 useEffect(()=>{let live=true;let player:any;setStatus('等待官方播放器加载 · 尚未验证本次播放');setHandoffStatus('');const timeout=setTimeout(()=>{if(live)setStatus('未在12秒内收到官方播放器就绪确认；请打开官方页面或复制链接')},12000);
  const mode=embeddingMode(source);
  if(!iframeUrl||mode==='UNAVAILABLE'){clearTimeout(timeout);setStatus(!httpContext?'当前页面缺少有效 HTTP(S) 来源；请通过受支持的本机服务打开，不能伪造 Referer':'请在官方平台观看 · 嵌入权限未核验');return()=>{live=false}};
  const container=mount.current;if(!container){clearTimeout(timeout);return()=>{live=false}};
  const frame=document.createElement('iframe');frame.className='official-theater-frame';frame.width='640';frame.height='360';frame.title=source.title;frame.src=iframeUrl;frame.referrerPolicy='strict-origin-when-cross-origin';frame.allow='encrypted-media; picture-in-picture; fullscreen';frame.allowFullscreen=true;container.replaceChildren(frame);
  if(mode==='BILIBILI_IFRAME'){clearTimeout(timeout);setStatus('官方嵌入许可已记录 · 实际播放待人工验证');return()=>{live=false;container.replaceChildren()}};
  loadOfficialAPI().then(()=>{if(!live)return;player=new (window as any).YT.Player(frame,{events:{onReady:()=>{if(live){clearTimeout(timeout);setStatus('官方播放器已加载 · 点击播放以验证')}} ,onStateChange:(event:any)=>{if(!live)return;if(event.data===1)setStatus('官方播放器报告正在播放 · 请核对比赛画面与时间推进；不作为 Native 或 Vision 验收');else if(event.data===2)setStatus('官方播放器已暂停');else if(event.data===0)setStatus('官方播放器报告播放结束 · 不代表已经完整核验比赛')},onError:(event:any)=>{if(live){clearTimeout(timeout);setStatus(`官方播放不可用（${event.data}），请打开官方页面或复制链接；101/150为嵌入限制，153为来源身份问题，不绕过限制`)}}}})}).catch(error=>{if(live)setStatus(error.message+'；请打开官方页面或复制链接')});
  return()=>{live=false;clearTimeout(timeout);try{player?.destroy()}finally{container.replaceChildren()}};
 },[source.video_id,iframeUrl]);
 return <section className="official-theater" aria-label="私人影院"><button onClick={onBack}>返回比赛视频</button><h1>{source.title}</h1>
 <p>来源：{onlineAdapter(source.provider)?.name||source.provider} · {source.channel||source.source_publisher||'发布者待核对'} · 仅普通观看，Vision 不可用</p>
 <div className="official-theater-actions"><a className="official-theater-source-link" href={source.source_url} target="_blank" rel="noopener noreferrer" onClick={openOfficial}>无法内嵌？在官方平台观看 ↗</a><OfficialLinkRecovery url={source.source_url}/></div>
 <div className="official-theater-viewport" ref={mount}/>
 <p role="status">{status}</p>{handoffStatus&&<p role="status">{handoffStatus}</p>}
 <details><summary>来源与播放说明</summary><p>{source.playback_limitation||'平台可能限制登录、地区或内嵌播放，请以当前官方播放器结果为准。'}</p><p>历史记录：{source.playback_status||'NOT_TESTED'} · 本次状态与历史 Native 结果彼此独立。</p><p>各版本时间轴独立；在线观看不授予封面、下载或 Vision 分析权利。</p><a href="https://www.youtube.com/t/terms" target="_blank" rel="noopener noreferrer">YouTube 条款</a> · <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">Google 隐私政策</a></details></section>;
}
