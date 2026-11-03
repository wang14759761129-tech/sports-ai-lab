import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  buildOfficialJump, createMoment, deleteMoment, formatTimestamp,
  loadMoments, loadMomentState, parseTags, parseTimestamp, saveMoments, writeMoments, updateMoment,filterMomentsByTag,
} from '../src/momentCards.mjs';

// Timestamp parsing
assert.equal(parseTimestamp('12:34'), 754);
assert.equal(parseTimestamp('1:02:03'), 3723);
assert.equal(parseTimestamp('0:00'), 0);
assert.equal(parseTimestamp('12:60'), null);
assert.equal(parseTimestamp('abc'), null);
assert.equal(parseTimestamp(''), null);
assert.equal(formatTimestamp(754), '12:34');
assert.equal(formatTimestamp(3723), '1:02:03');

// Tags
assert.deepEqual(parseTags('关键分, 发球， 关键分'), ['关键分', '发球']);

// Create -> edit -> delete, with isolated memory storage (not production DB)
const memory = new Map();
const store = { getItem: (k) => memory.get(k) ?? null, setItem: (k, v) => memory.set(k, v) };
let r = createMoment([], { videoKey: 'official:0QgbtsBWZhk', title: '关键分变线', timestamp: '12:34', note: '当时不敢变线', tags: '关键分, 变线' });
assert.equal(r.errors.length, 0);
assert.equal(r.moments.length, 1);
assert.equal(r.moments[0].seconds, 754);
assert.equal(saveMoments(store, r.moments), true);
assert.equal(loadMoments(store).length, 1);

const bad = createMoment(r.moments, { videoKey: '', title: '', timestamp: '99:99', note: '', tags: '' });
assert.ok(bad.errors.length >= 2, 'invalid input must be rejected, not saved');

let edited = updateMoment(r.moments, r.moments[0].id, { videoKey: 'official:0QgbtsBWZhk', title: '关键分变线（改）', timestamp: '13:01', note: '下次提前准备', tags: '关键分' });
assert.equal(edited.errors.length, 0);
assert.equal(edited.moments[0].title, '关键分变线（改）');
assert.equal(edited.moments[0].seconds, 781);
assert.equal(saveMoments(store,edited.moments),true);
assert.equal(loadMoments(store)[0].seconds,781,'Re-reading storage retains the edited 13:01 marker');
const second=createMoment(edited.moments,{videoKey:'official:0QgbtsBWZhk',title:'接发球',timestamp:'14:00',note:'另一条个人标记',tags:'接发球'});
assert.equal(filterMomentsByTag(second.moments,'关键分').length,1);
assert.equal(filterMomentsByTag(second.moments,'接发球').length,1);
assert.equal(filterMomentsByTag(second.moments,'UNKNOWN').length,0);

let afterDelete = deleteMoment(edited.moments, edited.moments[0].id);
assert.equal(afterDelete.length, 0);
assert.equal(saveMoments(store,afterDelete),true);
assert.equal(loadMoments(store).length,0,'A persisted deletion remains removed after re-read');
assert.equal(saveMoments(store,edited.moments),true);

// Official jump: YouTube precise, others plain, local none
const yt = { watchUrl: 'https://www.youtube.com/watch?v=0QgbtsBWZhk', source: { provider: 'YOUTUBE_OFFICIAL', video_id: '0QgbtsBWZhk' } };
const jump = buildOfficialJump(yt, 754);
assert.equal(jump.precise, true);
assert.equal(jump.url, 'https://www.youtube.com/watch?v=0QgbtsBWZhk&t=754');
const bili = { watchUrl: 'https://www.bilibili.com/video/BV1nb421H7jB/', source: { provider: 'BILIBILI', video_id: 'BV1nb421H7jB' } };
const jump2 = buildOfficialJump(bili, 754);
assert.equal(jump2.precise, false);
assert.equal(jump2.url, bili.watchUrl);
assert.equal(buildOfficialJump({ watchUrl: null, source: {} }, 10).url, null);
// ID mismatch must not produce a precise jump
const mismatch = buildOfficialJump({ watchUrl: 'https://www.youtube.com/watch?v=OtherId1234', source: { provider: 'YOUTUBE_OFFICIAL', video_id: '0QgbtsBWZhk' } }, 10);
assert.equal(mismatch.precise, false);
assert.equal(mismatch.url, null, 'Mismatched IDs reject even an un-timed misleading link');
for(const watchUrl of ['http://www.youtube.com/watch?v=0QgbtsBWZhk','https://youtube.com.evil.invalid/watch?v=0QgbtsBWZhk','https://redacted@example.invalid/watch?v=0QgbtsBWZhk','https://www.youtube.com/watch?v=0QgbtsBWZhk&v=OtherId1234','javascript:alert(1)']){
 assert.equal(buildOfficialJump({...yt,watchUrl},754).url,null);
}
assert.equal(buildOfficialJump({...yt,source:{...yt.source,video_source:{source_id:'OtherId1234'}}},754).url,null);
assert.equal(buildOfficialJump({...bili,watchUrl:'https://www.bilibili.com/video/BV1Other12345/'},754).url,null);
assert.equal(buildOfficialJump({...yt,source:{...yt.source,source_url:'https://www.youtube.com/watch?v=OtherId1234'}},754).url,null);
assert.equal(buildOfficialJump(yt,NaN).url,null);
assert.equal(buildOfficialJump({...yt,source:{provider:'UNKNOWN'}},754).url,null);

// Initial reads are pure, even repeated for Strict Mode/remount; never write [].
const before=new Map(memory);let writes=0;
const counted={getItem:k=>memory.get(k)??null,setItem:(k,v)=>{writes++;memory.set(k,v)}};
assert.equal(loadMomentState(counted).moments.length,1);
assert.equal(loadMomentState(counted).moments.length,1);
assert.equal(writes,0);
assert.deepEqual(memory,before);
assert.equal(saveMoments(undefined,[]),false,'Absent storage is a failure, not optional-chain success');
assert.equal(saveMoments(store,[r.moments[0],r.moments[0]]),false,'Duplicate persisted IDs are rejected');
assert.equal(loadMomentState(undefined).writable,false);
const blocked={getItem:()=>{throw Error('SecurityError')},setItem:()=>{throw Error('SecurityError')}};
assert.equal(loadMomentState(blocked).writable,false);
assert.equal(saveMoments(blocked,r.moments),false);
const quota={getItem:()=>null,setItem:()=>{const e=Error('full');e.name='QuotaExceededError';throw e}};
assert.match(writeMoments(quota,r.moments).error,/空间不足/);
assert.equal(writeMoments({setItem:()=>{throw Error('disk')}},r.moments).ok,false);
assert.equal(loadMomentState({getItem:()=>'{broken',setItem:()=>{throw Error('must not write')}}).writable,false);
assert.equal(loadMomentState({getItem:()=>JSON.stringify([{id:'bad'}]),setItem:()=>{}}).writable,false);

// Demo renderer treats every user field as text; fake DOM rejects HTML sinks.
const {renderCards}=await import('../../qa/moment-cards-demo/render.mjs');
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.textContent=''}
 set innerHTML(value){throw Error('Unsafe HTML sink: '+value)}
 append(...nodes){this.children.push(...nodes)}
 replaceChildren(...nodes){this.children=nodes}
}
const payload='<img src=x onerror=globalThis.__momentXss=1>';
const hostile=createMoment([],{videoKey:'official:0QgbtsBWZhk',title:'<svg/onload=alert(1)>',timestamp:'12:34',note:payload,tags:['<script>alert(1)</script>']}).moments;
const container=new Element('div');
renderCards({createElement:tag=>new Element(tag)},container,hostile,[{...yt,key:'official:0QgbtsBWZhk',title:'Registered',event:'QA'}],()=>{},()=>{});
const allNodes=[];function walk(n){allNodes.push(n);n.children.forEach(walk)}walk(container);
assert.ok(allNodes.some(n=>n.textContent===payload));
assert.ok(allNodes.some(n=>n.textContent==='<svg/onload=alert(1)>'));
assert.ok(!allNodes.some(n=>['script','img','svg'].includes(n.tag)));

// Static integration checks: React component + VideoFeed entry + CSS exist
const feed = readFileSync(new URL('../src/VideoFeed.tsx', import.meta.url), 'utf8');
assert.ok(feed.includes("lazy(()=>import('./MomentCardsPage'))"), 'VideoFeed must load the real Moment Cards component on demand');
assert.ok(feed.includes('<WorkspaceFrame name="时刻卡片"'), 'Lazy workspace must provide loading and failure recovery');
assert.ok(feed.includes("switchSpace('moments')"), 'VideoFeed must offer a Moment Cards entry through the shared navigation');
assert.ok(feed.includes('<MomentCards videos={all}'), 'VideoFeed must render MomentCards with the current feed');
const component = readFileSync(new URL('../src/MomentCardsPage.tsx', import.meta.url), 'utf8');
assert.ok(component.includes('返回 Cinema'), 'MomentCards must offer a return to Cinema');
assert.ok(component.includes('localStorage'), 'MomentCards must use isolated browser storage');
assert.ok(component.includes('useState(initialMoments)'), 'Mount reads persisted state lazily');
assert.ok(!component.includes('useEffect'), 'No mount/save effect can overwrite initial records');
assert.ok(component.includes('if(commit(result.moments))cancelEdit()'), 'Only a durable save clears the form');

console.log('Moment Cards: timestamp/tags/create/edit/delete/YouTube-precise-jump/integration checks passed');
