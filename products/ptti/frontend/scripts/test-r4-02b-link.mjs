import assert from 'node:assert/strict';
import {resolveOfficialLink as check} from '../src/officialLinkGate.mjs';
const s={metadata_verified_at:'2026-10-01T00:00:00Z',provenance:{metadata_method:'MANUAL_PUBLIC_PAGE_REVIEW'},provider:'YOUTUBE_OFFICIAL',video_id:'0QgbtsBWZhk',source_key:'YOUTUBE:0QgbtsBWZhk',source_url:'https://www.youtube.com/watch?v=0QgbtsBWZhk',match_id:'match:1',playback_status:'EMBED_BLOCKED',video_source:{provider:'YOUTUBE',source_id:'0QgbtsBWZhk',match_id:'match:1'}};
assert.equal(check(s,[s],'match:1').status,'REGISTERED');
for(const bad of [{...s,source_url:'javascript:alert(1)'},{...s,source_url:'https://youtube.com.evil.invalid/watch?v=0QgbtsBWZhk'},{...s,source_url:'https://www.youtube.com/watch?v=H77vNFk3neg'},{...s,source_url:'https://www.youtube.com/watch?v=0QgbtsBWZhk&next=https://evil.invalid'},{...s,video_source:{...s.video_source,source_id:'H77vNFk3neg'}},{...s,match_id:'match:2'},{...s,external_viewing_permission:'DENIED'},{...s,source_key:'YOUTUBE:H77vNFk3neg'}])assert.equal(check(bad,[s],'match:1').status,'UNAVAILABLE');
assert.equal(check(s,[]).status,'UNAVAILABLE');assert.equal(check(s,[s,s]).status,'UNAVAILABLE');assert.equal(check(s,[s],'match:2').status,'UNAVAILABLE');
const b={metadata_verified_at:'2026-10-01T00:00:00Z',provenance:{metadata_method:'MANUAL_PUBLIC_PAGE_REVIEW'},provider:'BILIBILI',video_id:'BV1nb421H7jB',source_key:'BILIBILI:BV1nb421H7jB',source_url:'https://www.bilibili.com/video/BV1nb421H7jB/'};assert.equal(check(b,[b]).status,'REGISTERED');
console.log('Official link identity positives and negatives PASS');
