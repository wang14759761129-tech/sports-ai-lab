import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, readdirSync, readFileSync, writeFileSync, copyFileSync } from 'node:fs';
import { resolve, join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
function walk(dir, prefix = '') {
  return readdirSync(dir, {withFileTypes:true}).flatMap(entry => {
    assert(!entry.isSymbolicLink(), 'No symlinks in delivery');
    const name = prefix + entry.name;
    return entry.isDirectory() ? walk(join(dir, entry.name), name + '/') : [name];
  });
}
export function inspectFile(name, bytes) {
  assert(!/(?:^|\/)(?:\.env|\.git|internal-review|qa)(?:[/.]|$)/i.test(name), 'Private file');
  assert(!/\.(?:db|sqlite\d*|map|pem|key|mp4|mov|exe)$/i.test(name), 'Non-static or private file');
  if (!/\.(?:js|css|html|json)$/.test(name)) return;
  const text = bytes.toString('utf8');
  assert(!/-----BEGIN .*PRIVATE KEY-----|sk-proj-[\w-]{20,}|AIza[\w-]{30,}/.test(text), 'Potential credential');
  assert(!/https?:\/\/(?:localhost|127\.0\.0\.1)(?::\d+)?/i.test(text), 'Loopback runtime reference');
  assert(!/[A-Z]:[\\/](?:Users|PTTI-Worktrees)[\\/]/i.test(text), 'Host path');
}
if (process.argv.includes('--self-test')) {
  for (const [name, data] of [['.env','secret'],['x.db','x'],['x.js','http://127.0.0.1:4183'],['x.json','C:/PTTI-Worktrees/private'],['x.js','sk-proj-'+'a'.repeat(25)]]) {
    assert.throws(() => inspectFile(name, Buffer.from(data)));
  }
  inspectFile('assets/app.js', Buffer.from('fetch("/data/public.json")'));
  console.log('PASS: five unsafe package cases rejected; same-origin data allowed');
} else {
  const sourceCommit = execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8',windowsHide:true}).trim();
  const dirty = execFileSync('git',['status','--porcelain','--untracked-files=normal'],{cwd:root,encoding:'utf8',windowsHide:true}).trim();
  assert.equal(dirty,'','Commit and clean the candidate before creating its release identity');
  execFileSync(process.execPath,[join(root,'node_modules/typescript/bin/tsc'),'-b'],{cwd:root,stdio:'inherit',windowsHide:true});
  execFileSync(process.execPath,[join(root,'node_modules/vite/bin/vite.js'),'build'],{cwd:root,stdio:'inherit',windowsHide:true});
  for (const script of ['check-goal14-public-isolation.mjs','check-goal16-media-v02.mjs','check-goal17-additions.mjs','check-goal19-watchability.mjs']) {
    execFileSync(process.execPath, [join(root,'scripts',script),'--built'], {cwd:root,stdio:'inherit',windowsHide:true});
  }
  const files = walk(join(root,'dist')).sort();
  const manifest = files.map(name => {
    const bytes = readFileSync(join(root,'dist',name));
    inspectFile(name, bytes);
    return {path:name, bytes:bytes.length, sha256:hash(bytes)};
  });
  const sourceFile = name => hash(readFileSync(join(root,name)));
  const releaseIdentity = {
    schema:'ptti.private-alpha-release-identity/0.1',
    source_commit:sourceCommit,
    source_worktree_clean:true,
    public_catalog_sha256:sourceFile('public/data/match-library-strict-public.json'),
    match_additions_sha256:sourceFile('public/data/goal17-official-match-video-additions.json'),
    playback_core_git_commit:'304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe',
    playback_core_source_sha256:'a59df06b688d75885bfb8ed51364e73edbaedaaa2b3746b5f7fd1d1edf67caf2',
    watch_routing_source_sha256:'1fa1e6100eb85f56cc51819d1e0cffaef500d6fa96bba616f6b281d60bb51619',
    dist_files_sha256:hash(JSON.stringify(manifest)),
  };
  const identityBytes = Buffer.from(JSON.stringify(releaseIdentity,null,2)+'\n');
  manifest.push({path:'release-identity.json',bytes:identityBytes.length,sha256:hash(identityBytes)});
  const id = hash(JSON.stringify(manifest));
  const destination = join(root,'.alpha-qa','goal20-2',id);
  mkdirSync(join(destination,'site'),{recursive:true});
  for (const file of manifest) {
    const target = join(destination,'site',file.path);
    mkdirSync(dirname(target),{recursive:true});
    if (file.path === 'release-identity.json') writeFileSync(target,identityBytes);
    else copyFileSync(join(root,'dist',file.path),target);
    assert.equal(hash(readFileSync(target)),file.sha256);
  }
  const receipt = {schema:'ptti.controlled-alpha-package/0.1',source_commit:sourceCommit,artifact_sha256:id,files:manifest,created_at:new Date().toISOString(),deployment:'NOT_DEPLOYED',access_control:'REQUIRES_HOST_CONFIGURATION_AND_UNAUTHENTICATED_TEST',browser_acceptance:'NOT_TESTED_FOR_THIS_PACKAGE',feedback:'Existing Watch form: local USER_REPORTED JSON export; no upload'};
  writeFileSync(join(destination,'BUILD_RECEIPT.json'),JSON.stringify(receipt,null,2)+'\n');
  console.log(JSON.stringify({destination,artifact_sha256:id,files:manifest.length,bytes:manifest.reduce((sum,f)=>sum+f.bytes,0)},null,2));
}
