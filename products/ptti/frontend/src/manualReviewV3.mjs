import {createReviewV2,validateReviewV2} from './manualReviewV2.mjs';
import {prepareManualReviewImport,MAX_REVIEW_BYTES} from './manualReviewImport.mjs';

export const MANUAL_REVIEW_V3='ptti.manual-review/3';
const tags=new Set(['serve','receive','rally','other']);
const results=new Set(['unknown','won','lost','other']);
/** Construct only after the selected local media has been identified. */
export function createReviewV3(media,marks,rallies){
 const review=createReviewV2(media,marks);
 if(!Array.isArray(rallies)||review.marks.length+rallies.length>10000)throw Error('INVALID_RALLIES');
 const ids=new Set(review.marks.map(m=>m.id));
 const safe=rallies.map(r=>{
  if(!r||typeof r.id!=='string'||!/^[A-Za-z0-9_-]{1,128}$/.test(r.id)||ids.has(r.id)||!Number.isFinite(r.start_seconds)||!Number.isFinite(r.end_seconds)||r.start_seconds<0||r.start_seconds>=r.end_seconds||r.end_seconds>review.media.duration_seconds||!tags.has(r.tag)||!results.has(r.result)||typeof r.note!=='string'||r.note.length>2000)throw Error('INVALID_RALLY');
  ids.add(r.id);return {id:r.id,start_seconds:r.start_seconds,end_seconds:r.end_seconds,tag:r.tag,result:r.result,note:r.note};
 });
 return {...review,schema:MANUAL_REVIEW_V3,rallies:safe};
}

/** Parse for preview only. Existing v2 imports remain lossless. */
export function prepareReviewV3Import(text,expected){
 if(typeof text!=='string'||new TextEncoder().encode(text).length>MAX_REVIEW_BYTES)throw Error('IMPORT_TOO_LARGE');
 let data;try{data=JSON.parse(text)}catch{throw Error('INVALID_JSON')}
 if(!data||typeof data!=='object'||Array.isArray(data))throw Error('INVALID_REVIEW');
 if(data.schema==='ptti.manual-review/2')return {...prepareManualReviewImport(text,expected),rallies:[]};
 if(data.schema!==MANUAL_REVIEW_V3)throw Error('INVALID_REVIEW');
 // Reuse all v2 provenance, fingerprint, duration and media checks.
 const v2={...data,schema:'ptti.manual-review/2'};delete v2.rallies;
 const preview=prepareManualReviewImport(JSON.stringify(v2),expected);
 const validated=validateReviewV2(v2);
 const result=createReviewV3(validated.media,validated.marks,data.rallies);
 return {...preview,schema:MANUAL_REVIEW_V3,rallies:result.rallies};
}
