import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';

const folder=mkdtempSync(join(tmpdir(),'ptti-score-observation-'));
try {
  const result=spawnSync(process.execPath,['node_modules/typescript/bin/tsc','src/scoreObservation.ts',
    '--target','ES2022','--module','ES2022','--strict','--skipLibCheck','--outDir',folder],{encoding:'utf8'});
  assert.equal(result.status,0,result.stdout+result.stderr);
  writeFileSync(join(folder,'package.json'),'{"type":"module"}');
  const {observationAnchorMs,observationSeekMs,canPlayConfirmedScore,isUnboundedScoreObservation}=await import(
    pathToFileURL(join(folder,'scoreObservation.js')));
  const observation={point_start_ms:null,point_end_ms:null,score_display_ms:24000,
    verification_status:'REVIEW_REQUIRED',availability_status:'AVAILABLE'};
  assert.equal(observationAnchorMs(observation),24000,'unbounded observation uses its recorded board time');
  assert.equal(observationSeekMs(observation),22500,'review starts 1.5s before the observation');
  assert.equal(observationSeekMs({...observation,score_display_ms:500}),0,'pre-roll clamps at the video start');
  assert.equal(observationAnchorMs({...observation,point_start_ms:0}),0,'explicit source time zero is preserved');
  assert.equal(canPlayConfirmedScore(observation),false,'an observation is never point playback');
  assert.equal(canPlayConfirmedScore({...observation,verification_status:'CONFIRMED',
    point_start_ms:1000,point_end_ms:2000}),true);
  assert.equal(canPlayConfirmedScore({...observation,verification_status:'CONFIRMED',
    point_start_ms:2000,point_end_ms:1000}),false,'invalid ranges cannot enter confirmed playback');
  assert.equal(canPlayConfirmedScore({...observation,verification_status:'CONFIRMED',
    point_start_ms:1000,point_end_ms:2000,availability_status:'MISSING_FILE'}),false);
  assert.equal(isUnboundedScoreObservation(observation),true,'unbounded pending rows are labeled as observations');
  assert.equal(isUnboundedScoreObservation({...observation,point_start_ms:1000}),false);
  console.log('10 passed, 0 failed: observation anchor, pre-roll, zero, and confirmed playback guard');
} finally { rmSync(folder,{recursive:true,force:true}); }
