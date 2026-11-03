import assert from 'node:assert/strict';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {selectCandidate,verifyCandidate,verifyBuildReceipt,assertBuildDestination} from '../goal12-6/candidate.mjs';
import {core,repo} from '../goal12-6/prepare.mjs';
const selected=await selectCandidate('qa/goal12-7/insight.config.json');
assert.equal(selected.candidate,'82580591ada031a5943b65756811ab2e2a1633d8');assert.equal(selected.insight,true);
const old=await selectCandidate();assert.equal(old.candidate,'e788e2f4c4ac0d6677155a2d3a43d0d22491f2a3');assert.notEqual(selected.appPath,old.appPath);assert.notEqual(selected.buildPath,old.buildPath);
assertBuildDestination(selected,selected.buildPath);assert.throws(()=>assertBuildDestination(selected,old.buildPath));assert.throws(()=>assertBuildDestination(selected,path.join(repo,'../outside')));
await verifyCandidate(selected);
const {verifyPinnedPlaybackCore}=await import(pathToFileURL(path.join(selected.appPath,'src/playback-core-pin.mjs')));const pin=verifyPinnedPlaybackCore(selected.appPath);assert.equal(pin.coreCommit,core);
const {prepareQuickSource,validateReviewTargets}=await import(pathToFileURL(path.join(selected.appPath,'src/review-targets.mjs')));
const source=await prepareQuickSource(await readFile(path.join(selected.appPath,'scripts/fixtures/review-targets/quick-input.json'),'utf8'));const targets=validateReviewTargets(JSON.parse(await readFile(path.join(selected.appPath,'scripts/fixtures/review-targets/targets.json'))),source);
assert.equal(source.points.length,19);assert.deepEqual(targets.review_targets.find(t=>t.subject_role==='player'&&t.observed_rally_stage==='END_AFTER_3_4_CONTACTS').point_ids.map(i=>i.split('/').at(-1)),['p002','p004','p006']);
// Synthetic receipts exercise the exact runtime verifier; these are not real build artifacts.
const fileHashes={'index.html':'unit-hash'};const good={frozen:selected.candidate,candidate:selected.candidate,config_name:selected.name,core,core_source_sha256:pin.sourceHash,files:fileHashes};verifyBuildReceipt(selected,good,fileHashes,pin);
let negatives=0;for(const mutate of [r=>r.frozen=old.candidate,r=>r.candidate=old.candidate,r=>r.core='0'.repeat(40),r=>r.core_source_sha256='0'.repeat(64),r=>r.config_name='wrong',r=>delete r.files,r=>r.files['index.html']='changed']){const bad=structuredClone(good);mutate(bad);assert.throws(()=>verifyBuildReceipt(selected,bad,fileHashes,pin));negatives++;}
const failedBuild={...good,contract_version:'ptti.qa-build-receipt/0.1',status:'FAIL',failure_reason:'unit build failure'};assert.throws(()=>verifyBuildReceipt(selected,failedBuild,fileHashes,pin));
const report={failed_build_receipt_rejected:true,status:'PASS',scope:'CONFIGURATION_AND_NODE_IDENTITY_TESTS_NO_BROWSER',candidate:selected.candidate,old_candidate:old.candidate,core,canonical_input_sha256:source.hash,receipt_rejection_cases:negatives,actual_build:'NOT_TESTED',chrome:'NOT_TESTED'};
const dir=path.join(repo,'.alpha-qa/goal12-7-config-tests');await mkdir(dir,{recursive:true});await writeFile(path.join(dir,'report.json'),JSON.stringify(report,null,2));console.log(`PASS: new/old config isolation, exact Git source snapshot/Core, actual19-point canonical identity, ${negatives} receipt rejection cases. Actual build and Chrome NOT_TESTED.`);
