import assert from 'node:assert/strict';import {readReadyTime} from '../src/proLabMedia.mjs';
assert.equal(readReadyTime({readyState:1,duration:20,currentTime:0,error:null}),0);
assert.equal(readReadyTime({readyState:1,duration:20,currentTime:12.5,error:null}),12.5);
for(const bad of [null,{readyState:0,duration:20,currentTime:0},{readyState:1,duration:NaN,currentTime:0},{readyState:1,duration:20,currentTime:0,error:{}},{readyState:1,duration:20,currentTime:21}])assert.throws(()=>readReadyTime(bad),/MEDIA_NOT_READY/);
console.log('PASS media readiness: true zero preserved; missing, undecoded, invalid and error rejected');
