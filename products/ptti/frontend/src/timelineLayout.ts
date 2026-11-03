import type {DemoMoment} from './demoMoments';
export function timelineMarkers(items:DemoMoment[],duration:number){
 if(!Number.isFinite(duration)||duration<=0)return [];
 const lanes:number[]=[];
 return [...items].filter(m=>Number.isFinite(m.time)&&m.time>=0&&m.time<=duration).sort((a,b)=>a.time-b.time||a.id.localeCompare(b.id)).map(m=>{const percent=m.time/duration*100;let lane=lanes.findIndex(end=>percent-end>=5);if(lane<0)lane=lanes.length;lanes[lane]=percent;return {...m,percent,lane}});
}
