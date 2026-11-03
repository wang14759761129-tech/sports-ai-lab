import assert from 'node:assert/strict';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import {createSimulatedDemoReport,createPersonalMatchReport} from '../src/personal-match-report.mjs';
import {expectedOneGameServer} from '../src/my-match-one-game.mjs';
import {premiereMoments,personalArenaContext} from '../src/premiere.mjs';
import {ARENA_TACTICS,createArenaChallengeState,reduceArenaChallenge} from '../src/arena-challenge.mjs';
const demo=createSimulatedDemoReport(), before=JSON.stringify(demo);
assert.equal(demo.source.type,'SIMULATED_DEMO'); assert.equal(demo.confirmation_status,'SIMULATED_NOT_REAL_MATCH'); assert.equal(demo.media_scope,'NO_MEDIA');
assert.equal(demo.evidence_identity.local_match_id,null); assert.equal(demo.evidence_identity.public_match_id,null); assert.equal(demo.evidence_identity.public_video_source_id,null);
assert.deepEqual(demo.calculated_results.final.score,{player_a:12,player_b:10});
for(const row of demo.data_facts.recorded_points) assert.equal(row.server,expectedOneGameServer('PLAYER_A',row.point_number));
assert.equal(premiereMoments(demo)[17].a,9); assert.equal(premiereMoments(demo)[17].b,9);
assert.equal(personalArenaContext(demo,18),null,'demo never enters the real historical-record bridge');
assert.equal(createPersonalMatchReport(null,[],{}).ok,false,'personal media contract stays mandatory');
for(const tactic of ARENA_TACTICS) {let state=reduceArenaChallenge(createArenaChallengeState(),{type:'choose',choice:tactic.id});assert.equal(state.selectedChoice,tactic.id);state=reduceArenaChallenge(state,{type:'retry'});assert.equal(state.selectedChoice,null);}
assert.equal(JSON.stringify(demo),before); assert.deepEqual(createSimulatedDemoReport(),demo);
assert.doesNotMatch(before,/start_seconds|end_seconds|bound_video|\.mp4|C:\\/);
const root=new URL('../',import.meta.url),out=new URL('.alpha-qa/goal50/',root); await mkdir(out,{recursive:true});
const kit=await build({stdin:{contents:`export {FirstExperienceDemo} from './src/FirstExperienceDemo';export {renderToStaticMarkup} from 'react-dom/server';export {createElement} from 'react';`,resolveDir:fileURLToPath(root),loader:'tsx'},bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',write:false});const file=new URL('kit.mjs',out);await writeFile(file,kit.outputFiles[0].contents);const {FirstExperienceDemo,renderToStaticMarkup,createElement}=await import(file.href+'?'+Date.now());
for(const locale of ['zh-CN','en']) {const html=renderToStaticMarkup(createElement(FirstExperienceDemo,{locale,onBack(){},onReview(){}}));assert.match(html,/SIMULATED DEMO/);assert.match(html,/9:9/);assert.match(html,/data-personal-report/);assert.match(html,/aria-pressed/);assert.doesNotMatch(html,/<video|<iframe|type="file"|undefined/);assert(html.includes(locale==='en'?'Review My Match':'复盘我的比赛'));await writeFile(new URL(locale+'-OFFLINE.html',out),html);}
const source=await readFile(new URL('src/FirstExperienceDemo.tsx',root),'utf8');assert.doesNotMatch(source,/fetch\s*\(|localStorage|sessionStorage|setPoints|setDraft|createObjectURL|onRecord|<video/);assert.match(source,/setArena\(false\)/);assert.match(source,/reportRef/);assert.match(source,/setPoint\(m.point\)/);
const app=await readFile(new URL('src/App.tsx',root),'utf8');assert.match(app,/const FirstExperienceDemo = lazy/);assert.match(app,/hidden=\{demoOpen\}/);assert.match(app,/!demoOpen && <header/,'CSS display rules cannot unhide the demo navigation');assert.match(app,/active=\{!demoOpen/);assert.match(app,/setDemoOpen\(false\); openMyMatches/);
console.log('PASS GOAL50: legal 12:10 synthetic scores/service rotation, 9:9 checkpoint, no personal evidence/media binding, immutable isolated simulation, bilingual offline report/Premiere render, lazy entry and return wiring. GUI/focus/MP4 NOT_TESTED.');
