import assert from 'node:assert/strict';
import {MEDIA,encode,decode,stats,csv} from '../src/rallyData.ts';
import {validateReturn} from '../src/spaceContext.ts';
const item={id:'synthetic-1',media:MEDIA,event:'demo-1',time:2,server:'A',winner:'B',shots:3,serve:'',receive:'',third:'',note:' =1+1'};
const stored=encode([item],'demo-1');assert.equal(decode(stored,'demo-1')[0].id,item.id);assert.throws(()=>decode(stored,'demo-2'));assert.equal(stats([item]).wins.B,1);assert.equal(stats([{...item,winner:'A'}]).wins.A,1);assert.equal(stats([]).n,0);assert.match(csv([item]),/"' =1\+1"/);
const c={sha256:MEDIA,cardId:'demo-1',momentId:'m',time:2,sceneId:'demo-arena-01',createdAt:Date.now()};assert.equal(validateReturn(c,MEDIA,'demo-1',[{id:'m',time:2,note:''}],20),2);assert.throws(()=>validateReturn(c,MEDIA,'demo-2',[{id:'m',time:2,note:''}],20));assert.throws(()=>validateReturn(c,MEDIA,'demo-1',[],20));
console.log('PASS synthetic rally roundtrip, stats, CSV formula, same-SHA event isolation and deleted Moment rejection');
import {freshArena,step,score,restoreArena} from '../src/arenaState.ts';
let arena=freshArena();for(let i=0;i<4;i++){arena=step(arena,'lock','A');const locked=structuredClone(arena);assert.deepEqual(step(arena,'lock','B'),locked);arena=step(arena,'reveal');assert.deepEqual(step(arena,'reveal'),arena);if(i<3)arena=step(arena,'next');}assert.deepEqual(score(arena),{A:12,B:10});assert.deepEqual(restoreArena(JSON.stringify(arena),arena.eventId),arena);assert.deepEqual(step(arena,'reset').records,[]);console.log('PASS Arena simulated 9:9 to 12:10, locking, replay and reset');
import {createDemoSyntheticFetcher} from '../src/demoSyntheticFetcher.mjs';
let received='';const fetchSynthetic=createDemoSyntheticFetcher(async url=>{received=url;return {ok:true}});assert.equal((await fetchSynthetic('https://untrusted.invalid')).ok,true);assert.equal(received,'/demo-synthetic.mp4');assert.throws(()=>createDemoSyntheticFetcher(null));console.log('PASS synthetic-only captured fetch ignores arbitrary URLs');

import {createMutationGuard} from '../src/demoActions.ts';
const gate=createMutationGuard();assert.equal(gate.begin(),true);assert.equal(gate.begin(),false);gate.end();assert.equal(gate.begin(),true);gate.end();assert.throws(()=>encode([item,item],'demo-1'),/重复/);assert.throws(()=>validateReturn(c,'invalid','demo-1',[{id:'m',time:2,note:''}],20));assert.throws(()=>validateReturn({...c,createdAt:Date.now()-86400001},MEDIA,'demo-1',[{id:'m',time:2,note:''}],20));console.log('PASS duplicate mutation guard, duplicate ID, wrong media and expired return');

import {readFileSync} from 'node:fs';
const samples=JSON.parse(readFileSync(new URL('./prolab-lite-demo.json',import.meta.url),'utf8'));const summary=stats(decode(encode(samples,'demo-1'),'demo-1'));assert.equal(summary.n,6);assert.deepEqual(summary.wins,{A:4,B:2});assert.equal(summary.average,23/6);assert.equal(summary.thirdN,5);assert.deepEqual(summary.service,[{player:'A',n:3,wins:2},{player:'B',n:3,wins:1}]);assert.match(csv([{...item,note:'=1+1'}]),/"\x27=1\+1"/);console.log('PASS six-rally demo computed totals and CSV protection');
