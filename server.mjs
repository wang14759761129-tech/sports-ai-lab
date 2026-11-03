import http from 'node:http';
import {readFile} from 'node:fs/promises';
const allowed=new Set(['index.html','style.css','app.mjs','state.mjs','art.svg']);
const mime={html:'text/html; charset=utf-8',css:'text/css',mjs:'text/javascript',svg:'image/svg+xml'};
const server=http.createServer(async(req,res)=>{try{const path=new URL(req.url,'http://localhost').pathname;const name=path==='/'?'index.html':path.slice(1);if(!allowed.has(name)){res.writeHead(404).end();return}res.writeHead(200,{'Content-Type':mime[name.split('.').pop()],'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});res.end(await readFile(new URL('./dist/'+name,import.meta.url)))}catch{res.writeHead(500).end('Preview unavailable')}});
server.listen(4186,'127.0.0.1',()=>console.log('PTTI GEX local preview: http://127.0.0.1:4186'));
