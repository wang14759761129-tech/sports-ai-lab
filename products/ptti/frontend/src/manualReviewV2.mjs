export const MANUAL_REVIEW_V2 = 'ptti.manual-review/2';
const tags = new Set(['serve','receive','rally','other']);
function checkedMedia(media) {
 if (!media || !Number.isFinite(media.duration_seconds) || media.duration_seconds <= 0) throw Error('INVALID_MEDIA');
 const identity = media.identity;
 if (!identity || !((identity.kind === 'SHA256' && typeof identity.value === 'string' && /^[a-f0-9]{64}$/.test(identity.value)) || (identity.kind === 'SESSION' && typeof identity.value === 'string' && /^[A-Za-z0-9_-]{16,128}$/.test(identity.value)))) throw Error('INVALID_MEDIA_IDENTITY');
 return {identity:{kind:identity.kind,value:identity.value},duration_seconds:media.duration_seconds};
}
export function createReviewV2(media, marks) {
 const m = checkedMedia(media);
 if (!Array.isArray(marks)) throw Error('INVALID_MARKS');
 const ids = new Set();
 const safe = marks.map(mark => {
  if (!mark || typeof mark.id !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(mark.id) || ids.has(mark.id) || !Number.isFinite(mark.seconds) || mark.seconds < 0 || mark.seconds > m.duration_seconds || !tags.has(mark.tag) || typeof mark.note !== 'string' || mark.note.length > 2000) throw Error('INVALID_MARK');
  ids.add(mark.id);
  return {id:mark.id,seconds:mark.seconds,tag:mark.tag,note:mark.note};
 });
 return {schema:MANUAL_REVIEW_V2,media:m,origin:'MANUAL_USER_RECORDED',verification:'NOT_INDEPENDENTLY_VERIFIED',association:'NO_MATCH_ASSOCIATION',persistence:'SESSION_ONLY',marks:safe};
}
export function validateReviewV2(data, expectedMedia) {
 if (!data || data.schema !== MANUAL_REVIEW_V2 || data.origin !== 'MANUAL_USER_RECORDED' || data.verification !== 'NOT_INDEPENDENTLY_VERIFIED' || data.association !== 'NO_MATCH_ASSOCIATION' || data.persistence !== 'SESSION_ONLY') throw Error('INVALID_REVIEW');
 const clean = createReviewV2(data.media,data.marks);
 if (expectedMedia) {
  const expected = checkedMedia(expectedMedia);
  if (clean.media.identity.kind !== expected.identity.kind || clean.media.identity.value !== expected.identity.value || clean.media.duration_seconds !== expected.duration_seconds) throw Error('MEDIA_IDENTITY_MISMATCH');
 }
 return clean;
}
