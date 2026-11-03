import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { readFile } from 'node:fs/promises';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let state;
try { state = JSON.parse(await readFile(path.join(root, 'logs/control.json'), 'utf8')); }
catch (e) { if(e.code === 'ENOENT') { console.log('Candidate is already stopped.'); process.exit(0); } throw e; }
const manifest = JSON.parse(await readFile(path.join(root,'manifest.json'),'utf8'));
if(state.artifact !== manifest.artifact_id || !/^\\\\\.\\pipe\\ptti-ic-[a-f0-9]{32}$/.test(state.pipe) || !/^[a-f0-9]{64}$/.test(state.token)) throw new Error('Invalid candidate control identity. Nothing stopped.');
await new Promise((resolve,reject)=>{
 const socket = net.createConnection(state.pipe);
 const timer=setTimeout(()=>{socket.destroy();reject(new Error('Candidate stop timed out.'));},5000);
 socket.on('connect',()=>socket.write(state.token+'\n'));
 let reply='';
 socket.on('data',data=>{reply+=data;});
 socket.on('end',()=>{clearTimeout(timer); if(reply==='STOPPED')resolve();else reject(new Error('Candidate refused stop.'));});
 socket.on('error',e=>{clearTimeout(timer); if(['ENOENT','ECONNREFUSED'].includes(e.code)) resolve(); else reject(e);});
});
console.log('Candidate stopped; video/session memory released.');
