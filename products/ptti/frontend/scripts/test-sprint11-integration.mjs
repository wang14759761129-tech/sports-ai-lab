import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';import {createHash} from 'node:crypto';
const hash=path=>createHash('sha256').update(readFileSync(new URL(path,import.meta.url))).digest('hex');
assert.equal(hash('../src/vendor/playback/index.ts'),'a59df06b688d75885bfb8ed51364e73edbaedaaa2b3746b5f7fd1d1edf67caf2');
assert.equal(hash('../src/vendor/playback/momentPlaybackAdapter.ts'),'b34ca539e3131cbcad4a08b6007922a1d4933aa1bc8b79f60ee52cb7b23aebfb');
assert.equal(hash('../src/match-contract-v1.mjs'),'d11946f5796fcc2c704079af64bbb28643f9798f1436e0ee1b33edf55fd99eac');
const app=readFileSync(new URL('../src/DemoApp.tsx',import.meta.url),'utf8');
assert.match(app,/validateDemoIdentity\(hash,data.sha256,video,data.event_id\)/);assert.match(app,/new LocalVideoPlaybackController\(media,\{createVideoIdentity:\(\)=>hash\}\)/);assert.match(app,/adapter\.pause\(\)/);assert.match(app,/adapter\.seekExact\(time\)/);assert.match(app,/adapter\.seekExact\(m.time\)/);assert.match(app,/cancelPendingSeek\(\)/);assert.match(app,/controllerRef\.current\?\.release\(\)/);assert.doesNotMatch(app,/src="\/demo-synthetic\.mp4"/);
console.log('PASS pinned module hashes and session integration wiring; actual media and GUI NOT_TESTED');
