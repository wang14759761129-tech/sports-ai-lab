import {useEffect,useRef,useState} from 'react';

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
 const mount=useRef<HTMLDivElement>(null),[status,setStatus]=useState('等待官方播放器加载 · 尚未验证播放');
 useEffect(()=>{let live=true;let player:any;const timeout=setTimeout(()=>{if(live)setStatus('官方播放器加载超时，请检查网络或打开官方来源')},12000);
  loadOfficialAPI().then(()=>{if(!live||!mount.current)return;const child=document.createElement('div');mount.current.appendChild(child);player=new (window as any).YT.Player(child,{videoId:source.video_id,width:'100%',height:'100%',playerVars:{origin:window.location.origin,playsinline:1},events:{onReady:()=>{if(live){clearTimeout(timeout);setStatus('官方播放器已加载 · 点击播放以验证')}} ,onStateChange:(event:any)=>{if(live&&event.data===1)setStatus('本次会话已实际播放 · 官方嵌入视频')},onError:(event:any)=>{if(live){clearTimeout(timeout);setStatus(`官方播放不可用（${event.data}），请打开官方来源；不会提取视频流`)}}}})}).catch(error=>{if(live)setStatus(error.message)});
  return()=>{live=false;clearTimeout(timeout);player?.destroy();mount.current?.replaceChildren()};
 },[source.video_id]);
 return <section><button onClick={onBack}>返回比赛视频</button><h1>{source.title}</h1><div className="official-player" ref={mount}/><p role="status">{status}</p><p>来源：World Table Tennis 官方频道 · 仅官方嵌入播放，Vision 不可用</p><a href={source.source_url} target="_blank" rel="noopener noreferrer">打开官方来源</a><p className="small">时长与发布时间尚未通过 Data API 核验。视频、广告与播放控制均由官方播放器提供。</p></section>;
}
