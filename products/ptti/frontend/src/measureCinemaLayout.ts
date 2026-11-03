/** Read-only, user-triggered measurements. No application data or text is collected. */
export function measureCinemaLayout(){
 const visible=(el:Element)=>el.getClientRects().length>0&&getComputedStyle(el).visibility!=='hidden';
 const find=(selector:string)=>Array.from(document.querySelectorAll(selector)).find(visible);
 const box=(el:Element|undefined)=>{if(!el)return null;const r=el.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}};
 const shell=find('.studio-shell'),header=shell?.querySelector('.studio-topbar'),main=shell?.querySelector('.studio-main');
 const grid=find('.cinema-shelf .feed-grid');const cards=grid?Array.from(grid.querySelectorAll('.feed-video')).filter(visible):[];
 const cardBoxes=cards.map(el=>({card:box(el),cover:box(el.querySelector('.feed-cover')||undefined)}));
 const firstRow=cardBoxes.length?cardBoxes.filter(b=>Math.abs(b.card!.y-cardBoxes[0].card!.y)<2):[];
 const shellStyle=shell?getComputedStyle(shell):null,gridStyle=grid?getComputedStyle(grid):null;
 const headerBox=box(header||undefined),mainBox=box(main||undefined);
 return {schema:'ptti-layout-measurement/1',measuredAt:new Date().toISOString(),source:'LIVE_DOM_USER_TRIGGERED',viewport:{innerWidth:window.innerWidth,innerHeight:window.innerHeight,devicePixelRatio:window.devicePixelRatio},shell:{status:shell?'MEASURED':'NOT_VISIBLE',box:box(shell),display:shellStyle?.display??null,flexDirection:shellStyle?.flexDirection??null,header:headerBox,content:mainBox,observedArrangement:headerBox&&mainBox?(mainBox.y>=headerBox.y+headerBox.height-2?'VERTICAL':'SIDE_OR_OVERLAPPING'):null},wall:{status:grid?'MEASURED':'NOT_VISIBLE',box:box(grid),columnsInFirstRenderedRow:firstRow.length,computedGridTemplateColumns:gridStyle?.gridTemplateColumns??null,computedColumnGap:gridStyle?.columnGap??null,computedRowGap:gridStyle?.rowGap??null,measuredFirstRowGaps:firstRow.slice(1).map((b,i)=>b.card!.x-firstRow[i].card!.x-firstRow[i].card!.width),cards:cardBoxes.map((b,i)=>({index:i,...b,coverAspectRatio:b.cover&&b.cover.height?b.cover.width/b.cover.height:null}))},overflow:{clientWidth:document.documentElement.clientWidth,scrollWidth:document.documentElement.scrollWidth,horizontal:document.documentElement.scrollWidth>document.documentElement.clientWidth+1},player:box(find('.studio-main video')),controls:{search:box(find('.studio-search')),filters:box(find('.feed-categories')),favoriteButtons:Array.from(document.querySelectorAll('.feed-save')).filter(visible).map(box)}};
}
