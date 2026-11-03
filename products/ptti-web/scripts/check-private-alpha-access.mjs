import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';

export function deniedByAccess(response) {
  if (response.status === 403) return true;
  if (![301, 302, 303, 307, 308].includes(response.status)) return false;
  const location = response.headers.get('location');
  if (!location) return false;
  try { return new URL(location).hostname.endsWith('.cloudflareaccess.com'); }
  catch { return false; }
}

export async function probeAnonymous(origin, paths, fetcher = fetch) {
  assert.equal(new URL(origin).protocol, 'https:', 'Only HTTPS remote Access hosts are accepted');
  const results = [];
  for (const path of paths) {
    assert(path.startsWith('/') && !path.startsWith('//'));
    const response = await fetcher(new URL(path, origin), {redirect:'manual', credentials:'omit', cache:'no-store'});
    results.push({path, status:response.status, denied:deniedByAccess(response)});
  }
  if (results.some(result => !result.denied)) throw new Error(`ACCESS_BLOCKED: ${JSON.stringify(results.filter(result => !result.denied))}`);
  return results;
}

if (process.argv.includes('--self-test')) {
  const mock = (status, location = null) => ({status, headers:{get: () => location}});
  assert(deniedByAccess(mock(302,'https://team.cloudflareaccess.com/cdn-cgi/access/login')));
  assert(deniedByAccess(mock(403)));
  for (const response of [mock(200),mock(302,'https://public.example/'),mock(404),mock(302)]) assert(!deniedByAccess(response));
  await assert.rejects(probeAnonymous('https://preview.example/', ['/','/assets/app.js'], async () => mock(200)), /ACCESS_BLOCKED/);
  console.log('PASS: anonymous product bytes and unrelated redirects fail closed');
} else if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  const origin = process.env.PTTI_PRIVATE_ALPHA_ORIGIN;
  const paths = process.env.PTTI_PRIVATE_ALPHA_PROBE_PATHS?.split(',').filter(Boolean);
  if (!origin || !paths?.length) throw new Error('Set PTTI_PRIVATE_ALPHA_ORIGIN and comma-separated PTTI_PRIVATE_ALPHA_PROBE_PATHS');
  console.log(JSON.stringify(await probeAnonymous(origin, paths),null,2));
}
