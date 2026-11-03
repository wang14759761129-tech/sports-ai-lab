import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';import {webcrypto} from 'node:crypto';import {loadPinnedCinema} from '../src/pinnedCinema.mjs';import {parsePinnedMatchContract} from '../src/match-contract-v1.mjs';
if(!globalThis.crypto)globalThis.crypto=webcrypto;
const raw=readFileSync(new URL('../src/sprint08-cinema-projection.json',import.meta.url),'utf8');const {projection,matches}=await loadPinnedCinema(raw);
assert.equal(matches.length,8);assert.equal(projection.video_sources.length,18);assert.equal(projection.video_sources.filter(s=>s.match_id===null).length,10);
assert.equal(matches.reduce((n,m)=>n+m.sources.length,0),8);
for(const match of matches){assert.equal(match.contract_version,'ptti.match/1.0');assert.equal(match.media_sha256,null);assert.equal(match.sources.every(s=>s.media_sha256===null&&s.authorization.embedding==='UNKNOWN'&&s.availability.playback==='NOT_TESTED'),true);assert.deepEqual(match.sources.map(s=>s.source_id),projection.matches.find(m=>m.match_id===match.match_id).source_ids);assert.equal((await parsePinnedMatchContract(new TextEncoder().encode(raw),match.match_id)).match_id,match.match_id)}
await assert.rejects(()=>loadPinnedCinema(raw+' '),/PROJECTION_SHA_MISMATCH/);await assert.rejects(()=>parsePinnedMatchContract(new TextEncoder().encode(raw),'unknown'),/MATCH_NOT_UNIQUE/);
console.log('PASS pinned bytes, 8 exact match queries, 8 linked / 10 unlinked, unknown-media rights and tamper rejection');
