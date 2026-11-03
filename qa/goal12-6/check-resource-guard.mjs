import assert from 'node:assert/strict';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import path from 'node:path';
import { QaResourceGuard, ResourceBlocked } from './resource-guard.mjs';
import { repo } from './prepare.mjs';
import { preserveBlockedEvidence } from './evidence.mjs';
const results=[];
async function test(name,run) {await run();results.push({name,status:'PASS',scope:'SIMULATED_RESOURCE_UNIT_TEST_NO_CHROME'});console.log('PASS '+name);}
function rig(values) {
 let pos=0,poll,closed=0,launched=0,clock=0;const evidence={completed:['prior-evidence'],samples:[],blocks:[]},waits=[];
 const guard=new QaResourceGuard({read:async()=>{const v=values[pos++];if(v instanceof Error)throw v;return v;},wait:async ms=>{waits.push(ms);clock+=ms;},every:(fn,ms)=>{assert.equal(ms,1000);poll=fn;return 1;},cancel:()=>{},now:()=>clock,onSample:s=>evidence.samples.push(s),onBlock:e=>evidence.blocks.push(e.message)});
 return {guard,evidence,waits,get reads(){return pos;},get closed(){return closed;},get launched(){return launched;},poll:()=>poll(),clock:v=>{clock=v;},create:async()=>{launched++;return {close:async()=>{closed++;}};}};
}
for(const [name,values] of [['first',[2.99]],['second',[3.1,2.99]],['third',[3.1,3.1,2.99]]]) await test(`preflight ${name} below3 never starts browser`,async()=>{const r=rig(values);await assert.rejects(r.guard.preflight(),ResourceBlocked);await assert.rejects(r.guard.launch(r.create),ResourceBlocked);assert.equal(r.launched,0);await r.guard.dispose();});
await test('exact3 accepted only after three samples spaced10 seconds apart',async()=>{const r=rig([3,3,3,3]);await r.guard.preflight();assert.equal(r.reads,3);assert.deepEqual(r.waits,[10000,10000]);assert.deepEqual(r.evidence.samples.map(s=>s.at_ms),[0,10000,20000]);await r.guard.launch(r.create);assert.equal(r.launched,1);await r.guard.dispose();assert.equal(r.closed,1);});
await test('launch without successful preflight is refused',async()=>{const r=rig([4]);await assert.rejects(r.guard.launch(r.create),ResourceBlocked);assert.equal(r.launched,0);});
await test('drop immediately before launch refuses browser',async()=>{const r=rig([3.5,3.5,3.5,2.9]);await r.guard.preflight();await assert.rejects(r.guard.launch(r.create),ResourceBlocked);assert.equal(r.launched,0);});
await test('runtime drop aborts in-flight action, saves prior evidence, closes owned only',async()=>{const r=rig([3.5,3.5,3.5,3.5,2.49]);const user={closed:false};await r.guard.preflight();await r.guard.launch(r.create);const pending=r.guard.perform(()=>new Promise(()=>{}));const rejected=assert.rejects(pending,ResourceBlocked);await r.poll();await rejected;let action=false;await assert.rejects(r.guard.perform(()=>{action=true;}),ResourceBlocked);assert.equal(action,false);await r.guard.dispose();assert.equal(r.closed,1);assert.equal(user.closed,false);assert.deepEqual(r.evidence.completed,['prior-evidence']);assert.equal(r.evidence.blocks.length,1);});
await test('exact2.5 runtime passes and next measurement error fails closed',async()=>{const r=rig([3,3,3,3,2.5,Error('reader timeout')]);await r.guard.preflight();await r.guard.launch(r.create);await r.guard.checkpoint();await assert.rejects(r.guard.checkpoint(),/measurement/);await r.guard.dispose();assert.equal(r.closed,1);});
await test('invalid measurement cannot grant startup',async()=>{const r=rig([NaN]);await assert.rejects(r.guard.preflight(),ResourceBlocked);assert.equal(r.launched,0);});
await test('resource drop during launch also closes late returned owned browser',async()=>{const r=rig([3,3,3,3,2]);await r.guard.preflight();let resolve,closed=0;const pending=r.guard.launch(()=>new Promise(r=>{resolve=r;}));while(!resolve)await new Promise(r=>setImmediate(r));const rejected=assert.rejects(pending,ResourceBlocked);await r.poll();await rejected;resolve({close:async()=>{closed++;}});await new Promise(r=>setImmediate(r));await r.guard.dispose();assert.equal(closed,1);});
await test('bounded duration fails without touching external processes',async()=>{const r=rig([3,3,3,3,3]);await r.guard.preflight();await r.guard.launch(r.create);r.clock(180001);await assert.rejects(r.guard.checkpoint(),/execution bound/);await r.guard.dispose();assert.equal(r.closed,1);});
await test('actual evidence writer preserves completed checks and downloads on guard abort',async()=>{
 const dir=path.join(repo,'.alpha-qa/goal12-7-guard-tests');await mkdir(dir,{recursive:true});
 const file=path.join(dir,'partial-evidence-unit.json');const prior={status:'NOT_TESTED',checks:[{status:'PASS'},{status:'NOT_TESTED'}],downloads:[{file:'simulated-unit-artifact-not-browser.json'}]};
 const guard=new QaResourceGuard({read:async()=>2,wait:async()=>{},onBlock:error=>preserveBlockedEvidence(file,prior,prior.checks[1],error)});
 await assert.rejects(guard.preflight(),ResourceBlocked);const stored=JSON.parse(await readFile(file));assert.equal(stored.status,'BLOCKED');assert.equal(stored.checks[0].status,'PASS');assert.equal(stored.checks[1].status,'BLOCKED');assert.deepEqual(stored.downloads,prior.downloads);await guard.dispose();
});
const out=path.join(repo,'.alpha-qa/goal12-7-guard-tests');await mkdir(out,{recursive:true});await writeFile(path.join(out,'report.json'),JSON.stringify({status:'PASS',tests:results,chrome:'NOT_TESTED',actual_browser_instances:0},null,2));console.log(`${results.length} simulated guard tests PASS; Chrome NOT_TESTED.`);
