import assert from 'node:assert/strict';import {saveReviewJSON,reviewDirty} from '../src/saveReviewJSON.mjs';
const json='{"schema":"ptti.manual-review/2"}';let calls=0;const download=()=>{calls++};
for(const status of ['saved','cancelled','error']){const result=await saveReviewJSON(json,{native:true,bridge:{save_prolab_json:async value=>{assert.equal(value,json);return {status}}},browserDownload:download});assert.equal(result.status,status)}
assert.equal((await saveReviewJSON(json,{native:true,browserDownload:download})).status,'unavailable');assert.equal(calls,0);
assert.equal((await saveReviewJSON(json,{native:true,bridge:{save_prolab_json:async()=>{throw Error('failed')}},browserDownload:download})).status,'error');
assert.equal((await saveReviewJSON(json,{native:false,browserDownload:download})).status,'requested');assert.equal(calls,1);
assert.equal((await saveReviewJSON('x'.repeat(2*1024*1024+1),{native:false,browserDownload:download})).status,'error');
assert.equal(reviewDirty([], 'empty',null),false);assert.equal(reviewDirty([1],'one',null),true);assert.equal(reviewDirty([1],'one','one'),false);assert.equal(reviewDirty([1],'two','one'),true);assert.equal(reviewDirty([], 'empty','one'),true);
console.log('PASS saved/cancelled/error/unavailable/download and dirty snapshot');
