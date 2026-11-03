export type DemoMoment={id:string;time:number;note:string};
export function validateDemoIdentity(actual:string,expected:string,event:string,returnedEvent:string):void {
 if(!actual||actual!==expected||!event||event!==returnedEvent)throw Error('视频或赛事身份不一致，未加载时刻');
}
export function sortedMoments(items:DemoMoment[]):DemoMoment[]{return [...items].sort((a,b)=>a.time-b.time||a.id.localeCompare(b.id))}
export function updateMoment(items:DemoMoment[],id:string,note:string):DemoMoment[]{return sortedMoments(items.map(item=>item.id===id?{...item,note}:item))}
export function removeMoment(items:DemoMoment[],id:string):DemoMoment[]{return items.filter(item=>item.id!==id)}

export function requireDemoResponse(ok:boolean,message:string):void {if(!ok)throw Error(message)}
