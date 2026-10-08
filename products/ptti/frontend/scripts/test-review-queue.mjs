import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';

const folder=mkdtempSync(join(tmpdir(),'ptti-review-queue-'));
try{
 const compilation=spawnSync(process.execPath,['node_modules/typescript/bin/tsc','src/reviewQueueRequests.ts',
   '--target','ES2022','--module','ES2022','--strict','--skipLibCheck','--outDir',folder],{encoding:'utf8'});
 assert.equal(compilation.status,0,compilation.stdout+compilation.stderr);
 writeFileSync(join(folder,'package.json'),'{"type":"module"}');
 const {ReviewQueueRequests,nextCandidateAfterReview,shouldHandleReviewShortcut}=await import(pathToFileURL(join(folder,'reviewQueueRequests.js')));
 const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}};
 let count=0;
 const check=async(name,fn)=>{await fn();count++;console.log(`PASS ${name}`)};
 await check('switching video discards old response',async()=>{
  const requests=new ReviewQueueRequests(),old=deferred();const applied=[];
  requests.setScope('video-A');const first=requests.load('video-A',()=>old.promise,value=>applied.push(value),assert.fail,()=>{});
  requests.setScope('video-B');await requests.load('video-B',async()=>'B',value=>applied.push(value),assert.fail,()=>{});
  old.resolve('A');assert.equal(await first,null);assert.deepEqual(applied,['B']);
 });
 await check('older page response cannot overwrite newer page',async()=>{
  const requests=new ReviewQueueRequests(),old=deferred();const applied=[];requests.setScope('same');
  const first=requests.load('same',()=>old.promise,value=>applied.push(value),assert.fail,()=>{});
  await requests.load('same',async()=>2,value=>applied.push(value),assert.fail,()=>{});
  old.resolve(1);await first;assert.deepEqual(applied,[2]);
 });
 await check('network failure remains failure, not empty successful queue',async()=>{
  const requests=new ReviewQueueRequests(),errors=[];requests.setScope('same');
  const result=await requests.load('same',async()=>{throw new Error('offline')},assert.fail,error=>errors.push(error),()=>{});
  assert.equal(result,null);assert.deepEqual(errors,['offline']);
 });
 await check('review stays on current page and selects following item',()=>{
  const previous=['31','32','33'].map(evidence_id=>({evidence_id}));
  assert.equal(nextCandidateAfterReview(previous,[previous[0],previous[2]],'32')?.evidence_id,'33');
  assert.equal(nextCandidateAfterReview(previous,previous,'32'),null);
  assert.equal(nextCandidateAfterReview(previous,[previous[0],previous[1]],'33'),null);
 });
 await check('repeated, composing and text-input shortcuts are ignored',()=>{
  const event={repeat:false,isComposing:false,altKey:false,ctrlKey:false,metaKey:false,shiftKey:false};
  assert.equal(shouldHandleReviewShortcut(event,false),true);
  for(const key of Object.keys(event))assert.equal(shouldHandleReviewShortcut({...event,[key]:true},false),false);
  assert.equal(shouldHandleReviewShortcut(event,true),false);
 });
 await check('stale completion cannot clear newer request loading state',async()=>{
  const requests=new ReviewQueueRequests(),old=deferred(),current=deferred(),loading=[];
  requests.setScope('same');
  const first=requests.load('same',()=>old.promise,()=>{},assert.fail,value=>loading.push(value));
  const second=requests.load('same',()=>current.promise,()=>{},assert.fail,value=>loading.push(value));
  old.resolve(1);await first;assert.deepEqual(loading,[true,true]);
  current.resolve(2);await second;assert.deepEqual(loading,[true,true,false]);
 });
 console.log(`${count} passed, 0 failed`);
}finally{rmSync(folder,{recursive:true,force:true})}
