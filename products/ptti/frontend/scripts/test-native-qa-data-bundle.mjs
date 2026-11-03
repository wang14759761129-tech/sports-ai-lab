import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
globalThis.crypto??=webcrypto;
const {createMatch}=await import('../src/fanArenaEngine.mjs');
const {FAN_ARENA_STORAGE_KEY}=await import('../src/fanArenaEngine.mjs');
const {MOMENT_STORAGE_KEY}=await import('../src/momentCards.mjs');
const {PRO_LAB_STORAGE_KEY}=await import('../src/proLabNotes.mjs');
const {createNativeQaBundle,importNativeQaBundle,validateNativeQaBundle}=await import('../src/nativeQaDataBundle.mjs');
class MemoryStorage{
 constructor(seed={}){this.values=new Map(Object.entries(seed))}
 getItem(key){return this.values.has(key)?this.values.get(key):null}
 setItem(key,value){this.values.set(key,String(value))}
 removeItem(key){this.values.delete(key)}
}
const arena={match:createMatch(1234),predictions:[],history:[]};
const source=new MemoryStorage({[MOMENT_STORAGE_KEY]:'[]',[PRO_LAB_STORAGE_KEY]:'[]',[FAN_ARENA_STORAGE_KEY]:JSON.stringify(arena)});
const bundle=await createNativeQaBundle({storage:source,favorites:['match:qa-match'],sourceCommit:'a'.repeat(40),now:0});
assert.equal(await validateNativeQaBundle(JSON.parse(JSON.stringify(bundle))),true);
assert.equal(JSON.stringify(bundle).includes('videoBytes'),false);
assert.equal(JSON.stringify(bundle).includes('cookie'),false);
const destination=new MemoryStorage();let favorites=[];
const request=async(path,options={})=>{
 if(path==='/api/video-evidence/library')return {ok:true,json:async()=>({feed_favorites:favorites})};
 assert.equal(path,'/api/video-evidence/library/feed/favorite');
 const value=JSON.parse(options.body);favorites=value.saved?[...new Set([...favorites,value.key])]:favorites.filter(key=>key!==value.key);
 return {ok:true,json:async()=>({favorites})};
};
const imported=await importNativeQaBundle(bundle,{storage:destination,request});
assert.equal(imported.ok,true);
assert.equal(destination.getItem(FAN_ARENA_STORAGE_KEY),source.getItem(FAN_ARENA_STORAGE_KEY));
assert.deepEqual(favorites,['match:qa-match']);
const blocked=await importNativeQaBundle(bundle,{storage:destination,request});
assert.equal(blocked.ok,false,'restore must never overwrite existing local records');
const corrupt={...bundle,sha256:'0'.repeat(64)};
await assert.rejects(()=>validateNativeQaBundle(corrupt),/SHA-256/);

const rollbackTarget=new MemoryStorage();let rollbackFavorites=[];let rejectSecond=false;
const rollbackRequest=async(path,options={})=>{
 if(path==='/api/video-evidence/library')return {ok:true,json:async()=>({feed_favorites:rollbackFavorites})};
 const value=JSON.parse(options.body);
 if(value.saved&&rejectSecond){rejectSecond=false;return {ok:false,json:async()=>({})}}
 rollbackFavorites=value.saved?[...new Set([...rollbackFavorites,value.key])]:rollbackFavorites.filter(key=>key!==value.key);
 return {ok:true,json:async()=>({favorites:rollbackFavorites})};
};
const multiKey={...bundle,data:{...bundle.data,feedFavorites:['match:first','match:second']}};
const {sha256,...unsigned}=multiKey;multiKey.sha256=await (async()=>{
 const encoder=new TextEncoder();const canonical=value=>value===null||typeof value!=='object'?JSON.stringify(value):Array.isArray(value)?`[${value.map(canonical).join(',')}]`:`{${Object.keys(value).sort().map(key=>`${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
 const digest=await webcrypto.subtle.digest('SHA-256',encoder.encode(canonical(unsigned)));
 return [...new Uint8Array(digest)].map(byte=>byte.toString(16).padStart(2,'0')).join('');
})();
rejectSecond=true;
const failed=await importNativeQaBundle(multiKey,{storage:rollbackTarget,request:rollbackRequest});
assert.equal(failed.ok,false);
assert.match(failed.error,/已回滚/);
assert.equal(rollbackTarget.getItem(MOMENT_STORAGE_KEY),null);
assert.deepEqual(rollbackFavorites,[]);
console.log('Native QA bundle tests passed: allowlist, checksum, empty-target guard, explicit restore, and rollback.');
