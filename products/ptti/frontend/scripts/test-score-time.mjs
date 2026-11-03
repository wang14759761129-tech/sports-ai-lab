import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';

const folder=mkdtempSync(join(tmpdir(),'ptti-score-time-'));
try {
  const result=spawnSync(process.execPath,['node_modules/typescript/bin/tsc','src/scoreTime.ts',
    '--target','ES2022','--module','ES2022','--strict','--skipLibCheck','--outDir',folder],{encoding:'utf8'});
  assert.equal(result.status,0,result.stdout+result.stderr);
  writeFileSync(join(folder,'package.json'),'{"type":"module"}');
  const {scoreSecondsDraft}=await import(pathToFileURL(join(folder,'scoreTime.js')));
  assert.equal(scoreSecondsDraft(''),'','cleared boundaries must remain unknown, not source time zero');
  assert.equal(scoreSecondsDraft('0'),'0','explicit video start is distinct from unknown');
  assert.equal(scoreSecondsDraft('3.1'),'3100');
  assert.equal(scoreSecondsDraft('3.2'),'3200');
  assert.equal(scoreSecondsDraft(String(1/120)),'8','millisecond storage rounding is explicit; not frame-accurate');
  console.log('5 passed, 0 failed: unknown boundary, explicit zero, source PTS seconds, storage rounding');
} finally { rmSync(folder,{recursive:true,force:true}); }
