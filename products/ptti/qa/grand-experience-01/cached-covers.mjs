import assert from 'node:assert/strict';

// Real browser regression, not a fake image or permission grant. Run only on
// the isolated Founder QA Cinema with all eight registered YouTube cards.
export async function verifyCachedCovers(page){
 const results=[];
 for(let pass=0;pass<3;pass++){
  if(pass){await page.reload();await page.waitForSelector('.grand-navigation')}
  await page.waitForFunction(()=>{const nodes=[...document.querySelectorAll('[data-qa-video-id]')];return nodes.length===8&&nodes.every(n=>n.querySelector('img')?.complete)});
  const covers=await page.evaluate(()=>[...document.querySelectorAll('[data-qa-video-id]')].map(n=>({id:n.dataset.qaVideoId,state:n.dataset.coverState,width:n.querySelector('img')?.naturalWidth})));
  assert.equal(covers.length,8);
  for(const cover of covers){assert.ok(cover.width>0,`${cover.id} must really decode`);assert.equal(cover.state,'LOADED',`${cover.id}: a decoded cached cover must not remain LOADING`)}
  results.push({pass,loaded:covers.length});
 }
 return results;
}
