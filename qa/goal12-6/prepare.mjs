import { execFileSync, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {assertPublicArtifact} from './artifact-isolation.mjs';
export const frozen = 'e788e2f4c4ac0d6677155a2d3a43d0d22491f2a3';
export const core = '304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe';
export const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
export const app = path.join(repo, 'products/ptti-web');
export const hash = bytes => createHash('sha256').update(bytes).digest('hex');
export function sourceGuard() {
  // No runtime dependence on another worktree; compare QA app files with the frozen commit.
  execFileSync('git', ['diff', '--exit-code', frozen, '--', 'products/ptti-web'], {cwd:repo, windowsHide:true});
  const extra=execFileSync('git',['ls-files','--others','--exclude-standard','products/ptti-web'],{cwd:repo,encoding:'utf8',windowsHide:true}).trim();
  if(extra) throw Error('Untracked application files require review: '+extra);
}
export function memory() {
 const r=spawnSync('powershell',['-NoProfile','-Command','(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'],{encoding:'utf8',windowsHide:true,timeout:3000});
 const gib=Number(r.stdout.trim())/1048576;
 if(r.status!==0 || !r.stdout.trim() || !Number.isFinite(gib)) throw Error('BLOCKED: RAM measurement unavailable');
 return gib;
}
export async function fileHashes(dir, prefix='') {
 const out={}; for(const e of await readdir(path.join(dir,prefix),{withFileTypes:true})) {
  const p=path.posix.join(prefix,e.name); if(e.isDirectory()) Object.assign(out,await fileHashes(dir,p)); else out[p]=hash(await readFile(path.join(dir,p)));
 } return out;
}
export async function restoreQaCoreBytes() {
 // Windows autocrlf can alter checkout bytes. Restore only this QA worktree's
 // tracked blob, after matching SOURCE_PIN; never rewrite the frozen candidate.
 const relative='products/ptti-web/vendor/playback-core-304eb661/src/index.ts';
 const pin=JSON.parse(await readFile(path.join(app,'vendor/playback-core-304eb661/SOURCE_PIN.json')));
 const original=execFileSync('git',['show',`${frozen}:${relative}`],{cwd:repo,windowsHide:true});
 if(hash(original)!==pin.source_sha256) throw Error('Frozen Core blob does not match SOURCE_PIN');
 const file=path.join(repo,relative); if(hash(await readFile(file))!==pin.source_sha256) await writeFile(file,original);
}
export async function prepare(output, selected = null, logBuild = null) {
 const buildApp=selected?.appPath ?? app;
 if(selected) { const {verifyCandidate}=await import('./candidate.mjs'); await verifyCandidate(selected); } else sourceGuard(); if(memory()<3) throw Error('BLOCKED: prepare build requires 3 GiB available; Chrome hard guard remains 2.5 GiB');
 if(!selected || selected.appPath===app) await restoreQaCoreBytes();
 const {verifyPinnedPlaybackCore}=await import('../../products/ptti-web/src/playback-core-pin.mjs');
 const pin=verifyPinnedPlaybackCore(buildApp); if(pin.coreCommit!==core) throw Error('Wrong Core');
 const out=path.resolve(output); if(selected) { const {assertBuildDestination}=await import('./candidate.mjs'); assertBuildDestination(selected,out); } const allowed=path.join(repo,'.alpha-qa')+path.sep;
 if(!out.startsWith(allowed)) throw Error('Output must be within QA worktree .alpha-qa');
 await mkdir(out,{recursive:true});
 const result=spawnSync(process.execPath,[path.join(buildApp,'node_modules/vite/bin/vite.js'),'build','--mode','local-rc'],{cwd:buildApp,windowsHide:true,encoding:'utf8',timeout:120000,maxBuffer:4*1024*1024,env:{...process.env,PTTI_RC_BUILD_OUT:path.join(out,'dist'),PTTI_PLAYBACK_CORE_SOURCE:pin.sourcePath}});
 const buildLog=(result.stdout||'')+(result.stderr||''); if(logBuild)logBuild(buildLog); process.stdout.write(result.stdout||'');process.stderr.write(result.stderr||'');
 if(result.status!==0) throw Error('QA local-RC build failed: '+(result.error?.message??result.status));
 const files=await fileHashes(path.join(out,'dist'));
 const publicDoc=JSON.parse(await readFile(path.join(out,'dist/data/match-library-strict-public.json')));
 if(publicDoc.video_sources.length!==0) throw Error('public0 violated');
 for(const name of Object.keys(files)) assertPublicArtifact(name,await readFile(path.join(out,'dist',name)));
 const fixturePaths=['quick-input.json','targets.json']; const fixtureHashes={};
 for(const f of fixturePaths) fixtureHashes[f]=hash(await readFile(path.join(buildApp,'scripts/fixtures/review-targets',f)));
 if(selected) { const {verifyCandidate}=await import('./candidate.mjs'); await verifyCandidate(selected); }
 await writeFile(path.join(out,'qa-build.json'),JSON.stringify({scope:'LOCAL_QA_ONLY_NOT_RELEASE_ARTIFACT',frozen:selected?.candidate ?? frozen,candidate:selected?.candidate ?? frozen,config_name:selected?.name ?? 'goal12-6',core,core_source_sha256:pin.sourceHash,files,fixtureHashes},null,2));
}
if(process.argv[1]===fileURLToPath(import.meta.url)) {
 if(!process.argv[2]) throw Error('Usage: node qa/goal12-6/prepare.mjs .alpha-qa/goal12-6-build');
 const index=process.argv.indexOf('--config');
 const selected=index<0?null:await (await import('./candidate.mjs')).selectCandidate(process.argv[index+1]);
 await prepare(process.argv[2],selected);
}
