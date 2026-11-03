import assert from 'node:assert/strict';import {readReadyTime,requestPauseSeek,isVerifiedSyntheticDigest,requireVerifiedStorage} from '../src/proLabMedia.mjs';
assert.equal(readReadyTime({readyState:1,duration:20,currentTime:0,error:null}),0);
assert.equal(readReadyTime({readyState:1,duration:20,currentTime:12.5,error:null}),12.5);
for(const bad of [null,{readyState:0,duration:20,currentTime:0},{readyState:1,duration:NaN,currentTime:0},{readyState:1,duration:20,currentTime:0,error:{}},{readyState:1,duration:20,currentTime:21}])assert.throws(()=>readReadyTime(bad),/MEDIA_NOT_READY/);
console.log('PASS media readiness: true zero preserved; missing, undecoded, invalid and error rejected');

let paused=false;const v={readyState:1,duration:20,currentTime:1,error:null,pause(){paused=true}};requestPauseSeek(v,12.5);assert.equal(paused,true);assert.equal(v.currentTime,12.5);assert.throws(()=>requestPauseSeek(v,21),/INVALID_SEEK_TARGET/);const bad={readyState:1,duration:20,get currentTime(){return 1},set currentTime(_){throw Error('SEEK_FAILED')},pause(){}};assert.throws(()=>requestPauseSeek(bad,2),/SEEK_FAILED/);assert.throws(()=>requestPauseSeek({readyState:0,duration:20,currentTime:0},2),/MEDIA_NOT_READY/);console.log('PASS seek request, invalid target, setter failure and unready media');

const digest='a'.repeat(64);assert.equal(isVerifiedSyntheticDigest(digest,digest),true);assert.equal(isVerifiedSyntheticDigest('b'.repeat(64),digest),false);assert.equal(isVerifiedSyntheticDigest('invalid',digest),false);assert.doesNotThrow(()=>requireVerifiedStorage(true,false));for(const [identity,broken] of [[false,false],[true,true],[false,true]])assert.throws(()=>requireVerifiedStorage(identity,broken),/未修改记录/);console.log('PASS media identity and fail-closed storage writes');
