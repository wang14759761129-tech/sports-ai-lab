import {useEffect,useState} from 'react';
import {canPlayConfirmedScore} from './scoreObservation';

export default function FixedScoreLinks({videoId,onJump}:{videoId:string;onJump:(row:any,play:boolean)=>void}){
 const [rows,setRows]=useState<any[]>([]),[notice,setNotice]=useState('');
 useEffect(()=>{let live=true;setRows([]);setNotice('');if(videoId)fetch('/api/video-evidence/scores?video_id='+encodeURIComponent(videoId)).then(async r=>{if(!r.ok)throw Error();const d=await r.json();if(live)setRows(d)}).catch(()=>{if(live)setNotice('比分索引暂不可用')});return()=>{live=false}},[videoId]);
 return <div className="fixed-score-links"><div className="actions">{['0:0','3:3','5:5','9:9','10:10+'].map(label=>{const value=Number(label.split(':')[0]);const found=rows.find(r=>r.video_id===videoId&&canPlayConfirmedScore(r)&&r.score_a_before===r.score_b_before&&(label==='10:10+'?r.score_a_before>=10:r.score_a_before===value));return <button key={label} title={found?'播放已确认比分片段':'尚未索引已确认的一分'} onClick={()=>found?onJump(found,true):setNotice(`${label} 尚未索引已确认的一分；可在复核工具中查看待确认观察。`)}>{label}<small>{found?'可播放':'尚未索引'}</small></button>})}</div>{notice&&<p role="status">{notice}</p>}</div>;
}
