import assert from 'node:assert/strict';
import { readdir, readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const distRoot = path.join(projectRoot, 'dist');

async function collectFiles(directory, prefix = '') {
  const result = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const relative = path.posix.join(prefix, entry.name);
    if (entry.isSymbolicLink()) throw new Error(`Symlink is not allowed in preview output: ${relative}`);
    if (entry.isDirectory()) result.push(...await collectFiles(path.join(directory, entry.name), relative));
    else if (entry.isFile()) result.push(relative);
    else throw new Error(`Unexpected filesystem entry in preview output: ${relative}`);
  }
  return result;
}

const files = (await collectFiles(distRoot)).sort();
assert(files.includes('_headers'), 'Cloudflare Pages _headers is missing from dist/');
assert(files.includes('index.html'), 'Production index.html is missing from dist/');
assert(files.includes('data/cinema.json'), 'Public match source data is missing from dist/');
for (const file of files) {
  const allowed = file === '_headers'
    || file === 'index.html'
    || file === 'data/cinema.json'
    || /^assets\/index-[\w-]+\.(?:js|css)$/.test(file);
  assert(allowed, `Unexpected file in public preview package: ${file}`);
  assert(!/\.(?:sqlite3?|db|mp4|m4v|mov|webm|mkv|pem|key|p12|pfx|env)$/i.test(file), `Private/binary asset is not allowed: ${file}`);
}

const contentsByFile = await Promise.all(files.map(async (file) => {
  const contents = await readFile(path.join(distRoot, file), 'utf8');
  const { size } = await stat(path.join(distRoot, file));
  assert(size < 25 * 1024 * 1024, `Cloudflare Pages file-size limit exceeded: ${file}`);
  return [file, contents];
}));
const contents = new Map(contentsByFile);
const allText = contentsByFile.map(([, value]) => value).join('\n');
for (const [label, pattern] of [
  ['private key block', /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/],
  ['OpenAI project key', /sk-proj-[A-Za-z0-9_-]{20,}/],
  ['Google API key', /AIza[0-9A-Za-z_-]{30,}/],
  ['Cloudflare API token assignment', /(?:CLOUDFLARE_API_TOKEN|CF_API_TOKEN)\s*[:=]\s*["']?[A-Za-z0-9_-]{20,}/i],
]) assert(!pattern.test(allText), `Potential ${label} found in dist/`);

const headers = contents.get('_headers');
const csp = headers.match(/^\s*Content-Security-Policy:\s*(.+)$/mi)?.[1] ?? '';
assert(csp, 'CSP header is missing from _headers');
for (const directive of ["default-src 'self'", "script-src 'self'", "style-src 'self'", "connect-src 'self'", "frame-src 'none'", "media-src 'none'"]) {
  assert(csp.includes(directive), `CSP is missing required directive: ${directive}`);
}
assert(!/\b(?:unsafe-inline|unsafe-eval)\b/.test(csp), 'CSP must not allow unsafe inline code or eval');

const html = contents.get('index.html');
assert(!/<(?:iframe|video|audio)\b/i.test(html), 'Preview HTML must not embed external media');
assert(!/\son[a-z]+\s*=/i.test(html), 'Inline event handlers are not allowed in preview HTML');
for (const [, assetUrl] of html.matchAll(/<(?:script|link)\b[^>]*(?:src|href)=["']([^"']+)["'][^>]*>/gi)) {
  assert(!/^https?:\/\//i.test(assetUrl), `Production page references a remote script/stylesheet: ${assetUrl}`);
}
assert(!/<(?:img|iframe|video|audio)\b/i.test(allText), 'Preview bundle contains an embedded image/media/frame element');

const matchData = JSON.parse(contents.get('data/cinema.json'));
assert(Array.isArray(matchData), 'Cinema source must remain a JSON list');
assert(matchData.every((record) => !record.thumbnailUrl && !record.posterUrl && !record.videoFile), 'Cinema source must not expose unapproved covers or hosted video files');

const totalBytes = contentsByFile.reduce((sum, [file]) => sum + Buffer.byteLength(contents.get(file)), 0);
console.log(`Preview package PASS: ${files.length} static files, ${(totalBytes / 1024).toFixed(1)} KiB total.`);
console.log(`Files: ${files.join(', ')}`);
console.log('Headers: _headers present; same-origin CSP and static security directives verified (HTTP response not tested).');
console.log('Privacy/content: no database, video, credential marker, remote script/style, embed, or unapproved cover field found.');
