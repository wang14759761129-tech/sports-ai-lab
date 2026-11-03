import assert from 'node:assert/strict';
import { createBetaServer } from './player-beta-server.mjs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { readFile, writeFile, readdir, mkdir, cp, lstat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const project=fileURLToPath(new URL('../',import.meta.url));
const git=(...args)=>execFileSync('git',args,{cwd:project,encoding:'utf8',windowsHide:true}).trim();
assert.equal(git('status','--porcelain'),'','Commit or preserve changes before building a candidate; never auto-stash.');
assert.equal(git('branch','--show-current'),'codex/ptti-goal14-fan-experience');
const head=git('rev-parse','HEAD');const id='PTTI-GOAL49-S-SOURCE-VALIDATED-'+head.slice(0,12);
const parent=path.join(project,'.alpha-qa','goal49');await mkdir(parent,{recursive:true});
const output=path.join(parent,id);await mkdir(output,{recursive:false});
// Existing directories are never overwritten. Builds use the established production guards.
try {execFileSync(process.env.ComSpec||'cmd.exe',['/d','/s','/c','npm run build'],{cwd:project,stdio:'inherit',windowsHide:true});
  assert.equal(git('rev-parse','HEAD'),head);assert.equal(git('status','--porcelain'),'');
  await cp(path.join(project,'dist'),path.join(output,'site'),{recursive:true,errorOnExist:true,force:false});
  await cp(path.join(project,'scripts/player-beta-server.mjs'),path.join(output,'server.mjs'));
  await cp(path.join(project,'scripts/player-beta-checklist.md'),path.join(output,'START-HERE.md'));
  await writeFile(path.join(output,'Start-Player-Beta.cmd'),'@echo off\r\ncd /d "%~dp0"\r\nnode server.mjs 4199\r\npause\r\n');
  const files={};let bytes=0;
  async function walk(dir,prefix=''){for(const entry of await readdir(dir,{withFileTypes:true})){const name=prefix+entry.name;const target=path.join(dir,entry.name);assert(!(await lstat(target)).isSymbolicLink());if(entry.isDirectory())await walk(target,name+'/');else{assert(!/\.(mp4|mov|sqlite|db|env|map)$/i.test(name));const data=await readFile(target);files[name]=createHash('sha256').update(data).digest('hex');bytes+=data.length;if(/\.(js|json|html|css)$/.test(name))assert(!/C:\\PTTI-Worktrees|PRIVATE-DO-NOT-EXPORT/.test(data.toString()));}}}
  await walk(output);
  const manifest={schema:'ptti.player-beta-candidate/0.1',candidate_id:id,source_commit:head,branch:git('branch','--show-current'),classification:'SOURCE-VALIDATED CANDIDATE',release_approved:false,published:false,created_at:new Date().toISOString(),node_required:'20+',catalog:{matches:8,sources:19,athletes:8,verification:'GOAL45_BUILD_GUARD'},checks:{typescript:'PASS',production_build:'PASS',offline_regression:'PASS',loopback_http:'PASS_STATIC_FILES_ONLY',browser_gui:'NOT_TESTED',real_mp4:'NOT_TESTED',external_video:'NOT_TESTED',recruited:'0/5',tested:'0/5'},package_bytes_excluding_manifest:bytes,files};
  const server=createBetaServer(output,manifest);
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  try {const base='http://127.0.0.1:'+server.address().port;
    for(const [name,sha] of Object.entries(files).filter(([n])=>n.startsWith('site/'))){const res=await fetch(base+'/'+name.slice(5));assert.equal(res.status,200);assert.equal(createHash('sha256').update(Buffer.from(await res.arrayBuffer())).digest('hex'),sha);}
    assert.equal((await fetch(base+'/manifest.json')).status,404);
    assert.equal((await fetch(base+'/',{method:'POST'})).status,405);
    assert.equal((await fetch(base+'/',{headers:{Origin:'https://example.com'}})).status,403);
  } finally {await new Promise(resolve=>server.close(resolve));}
  await writeFile(path.join(output,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');console.log('CANDIDATE='+output);console.log('PACKAGE_BYTES_EXCLUDING_MANIFEST='+bytes);
} catch(error) {await writeFile(path.join(output,'BUILD-FAILED.txt'),'Candidate incomplete; do not use. '+String(error));throw error;}
