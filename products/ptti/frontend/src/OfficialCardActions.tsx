import type {FeedVideo} from './feedCatalog.js';
import FeedStoryLink from './FeedStoryLink.js';
import OfficialLinkRecovery from './OfficialLinkRecovery.js';

type Props={
 video:FeedVideo;
 matches:any[];
 failedWatchUrl?:string|null;
 onRetryWatch?:(url:string)=>void;
 onOpenStory:(matchId:string)=>void;
};

function providerLabel(provider:string){return provider==='BILIBILI'?'Bilibili':'YouTube'}

export default function OfficialCardActions({video,matches,failedWatchUrl,onRetryWatch,onOpenStory}:Props){
 const platform=providerLabel(video.source.provider);
 return <div className="feed-card-actions">
  {video.kind==='OFFICIAL'&&video.watchUrl&&<div className="feed-card-source-actions">
   <span className="feed-platform-badge" aria-label={`来源平台：${platform}`}>{platform}</span>
   <OfficialLinkRecovery url={video.watchUrl} buttonLabel="复制链接"/>
   {failedWatchUrl===video.watchUrl&&<><span className="feed-card-open-failure" role="alert">系统浏览器未能打开官方页面；可重试或复制链接。</span>{onRetryWatch&&<button type="button" className="feed-watch-retry" onClick={()=>onRetryWatch(video.watchUrl!)}>重试打开</button>}</>}
  </div>}
  <FeedStoryLink video={video} matches={matches} onOpen={onOpenStory}/>
 </div>;
}
