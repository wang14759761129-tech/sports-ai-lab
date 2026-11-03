import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const root=process.env.PTTI_FRONTEND_DEPENDENCIES_ROOT;
const require=createRequire(root?`${root}/package.json`:import.meta.url);
const {createServer:createVite}=await import(pathToFileURL(require.resolve('vite')));
const received=[];
const backend=createServer((req,res)=>{received.push({host:req.headers.host,origin:req.headers.origin});res.setHeader('Content-Type','application/json');res.end('[]')});
await new Promise(resolve=>backend.listen(0,'127.0.0.1',resolve));
process.env.PTTI_QA_API_TARGET=`http://127.0.0.1:${backend.address().port}`;
let vite;
try{
 vite=await createVite({configFile:false,server:{host:'127.0.0.1',port:0,proxy:{'/api':process.env.PTTI_QA_API_TARGET}},logLevel:'error'});await vite.listen();
 const oldOrigin=`http://127.0.0.1:${vite.httpServer.address().port}`;
 await fetch(`${oldOrigin}/api/video-evidence/videos`,{headers:{Origin:oldOrigin}});
 assert.equal(received.at(-1).host,new URL(process.env.PTTI_QA_API_TARGET).host);
 assert.equal(received.at(-1).origin,oldOrigin);
 assert.notEqual(`http://${received.at(-1).host}`,received.at(-1).origin,'Legacy string proxy must reproduce the mismatched Host/Origin');
 console.log('Legacy string proxy reproduced Host/Origin mismatch');await vite.close();
 vite=await createVite({configFile:'vite.config.ts',server:{host:'127.0.0.1',port:0},logLevel:'error'});await vite.listen();
 const origin=`http://127.0.0.1:${vite.httpServer.address().port}`;
 assert.equal((await fetch(`${origin}/api/video-evidence/videos`,{headers:{Origin:origin}})).status,200);
 assert.deepEqual(received.at(-1),{host:new URL(origin).host,origin},'Proxy must retain matching browser Host/Origin');
 await fetch(`${origin}/api/video-evidence/videos`,{headers:{Origin:'https://evil.example'}});
 assert.equal(received.at(-1).origin,'https://evil.example','Foreign Origin must reach the backend unchanged and be rejected there');
 console.log('Real Vite proxy: same-origin Host retained; foreign Origin unchanged; isolated dynamic backend port passed');
}finally{await vite?.close();await new Promise(resolve=>backend.close(resolve))}
