import assert from 'node:assert/strict';
import {readProgress,writeProgress,playbackState,resumeDecision,guardedPlay,timelinePosition,recentProgress,removeProgress} from '../src/localPlayback.mjs';
const map=new Map(),storage={getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,v)};
const a='sha256-chunks-v1:'+'a'.repeat(64),b='sha256-chunks-v1:'+'b'.repeat(64);
assert.equal(readProgress(storage,a,20),null);writeProgress(storage,a,12.5,20);assert.equal(readProgress(storage,a,20),12.5);assert.equal(readProgress(storage,b,20),null);
assert.throws(()=>readProgress(storage,a,10));assert.throws(()=>writeProgress(storage,a,21,20));assert.throws(()=>writeProgress(storage,'match:foo',1,20));
const before=map.get('ptti.local-video-progress/1');assert.throws(()=>writeProgress({...storage,setItem(){throw Error('quota')}},a,2,20));assert.equal(map.get('ptti.local-video-progress/1'),before);
map.set('ptti.local-video-progress/1',JSON.stringify({schema:1,entries:{[a]:{seconds:99,duration:20}}})); const damaged=map.get('ptti.local-video-progress/1');assert.throws(()=>writeProgress(storage,a,1,20));assert.equal(map.get('ptti.local-video-progress/1'),damaged);
map.set('ptti.local-video-progress/1','');assert.throws(()=>readProgress(storage,a,20));assert.throws(()=>writeProgress(storage,a,1,20));assert.equal(map.get('ptti.local-video-progress/1'),'');
for(const invalid of [null,false,0,[],{seconds:0,duration:0}]){map.set('ptti.local-video-progress/1',JSON.stringify({schema:1,entries:{[a]:invalid}}));const original=map.get('ptti.local-video-progress/1');assert.throws(()=>readProgress(storage,a,20));assert.throws(()=>writeProgress(storage,a,1,20));assert.equal(map.get('ptti.local-video-progress/1'),original)}
assert.deepEqual(resumeDecision(8,20,false),{action:'RESTORE',seconds:8});assert.deepEqual(resumeDecision(8,20,true),{action:'PRESERVE_CURRENT'});assert.deepEqual(resumeDecision(20,20,false),{action:'NO_RESTORE'});assert.deepEqual(resumeDecision(null,20,false),{action:'NO_RESTORE'});
assert.equal(playbackState(null),'idle');assert.equal(playbackState({readyState:0}),'loading');assert.equal(playbackState({readyState:1,paused:true,currentTime:0}),'ready');assert.equal(playbackState({readyState:2,paused:false}),'playing');assert.equal(playbackState({readyState:2,paused:true,currentTime:2}),'paused');assert.equal(playbackState({readyState:2,ended:true}),'ended');assert.equal(playbackState({error:{}}),'error');assert.equal(playbackState(null,true),'blocked');
console.log('local playback contract PASS');

let resolvePlay;let current=true;let pauses=0;const delayed={play:()=>new Promise(resolve=>{resolvePlay=resolve}),pause:()=>{pauses++}};
const pending=guardedPlay(delayed,()=>current);current=false;resolvePlay();assert.equal(await pending,'inactive');assert.equal(pauses,1);
assert.equal(await guardedPlay({play:()=>Promise.reject(Error('blocked')),pause(){}},()=>true),'blocked');
assert.equal(await guardedPlay({play:()=>{throw Error('blocked')},pause(){}},()=>true),'blocked');
assert.equal(await guardedPlay({play:()=>Promise.resolve(),pause(){}},()=>true),'playing');
console.log('delayed playback release PASS (mock media)');

assert.equal(timelinePosition(0,12),0);assert.equal(timelinePosition(6,12),50);assert.equal(timelinePosition(12,12),100);assert.throws(()=>timelinePosition(13,12));assert.throws(()=>timelinePosition(0,0));console.log('timeline bounds PASS');

const h=new Map(),hs={getItem:k=>h.get(k)??null,setItem:(k,v)=>h.set(k,v)};writeProgress(hs,a,3,20,'C:\\private\\clip.mp4');writeProgress(hs,b,4,20,'clip-b.mp4');assert.equal(recentProgress(hs).length,2);assert.equal(recentProgress(hs).find(x=>x.id===a).displayName,'clip.mp4');assert.ok(!h.get('ptti.local-video-progress/1').includes('private'));assert.throws(()=>recentProgress(hs,0));console.log('local history identity and filename boundary PASS');

assert.equal(removeProgress(hs,a),true);assert.equal(recentProgress(hs).length,1);assert.equal(recentProgress(hs)[0].id,b);assert.equal(removeProgress(hs,a),false);assert.throws(()=>removeProgress(hs,'bad'));console.log('history deletion leaves other video intact PASS');
