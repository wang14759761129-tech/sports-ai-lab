import assert from 'node:assert/strict';import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';import {tmpdir} from 'node:os';import {join} from 'node:path';import {spawnSync} from 'node:child_process';import {pathToFileURL} from 'node:url';
const dir=mkdtempSync(join(tmpdir(),'ptti-demo-actions-'));
try {
 const r=spawnSync(process.execPath,['node_modules/typescript/bin/tsc','src/demoActions.ts','--target','ES2022','--module','ES2022','--lib','ES2022,DOM','--strict','--skipLibCheck','--outDir',dir],{encoding:'utf8'});assert.equal(r.status,0,r.stdout+r.stderr);writeFileSync(join(dir,'package.json'),'{"type":"module"}');
 const {createMutationGuard,fetchWithTimeout}=await import(pathToFileURL(join(dir,'demoActions.js')));const gate=createMutationGuard();
 assert.equal(gate.begin(),true);assert.equal(gate.pending,true);assert.equal(gate.begin(),false);gate.end();assert.equal(gate.pending,false);assert.equal(gate.begin(),true);gate.end();
 let abortSeen=false;await assert.rejects(fetchWithTimeout((_url,init)=>new Promise((_resolve,reject)=>{init.signal.addEventListener('abort',()=>{abortSeen=true;reject(new Error('aborted'))})}),'http://test',{},10),/请求超时/);assert.equal(abortSeen,true);
 await assert.rejects(fetchWithTimeout(()=>Promise.reject(new Error('offline')),'http://test',{},10),/offline/);
 const response=await fetchWithTimeout(()=>Promise.resolve(new Response('ok',{status:200})),'http://test');assert.equal(response.status,200);
 console.log('9 passed: pending, duplicate prevention, timeout, offline and recovery state');
} finally {rmSync(dir,{recursive:true,force:true})}
