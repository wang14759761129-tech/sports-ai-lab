import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { readFile, appendFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const manifestBytes = await readFile(path.join(root, 'manifest.json'));
const manifest = JSON.parse(manifestBytes);
if (manifest.contract_version !== 'ptti.web-rc-manifest/0.1') throw new Error('Unsupported RC manifest');
const portArg = process.argv.indexOf('--port');
const port = portArg === -1 ? manifest.default_port : Number(process.argv[portArg + 1]);
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Invalid local port');
const manifestSha = createHash('sha256').update(manifestBytes).digest('hex');
await mkdir(path.join(root, 'logs'), { recursive: true });
const log = text => appendFile(path.join(root, 'logs', 'server.log'), `${new Date().toISOString()} ${text}\n`);
const csp = "default-src 'none'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self' data: blob:; media-src blob:; connect-src 'self'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'";
const site = new Map(Object.entries(manifest.files).filter(([name]) => name.startsWith('site/')).map(([name, sha]) => ['/' + name.slice(5), { name, sha }]));
const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8' };
const server = http.createServer(async (req, res) => {
  res.setHeader('Content-Security-Policy', csp); res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY'); res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()');
  res.setHeader('Cross-Origin-Resource-Policy', 'same-origin'); res.setHeader('Cache-Control', 'no-store');
  if (req.headers.host !== `127.0.0.1:${port}` || (req.headers.origin && req.headers.origin !== `http://127.0.0.1:${port}`) || (req.headers['sec-fetch-site'] && req.headers['sec-fetch-site'] !== 'same-origin' && req.headers['sec-fetch-site'] !== 'none')) { res.writeHead(403).end(); return; }
  if (!['GET','HEAD'].includes(req.method)) { res.writeHead(405).end(); return; }
  let pathname; try { pathname = decodeURIComponent(new URL(req.url, `http://127.0.0.1:${port}`).pathname); } catch { res.writeHead(400).end(); return; }
  try {
    if (pathname === '/__ptti/health.json') {
      res.setHeader('Content-Type', 'application/json; charset=utf-8');
      res.end(JSON.stringify({ app: 'ptti-portable-web-rc', artifact_id: manifest.artifact_id, manifest_sha256: manifestSha, san_head: manifest.san.commit, playback_head: manifest.playback.commit, catalog: 'STRICT_PUBLIC', public_matches: 0, private_sources: 0, port })); return;
    }
    let name, expected;
    if (pathname === '/__ptti/demo-review.json') { name = 'app/demo-review.json'; expected = manifest.files[name]; }
    else { const file = site.get(pathname === '/' ? '/index.html' : pathname); if (file) { name = file.name; expected = file.sha; } }
    if (!name || !expected) { res.writeHead(404).end(); return; }
    const bytes = await readFile(path.join(root, name));
    if (createHash('sha256').update(bytes).digest('hex') !== expected) { res.writeHead(503).end('RC integrity check failed. See logs.'); await log(`INTEGRITY_FAIL ${name}`); return; }
    res.setHeader('Content-Type', mime[path.extname(name)] || 'application/octet-stream');
    if (req.method === 'HEAD') res.end(); else res.end(bytes);
  } catch (error) { res.writeHead(503).end('Local RC file unavailable.'); await log(`ERROR ${error.message}`); }
});
server.on('error', async error => { await log(`START_FAILED ${error.code}: ${error.message}`); process.exitCode = 1; });
server.listen(port, '127.0.0.1', async () => { await log(`READY artifact=${manifest.artifact_id} port=${port} san=${manifest.san.commit} core=${manifest.playback.commit}`); });
