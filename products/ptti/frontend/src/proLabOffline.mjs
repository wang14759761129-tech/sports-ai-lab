export function offlineReviewRows({event,rows,examples,unavailable,broken}){
 if(!Array.isArray(rows)||!Array.isArray(examples))throw Error('INVALID_REVIEW_ROWS');
 if(unavailable&&!broken&&event==='demo-1'&&rows.length===0)return {rows:examples,usingExamples:true};
 return {rows,usingExamples:false};
}
export function mayUseMedia(identity,mediaReady,unavailable){return identity===true&&mediaReady===true&&unavailable===false;}
export function exportReview(kind,rows,event,usingExamples,encode,csv){
 const origin=usingExamples?'BUILT_IN_FICTIONAL_DEMO':'LOCAL_SAVED_DEMO';
 if(kind==='json'){const data=JSON.parse(encode(rows,event));return JSON.stringify({...data,record_origin:origin},null,2)}
 if(kind==='csv'){const header=csv([]);return ['record_origin,'+header,...rows.map(row=>'"'+origin+'",'+csv([row]).slice(header.length+2))].join('\r\n')}
 throw Error('INVALID_EXPORT_FORMAT');
}
export function reviewStatus(usingExamples, rowCount, identity, mediaReady, identityFailed, mediaFailed) {
 const source=usingExamples?'内置虚构 DEMO':rowCount>0?'本机保存记录':'暂无记录';
 const media=mayUseMedia(identity,mediaReady,identityFailed||mediaFailed)?'已验证可播放':'暂不可用';
 const reason=identityFailed?'媒体身份校验失败或不匹配':mediaFailed?'媒体加载失败':!identity?'媒体身份尚未确认':!mediaReady?'媒体尚未就绪':'';
 return {source,media,reason};
}
