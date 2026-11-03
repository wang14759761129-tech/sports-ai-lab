import assert from 'node:assert/strict';
import {momentLocalVideo} from '../src/originalMomentRoute.mjs';
import {createMoment,loadMomentState,writeMoments} from '../src/momentCards.mjs';
const mem=new Map(),storage={getItem:k=>mem.get(k)??null,setItem:(k,v)=>mem.set(k,v)};
const result=createMoment([],{videoKey:'local:one',title:'test',timestamp:'12:34',note:'',tags:[]});assert.equal(result.errors.length,0);assert.equal(writeMoments(storage,result.moments).ok,true);const moment=loadMomentState(storage).moments[0];assert.equal(moment.seconds,754);
const v={key:'local:one',kind:'LOCAL',source:{video_id:'one',availability_status:'AVAILABLE'}};assert.equal(momentLocalVideo(moment,[v]),v);assert.equal(momentLocalVideo(moment,[]),null);assert.equal(momentLocalVideo(moment,[v,v]),null);assert.equal(momentLocalVideo(moment,[{...v,source:{...v.source,video_id:'two'}}]),null);assert.equal(momentLocalVideo(moment,[{...v,source:{...v.source,availability_status:'MISSING_FILE'}}]),null);assert.equal(loadMomentState(storage).moments.length,1);
console.log('Moment storage, identity and unavailable source checks PASS');
