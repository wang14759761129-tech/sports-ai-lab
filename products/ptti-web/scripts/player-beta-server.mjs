import http from 'node:http';
import path from 'node:path';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
export function createBetaServer(root, manifest) {
  const allowed = new Map(Object.entries(manifest.files).filter(([name])=>name.startsWith('site/')).map(([name,sha])=>['/'+name.slice(5),{name,sha}]));
  return http.createServer(async(req,res)=>{
    res.setHeader('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self' data: blob:; media-src blob:; connect-src 'self'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'");
    res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','no-referrer');res.setHeader('Cache-Control','no-store');
    const origin='http://127.0.0.1:'+req.socket.localPort;
    if(req.headers.host!==new URL(origin).host || (req.headers.origin && req.headers.origin!==origin) || (req.headers['sec-fetch-site'] && !['same-origin','none'].includes(req.headers['sec-fetch-site']))) {res.writeHead(403).end();return;}
    if(!['GET','HEAD'].includes(req.method)){res.writeHead(405).end();return;}
    let pathname;try{pathname=decodeURIComponent(new URL(req.url,origin).pathname);}catch{res.writeHead(400).end();return;}
    const item=allowed.get(pathname==='/'?'/index.html':pathname);
    if(!item){res.writeHead(404).end();return;}
    try {const bytes=await readFile(path.join(root,item.name));if(createHash('sha256').update(bytes).digest('hex')!==item.sha){res.writeHead(503).end('Candidate integrity failure');return;}
      const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.svg':'image/svg+xml','.webp':'image/webp'};
      res.setHeader('Content-Type',mime[path.extname(item.name)]||'application/octet-stream');res.end(req.method==='HEAD'?undefined:bytes);
    } catch {res.writeHead(503).end('Candidate file unavailable');}
  });
}
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const root=path.dirname(fileURLToPath(import.meta.url));const manifest=JSON.parse(await readFile(path.join(root,'manifest.json'),'utf8'));
  if(manifest.schema!=='ptti.player-beta-candidate/0.1')throw new Error('Invalid manifest');
  const port=Number(process.argv[2]||4199);if(!Number.isInteger(port)||port<1024||port>65535)throw new Error('Invalid port');
  const server=createBetaServer(root,manifest);server.on('error',e=>{console.error(e.code);process.exitCode=1;});
  server.listen(port,'127.0.0.1',()=>console.log(manifest.candidate_id+'\nhttp://127.0.0.1:'+port+'\nCtrl+C to stop. No browser is opened.'));
}
