import assert from 'node:assert/strict';
import {confirmMomentContent} from '../src/confirmMomentContent.mjs';
const sha='a'.repeat(64), good=async()=>({ok:true,json:async()=>({status:'CONTENT_MATCH_AT_CHECK',video_id:'one',sha256:sha})});
await confirmMomentContent('one',sha,good);
await assert.rejects(()=>confirmMomentContent('one','bad',good));
await assert.rejects(()=>confirmMomentContent('one',sha,async()=>({ok:false})));
await assert.rejects(()=>confirmMomentContent('one',sha,async()=>({ok:true,json:async()=>({status:'CONTENT_MATCH_AT_CHECK',video_id:'two',sha256:sha})})));
await assert.rejects(()=>confirmMomentContent('one',sha,async()=>{throw Error('offline')}));
console.log('Moment content confirmation positive and negative PASS');
