import assert from 'node:assert/strict';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
const ram=Number(spawnSync('powershell',['-NoProfile','-Command','(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'],{encoding:'utf8',windowsHide:true}).stdout.trim())/1048576;
if(!Number.isFinite(ram)||ram<2.5)throw new Error(`BLOCKED RAM ${ram.toFixed(2)} GiB < 2.5 GiB`);
const root=path.resolve(process.argv[2]); const manifest=JSON.parse(await readFile(path.join(root,'manifest.json'),'utf8'));
const base=`http://127.0.0.1:${manifest.default_port}/`;
const demo=await(await fetch(base+'__ptti/demo-review.json')).json();
const target=demo.targets.review_targets.find(t=>t.subject_role==='player'&&t.observed_rally_stage==='END_AFTER_3_4_CONTACTS');
assert.deepEqual(target.point_ids.map(id=>id.split('/').at(-1)),['p002','p004','p006']);
const qa=path.resolve('.alpha-qa/goal11-2-rc'); await mkdir(qa,{recursive:true});
const {chromium}=await import(pathToFileURL(process.env.PTTI_PLAYWRIGHT_MODULE).href);
const browser=await chromium.launch({executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',headless:true});
const actions=[],errors=[],externalRequests=[],writes=[]; const started=Date.now();
try{
 const page=await browser.newPage({viewport:{width:1366,height:768},acceptDownloads:true}); page.setDefaultTimeout(12000);
 page.on('pageerror',e=>errors.push(e.message)); page.on('dialog',d=>d.accept());
 page.on('request',r=>{if(!r.url().startsWith(base)&&!r.url().startsWith('blob:')&&!r.url().startsWith('data:'))externalRequests.push(r.url()); if(!['GET','HEAD'].includes(r.method()))writes.push(r.url());});
 await page.goto(base); await page.locator('[data-cinema-demo] .cinema-demo-n').waitFor();
 assert.equal(await page.locator('video').count(),0); assert.equal(await page.locator('main[data-catalog-mode="public"]').count(),1);
 await page.screenshot({path:path.join(qa,'rc-cinema-1366.png')}); actions.push('compiled candidate displays 19 synthetic points with public0 and no footage');
 await page.locator('[data-load-golden]').click(); await page.locator('[data-targets-match="MATCHED"]').waitFor();
 assert.match(await page.locator('[data-targets-match]').innerText(),new RegExp(manifest.synthetic_demo.canonical_input_sha256));
 await page.getByLabel('选择本机 MP4 视频',{exact:true}).setInputFiles(path.resolve('.alpha-qa/goal10-6-SYNTHETIC-TEST-PATTERN-60s.mp4'));
 await page.getByText('视频已就绪',{exact:true}).waitFor(); const video=page.locator('video'); await video.evaluate(v=>{v.muted=true;});
 const identity=await video.evaluate(v=>v.currentSrc); assert(identity.startsWith('blob:'));
 await page.locator(`[data-target-stage="${target.observed_rally_stage}"]`).click();
 for(const id of target.point_ids.slice(0,2)){
  await page.locator(`.local-video-point-row[data-point-id="${id}"] .local-video-point`).click();
  await page.locator('[data-confirm-boundary="start"]').click(); await page.locator('[data-confirm-boundary="end"]').click();
  await page.getByRole('button',{name:'保存本分',exact:true}).click();
 }
 assert.equal(await page.locator('[data-target-playable="true"]').count(),2);
 assert.equal(await page.locator(`[data-comparison-point="${target.point_ids[2]}"]`).isEnabled(),false);
 for(const [index,end]of [[0,5.4],[1,9.4]]){
  await page.locator(`[data-comparison-point="${target.point_ids[index]}"]`).click();
  await page.waitForFunction(end=>{const v=document.querySelector('video');return v?.paused&&v.currentTime>=end&&v.currentTime<end+.4;},end,{timeout:6000});
 }
 actions.push('bundled Core: confirmed p002/p004 actually replay under blob CSP; p006 refused');
 const note='我比较了p002与p004的回放操作，具体动作与技术差异需要在真实比赛录像中继续观察。';
 await page.locator('[data-comparison-note]').fill(note); const download=page.waitForEvent('download'); await page.locator('[data-export-comparison]').click();
 const exportedPath=path.join(qa,'rc-review-notes.json'); await(await download).saveAs(exportedPath);
 const exported=JSON.parse(await readFile(exportedPath,'utf8')); assert.equal(exported.user_observation.text,note); assert.deepEqual(exported.system_facts.target.point_ids,target.point_ids);
 assert.deepEqual(exported.system_facts.point_rows.map(p=>p.current_session_playback),['LOCAL_SESSION_ONLY','LOCAL_SESSION_ONLY','NOT_PLAYABLE']);
 assert.equal(exported.system_facts.current_video_session.playback_authorization_persists_in_export,false);
 const draftDownload=page.waitForEvent('download'); await page.locator('[data-export-draft]').click(); await(await draftDownload).saveAs(path.join(qa,'rc-quick-draft.json'));
 const draft=JSON.parse(await readFile(path.join(qa,'rc-quick-draft.json'),'utf8')); assert.equal(draft.contract_version,'ptti.quick-annotation/0.2'); assert.equal(draft.points.length,19);
 actions.push('actual local comparison-note JSON and v0.2 draft downloads verified');
 for(const name of ['Insight','Review']){await page.locator('.primary-nav button').filter({hasText:name}).click();assert.equal(await video.evaluate(v=>v.currentSrc),identity);}
 await page.screenshot({path:path.join(qa,'rc-review-1366.png')}); await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)); await page.screenshot({path:path.join(qa,'rc-review-390.png')});
 await page.reload(); await page.locator('[data-load-golden]').waitFor(); assert.equal(await page.locator('video').count(),0);
 await page.getByLabel('导入已有 Quick Annotation JSON 草稿',{exact:true}).setInputFiles(path.join(qa,'rc-quick-draft.json'));
 await page.locator('[data-imported-draft-summary]').waitFor(); assert.equal(await page.locator('video').count(),0);
 await page.getByRole('button',{name:'English',exact:true}).click(); await page.locator('[data-source-library] summary').first().click(); await page.locator('[data-library-empty]').waitFor();
 assert.equal(await page.locator('[data-library-source]').count(),0); actions.push('refresh/reimport retains no video authority; English strict-public library remains empty');
 assert.deepEqual(errors,[]); assert.deepEqual(externalRequests,[]); assert.deepEqual(writes,[]);
 const storage=await page.evaluate(()=>Object.keys(localStorage)); assert(storage.every(k=>k==='ptti-web-locale'),`Unexpected persisted data: ${storage}`);
 await writeFile(path.join(qa,'browser-report.json'),JSON.stringify({status:'PASS',elapsed_ms:Date.now()-started,artifact_id:manifest.artifact_id,source_san:manifest.san.commit,playback:manifest.playback.commit,ram_gib:ram,actions,point_ids:target.point_ids,session_replay_ids:target.point_ids.slice(0,2),independent_media_verified:0,errors,externalRequests,writes,storage_keys:storage,real_user_count:0},null,2));
 console.log(`Portable RC Chrome PASS: ${actions.length} groups; ${Date.now()-started}ms; real compiled runtime video, notes and exports; public0.`);
}finally{await browser.close();}
