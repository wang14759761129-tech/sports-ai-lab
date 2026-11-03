import assert from 'node:assert/strict';
import {persistFavoriteKeys} from '../src/favoritePersistence.mjs';

const response = favorites => ({ok:true,json:async()=>({favorites})});
let calls=[];
const success=await persistFavoriteKeys(['match:a','match:a','official:a'],false,['match:a','official:a','match:b'],async(url,options)=>{
  calls.push({url,options});return response(calls.length===1?['official:a','match:b']:['match:b']);
});
assert.deepEqual(success,{favorites:['match:b'],error:''});
assert.equal(calls.length,2,'Duplicate keys do not duplicate writes');

for(const failure of ['rejected','lost-response','malformed','read-failed']){
  calls=[];
  const result=await persistFavoriteKeys(['match:a'],false,['match:a'],async(url,options)=>{
    calls.push({url,options});
    if(options){
      if(failure==='lost-response')throw Error('response lost after server commit');
      if(failure==='malformed')return {ok:true,json:async()=>({favorites:[42]})};
      return {ok:false};
    }
    if(failure==='read-failed')throw Error('network unavailable');
    return response(failure==='lost-response'?[]:['match:a']);
  });
  assert.deepEqual(result.favorites,failure==='lost-response'?[]:['match:a']);
  assert.ok(result.error,'Failed writes retain a visible error after reconciliation');
  assert.equal(calls.length,2,'One failed mutation triggers exactly one read, never a repeated write');
}

calls=[];
const partial=await persistFavoriteKeys(['official:a','match:a'],false,['official:a','match:a','match:b'],async(url,options)=>{
  calls.push({url,options});
  if(calls.length===1)return response(['match:a','match:b']);
  if(options)return {ok:false};
  return response(['match:a','match:b']);
});
assert.deepEqual(partial.favorites,['match:a','match:b']);
assert.ok(partial.error);
console.log('Favorite persistence behavior: 6 scenarios PASS');
