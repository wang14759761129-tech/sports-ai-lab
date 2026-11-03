export function offlineReviewRows({event,rows,examples,unavailable,broken}){
 if(!Array.isArray(rows)||!Array.isArray(examples))throw Error('INVALID_REVIEW_ROWS');
 if(unavailable&&!broken&&event==='demo-1'&&rows.length===0)return {rows:examples,usingExamples:true};
 return {rows,usingExamples:false};
}
export function mayUseMedia(identity,mediaReady,unavailable){return identity===true&&mediaReady===true&&unavailable===false;}
