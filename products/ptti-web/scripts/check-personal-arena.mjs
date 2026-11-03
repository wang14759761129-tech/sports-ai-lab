import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { session, context, points } from './check-premiere.mjs';
import { createPersonalMatchReport } from '../src/personal-match-report.mjs';
import { personalArenaContext } from '../src/premiere.mjs';
import { ARENA_TACTICS, createArenaChallengeState, reduceArenaChallenge } from '../src/arena-challenge.mjs';
const report=createPersonalMatchReport(session,points,context).value;const before=JSON.stringify(report);
const snapshot=personalArenaContext(report,18);
assert.deepEqual(snapshot,{score:{player_a:9,player_b:9},point_index:18,completeness:'GAME_COMPLETE',source:'USER_MANUAL',verification:'NOT_INDEPENDENTLY_VERIFIED'});
for(const point of [null,0,1,14,17,19,20,22,999,'18',NaN]) assert.equal(personalArenaContext(report,point),null);
assert.equal(personalArenaContext(null,18),null);
for(const field of ['schema','source','confirmation_status']) {const bad=structuredClone(report);bad[field]='invalid';assert.equal(personalArenaContext(bad,18),null);}
const partial=createPersonalMatchReport(session,points.slice(0,18),context).value;assert.equal(personalArenaContext(partial,18).completeness,'IN_PROGRESS');
assert.doesNotMatch(JSON.stringify(snapshot),/session_id|match_id|file|path|video|tactic|spin|placement/);
let state=createArenaChallengeState();state=reduceArenaChallenge(state,{type:'choose',choice:ARENA_TACTICS[0].id});assert.equal(state.selectedChoice,ARENA_TACTICS[0].id);state=reduceArenaChallenge(state,{type:'generate-takeaway'});assert.equal(state.takeawayGenerated,true);state=reduceArenaChallenge(state,{type:'retry'});assert.equal(state.selectedChoice,null);assert.equal(JSON.stringify(report),before);
const root=new URL('../',import.meta.url);const out=new URL('.alpha-qa/goal48/',root);await mkdir(out,{recursive:true});
const kit=await build({stdin:{contents:`export {PersonalArenaChallenge} from './src/PersonalArenaChallenge';export {ArenaChallengeView} from './src/ArenaChallengePage';export {renderToStaticMarkup} from 'react-dom/server';export {createElement} from 'react';`,resolveDir:fileURLToPath(root),loader:'tsx'},bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',write:false});const file=new URL('kit.mjs',out);await writeFile(file,kit.outputFiles[0].contents);const {PersonalArenaChallenge,ArenaChallengeView,renderToStaticMarkup,createElement}=await import(file.href+'?'+Date.now());
for(const locale of ['zh-CN','en']) {const html=renderToStaticMarkup(createElement(PersonalArenaChallenge,{context:snapshot,locale,onBack:()=>{},onReport:()=>{}}));assert.match(html,/data-personal-arena="SIMULATED_ONLY"/);assert.match(html,/data-arena-score="9:9"/);assert.doesNotMatch(html,/data-arena-open-journal|<video|PRIVATE|undefined/);assert.match(html,/Journal/);await writeFile(new URL(locale+'.html',out),html);}
let backs=0;const view=ArenaChallengeView({locale:'en',state:createArenaChallengeState(),onAction:()=>{},onBack:()=>backs++});function visit(node){if(!node||typeof node!=='object')return;if(node.props?.['data-arena-back']!==undefined)node.props.onClick();for(const child of [node.props?.children].flat(Infinity))visit(child);}visit(view);assert.equal(backs,1);
const component=await readFile(new URL('src/PersonalArenaChallenge.tsx',root),'utf8');assert.doesNotMatch(component,/fetch\s*\(|localStorage|sessionStorage|onOpenJournal=|setPoints|setDraft/);
console.log('PASS GOAL48: 9:9-only allowlist context, invalid/unavailable rejection, complete/partial flags, no identity/media propagation, existing simulation reducer isolation, return handler, bilingual SSR with no Journal action. GUI/focus/real media NOT_TESTED.');
