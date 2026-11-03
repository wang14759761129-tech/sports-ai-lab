export const REVIEW_SCHEMA='ptti.manual-review-session/1';
export function createManualMark({id,sha256,eventId,seconds,duration,tag,note}){
 if(typeof id!=='string'||!id||!/^[a-f0-9]{64}$/.test(sha256)||!/^demo-[1-8]$/.test(eventId)||!Number.isFinite(seconds)||!Number.isFinite(duration)||duration<=0||seconds<0||seconds>duration||!['serve','receive','rally','other'].includes(tag)||typeof note!=='string'||note.length>500)throw Error('INVALID_MANUAL_MARK');
 return {id,video_sha256:sha256,demo_event_id:eventId,seconds,tag,note,origin:'MANUAL_USER_RECORDED',verification:'NOT_INDEPENDENTLY_VERIFIED',media_scope:'SYNTHETIC_DEMO'};
}
export function exportManualReview(marks,sha256,eventId,duration){
 if(!Array.isArray(marks))throw Error('INVALID_MARKS');
 const validated=marks.map(m=>createManualMark({id:m.id,sha256,eventId,seconds:m.seconds,duration,tag:m.tag,note:m.note}));
 if(marks.some(m=>m.video_sha256!==sha256||m.demo_event_id!==eventId)||new Set(validated.map(m=>m.id)).size!==marks.length)throw Error('IDENTITY_MISMATCH');
 return {schema:REVIEW_SCHEMA,data_origin:'MANUAL_USER_RECORDED',verification:'NOT_INDEPENDENTLY_VERIFIED',media_scope:'SYNTHETIC_DEMO',video_sha256:sha256,demo_event_id:eventId,marks:validated};
}
