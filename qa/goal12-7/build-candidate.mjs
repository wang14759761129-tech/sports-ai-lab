import assert from 'node:assert/strict';
import {execFileSync,spawnSync} from 'node:child_process';
import {appendFileSync} from 'node:fs';
import {mkdir,readFile,writeFile,access,copyFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {selectCandidate,verifyCandidate,verifyBuildReceipt,assertBuildDestination} from '../goal12-6/candidate.mjs';
import {prepare,repo,core,hash,fileHashes,memory} from '../goal12-6/prepare.mjs';
const selected=await selectCandidate('qa/goal12-7/insight.config.json');assertBuildDestination(selected,selected.buildPath);
const out=selected.buildPath;await mkdir(out,{recursive:true});const receiptFile=path.join(out,'BUILD_RECEIPT.json');
let previousFailure=null;
try{const previous=JSON.parse(await readFile(receiptFile,'utf8'));if(!process.argv.includes('--retry-after-qa-fix')||previous.status!=='FAIL')throw Error('Existing receipt cannot be replaced without explicit failed-build retry');previousFailure=path.join(out,'BUILD_RECEIPT.failed-'+new Date().toISOString().replace(/[:.]/g,'-')+'.json');await copyFile(receiptFile,previousFailure);}catch(e){if(e.code!=='ENOENT')throw e;}
const logFile=path.join(out,'build.log');
const receipt={previous_failure_receipt:previousFailure,contract_version:'ptti.qa-build-receipt/0.1',status:'FAIL',scope:'LOCAL_QA_ONLY_NOT_RELEASE_ARTIFACT',candidate:selected.candidate,frozen:selected.candidate,config_name:selected.name,core,qa_commit:execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8',windowsHide:true}).trim(),source_location:selected.appPath,artifact_location:path.join(out,'dist'),started_at:new Date().toISOString(),node_version:process.version,validation:{source:'NOT_TESTED',typescript:'NOT_TESTED',build:'NOT_TESTED',core:'NOT_TESTED',public_isolation:'NOT_TESTED',manifest:'NOT_TESTED',qa_receipt:'NOT_TESTED'},ram_samples:[],commands:[],files:{},failure_reason:'Build has not completed'};
let stage='preconditions';
async function persist(){await writeFile(receiptFile,JSON.stringify(receipt,null,2));}
function ram(label){const gib=memory();receipt.ram_samples.push({label,gib});if(gib<3)throw Error(`BLOCKED: ${label} RAM ${gib.toFixed(3)} GiB <3`);}
function command(name,exe,args){stage=name;const result=spawnSync(exe,args,{cwd:selected.appPath,encoding:'utf8',windowsHide:true,timeout:120000,maxBuffer:4*1024*1024});appendFileSync(logFile,JSON.stringify({name,executable:exe,args,exit_code:result.status})+'\n'+(result.stdout||'')+(result.stderr||'')+'\n');receipt.commands.push({name,exit_code:result.status,error:result.error?.message??null});if(result.status!==0)throw Error(`${name} failed: ${result.error?.message??result.status}`);}
await persist();
try {
 await verifyCandidate(selected);receipt.validation.source='PASS';
 const {verifyPinnedPlaybackCore}=await import(pathToFileURL(path.join(selected.appPath,'src/playback-core-pin.mjs')));const pin=verifyPinnedPlaybackCore(selected.appPath);assert.equal(pin.coreCommit,core);receipt.core_source_sha256=pin.sourceHash;receipt.core_archive_sha256=pin.pin.archive_sha256;receipt.validation.core='PASS';
 receipt.package_lock_sha256=hash(await readFile(path.join(selected.appPath,'package-lock.json')));
 ram('before dependencies');
 let installed=true;try{await access(path.join(selected.appPath,'node_modules/typescript/bin/tsc'));}catch{installed=false;}
 if(!installed)command('dependencies','cmd.exe',['/d','/s','/c','npm.cmd ci --ignore-scripts --no-audit --no-fund']);
 ram('before TypeScript');command('typescript',process.execPath,[path.join(selected.appPath,'node_modules/typescript/bin/tsc'),'-p','tsconfig.json','--noEmit']);receipt.validation.typescript='PASS';
 stage='build';await prepare(out,selected,text=>appendFileSync(logFile,text));receipt.validation.build='PASS';
 const initial=JSON.parse(await readFile(path.join(out,'qa-build.json'),'utf8'));receipt.fixtureHashes=initial.fixtureHashes;
 const {consumeMatchLibrary}=await import(pathToFileURL(path.join(selected.appPath,'src/match-library.mjs')));
 const {consumeReadonlyProjection}=await import(pathToFileURL(path.join(selected.appPath,'src/readonly-catalog.mjs')));
 assert.equal(consumeMatchLibrary(JSON.parse(await readFile(path.join(out,'dist/data/match-library-strict-public.json'))),'STRICT_PUBLIC').source_count,0);
 assert.equal(consumeReadonlyProjection(JSON.parse(await readFile(path.join(out,'dist/data/web-strict-public.json')))).matches.length,0);receipt.validation.public_isolation='PASS';
 stage='manifest';const manifest={contract_version:'ptti.web-build-manifest/0.1',san_commit:selected.candidate,san_worktree_state:'VERIFIED_EXACT_GIT_SNAPSHOT',qa_commit:receipt.qa_commit,playback_core_commit:core,playback_core_source_sha256:pin.sourceHash,playback_core_archive_sha256:pin.pin.archive_sha256,strict_public_video_source_count:0,strict_public_web_match_count:0,internal_cinema_source_review_included:false,artifact_scope:receipt.scope,file_sha256:await fileHashes(path.join(out,'dist'))};
 // Snapshot source identity comes from verified Git blobs, not the enclosing QA worktree HEAD.
 const {assertBuildManifestMatchesCorePin}=await import(pathToFileURL(path.join(selected.appPath,'scripts/check-playback-core-pin.mjs')));assertBuildManifestMatchesCorePin(manifest,pin);assert.equal(manifest.san_commit,selected.candidate);
 await writeFile(path.join(out,'dist/ptti-build-manifest.json'),JSON.stringify(manifest,null,2));
 for(const [name,expected]of Object.entries(manifest.file_sha256))assert.equal(hash(await readFile(path.join(out,'dist',name))),expected);
 receipt.files=await fileHashes(path.join(out,'dist'));receipt.manifest_sha256=receipt.files['ptti-build-manifest.json'];receipt.validation.manifest='PASS';
 await verifyCandidate(selected);receipt.status='PASS';receipt.failure_reason=null;
 stage='qa-receipt';verifyBuildReceipt(selected,receipt,await fileHashes(path.join(out,'dist')),pin);receipt.validation.qa_receipt='PASS';
 await writeFile(path.join(out,'qa-build.json'),JSON.stringify(receipt,null,2));
}catch(error){receipt.status='FAIL';receipt.failure_reason={stage,message:error.message,stack:error.stack};if(stage in receipt.validation)receipt.validation[stage]='FAIL';process.exitCode=1;}
finally{receipt.finished_at=new Date().toISOString();await persist();console.log(JSON.stringify({status:receipt.status,receipt:receiptFile,validation:receipt.validation,failure_reason:receipt.failure_reason}));}
