import assert from 'node:assert/strict';
import {resolveReferenceLink as ref} from '../src/referenceLinkGate.mjs';
import {resolveOfficialLink as video} from '../src/officialLinkGate.mjs';
const x={source_id:'report:1',source_url:'https://www.ittf.com/report/1'};assert.equal(ref(x,[x]),x.source_url);
for(const url of ['javascript:alert(1)','data:text/html,hello','http://www.ittf.com/','https://redacted@example.invalid/','https://127.0.0.1/','https://www.youtube.com/watch?v=0QgbtsBWZhk']){const bad={...x,source_url:url};assert.equal(ref(bad,[bad]),null)}
assert.equal(ref(x,[]),null);assert.equal(ref(x,[x,x]),null);assert.equal(ref({...x,source_url:'https://example.com'},[x]),null);
const row={metadata_verified_at:'2026-10-01T00:00:00Z',provenance:{metadata_method:'MANUAL'},provider:'YOUTUBE_OFFICIAL',video_id:'0QgbtsBWZhk',source_url:'https://www.youtube.com/watch?v=0QgbtsBWZhk',match_id:'m1',source_key:'YOUTUBE:0QgbtsBWZhk',video_source:{provider:'YOUTUBE',source_id:'0QgbtsBWZhk',match_id:'m1'}};
assert.equal(video({...row,source_key:undefined,video_source:undefined},[row],'m1').status,'UNAVAILABLE');assert.equal(video(row,[row],'m1').status,'REGISTERED');assert.equal(video(row,[row],'m2').status,'UNAVAILABLE');assert.equal(video(row,[row,row],'m1').status,'UNAVAILABLE');assert.equal(video({...row,video_id:'H77vNFk3neg'},[row],'m1').status,'UNAVAILABLE');
console.log('R4 reference and video source negative tests PASS');
