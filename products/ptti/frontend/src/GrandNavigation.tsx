import type {KeyboardEvent,ReactNode} from 'react';
import './grand-experience.css';

export type GrandSpace='cinema'|'moments'|'pro-lab'|'arena';
export function NavigationVisibility({active,hasData,children}:{active:GrandSpace;hasData:boolean;children:ReactNode}){
 return <div hidden={active==='cinema'&&hasData}>{children}</div>;
}
export const GRAND_SPACES:{id:GrandSpace;label:string;description:string;index:string}[]=[
 {id:'cinema',label:'Cinema',description:'发现 · 观看',index:'01'},
 {id:'moments',label:'Moment Cards',description:'标记 · 珍藏',index:'02'},
 {id:'pro-lab',label:'Pro Lab',description:'观察 · 复盘',index:'03'},
 {id:'arena',label:'Fan Arena',description:'判断 · 挑战',index:'04'},
];
export default function GrandNavigation({active,onChange}:{active:GrandSpace;onChange:(space:GrandSpace)=>void}){
 function moveFocus(event:KeyboardEvent<HTMLElement>){
  const buttons=Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button'));
  const index=buttons.indexOf(document.activeElement as HTMLButtonElement);
  if(index<0)return;
  const next=event.key==='ArrowRight'?(index+1)%buttons.length:event.key==='ArrowLeft'?(index-1+buttons.length)%buttons.length:event.key==='Home'?0:event.key==='End'?buttons.length-1:-1;
  if(next>=0){event.preventDefault();buttons[next].focus()}
 }
 return <nav className="grand-navigation" aria-label="PTTI 四空间" onKeyDown={moveFocus}>{GRAND_SPACES.map(space=><button key={space.id} id={`grand-nav-${space.id}`} aria-label={space.label} aria-current={active===space.id?'page':undefined} aria-controls={`grand-panel-${space.id}`} onClick={()=>onChange(space.id)}><span className="grand-space-index" aria-hidden="true">{space.index}</span><span><strong>{space.label}</strong><small>{space.description}</small></span><span className="grand-active-mark" aria-hidden="true"/></button>)}</nav>;
}
