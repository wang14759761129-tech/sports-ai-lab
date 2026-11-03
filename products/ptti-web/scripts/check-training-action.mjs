import assert from 'node:assert/strict';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import {createSimulatedDemoReport,createPersonalMatchReport} from '../src/personal-match-report.mjs';
import {createWatchCopyGuard} from '../src/watch-copy-guard.mjs';
import {session,context,points} from './check-premiere.mjs';
const root=new URL('../',import.meta.url),out=new URL('.alpha-qa/goal51/',root);await mkdir(out,{recursive:true});
const kit=await build({stdin:{contents:`export {createTrainingAction,formatTrainingAction} from './src/training-action';export {TrainingActionLoop} from './src/TrainingActionLoop';export {renderToStaticMarkup} from 'react-dom/server';export {createElement} from 'react';`,resolveDir:fileURLToPath(root),loader:'tsx'},bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',write:false});const file=new URL('kit.mjs',out);await writeFile(file,kit.outputFiles[0].contents);const {createTrainingAction,formatTrainingAction,TrainingActionLoop,renderToStaticMarkup,createElement}=await import(file.href+'?'+Date.now());
const reports=[createSimulatedDemoReport(),createPersonalMatchReport(session,points,context).value];
const unknown=createPersonalMatchReport(session,points.map(p=>({...p,server:'UNKNOWN'})),{...context,first_server:'UNKNOWN'});assert(unknown.ok);reports.push(unknown.value);
const partial=createPersonalMatchReport(session,points.slice(0,19),context);assert(partial.ok);reports.push(partial.value);
const snapshot=JSON.stringify(reports);const kinds=new Set();
for(const report of reports) for(const locale of ['zh-CN','en']) {
 assert.equal(createTrainingAction(report,null,locale),null);assert.equal(createTrainingAction(report,'stale-choice',locale),null);
 const empty=renderToStaticMarkup(createElement(TrainingActionLoop,{report,questionId:null,locale,disabled:false}));assert(!empty.includes('Export action JSON'));
 for(const q of report.training_questions) {
  kinds.add(q.kind);const plan=createTrainingAction(report,q.question_id,locale);assert(plan);assert.equal(plan.schema,'ptti.training-observation-action/0.1');assert.equal(plan.evidence.sample_count,q.sample_count);assert.equal(plan.verification,report.confirmation_status);assert.equal(plan.source,report.source.type);assert.equal(plan.simulated,report.source.type==='SIMULATED_DEMO');assert.equal(plan.auto_saved,false);assert.equal(plan.public_match_id,null);assert.equal(plan.video_source_id,null);
  if(q.kind==='KEY_SCORE_RANGE') {const stage=report.calculated_results.key_stages.find(s=>s.id===q.stage_id);assert.equal(plan.evidence.sample_count,stage.sample_count);assert.deepEqual(plan.evidence.point_range,{first_point:stage.first_point,last_point:stage.last_point});}
  if(q.kind==='SCORING_RUN') assert.equal(plan.evidence.sample_count,q.length);
  if(q.kind==='SERVE_RECEIVE') assert.equal(report.calculated_results.serve_receive.status,'AVAILABLE');
  for(const key of ['observation_question','next_training_action','verification_method','limitations']) assert(plan[key].length>15);
  const text=formatTrainingAction(plan);assert(text.includes(plan.evidence.basis));assert(text.includes(plan.next_training_action));assert(text.includes(plan.simulated?'SIMULATED DEMO':'MANUAL USER RECORD'));
  const serialized=JSON.stringify(plan);assert.doesNotMatch(serialized,/PRIVATE|\.mp4|C:\\|file_name|file_path|session_id|dataset_id|start_seconds|end_seconds|bound_video|http/);
  const html=renderToStaticMarkup(createElement(TrainingActionLoop,{report,questionId:q.question_id,locale,disabled:false,onOpenJournal(){}}));assert.match(html,/data-training-action/);assert.match(html,/data-action-source/);assert.doesNotMatch(html,/undefined|<video|<iframe/);assert(html.includes(locale==='en'?'Export action JSON':'导出行动 JSON'));
 }
}
assert.deepEqual([...kinds].sort(),['KEY_SCORE_RANGE','MISSING_TECHNICAL_EVIDENCE','SCORING_RUN','SERVE_RECEIVE']);assert.equal(JSON.stringify(reports),snapshot);
assert(!unknown.value.training_questions.some(q=>q.kind==='SERVE_RECEIVE'));assert(!partial.value.training_questions.some(q=>q.kind==='SERVE_RECEIVE'));
const report=reports[0], ids=report.training_questions.map(q=>q.question_id);assert.notDeepEqual(createTrainingAction(report,ids[0],'en'),createTrainingAction(report,ids.at(-1),'en'));
assert.equal(createTrainingAction({...report,source:{type:'UNKNOWN'}},ids[0],'en'),null);
const guard=createWatchCopyGuard();assert.equal(await guard.copy('action',async()=>{throw Error('denied')}),'manual');assert.equal(await guard.copy('action'),'manual');let release;const old=guard.copy('old',()=>new Promise(resolve=>release=resolve));guard.invalidate();assert.equal(await guard.copy('new',async()=>{}),'copied');release();assert.equal(await old,null);
const source=await readFile(new URL('src/TrainingActionLoop.tsx',root),'utf8'),logic=await readFile(new URL('src/training-action.ts',root),'utf8');assert.doesNotMatch(source+logic,/fetch\s*\(|localStorage|sessionStorage|sendBeacon|XMLHttpRequest/);assert.match(source,/textarea readOnly value=\{text\}/);assert.match(source,/guard.current.invalidate/);assert.match(source,/if \(!result \|\| !alive.current\) return/);assert.match(source,/finally.*revokeObjectURL/);assert.match(source,/SIMULATED-training-action/);assert.match(source,/if \(disabled\) return/);
const view=await readFile(new URL('src/PersonalMatchReport.tsx',root),'utf8');assert.match(view,/TrainingActionLoop report=\{report\} questionId=\{selectedQuestionId\}/);
await writeFile(new URL('SIMULATED-action.json',out),JSON.stringify(createTrainingAction(reports[0],ids[0],'en'),null,2));
console.log('PASS GOAL51: all four evidence-derived action types, exact stage/run denominators, unknown/partial rate refusal, stale selection, bilingual offline rendering, SIMULATED export identity, private-field exclusion, immutable inputs, copy failure/stale guards and passive Journal wiring. GUI/download NOT_TESTED.');
