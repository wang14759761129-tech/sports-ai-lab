import assert from 'node:assert/strict';
import {savePlaybackMoment} from '../src/playbackMomentSave.mjs';
import {loadMomentState} from '../src/momentCards.mjs';
import {momentLocalVideo} from '../src/originalMomentRoute.mjs';
const data=new Map(),store={getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v)}, sha='a'.repeat(64),v={video_id:'one',availability_status:'AVAILABLE',hash_status:'VERIFIED',source_sha256:sha,duration_ms:1000000};
assert.equal(savePlaybackMoment(store,v,754,'关键分','备注').ok,true);const m=loadMomentState(store).moments[0];assert.equal(m.seconds,754);assert.equal(m.sourceSha256,sha);
const f={key:'local:one',kind:'LOCAL',source:v};assert.equal(momentLocalVideo(m,[f]),f);assert.equal(momentLocalVideo(m,[{...f,source:{...v,source_sha256:'b'.repeat(64)}}]),null);assert.equal(momentLocalVideo(m,[]),null);assert.equal(momentLocalVideo({...m,sourceSha256:undefined},[f]),null);assert.equal(momentLocalVideo(m,[f,f]),null);
const before=data.get('ptti-moment-cards-v1');assert.equal(savePlaybackMoment(store,{...v,hash_status:'UNKNOWN'},1,'x','').ok,false);assert.equal(savePlaybackMoment(store,v,1001,'x','').ok,false);assert.equal(data.get('ptti-moment-cards-v1'),before);
assert.equal(savePlaybackMoment({getItem:()=>'{bad',setItem:()=>{throw Error('unexpected')}},v,1,'x','').ok,false);assert.equal(savePlaybackMoment({getItem:()=>null,setItem:()=>{throw Error('disk')}},v,1,'x','').ok,false);console.log('Create, save, reload, identity and storage failure PASS');
