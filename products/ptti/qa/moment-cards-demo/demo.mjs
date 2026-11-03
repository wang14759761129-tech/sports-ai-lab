import {createMoment,deleteMoment,formatTimestamp,loadMomentState,writeMoments,updateMoment} from '../../frontend/src/momentCards.mjs';
import {renderCards} from './render.mjs';
const storageKey='ptti-moment-cards-demo-v1';
const seeds=[
 {key:'official:0QgbtsBWZhk',title:'Wang Chuqin vs Felix Lebrun',event:'China Smash 2025',watchUrl:'https://www.youtube.com/watch?v=0QgbtsBWZhk',source:{provider:'YOUTUBE_OFFICIAL',video_id:'0QgbtsBWZhk'}},
 {key:'official:vYsJLPTEIaI',title:'Sun Yingsha vs Wang Manyu',event:'WTT Singapore 2026',watchUrl:'https://www.youtube.com/watch?v=vYsJLPTEIaI',source:{provider:'YOUTUBE_OFFICIAL',video_id:'vYsJLPTEIaI'}},
 {key:'official:BV1nb421H7jB',title:'马龙 王楚钦VS樊振东 林高远 观众视角',event:'亚锦赛 2023',watchUrl:'https://www.bilibili.com/video/BV1nb421H7jB/',source:{provider:'BILIBILI',video_id:'BV1nb421H7jB'}},
];
const $=id=>document.getElementById(id);
let initial;
try{initial=loadMomentState(window.localStorage,storageKey)}catch{initial={moments:[],writable:false,error:'本机存储不可用'}}
let moments=initial.moments,editing=null;
for(const source of seeds){const option=document.createElement('option');option.value=source.key;option.textContent=`${source.event} · ${source.title}`;$('video').append(option);}
function clear(){editing=null;for(const id of ['ts','title','note','tags'])$(id).value='';}
function persist(next){
  if(!initial.writable){$('err').textContent=initial.error;return false}
  let result;try{result=writeMoments(window.localStorage,next,storageKey)}catch{result={ok:false,error:'本机存储不可用，未保存'}}
  if(!result.ok){$('err').textContent=result.error;return false}
  moments=next;$('err').textContent='';render();return true;
}
function render(){renderCards(document,$('list'),moments,seeds,m=>{
  editing=m.id;$('video').value=m.videoKey;$('ts').value=formatTimestamp(m.seconds);$('title').value=m.title;$('note').value=m.note;$('tags').value=m.tags.join(', ');
},m=>{if(confirm('确定删除这张时刻卡片吗？')&&persist(deleteMoment(moments,m.id))&&editing===m.id)clear();});}
$('save').onclick=()=>{
  const input={videoKey:$('video').value,title:$('title').value,timestamp:$('ts').value,note:$('note').value,tags:$('tags').value};
  const result=editing?updateMoment(moments,editing,input):createMoment(moments,input);
  if(result.errors.length){$('err').textContent=result.errors.join('；');return}
  if(persist(result.moments))clear();
};
$('clear').onclick=()=>{clear();$('err').textContent=initial.error;};
$('err').textContent=initial.error;render();
