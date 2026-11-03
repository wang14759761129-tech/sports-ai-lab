import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';
const folder=mkdtempSync(join(tmpdir(),'ptti-moment-seek-'));
try {
 const result=spawnSync(process.execPath,['node_modules/typescript/bin/tsc','src/momentSeek.ts','--target','ES2022','--module','ES2022','--strict','--skipLibCheck','--outDir',folder],{encoding:'utf8'});
 assert.equal(result.status,0,result.stdout+result.stderr);writeFileSync(join(folder,'package.json'),'{"type":"module"}');
 const {momentStartMs}=await import(pathToFileURL(join(folder,'momentSeek.js')));
 assert.equal(momentStartMs(12340,false,1.5),12340);assert.equal(momentStartMs(0,false,1.5),0);
 assert.equal(momentStartMs(12340,true,1.5),10840);assert.equal(momentStartMs(500,true,1.5),0);
 console.log('4 passed: exact saved time, zero, contextual playback and start clamp');
} finally {rmSync(folder,{recursive:true,force:true})}
