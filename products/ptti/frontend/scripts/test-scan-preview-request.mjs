import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import vm from 'node:vm';
const ts=createRequire(import.meta.url)('typescript');
const code=ts.transpileModule(readFileSync(new URL('../src/scanPreviewRequest.ts',import.meta.url),'utf8'),{
 compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}
}).outputText;
const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve()};
function harness(fetcher){
 const timers=new Map(),calls=[];let id=0;const module={exports:{}};
 vm.runInNewContext(code,{module,exports:module.exports,AbortController,
  fetch(url,options){calls.push({url,options});return fetcher(url,options)},
  setTimeout(fn){timers.set(++id,fn);return id},clearTimeout(i){timers.delete(i)}
 });
 return {read:module.exports.readScanPreviews,calls,timers,expire(){[...timers.values()].forEach(fn=>fn())}};
}
const never=()=>new Promise(()=>{});
for(const bodyHung of [false,true]){
 const h=harness(()=>bodyHung?Promise.resolve({ok:true,json:never}):never());
 let failure;const pending=h.read().catch(e=>{failure=e});await flush();h.expire();await pending;
 assert.equal(failure.name,'ScanPreviewTimeoutError');assert.equal(h.calls.length,1);
 assert(h.calls[0].options.signal.aborted);assert.equal(h.timers.size,0);
 assert.equal(h.calls[0].options.method,undefined,'Timeout reader can only GET, never rescan/register');
}
const aborted=new AbortController();aborted.abort();
const before=harness(never);await assert.rejects(before.read(aborted.signal),e=>e.name==='AbortError');
assert.equal(before.calls.length,0);assert.equal(before.timers.size,0);
const parent=new AbortController(),during=harness(never);
const pending=during.read(parent.signal);parent.abort();
await assert.rejects(pending,e=>e.name==='AbortError');assert.equal(during.timers.size,0);
assert(during.calls[0].options.signal.aborted);
for(const [status,value,pattern] of [[403,{detail:'预览读取被拒绝'},/被拒绝/],[200,{candidates:[]},/格式异常/]]){
 const h=harness(async()=>({ok:status===200,status,json:async()=>value}));
 await assert.rejects(h.read(),pattern);assert.equal(h.timers.size,0);
}
const ok=harness(async()=>({ok:true,json:async()=>[{status:'COMPLETED',candidates:[{status:'REVIEW_REQUIRED'}]}]}));
const rows=await ok.read();assert.equal(rows[0].candidates[0].status,'REVIEW_REQUIRED');
assert.equal(ok.timers.size,0);assert.equal(ok.calls[0].options.cache,'no-store');
console.log('7 negative/boundary cases PASS: fetch/body timeout, pre/during cancellation, HTTP/schema failure, complete review payload');
