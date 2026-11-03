import assert from 'node:assert/strict';
import http from 'node:http';
import {appendFileSync} from 'node:fs';
import path from 'node:path';
import { mkdir, readFile, writeFile, stat } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import {repo,core,hash,fileHashes} from './prepare.mjs';
import {selectCandidate,verifyCandidate,verifyBuildReceipt} from './candidate.mjs';
import {QaResourceGuard,readWindowsMemory} from './resource-guard.mjs';
import {preserveBlockedEvidence} from './evidence.mjs';
const run=process.argv.includes('--run');
if(!run) { console.log('PREPARED / NOT_TESTED. Explicit --run required; no server or browser started. See README.md.'); process.exit(0); }
const configIndex=process.argv.indexOf('--config');
const selected=await selectCandidate(configIndex<0?null:process.argv[configIndex+1]);
const {appPath:app,candidate:frozen}=selected;
const build=path.resolve(process.env.PTTI_QA_BUILD || selected.buildPath);
assert(build.startsWith(path.join(repo,'.alpha-qa')+path.sep));
const stamp=new Date().toISOString().replace(/[:.]/g,'-');
const output=path.join(selected.runRoot,stamp); await mkdir(output,{recursive:true});
const checks=['Cinema entrances','Simulated Insight and identity','Local media and confirmed boundaries','p002/p004 playback Seek switching','p006 denied','Navigation cancels and retains video session','Notes survive navigation','Actual download verified','Bilingual desktop/mobile screenshots','Export failure preserves notes'].map((name,i)=>({id:i+1,name,status:'NOT_TESTED'}));
const report={config_name:selected.name,guard:{launch_samples:3,preflight_interval_ms:10000,launch_minimum_gib:3,runtime_minimum_gib:2.5,interval_ms:1000,reader_timeout_ms:3000},status:'NOT_TESTED',frozen,core,started_at:new Date().toISOString(),checks,ram_samples:[],screenshots:[],downloads:[],events:[],page_errors:[],console_errors:[],blocked_requests:[],real_users:0,media_identity:'LOCAL_SESSION_ONLY; independent media verification=0'};
let browser,server,resourceBlock='',current=null; const started=Date.now();
const log=(type,data)=>{const event={at_ms:Date.now()-started,type,data};report.events.push(event);appendFileSync(path.join(output,'interaction.jsonl'),JSON.stringify(event)+'\n');};
const guard=new QaResourceGuard({read:readWindowsMemory,onSample:s=>{report.ram_samples.push(s);log('ram',s);},onBlock:error=>{
 resourceBlock=error.message;report.status='BLOCKED';if(current)current.status='BLOCKED';
 log('resource-block',error.message);preserveBlockedEvidence(path.join(output,'partial-report.json'),report,current,error);
}});
async function checkpoint(){await guard.checkpoint();}
async function step(id,fn) { current=checks[id-1]; await checkpoint(); log('step-start',current.name); await guard.perform(fn); await checkpoint(); current.status='PASS'; log('step-pass',current.name); current=null; }
try {
 await verifyCandidate(selected); report.qa_head=execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8',windowsHide:true}).trim();
 report.environment={node:process.version,platform:process.platform,arch:process.arch};
 await guard.preflight();
 const receipt=JSON.parse(await readFile(path.join(build,'qa-build.json'),'utf8'));

 const {verifyPinnedPlaybackCore}=await import('../../products/ptti-web/src/playback-core-pin.mjs'); const pin=verifyPinnedPlaybackCore(app); verifyBuildReceipt(selected,receipt,await fileHashes(path.join(build,'dist')),pin);
 const fixtures={}; for(const f of ['quick-input.json','targets.json']) { const bytes=await readFile(path.join(app,'scripts/fixtures/review-targets',f)); assert.equal(hash(bytes),receipt.fixtureHashes[f]); fixtures[f]=JSON.parse(bytes); }
 const targets=fixtures['targets.json']; const target=targets.review_targets.find(t=>t.subject_role==='player'&&t.observed_rally_stage==='END_AFTER_3_4_CONTACTS');
 assert.deepEqual(target.point_ids.map(id=>id.split('/').at(-1)),['p002','p004','p006']);
 assert.equal(targets.evidence_status,'SIMULATED_ONLY'); assert.equal(fixtures['quick-input.json'].points.length,19);
 report.fixture_hashes=receipt.fixtureHashes; report.canonical_input_sha256=targets.canonical_input_sha256; report.point_ids=target.point_ids;
 const media=process.env.PTTI_QA_SYNTHETIC_MP4; const mediaReceipt=JSON.parse(await readFile(process.env.PTTI_QA_MEDIA_RECEIPT,'utf8'));
 assert.equal(mediaReceipt.classification,'SYNTHETIC_TEST_PATTERN'); assert.equal(mediaReceipt.permission,'SELF_GENERATED_TEST_USE');
 assert((await stat(media)).size<20*1024*1024,'Only small synthetic test video allowed');
 const mediaBytes=await readFile(media); assert(mediaBytes.length<20*1024*1024,'Only small synthetic test video allowed'); assert.equal(hash(mediaBytes),mediaReceipt.sha256); report.media={...mediaReceipt};
 const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json'};
 server=http.createServer(async(req,res)=>{try {
  if(req.method!=='GET'||!['127.0.0.1','::ffff:127.0.0.1'].includes(req.socket.remoteAddress)) {res.writeHead(403).end();return;}
  const p=new URL(req.url,'http://127.0.0.1').pathname;
  if(p==='/__qa/identity.json') {res.setHeader('Content-Type','application/json');res.end(JSON.stringify({frozen,core}));return;}
  if(p==='/__ptti/demo-review.json') {res.setHeader('Content-Type','application/json');res.end(JSON.stringify({quick:fixtures['quick-input.json'],targets}));return;}
  if(p==='/favicon.ico'){res.writeHead(204).end();return;}
  const key=p==='/'?'index.html':p.slice(1);
  if(!Object.hasOwn(receipt.files,key)) {res.writeHead(404).end();return;}
  const bytes=await readFile(path.join(build,'dist',key)); assert.equal(hash(bytes),receipt.files[key]); res.setHeader('Content-Type',types[path.extname(key)]||'application/octet-stream');res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');res.end(bytes);
 }catch {res.writeHead(500).end();}});
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
 const base=`http://127.0.0.1:${server.address().port}/`; report.base=base;
 const {chromium}=await import(pathToFileURL(process.env.PTTI_PLAYWRIGHT_MODULE).href);
 browser=await guard.launch(()=>chromium.launch({executablePath:process.env.PTTI_CHROME_PATH||'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',headless:true}));
 const context=await browser.newContext({viewport:{width:1366,height:768},acceptDownloads:true}); const page=await context.newPage();page.setDefaultTimeout(10000);
 let observedDownloads=0;
 page.on('download',()=>{observedDownloads++;});
 page.on('request',r=>log('request',{method:r.method(),url:r.url().startsWith('blob:')?'blob:LOCAL_SESSION':r.url()}));
 page.on('pageerror',e=>report.page_errors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.console_errors.push(m.text());});
 // Never send an external request or upload. Unexpected attempts are evidence and fail the run.
 await context.route('**/*',async route=>{const r=route.request();if(r.url().startsWith(base)&&r.method()==='GET')await route.continue();else if(/^(blob:|data:)/.test(r.url()))await route.continue();else{report.blocked_requests.push({method:r.method(),url:r.url()});await route.abort();}});
 const nav=i=>page.locator('.primary-nav button').nth(i);const video=page.locator('video');
 const row=id=>page.locator(`.local-video-point-row[data-point-id="${id}"]`);
 const snap=async name=>{await page.screenshot({path:path.join(output,name),fullPage:true});report.screenshots.push(name);};
 let element,src,note='我比较了p002与p004的回放操作，具体动作与技术差异需要在真实比赛录像中继续观察。 <script>普通文本</script> **人工笔记**';
 const assertPaused=async()=>{await page.waitForFunction(()=>document.querySelector('video')?.paused===true);assert.equal(await page.locator('[data-target-cancel]').count(),0);};
 await step(1,async()=>{await page.goto(base);for(const type of ['local-video','simulated-review','match-source'])await page.locator(`[data-cinema-entry="${type}"]`).waitFor();await page.locator('.cinema-demo-n').waitFor();assert.equal(await video.count(),0);await snap('cinema-zh-1366.png');});
 await step(2,async()=>{await page.locator('[data-load-golden]').click();await page.locator('[data-targets-match="MATCHED"]').waitFor();assert.match(await page.locator('[data-targets-match]').innerText(),new RegExp(targets.canonical_input_sha256));assert.equal(await nav(1).getAttribute('aria-current'),'page');assert.equal(await video.count(),0);
 if(selected.insight) {
  const guidance=page.locator('[data-insight-media-guidance]');await guidance.waitFor();
  await page.locator('[data-targets-score]').waitFor();assert.match(await page.locator('[data-imported-draft-summary]').innerText(),/19/);
  await page.locator(`[data-target-stage="${target.observed_rally_stage}"]`).click();
  assert.equal(await page.locator('[data-target-playable="true"]').count(),0);
  for(const id of target.point_ids)assert.equal(await page.locator(`[data-comparison-point="${id}"]`).isEnabled(),false);
  const initialNote='取消选片保留模拟数据与人工观察。';await page.locator('[data-comparison-note]').fill(initialNote);
  const [cancelChooser]=await Promise.all([page.waitForEvent('filechooser'),guidance.locator('[data-load-local-media]').click()]);
  await cancelChooser.setFiles([]); // Browser empty-selection path; not an OS dialog-cancel claim.
  assert.equal(await page.locator('[data-comparison-note]').inputValue(),initialNote);assert.equal(await video.count(),0);
  assert.equal(await page.locator('[data-targets-match="MATCHED"]').count(),1);assert.match(await page.locator('[data-imported-draft-summary]').innerText(),/19/);
  log('empty-file-selection-retains-state',{points:19,video_count:0,native_dialog_cancel:'NOT_TESTED'});
  await guidance.locator('[data-return-cinema]').click();assert.equal(await nav(0).getAttribute('aria-current'),'page');
  await nav(1).click();assert.equal(await page.locator('[data-comparison-note]').inputValue(),initialNote);
  for(const locale of ['中文','English']) {
   await page.getByRole('button',{name:locale,exact:true}).click();
   assert.match(await guidance.innerText(),locale==='中文'?/当前为模拟统计演示，不包含比赛视频/:/simulated statistics demo with no match video included/);
   for(const width of [1366,390]) {await page.setViewportSize({width,height:width===390?844:768});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    for(const key of ['data-load-local-media','data-return-cinema']) {const button=guidance.locator(`[${key}]`);await button.scrollIntoViewIfNeeded();assert(await button.isVisible());const box=await button.boundingBox();assert(box&&box.width>0&&box.height>=44&&box.x>=0&&box.x+box.width<=width+1);}
    await snap(`insight-no-media-${locale==='中文'?'zh':'en'}-${width}.png`);
   }
  }
  await page.getByRole('button',{name:'中文',exact:true}).click();await page.setViewportSize({width:1366,height:768});
 }
 await snap('insight-no-media-zh.png');});
 await step(3,async()=>{if(selected.insight){const [chooser]=await Promise.all([page.waitForEvent('filechooser'),page.locator('[data-insight-media-guidance] [data-load-local-media]').click()]);await chooser.setFiles(media);log('local-media-button-selected-file','SYNTHETIC_TEST_PATTERN');}else await page.getByLabel('选择本机 MP4 视频',{exact:true}).setInputFiles(media);await page.getByText('视频已就绪',{exact:true}).waitFor();element=await video.elementHandle();src=await video.evaluate(v=>{v.muted=true;return v.currentSrc;});assert(src.startsWith('blob:'));await page.locator(`[data-target-stage="${target.observed_rally_stage}"]`).click();for(const id of target.point_ids.slice(0,2)){await row(id).locator('.local-video-point').click();for(const end of ['start','end']){const b=page.locator(`[data-confirm-boundary="${end}"]`);assert.equal(await b.getAttribute('aria-pressed'),'false');await b.click();}await page.getByRole('button',{name:'保存本分',exact:true}).click();}assert.equal(await page.locator('[data-target-playable="true"]').count(),2);});
 await step(4,async()=>{for(const [i,end] of [[0,5.4],[1,9.4],[0,5.4]]){await page.locator(`[data-comparison-point="${target.point_ids[i]}"]`).click();await page.waitForFunction(e=>{const v=document.querySelector('video');return v&&!v.paused&&v.currentTime<e;},end);await page.waitForFunction(e=>{const v=document.querySelector('video');return v?.paused&&v.currentTime>=e&&v.currentTime<e+.5;},end,{timeout:6000});log('clip-ended',target.point_ids[i]);}await video.evaluate(v=>{v.currentTime=12;});await page.waitForFunction(()=>Math.abs(document.querySelector('video').currentTime-12)<.25);});
 await step(5,async()=>{assert.equal(await page.locator(`[data-comparison-point="${target.point_ids[2]}"]`).isEnabled(),false);assert.equal(await page.locator(`[data-target-point-id="${target.point_ids[2]}"]`).getAttribute('data-target-playable'),'false');});
 await step(6,async()=>{for(const i of [0,1,2]){await page.locator(`[data-target-play="${target.observed_rally_stage}"]`).click();await page.waitForFunction(()=>!document.querySelector('video').paused);await nav(i).click();await assertPaused();if(selected.insight)await page.getByText('已暂停播放并结束连续回放，当前视频仍保留。',{exact:true}).waitFor();assert(await element.evaluate(e=>e===document.querySelector('video')));assert.equal(await video.evaluate(v=>v.currentSrc),src);assert.equal(await page.locator('[data-target-playable="true"]').count(),2);log('navigation-preserved-session',i);}});
 await step(7,async()=>{await page.locator('[data-comparison-note]').fill(note);if(selected.insight){await page.getByLabel('选择本机 MP4 视频',{exact:true}).setInputFiles([]);assert.equal(await page.locator('[data-comparison-note]').inputValue(),note);assert.equal(await video.evaluate(v=>v.currentSrc),src);assert(await element.evaluate(e=>e===document.querySelector('video')));assert.equal(await page.locator('[data-target-playable="true"]').count(),2);log('empty-selection-retains-active-session-and-note',{native_dialog_cancel:'NOT_TESTED'});}for(const i of [0,1,2]){await nav(i).click();assert.equal(await page.locator('[data-comparison-note]').inputValue(),note);}await snap('review-note-zh-1366.png');});
 await step(8,async()=>{const pending=page.waitForEvent('download');await page.locator('[data-export-comparison]').click();const d=await pending;assert.equal(await d.failure(),null);const dest=path.join(output,'actual-browser-review.json');await d.saveAs(dest);const bytes=await readFile(dest);const json=JSON.parse(bytes);assert.equal(json.user_observation.text,note);assert.equal(json.user_observation.authored_by,'USER');assert.equal(json.system_facts.analysis_identity.canonical_input_sha256,targets.canonical_input_sha256);assert.equal(json.system_facts.analysis_identity.evidence_status,'SIMULATED_ONLY');assert.deepEqual(json.system_facts.target.point_ids,target.point_ids);assert.equal(json.system_facts.target.lost_count,3);assert.deepEqual(json.system_facts.point_rows.map(p=>p.current_session_playback),['LOCAL_SESSION_ONLY','LOCAL_SESSION_ONLY','NOT_PLAYABLE']);assert.equal(json.system_facts.current_video_session.independently_verified_media_count,0);assert.equal(json.system_facts.current_video_session.playback_authorization_persists_in_export,false);report.downloads.push({file:path.basename(dest),sha256:hash(bytes),bytes:bytes.length,validation:'PASS'});});
 await step(9,async()=>{for(const locale of ['中文','English']){await page.getByRole('button',{name:locale,exact:true}).click();assert.equal(await page.getByRole('button',{name:locale,exact:true}).getAttribute('aria-pressed'),'true');if(selected.insight){await nav(1).click();assert.equal(await nav(1).getAttribute('aria-current'),'page');const panel=page.locator('[data-review-targets-panel]');await panel.waitFor({state:'visible'});assert(await panel.isVisible(),'Review Targets must be in the active Insight workspace');const playButton=panel.locator(`[data-target-play="${target.observed_rally_stage}"]`);assert(await playButton.isVisible(),'Target playback button must be visible');assert(await playButton.isEnabled(),'Target playback button must be enabled');const box=await playButton.boundingBox();assert(box&&box.width>0&&box.height>0,'Target playback button must be actionable');log('active-insight-target-control',{locale,visible:true,enabled:true,box});await playButton.click();await page.waitForFunction(()=>!document.querySelector('video').paused);await nav(0).click();await assertPaused();const expected=locale==='中文'?'已暂停播放并结束连续回放，当前视频仍保留。':'Playback is paused and continuous replay has ended. Your current video is retained.';await page.getByText(expected,{exact:true}).waitFor();log('navigation-feedback-locale',locale);}for(const width of [1366,390]){await page.setViewportSize({width,height:width===390?844:768});for(const [i,label]of [[0,'cinema'],[1,'insight'],[2,'review'],[4,'explore']]){await nav(i).click();await page.waitForFunction(index=>document.querySelectorAll('.primary-nav button')[index]?.getAttribute('aria-current')==='page',i);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await snap(`layout-${label}-${locale==='中文'?'zh':'en'}-${width}.png`);}}}await page.getByRole('button',{name:'中文',exact:true}).click();await nav(2).click();});
 await step(10,async()=>{const exportButton=page.locator('[data-export-comparison]');const downloadsBefore=observedDownloads;const videoBefore=await video.elementHandle();const sourceBefore=await video.evaluate(v=>v.currentSrc);const noteBefore=await page.locator('[data-comparison-note]').inputValue();assert.equal(await page.locator('[data-targets-match="MATCHED"]').count(),1);assert.equal(await page.locator('[data-imported-draft-summary]').innerText().then(text=>/19/.test(text)),true);assert.equal(await page.locator('[data-target-playable="true"]').count(),2);await page.evaluate(()=>{window.__qaCreateURL=URL.createObjectURL;URL.createObjectURL=()=>{throw Error('QA_INJECTED_EXPORT_FAILURE');};});try{await exportButton.click();await page.getByText('导出失败，请重试。',{exact:true}).waitFor();await page.waitForTimeout(250);assert.equal(observedDownloads,downloadsBefore,'Injected failure must not produce a browser download');assert.equal(await exportButton.isEnabled(),true,'User must be able to retry export');assert.equal(await page.locator('[data-comparison-note]').inputValue(),noteBefore);assert.equal(await page.locator('[data-targets-match="MATCHED"]').count(),1);assert.equal(await page.locator('[data-target-playable="true"]').count(),2);assert.equal(await video.evaluate(v=>v.currentSrc),sourceBefore);assert(await videoBefore.evaluate(e=>e===document.querySelector('video')));log('export-failure-preserved-state',{downloads:observedDownloads,points:19,playable:2,note_preserved:true,media_session_preserved:true});await snap('export-failure-note-retained.png');}finally{await page.evaluate(()=>{URL.createObjectURL=window.__qaCreateURL;delete window.__qaCreateURL;});}const retryPending=page.waitForEvent('download');await exportButton.click();const retry=await retryPending;assert.equal(await retry.failure(),null);const retryPath=path.join(output,'retry-after-export-failure.json');await retry.saveAs(retryPath);const retryBytes=await readFile(retryPath);const retryJson=JSON.parse(retryBytes);assert.equal(retryJson.user_observation.text,noteBefore);assert.equal(retryJson.system_facts.analysis_identity.canonical_input_sha256,targets.canonical_input_sha256);assert.equal(retryJson.system_facts.analysis_identity.evidence_status,'SIMULATED_ONLY');assert.deepEqual(retryJson.system_facts.target.point_ids,target.point_ids);assert.equal(retryJson.system_facts.current_video_session.playback_authorization_persists_in_export,false);report.downloads.push({file:path.basename(retryPath),sha256:hash(retryBytes),bytes:retryBytes.length,validation:'PASS_AFTER_INJECTED_FAILURE'});assert.equal(observedDownloads,downloadsBefore+1,'Only the explicit retry should create a download');report.export_failure_injection='URL.createObjectURL throws in page; no download emitted, error shown, note/19-point Insight/media session retained, export button remained enabled, subsequent retry produced and validated a real download.';});
 assert.deepEqual(report.page_errors,[]);assert.deepEqual(report.blocked_requests,[]);
 const keys=await page.evaluate(()=>Object.keys(localStorage));assert(keys.every(k=>k==='ptti-web-locale'));report.localStorage_keys=keys;
 await checkpoint();report.status='PASS';
}catch(e){report.status=resourceBlock||String(e.message).startsWith('BLOCKED:')?'BLOCKED':'FAIL';report.failure={step:current?.id??'preflight',message:resourceBlock||e.message,stack:e.stack};if(current)current.status=report.status;for(const c of checks)if(c.status==='NOT_TESTED'&&report.status==='BLOCKED')c.status='BLOCKED';}
finally{await guard.dispose();if(server)await new Promise(r=>server.close(r));report.elapsed_ms=Date.now()-started;report.minimum_available_ram_gib=report.ram_samples.length?Math.min(...report.ram_samples.map(s=>s.gib)):null;await writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2));await writeFile(path.join(output,'interaction.jsonl'),report.events.map(x=>JSON.stringify(x)).join('\n'));console.log(JSON.stringify({status:report.status,output,passed:checks.filter(c=>c.status==='PASS').length,total:10}));if(report.status!=='PASS')process.exitCode=2;}
