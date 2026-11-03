import type {FeedVideo} from './feedCatalog';

const categories:Record<string,string>={MS:'男单',WS:'女单',MD:'男双',WD:'女双',XD:'混双'};

export default function FeedCoverFallback({video,variant=0}:{video:FeedVideo;variant?:number}){
 const event=video.event&&video.event!=='赛事未核实'?video.event:'赛事信息待核实';
 const players=video.athleteNames.filter(Boolean).slice(0,4).join(' / ');
 const identity=players||video.title;
 const category=categories[video.category]||'比赛来源';
 const label=`PTTI 原创品牌占位封面，不是真实比赛画面。${event}。${identity}`;
 const safeVariant=Number.isInteger(variant)?((variant%9)+9)%9:0;
 return <div className="feed-brand-cover" role="img" aria-label={label} data-discipline={video.category} data-variant={safeVariant}>
  <span className="feed-brand-cover__topline"><span>PTTI CINEMA</span><span>{category}</span></span>
  <span className="feed-brand-cover__identity">
   <strong>{event}</strong>
   <span>{identity}</span>
  </span>
  <span className="feed-brand-cover__disclaimer">原创品牌视觉 · 非比赛截图</span>
 </div>;
}
