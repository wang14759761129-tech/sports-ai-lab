export type Side='A'|'B';
export type RecordEntry={pointId:string;choice:Side;result?:Side;status:'LOCKED'|'REVEALED'};
export type ArenaState={eventId:string;cursor:number;records:RecordEntry[]};
const results:Side[]=['A','B','A','A'];
export const pointId=(cursor:number)=>'point-'+(cursor+1);
export function freshArena(eventId='demo-arena-01'):ArenaState{return {eventId,cursor:0,records:[]}}
export function score(state:ArenaState){const value={A:9,B:9};state.records.filter(r=>r.status==='REVEALED').forEach(r=>{if(r.result)value[r.result]++});return value}
export function step(state:ArenaState,action:'lock'|'reveal'|'next'|'reset',choice?:Side):ArenaState{
 if(action==='reset')return freshArena(state.eventId);const n=structuredClone(state),id=pointId(n.cursor),record=n.records.find(r=>r.pointId===id);
 if(action==='lock'&&!record&&n.cursor<4&&(choice==='A'||choice==='B'))n.records.push({pointId:id,choice,status:'LOCKED'});
 if(action==='reveal'&&record?.status==='LOCKED'){record.result=results[n.cursor];record.status='REVEALED'}
 if(action==='next'&&record?.status==='REVEALED'&&n.cursor<3)n.cursor++;
 return n;
}
export function restoreArena(raw:string|null,eventId:string):ArenaState{
 if(!raw)return freshArena(eventId);const data=JSON.parse(raw);if(data.eventId!==eventId||!Number.isInteger(data.cursor)||data.cursor<0||data.cursor>3||!Array.isArray(data.records))throw Error('演示记录无效');
 let state=freshArena(eventId);
 for(let i=0;i<data.records.length;i++){const r=data.records[i];if(i>3||r.pointId!==pointId(i)||!['A','B'].includes(r.choice))throw Error('演示记录身份无效');state=step(state,'lock',r.choice);if(r.status==='REVEALED'){state=step(state,'reveal');if(state.records[i].result!==r.result)throw Error('模拟结果无效')}else if(r.status!=='LOCKED'||r.result!==undefined)throw Error('记录状态无效');if(i<data.records.length-1||data.cursor>i){if(r.status!=='REVEALED')throw Error('记录顺序无效');state=step(state,'next')}}
 if(state.cursor!==data.cursor)throw Error('回合位置无效');return state;
}
