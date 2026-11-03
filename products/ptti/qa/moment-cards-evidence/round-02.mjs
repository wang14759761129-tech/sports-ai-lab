const task=await taskSpace(1),page=task.page('p1');
await page.waitForSelector('.feed-video');
console.log(await page.evaluate(async()=>{
 const covers=[...document.querySelectorAll('[data-qa-video-id]')];
 for(const cover of covers){cover.scrollIntoView();const image=cover.querySelector('img');if(image){try{await image.decode()}catch{}}}
 const results=covers.map(c=>({id:c.dataset.qaVideoId,state:c.dataset.coverState,width:c.querySelector('img')?.naturalWidth??0}));
 window.scrollTo(0,0);
 return {founderMode:document.querySelector('.founder-qa-media-notice')?.textContent,results,columns:getComputedStyle(document.querySelector('.cinema-shelf .feed-grid')).gridTemplateColumns,windowWidth:innerWidth,storedMoments:localStorage.getItem('ptti-moment-cards-v1')};
}));
console.log(await page.snapshot());
