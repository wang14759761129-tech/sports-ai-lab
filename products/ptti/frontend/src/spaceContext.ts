import type {DemoMoment} from './demoMoments';
export type SpaceContext={sha256:string;cardId:string;momentId:string;time:number;sceneId:string;createdAt:number;momentTime?:number;momentNote?:string};
const SHA='23cd872e390f0393489f6ed3322764491c8ea3f76cfc1232852ed0da08b07da3';
export const arenaScene=(card:string)=>({ 'demo-1':'demo-arena-01','demo-2':'demo-arena-02'} as Record<string,string>)[card]||null;
export function validateReturn(c:SpaceContext,sha:string,card:string,moments:DemoMoment[],duration:number){
 if(!c||typeof c!=='object')throw Error('返回上下文缺失');
 if(!moments.some(m=>m.id===c.momentId))throw Error('来源 Moment 已删除或不属于当前赛事');
 if(c.sha256!==SHA||sha!==c.sha256||card!==c.cardId||arenaScene(card)!==c.sceneId||!moments.some(m=>m.id===c.momentId)||!Number.isFinite(c.time)||c.time<0||!Number.isFinite(duration)||c.time>duration||!Number.isFinite(c.createdAt)||Date.now()-c.createdAt>86400000||c.createdAt>Date.now()+1000)throw Error('跨空间上下文已失效，请重新选择原赛事和时刻');return c.time;
}
