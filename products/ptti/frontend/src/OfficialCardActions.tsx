import type {FeedVideo} from './feedCatalog.js';
import FeedStoryLink from './FeedStoryLink.js';
import OfficialLinkRecovery from './OfficialLinkRecovery.js';

type Props={
 video:FeedVideo;
 matches:any[];
 failedWatchUrl?:string|null;
 onOpenStory:(matchId:string)=>void;
};

function providerLabel(provider:string){return provider==='BILIBILI'?'Bilibili':'YouTube'}

export default function OfficialCardActions({video,matches,failedWatchUrl,onOpenStory}:Props){
 const platform=providerLabel(video.source.provider);
 return <div className="feed-card-actions">
  {video.kind==='OFFICIAL'&&video.watchUrl&&<div className="feed-card-source-actions">
   <span className="feed-platform-badge" aria-label={`来源平台：${platform}`}>{platform}</span>
   <OfficialLinkRecovery url={video.watchUrl} buttonLabel="复制链接"/>
   {failedWatchUrl===video.watchUrl&&<span className="feed-card-open-failure" role="alert">系统浏览器未能打开官方页面；可复制链接后手动打开。</span>}
  </div>}
  <FeedStoryLink video={video} matches={matches} onOpen={onOpenStory}/>
 </div>;
}
