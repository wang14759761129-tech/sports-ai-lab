import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdir, readFile, writeFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { repo, app, frozen, core, sourceGuard } from './prepare.mjs';
const git = args => execFileSync('git',args,{cwd:repo,windowsHide:true,maxBuffer:32*1024*1024});
const digest = bytes => createHash('sha1').update(Buffer.concat([Buffer.from(`blob ${bytes.length}\0`),bytes])).digest('hex');
function entries(commit) {
  const lines=git(['ls-tree','-r',commit,'--','products/ptti-web']).toString().trim().split('\n');
  return lines.map(line => { const m=/^(100644|100755) blob ([a-f0-9]{40})\t(products\/ptti-web\/.+)$/.exec(line); assert(m,'Only regular app files allowed'); return {mode:m[1],blob:m[2],file:m[3]}; });
}
export async function selectCandidate(configPath) {
  if(!configPath) return {name:'goal12-6',candidate:frozen,appPath:app,insight:false,buildPath:path.join(repo,'.alpha-qa/goal12-6-build'),runRoot:path.join(repo,'.alpha-qa/goal12-6-runs')};
  const config=JSON.parse((await readFile(path.resolve(configPath),'utf8')).replace(/^\uFEFF/,''));
  assert.deepEqual(Object.keys(config).sort(),['config_version','name','source_commit','core_commit','insight_onboarding'].sort());
  assert.equal(config.config_version,'ptti.qa-candidate/0.1');assert.equal(config.core_commit,core);
  assert(/^[a-f0-9]{40}$/.test(config.source_commit));assert(/^[a-z0-9-]+$/.test(config.name));assert.equal(typeof config.insight_onboarding,'boolean');
  git(['cat-file','-e',config.source_commit+'^{commit}']);
  return {name:config.name,candidate:config.source_commit,appPath:path.join(repo,'.alpha-qa/sources',config.source_commit,'products/ptti-web'),insight:config.insight_onboarding,buildPath:path.join(repo,'.alpha-qa',config.name+'-build'),runRoot:path.join(repo,'.alpha-qa',config.name+'-runs')};
}
export async function verifyCandidate(selected) {
  if(selected.appPath===app) {sourceGuard();return;}
  const expected=entries(selected.candidate); const allowed=new Set(expected.map(e=>e.file.slice('products/ptti-web/'.length)));
  for(const e of expected) assert.equal(digest(await readFile(path.join(selected.appPath,e.file.slice('products/ptti-web/'.length)))),e.blob,'Candidate source byte mismatch: '+e.file);
  async function scan(dir,prefix='') { for(const e of await readdir(dir,{withFileTypes:true})) { const rel=path.posix.join(prefix,e.name);if(rel==='node_modules')continue;assert(!e.isSymbolicLink(),'No source symlinks');if(e.isDirectory()) await scan(path.join(dir,e.name),rel);else assert(allowed.has(rel),'Unexpected candidate source file: '+rel); } }
  await scan(selected.appPath);
}
export function assertBuildDestination(selected, output) {
 assert.equal(path.resolve(output),selected.buildPath,'Configured candidate must use its own build directory');
}
export function verifyBuildReceipt(selected, receipt, actualFiles, pin) {
  if(receipt.contract_version==='ptti.qa-build-receipt/0.1') { assert.equal(receipt.status,'PASS','Build receipt is not PASS'); assert.equal(receipt.failure_reason,null,'Build receipt has failure reason'); }
  assert.equal(receipt.frozen,selected.candidate,'Receipt candidate mismatch');
  assert.equal(receipt.core,core,'Receipt Core mismatch');
  if(selected.insight) { assert.equal(receipt.candidate,selected.candidate); assert.equal(receipt.config_name,selected.name); }
  assert.equal(pin.coreCommit,core);assert.equal(receipt.core_source_sha256,pin.sourceHash,'Receipt Core source hash mismatch');
  assert.deepEqual(actualFiles,receipt.files,'Build file hash mismatch');
}
export async function materialize(selected) {
  assert.notEqual(selected.appPath,app,'Default frozen config already uses the unchanged QA checkout');
  await mkdir(selected.appPath,{recursive:true});
  for(const e of entries(selected.candidate)) {
    const dest=path.join(selected.appPath,e.file.slice('products/ptti-web/'.length));
    const bytes=git(['cat-file','blob',e.blob]);assert.equal(digest(bytes),e.blob);
    try { const old=await readFile(dest);assert(old.equals(bytes),'Refuse to overwrite different existing snapshot bytes'); }
    catch(err) {if(err.code!=='ENOENT')throw err;await mkdir(path.dirname(dest),{recursive:true});await writeFile(dest,bytes,{flag:'wx'});}
  }
  await verifyCandidate(selected);
}
if(process.argv.includes('--materialize')) {const selected=await selectCandidate(process.argv[process.argv.indexOf('--config')+1]);await materialize(selected);console.log('Exact Git source snapshot ready: '+selected.appPath);}
