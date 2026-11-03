import assert from 'node:assert/strict';
import {freshArena,arenaStep,pendingEvent,ended} from '../src/gex-moment/arena-events.mjs';
import {revealAt} from '../src/arena-clock.mjs';
let state=freshArena(20,'original-animation');
for(let i=0;i<4;i++){
 state=arenaStep(state,'choose',i%2?'B':'A');state=arenaStep(state,'lock');
 const locked=structuredClone(state);assert.deepEqual(arenaStep(state,'choose','B'),locked);
 const event=pendingEvent(state);assert.equal(event.source,'MOCK');assert.equal(event.timestamp_basis,'MOCK_POSITION_NOT_OBSERVED_POINT');
 assert.deepEqual(revealAt(state,event.timestamp-.01),state);assert.deepEqual(revealAt(state,NaN),state);
 state=revealAt(state,event.timestamp);assert.equal(state.records.length,i+1);assert.deepEqual(revealAt(state,event.timestamp),state);
 if(i<3)state=arenaStep(state,'next');
}
assert.deepEqual(state.score,{A:12,B:10});assert.equal(ended(state),true);
assert.equal(new Set(state.records.map(r=>r.eventId)).size,4);
assert.deepEqual(arenaStep(state,'reset'),freshArena(20,'original-animation'));
console.log('PASS simulated timeline gate, lock, four event scores, no double settlement and reset');
