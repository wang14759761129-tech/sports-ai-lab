import assert from 'node:assert/strict';
import {spawn,execFileSync} from 'node:child_process';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {resolve,dirname,join} from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
import net from 'node:net';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const receiptPath=process.env.PTTI_PRIVATE_ALPHA_RECEIPT;
const playwrightPath=process.env.PTTI_PLAYWRIGHT_MODULE;
const guardPath=process.env.PTTI_QA_RESOURCE_GUARD_MODULE;
if(!receiptPath||!playwrightPath||!guardPath) throw new Error('Set receipt, Playwright module and existing QA resource-guard paths');
const receipt=JSON.parse(await readFile(receiptPath,'utf8'));
const site=join(dirname(receiptPath),'site');
const identity=JSON.parse(await readFile(join(site,'release-identity.json'),'utf8'));
assert.equal(identity.source_commit,receipt.source_commit);
const report={version:'ptti.private-alpha-browser/0.1',receipt:receipt.artifact_sha256,source_commit:identity.source_commit,status:'NOT_TESTED',samples:[],steps:[],errors:[],screenshots:[],idle_samples:[],started_at:new Date().toISOString()};
const output=join(root,'.alpha-qa','goal20-3',new Date().toISOString().replace(/[:.]/g,'-'));
await mkdir(output,{recursive:true});
const {QaResourceGuard,readWindowsMemory}=await import(pathToFileURL(guardPath).href);
const guard=new QaResourceGuard({read:readWindowsMemory,onSample:s=>report.samples.push(s),onBlock:e=>{report.status='BLOCKED';report.errors.push(e.message)},maximumMs:180000});
let server;
let browser;
function idleSeconds(){
  const code=`Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class I { [StructLayout(LayoutKind.Sequential)] public struct S { public uint size; public uint tick; } [DllImport("user32.dll")] public static extern bool GetLastInputInfo(ref S s); public static double Read() { var s=new S(); s.size=(uint)Marshal.SizeOf(s); if(!GetLastInputInfo(ref s)) throw new Exception(); return unchecked((uint)Environment.TickCount-s.tick)/1000.0; } }'; [I]::Read()`;
  const stdout=execFileSync('powershell',['-NoProfile','-Command',code],{encoding:'utf8',windowsHide:true,timeout:3000}).trim();
  const value=Number(stdout);
  if(!Number.isFinite(value)) throw Error('Idle time unavailable');
  report.idle_samples.push(value);
  return value;
}
async function availablePort(port){return new Promise(resolve=>{const socket=net.connect({host:'127.0.0.1',port});socket.once('connect',()=>{socket.destroy();resolve(false)});socket.once('error',()=>resolve(true))});}
async function stage(name,fn){await guard.checkpoint();const value=await guard.perform(fn);await guard.checkpoint();report.steps.push({name,status:'PASS'});return value;}
try{
  if(idleSeconds()<60) throw Error('BLOCKED: natural input idle under 60 seconds');
  await guard.preflight();
  if(idleSeconds()<60) throw Error('BLOCKED: natural input idle under 60 seconds before Chrome');
  if(!await availablePort(4184)) throw Error('BLOCKED: private QA port 4184 is occupied');
  server=spawn(process.execPath,[join(root,'node_modules/vite/bin/vite.js'),'preview','--host','127.0.0.1','--port','4184','--strictPort','--outDir',site],{cwd:root,windowsHide:true,stdio:'ignore'});
  let ready=false;
  for(let i=0;i<20;i++){
    await new Promise(r=>setTimeout(r,250));
    try {ready=(await fetch('http://127.0.0.1:4184/')).ok;if(ready) break;} catch { /* bounded startup */ }
  }
  assert(ready,'Own static preview did not start');
  const {chromium}=await import(pathToFileURL(playwrightPath).href);
  browser=await guard.launch(()=>chromium.launch({executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',headless:true}));
  const context=await browser.newContext({viewport:{width:1366,height:768}});
  const page=await context.newPage();
  page.on('pageerror',e=>report.errors.push(`pageerror: ${e.message}`));
  page.on('console',m=>{if(m.type()==='error')report.errors.push(`console: ${m.text()}`)});
  const catalog=JSON.parse(await readFile(join(site,'data/match-library-strict-public.json'),'utf8'));
  const star=catalog.stars.find(s=>s.athlete_id==='athlete:121558');
  const match=catalog.matches.find(m=>m.video_source_ids.length);
  const source=catalog.video_sources.find(s=>s.source_id===match.video_source_ids[0]);
  assert(star&&match&&source);
  await stage('Cinema direct and refresh',async()=>{
    await page.goto('http://127.0.0.1:4184/',{waitUntil:'domcontentloaded'});
    await page.locator('[data-fan-welcome]').waitFor();
    await page.reload({waitUntil:'domcontentloaded'});
    await page.locator('[data-fan-welcome]').waitFor();
    await page.screenshot({path:join(output,'cinema-1366.png')});report.screenshots.push('cinema-1366.png');
  });
  await stage('Star profile direct and refresh',async()=>{
    const url=`http://127.0.0.1:4184/stars/${encodeURIComponent(star.athlete_id)}`;
    await page.goto(url,{waitUntil:'domcontentloaded'});
    await page.locator('[data-fan-star-detail]').waitFor();
    assert(await page.locator('[data-fan-star-detail] img').first().evaluate(img=>img.complete&&img.naturalWidth>0),'Reviewed portrait did not load');
    await page.reload({waitUntil:'domcontentloaded'});
    await page.locator('[data-fan-star-detail]').waitFor();
    assert.equal(page.url(),url);
    await page.screenshot({path:join(output,'star-1366.png')});report.screenshots.push('star-1366.png');
  });
  await stage('Match and Watch direct and refresh',async()=>{
    await page.goto(`http://127.0.0.1:4184/matches/${encodeURIComponent(match.match_id)}`,{waitUntil:'domcontentloaded'});
    await page.locator(`[data-fan-match-detail][data-public-match-id="${match.match_id}"]`).waitFor();
    const url=`http://127.0.0.1:4184/watch/${encodeURIComponent(source.source_id)}?fanMatch=${encodeURIComponent(match.match_id)}`;
    await page.goto(url,{waitUntil:'domcontentloaded'});
    await page.locator('[data-fan-watch-detail]').waitFor();
    await page.locator(`[data-fan-watch-detail] [data-linked-match-id="${match.match_id}"]`).waitFor();
    assert(await page.locator(`a[href="${source.official_url}"]`).count()>0,'Exact official source missing');
    await page.reload({waitUntil:'domcontentloaded'});
    await page.locator('[data-fan-watch-detail]').waitFor();
    await page.locator(`[data-fan-watch-detail] [data-linked-match-id="${match.match_id}"]`).waitFor();
    await page.screenshot({path:join(output,'watch-1366.png')});report.screenshots.push('watch-1366.png');
  });
  await stage('Mobile direct profile',async()=>{
    await page.setViewportSize({width:390,height:844});
    await page.goto(`http://127.0.0.1:4184/stars/${encodeURIComponent(star.athlete_id)}`,{waitUntil:'domcontentloaded'});
    await page.locator('[data-fan-star-detail]').waitFor();
    const widths=await page.evaluate(()=>({inner:innerWidth,document:document.documentElement.scrollWidth}));
    assert(widths.document<=widths.inner,'Horizontal overflow');
    await page.screenshot({path:join(output,'star-390.png')});report.screenshots.push('star-390.png');
  });
  assert.equal(report.errors.length,0,`Browser errors: ${report.errors.join('; ')}`);
  report.status='PASS';
} catch(error){report.status=report.status==='BLOCKED'||String(error.message).startsWith('BLOCKED:')?'BLOCKED':'FAIL';report.errors.push(String(error.message));}
finally{
  await guard.dispose();
  if(server)server.kill();
  report.minimum_available_ram_gib=report.samples.length?Math.min(...report.samples.map(s=>s.gib)):null;
  report.finished_at=new Date().toISOString();
  await writeFile(join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({status:report.status,steps:report.steps.length,minimum_available_ram_gib:report.minimum_available_ram_gib,output}));
  if(report.status!=='PASS')process.exitCode=2;
}
