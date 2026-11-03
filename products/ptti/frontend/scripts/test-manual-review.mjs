import assert from 'node:assert/strict';import {createManualMark,exportManualReview} from '../src/manualReview.mjs';
const sha='a'.repeat(64),base={id:'one',sha256:sha,eventId:'demo-1',seconds:2.5,duration:20,tag:'serve',note:'观察发球'};
const mark=createManualMark(base);assert.equal(mark.origin,'MANUAL_USER_RECORDED');assert.equal(mark.verification,'NOT_INDEPENDENTLY_VERIFIED');
const out=exportManualReview([mark],sha,'demo-1',20);assert.equal(out.marks[0].seconds,2.5);assert.equal(out.media_scope,'SYNTHETIC_DEMO');assert(!JSON.stringify(out).includes('C:\\'));assert(!JSON.stringify(out).includes('filename'));
for(const bad of [{...base,seconds:21},{...base,seconds:-1},{...base,sha256:'x'},{...base,eventId:'public-match'},{...base,tag:'diagnosis'},{...base,note:'x'.repeat(501)}])assert.throws(()=>createManualMark(bad));
assert.throws(()=>exportManualReview([mark],sha,'demo-2',20));assert.throws(()=>exportManualReview([mark,mark],sha,'demo-1',20));
console.log('PASS synthetic identity, timestamp, manual evidence, export and rejection boundaries');
