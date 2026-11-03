import { createServer } from 'node:http';
import { readdir } from 'node:fs/promises';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { projectBridgeMatches, consumeReadonlyProjection, hasBridgeVisualEvidence } from '../src/readonly-catalog.mjs';
import { getMatchDestination, hasVerifiedVisualPlayback } from '../src/watch-filter.mjs';
const reviewUrl = process.env.PTTI_REVIEW_URL || 'http://127.0.0.1:4174/';
const publicUrl = process.env.PTTI_PUBLIC_URL || 'http://127.0.0.1:4175/';
const bytes = await readFile(new URL('../.alpha-qa/bridge/web-internal-review.json', import.meta.url));
const payload = JSON.parse(bytes);
const rows = projectBridgeMatches(payload, { view: 'review', localReview: true });
assert.equal(rows.length,4);
assert.equal(projectBridgeMatches(payload, { view: 'public' }).length,0);
assert.deepEqual(rows.map(m => m.id), payload.matches.map(m => m.match_id));
for (const m of rows) assert.equal(m.bridge.source.matchId,m.id);
assert.equal(rows.filter(hasVerifiedVisualPlayback).length,2);
assert.equal(rows[3].routeType,'unknown');
assert.equal(rows[0].result,payload.matches[0].result, 'producer result must remain unchanged');
const corrupted=structuredClone(payload); corrupted.matches[0].result='4\uFFFD0';
assert.equal(projectBridgeMatches(corrupted,{view:'review',localReview:true})[0].bridge.resultInvalid,true);
assert.equal(getMatchDestination(rows[1]).url,payload.video_sources[1].canonical_url);
const original = JSON.stringify(payload);
const cases = {
  'wrong-version': p => { p.contract_version = 'ptti.match-media/0.1'; },
  'duplicate-match-id': p => { p.matches.push(structuredClone(p.matches[0])); },
  'duplicate-source-id': p => { p.video_sources.push(structuredClone(p.video_sources[0])); },
  'wrong-source-reference': p => { p.video_sources[0].match_id = 'not-a-match'; },
  'unsafe-url': p => { p.video_sources[0].canonical_url = 'javascript:alert(1)'; },
  'invalid-permission': p => { p.video_sources[0].rights.metadata_listing = 'YES'; },
  'local-asset': p => { p.local_video_assets = [{ locator: 'private' }]; },
};
for(const mutate of Object.values(cases)) { const p=structuredClone(payload); mutate(p); assert.throws(() => projectBridgeMatches(p,{view:'review',localReview:true})); }
for(const change of [e => { e.final_url = 'https://www.youtube.com/watch?v=wrong'; }, e => { e.time_last_seconds = 6; }, e => { e.checked_at = null; }, e => { e.checked_at = '2026-02-30'; }, e => { e.publisher_verified = null; }]) { const s=structuredClone(rows[1].bridge.source); change(s.evidence.external_video_page); assert.equal(hasBridgeVisualEvidence(s),false); }
assert.equal(JSON.stringify(payload),original);
const refused = spawnSync(process.execPath,['node_modules/vite/bin/vite.js','build','--mode','internal-review'],{encoding:'utf8'});
assert.notEqual(refused.status,0); assert((refused.stdout+refused.stderr).includes('Internal review cannot be built'));
assert.equal((await fetch(publicUrl+'__ptti/bridge.json')).status,404);
assert.equal((await fetch(publicUrl+'.alpha-qa/bridge/web-internal-review.json')).status,404);
assert.equal((await fetch(publicUrl+'data/cinema.json')).status,404);
assert.equal((await fetch(publicUrl+'scripts/fixtures/cinema-legacy.json')).status,404);
assert.equal(createHash('sha256').update(Buffer.from(await (await fetch(reviewUrl+'__ptti/bridge.json')).arrayBuffer())).digest('hex'),createHash('sha256').update(bytes).digest('hex'));
console.log('Bridge data PASS: actual producer bytes, stable match/source joins, review4/public0, result preserved/encoding negative case, no guessed ARTICLE, gates and negative versions/IDs/refs/permissions.');
const { chromium } = await import(process.env.PTTI_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PTTI_PLAYWRIGHT_MODULE).href : 'playwright');
const files = new Map();
async function collect(dir, prefix='/') { for(const item of await readdir(dir,{withFileTypes:true})) { if(item.isDirectory()) await collect(new URL(item.name+'/',dir),prefix+item.name+'/'); else files.set(prefix+item.name,await readFile(new URL(item.name,dir))); } }
await collect(new URL('../dist/',import.meta.url));
const headers=Object.fromEntries(files.get('/_headers').toString().split(/\r?\n/).filter(l=>l.includes(':')).map(l=>{const i=l.indexOf(':');return[l.slice(0,i).trim(),l.slice(i+1).trim()];}));
const server=createServer((req,res)=>{const p=new URL(req.url,'http://localhost').pathname;const name=p==='/'?'/index.html':p;const data=files.get(name);if(!data||name==='/_headers'){res.writeHead(404);res.end();return;}const content=name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.json')?'application/json':'text/html';res.writeHead(200,{...headers,'Content-Type':content});res.end(data);});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const productionUrl=`http://127.0.0.1:${server.address().port}/`;
const browser = await chromium.launch({channel:'chrome',headless:true});
try {
  const strictContext=await browser.newContext();const strictPage=await strictContext.newPage();const strictRequests=[];strictPage.on('request',r=>strictRequests.push(r.url()));
  await strictPage.goto(productionUrl+'?review=1');await strictPage.locator('.bridge-empty').waitFor();
  assert.equal(await strictPage.locator('main').getAttribute('data-catalog-mode'),'public');assert.equal(await strictPage.locator('.match-card').count(),0);
  assert(!strictRequests.some(url=>url.includes('__ptti/bridge')));assert.strictEqual((await fetch(productionUrl+'__ptti/bridge.json')).status,404);
  await strictContext.close();console.log('Actual production dist PASS: strict public0 with CSP, no review request/endpoint and no old fixture.');
  for(const width of [390,768,1440]) for(const locale of ['zh-CN','en']) {
    const context=await browser.newContext({viewport:{width,height:1000},permissions:['clipboard-read','clipboard-write']});
    await context.addInitScript(value => { if(!localStorage.getItem('ptti-web-locale')) localStorage.setItem('ptti-web-locale',value); },locale);
    const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
    const requests=[];page.on('request',r=>requests.push(r.url()));
    await page.goto(reviewUrl);await page.locator('.match-grid .match-card').nth(3).waitFor();
    assert.equal(await page.locator('main').getAttribute('data-catalog-mode'),'review');
    assert(!requests.some(u=>u.endsWith('/data/cinema.json')));
    await page.locator('#match-search').fill(locale==='zh-CN'?'樊振东':'Fan Zhendong');
    await page.waitForFunction(()=>document.querySelectorAll('.match-grid .match-card').length===2);
    await page.locator('.watch-filter-chip').nth(1).click();
    await page.waitForFunction(()=>document.querySelectorAll('.match-grid .match-card').length===1);
    await page.locator('.match-select').focus();await page.keyboard.press('Enter');await page.locator('.selected-match').waitFor();
    assert.equal(await page.locator('#selected-match-heading').evaluate(el=>el===document.activeElement),true);
    assert.equal(new URL(page.url()).searchParams.get('match'),payload.matches[1].match_id);
    assert.equal(await page.locator('.watch-source-card').getAttribute('data-source-id'),payload.video_sources[1].source_id);
    assert.equal(await page.locator('.match-actions a.button').getAttribute('href'),payload.video_sources[1].canonical_url);
    await page.locator('.detail-evidence summary').click();
    assert.equal(await page.locator('[data-permission="metadata_listing"]').innerText(),'UNKNOWN');
    assert.equal(await page.locator('[data-evidence="desktop_native_playback"]').innerText(),'NOT_TESTED');
    const link=await page.locator('#match-link').inputValue();
    await page.locator('.copy-share-text').click();
    await page.waitForFunction(()=>navigator.clipboard.readText().then(t=>t.includes('qIXmFTzXcs0')));
    assert((await page.evaluate(()=>navigator.clipboard.readText())).includes(link));
    const promise=page.waitForEvent('download');await page.locator('.download-match-card').click();const download=await promise;
    const chunks=[];for await(const c of await download.createReadStream()) chunks.push(c);const png=Buffer.concat(chunks);
    assert.equal(png.readUInt32BE(16),1200);assert.equal(png.readUInt32BE(20),675);
    await page.reload();await page.locator('.selected-match').waitFor();assert.equal(await page.locator('#match-link').inputValue(),link);
    assert.equal(await page.locator('html').getAttribute('lang'),locale);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    assert(await page.evaluate(()=>[...document.querySelectorAll('.selected-match button,.selected-match input,.selected-match a')].filter(e=>e.getBoundingClientRect().height>0).every(e=>e.getBoundingClientRect().height>=43.9)));
    await page.goto(reviewUrl+'?match='+encodeURIComponent(rows[3].id));await page.locator('.selected-match').waitFor();
    assert.equal(await page.locator('.visual-verified').count(),0);assert.equal(await page.locator('.route-unknown').count(),1);
    await page.goto(publicUrl+'?review=1&match='+encodeURIComponent(rows[1].id));await page.locator('.bridge-empty').waitFor();
    assert.equal(await page.locator('main').getAttribute('data-catalog-mode'),'public');assert.equal(await page.locator('.match-card').count(),0);
    assert.equal(await page.locator('.selected-match').count(),0);
    assert.deepEqual(errors,[]);console.log(`Bridge UI PASS: ${width}px ${locale}; real review4, stable deep link/source ID, actual canonical URL, UNKNOWN rights/native separate, PNG/copy/refresh, strict public0.`);
    await context.close();
  }
  for(const [name,mutate] of [...Object.entries(cases),['bad-json',null]]) {
    const context=await browser.newContext();const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
    const p=structuredClone(payload);if(mutate)mutate(p);let bad=true;
    await page.route('**/__ptti/bridge.json',route=>bad?route.fulfill({contentType:'application/json',body:mutate?JSON.stringify(p):'{'}):route.continue());
    await page.goto(reviewUrl);await page.locator('.state-error button').waitFor();assert.equal(await page.locator('.match-card').count(),0);
    bad=false;await page.locator('.state-error button').click();await page.locator('.match-grid .match-card').nth(3).waitFor();assert.deepEqual(errors,[]);
    console.log(`Bridge rejection/retry PASS: ${name}, no white screen or fixture fallback.`);await context.close();
  }
  const context=await browser.newContext();const page=await context.newPage();
  await page.route('**/data/web-strict-public.json',r=>r.fulfill({contentType:'application/json',body:JSON.stringify(payload)}));
  await page.goto(publicUrl);await page.locator('.bridge-empty').waitFor();assert.equal(await page.locator('.match-card').count(),0);await context.close();
  console.log('Strict public UNKNOWN permission injection PASS: zero records, no review query override.');
} finally { await browser.close(); await new Promise(resolve=>server.close(resolve)); }
