import assert from 'node:assert/strict';
import {downloadJsonBlob} from '../src/downloadBlob.mjs';
let revoked=[],pending,clicks=0;const env={url:{createObjectURL:()=> 'blob:test',revokeObjectURL:x=>revoked.push(x)},document:{createElement:()=>({click(){clicks++}})},defer:fn=>{pending=fn}};
downloadJsonBlob(new Blob(['{}']),'backup.json',env);assert.equal(clicks,1);assert.deepEqual(revoked,[]);pending();assert.deepEqual(revoked,['blob:test']);
revoked=[];assert.throws(()=>downloadJsonBlob(new Blob(), 'x',{...env,document:{createElement(){throw Error('blocked')}}}));assert.deepEqual(revoked,['blob:test']);
revoked=[];assert.throws(()=>downloadJsonBlob(new Blob(),'x',{...env,defer(){throw Error('timer')}}));assert.deepEqual(revoked,['blob:test']);
console.log('download URL cleanup PASS');
