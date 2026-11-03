import {MOMENT_STORAGE_KEY,loadMomentState} from './momentCards.mjs';
import {PRO_LAB_STORAGE_KEY,loadNotesState} from './proLabNotes.mjs';
import {FAN_ARENA_STORAGE_KEY,readArenaSnapshot} from './fanArenaEngine.mjs';

export const NATIVE_QA_BUNDLE_SCHEMA='ptti.native-qa-data-bundle/0.1';
export const NATIVE_QA_LOCAL_KEYS=Object.freeze([MOMENT_STORAGE_KEY,PRO_LAB_STORAGE_KEY,FAN_ARENA_STORAGE_KEY]);
const FAVORITES_PATH='/api/video-evidence/library/feed/favorite';
const LIBRARY_PATH='/api/video-evidence/library';
const SHA=/^[0-9a-f]{64}$/;
const COMMIT=/^[0-9a-f]{40}$/;

function canonical(value){
 if(value===null||typeof value!=='object')return JSON.stringify(value);
 if(Array.isArray(value))return `[${value.map(canonical).join(',')}]`;
 return `{${Object.keys(value).sort().map(key=>`${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
}
async function digest(value){
 if(!globalThis.crypto?.subtle)throw Error('此环境不支持安全校验，未导出或导入数据。');
 const bytes=new TextEncoder().encode(canonical(value));
 const hash=await globalThis.crypto.subtle.digest('SHA-256',bytes);
 return [...new Uint8Array(hash)].map(byte=>byte.toString(16).padStart(2,'0')).join('');
}
function validateLocalValue(key,raw){
 if(raw===null)return;
 if(typeof raw!=='string'||raw.length>10_000_000)throw Error(`QA 数据项 ${key} 无效或超过安全大小限制。`);
 const storage={getItem:requested=>requested===key?raw:null,setItem:()=>{}};
 const state=key===MOMENT_STORAGE_KEY?loadMomentState(storage):key===PRO_LAB_STORAGE_KEY?loadNotesState(storage):readArenaSnapshot(storage);
 if(!state?.writable)throw Error(`QA 数据项 ${key} 校验失败；原始记录未改变。`);
}
function validateFavorites(value){
 if(!Array.isArray(value)||value.length>1000||value.some(key=>typeof key!=='string'||!key||key.length>512)||new Set(value).size!==value.length)throw Error('收藏数据格式无效。');
 return [...value].sort();
}
function responseFavorites(body){
 const values=body?.feed_favorites??body?.favorites;
 return validateFavorites(values);
}

export async function createNativeQaBundle({storage,favorites,sourceCommit,now=Date.now()}){
 if(!COMMIT.test(sourceCommit||''))throw Error('Native QA 构建身份无效，未导出数据。');
 const localStorageData={};
 for(const key of NATIVE_QA_LOCAL_KEYS){
  let raw;try{raw=storage.getItem(key)}catch{throw Error('本机存储不可读取，未导出数据。')}
  validateLocalValue(key,raw);localStorageData[key]=raw;
 }
 const unsigned={schema:NATIVE_QA_BUNDLE_SCHEMA,createdAt:new Date(now).toISOString(),sourceCommit,
  data:{localStorage:localStorageData,feedFavorites:validateFavorites(favorites)}};
 return {...unsigned,sha256:await digest(unsigned)};
}

export async function validateNativeQaBundle(bundle){
 if(!bundle||typeof bundle!=='object'||Array.isArray(bundle))throw Error('QA 数据包不是有效对象。');
 const keys=Object.keys(bundle).sort().join(',');
 if(keys!=='createdAt,data,schema,sha256,sourceCommit'||bundle.schema!==NATIVE_QA_BUNDLE_SCHEMA||
    typeof bundle.createdAt!=='string'||!Number.isFinite(Date.parse(bundle.createdAt))||!COMMIT.test(bundle.sourceCommit||'')||!SHA.test(bundle.sha256||''))throw Error('QA 数据包版本或字段无效。');
 const data=bundle.data;
 if(!data||typeof data!=='object'||Array.isArray(data)||Object.keys(data).sort().join(',')!=='feedFavorites,localStorage')throw Error('QA 数据包内容字段无效。');
 const local=data.localStorage;
 if(!local||typeof local!=='object'||Array.isArray(local)||Object.keys(local).sort().join(',')!==[...NATIVE_QA_LOCAL_KEYS].sort().join(','))throw Error('QA 数据包本机数据字段不完整或含有未允许字段。');
 for(const key of NATIVE_QA_LOCAL_KEYS)validateLocalValue(key,local[key]);
 validateFavorites(data.feedFavorites);
 const {sha256,...unsigned}=bundle;
 if(await digest(unsigned)!==sha256)throw Error('QA 数据包 SHA-256 不匹配；未导入数据。');
 return true;
}

export async function importNativeQaBundle(bundle,{storage,request=fetch}){
 await validateNativeQaBundle(bundle);
 const writtenKeys=[];const attemptedFavorites=[];let initialFavorites=[];
 const rollback=async()=>{
  let failed=false;
  for(const key of [...writtenKeys].reverse())try{storage.removeItem(key);if(storage.getItem(key)!==null)failed=true}catch{failed=true}
  for(const key of attemptedFavorites)try{
   const response=await request(FAVORITES_PATH,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({key,saved:false})});
   if(!response.ok)failed=true;
  }catch{failed=true}
  try{
   const response=await request(LIBRARY_PATH);if(!response.ok)throw Error();
   if(JSON.stringify(responseFavorites(await response.json()))!==JSON.stringify(initialFavorites))failed=true;
  }catch{failed=true}
  return !failed;
 };
 try{
  for(const key of NATIVE_QA_LOCAL_KEYS){let current;try{current=storage.getItem(key)}catch{throw Error('目标本机存储不可读取，未导入。')};if(current!==null)throw Error('目标 Native QA 已有本机记录；为避免覆盖，恢复已取消。')}
  let response=await request(LIBRARY_PATH);if(!response.ok)throw Error('目标收藏状态无法读取，未导入。');
  initialFavorites=responseFavorites(await response.json());if(initialFavorites.length)throw Error('目标 Native QA 已有收藏；为避免覆盖，恢复已取消。');
 }catch(error){return {ok:false,error:error instanceof Error?error.message:'目标状态不可读取，未导入。'}}
 try{
  let response;
  for(const key of NATIVE_QA_LOCAL_KEYS){const raw=bundle.data.localStorage[key];if(raw===null)continue;writtenKeys.push(key);storage.setItem(key,raw);if(storage.getItem(key)!==raw)throw Error('本机存储回读不一致，正在回滚。')}
  for(const key of validateFavorites(bundle.data.feedFavorites)){
   attemptedFavorites.push(key);
   response=await request(FAVORITES_PATH,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({key,saved:true})});
   if(!response.ok)throw Error('有收藏无法在当前比赛目录中核对，正在回滚。');
   const result=responseFavorites(await response.json());if(!result.includes(key))throw Error('收藏写入未得到服务器确认，正在回滚。');
  }
  response=await request(LIBRARY_PATH);if(!response.ok||JSON.stringify(responseFavorites(await response.json()))!==JSON.stringify(validateFavorites(bundle.data.feedFavorites)))throw Error('收藏回读校验失败，正在回滚。');
  return {ok:true,error:'',sourceCommit:bundle.sourceCommit};
 }catch(error){
  const rolledBack=await rollback();
  return {ok:false,error:`${error instanceof Error?error.message:'QA 数据恢复失败'}${rolledBack?' 已回滚本次写入。':' 回滚未能完全确认，请停止使用目标 QA 环境并检查数据。'}`};
 }
}
