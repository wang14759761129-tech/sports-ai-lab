import assert from 'node:assert/strict';
import http from 'node:http';
import { mkdir,writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { createBetaServer } from './player-beta-server.mjs';
const root=fileURLToPath(new URL('../.alpha-qa/goal49-server/',import.meta.url));await mkdir(root,{recursive:true});
await writeFile(root+'index.html','synthetic');const manifest={files:{'site/index.html':createHash('sha256').update('synthetic').digest('hex')}};
await mkdir(root+'site',{recursive:true});await writeFile(root+'site/index.html','synthetic');
const server=createBetaServer(root,manifest);await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
try{const base='http://127.0.0.1:'+server.address().port;
let res=await fetch(base+'/');assert.equal(res.status,200);assert.equal(await res.text(),'synthetic');assert.match(res.headers.get('content-security-policy'),/media-src blob:/);
assert.equal((await fetch(base+'/',{method:'HEAD'})).status,200);assert.equal((await fetch(base+'/',{method:'POST'})).status,405);assert.equal((await fetch(base+'/',{headers:{Origin:'https://example.com'}})).status,403);assert.equal(await new Promise((resolve,reject)=>{const req=http.get(base+'/',{headers:{Host:'evil.example'}},res=>{res.resume();resolve(res.statusCode);});req.on('error',reject);}),403);
for(const path of ['/manifest.json','/../server.mjs','/%2e%2e%2fserver.mjs','/.git/config','/missing','/index.html%00'])assert.equal((await fetch(base+path)).status,404);
assert.equal((await fetch(base+'/%zz')).status,400);
await writeFile(root+'site/index.html','tampered');assert.equal((await fetch(base+'/')).status,503);
console.log('PASS GOAL49 server: temporary loopback HTTP, read-only/host/origin/path allowlist, CSP, missing files and tamper rejection. No browser or real media tested.');
}finally{await new Promise(resolve=>server.close(resolve));}
