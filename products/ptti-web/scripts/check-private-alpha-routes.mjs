import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fanLocationUrl,readFanLocation} from '../src/fan-location.mjs';
const base='https://invited.example/';
const catalog=JSON.parse(readFileSync(new URL('../public/data/match-library-strict-public.json',import.meta.url)));
const star=catalog.stars.find(row=>row.athlete_id==='athlete:121558');
const match=catalog.matches.find(row=>row.video_source_ids.length);
const source=catalog.video_sources.find(row=>row.source_id===match.video_source_ids[0]);
assert(star && match && source);
for(const route of [
  {page:'cinema'},
  {page:'cinema',matchId:match.match_id},
  {page:'stars'},
  {page:'stars',starId:star.athlete_id},
  {page:'watch',sourceId:source.source_id,matchId:match.match_id,starId:star.athlete_id,returnPage:'stars'},
  {page:'clips'},
  {page:'highlights'},
  {page:'arena'},
]) {
  const url=fanLocationUrl(base,route);
  const found=readFanLocation(url);
  assert(found,`route missing: ${url}`);
  assert.equal(found.page,route.page);
  if(route.matchId) assert.equal(found.matchId,route.matchId);
  if(route.starId) assert.equal(found.starId,route.starId);
  if(route.sourceId) assert.equal(found.sourceId,route.sourceId);
  assert(!url.includes('127.0.0.1') && !url.includes('localhost'));
}
assert.equal(readFanLocation(base+'/.git/config'),null);
assert.equal(readFanLocation(base+'/stars/%2Fbad'),null);
assert.equal(readFanLocation(base+'/watch/a/b'),null);
console.log('PASS: real catalog Cinema, match, star profile and Watch URLs survive direct read/refresh; malformed paths rejected');
