import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { inspectPublicProjection } from '../src/public-projection.mjs';

const catalogPath = resolve(process.cwd(), 'public/data/match-library-strict-public.json');

if (process.argv.includes('--self-test')) {
  const safe = { contract_version: 'ptti.match-library-index/0.1', view: 'STRICT_PUBLIC', source_manifest: [], quality_summary: { public_match_count: 1 } };
  assert.deepEqual(inspectPublicProjection(safe), []);
  assert.deepEqual(inspectPublicProjection(safe, '{"url":"https://www.youtube.com/watch?v=example"}'), [], 'web URLs are not misclassified as Windows drive paths');
  assert.match(inspectPublicProjection({ ...safe, source_manifest: { file: 'internal-review.json' } })[0], /source_manifest is not an array/);
  assert.match(inspectPublicProjection({ ...safe, quality_summary: [] })[0], /quality_summary is not an object/);
  assert.match(inspectPublicProjection({ ...safe, source_manifest: [{ file: 'products/generated/internal-review.json' }] })[0], /internal source_manifest/);
  assert.match(inspectPublicProjection({ ...safe, quality_summary: { goal11_internal_video_source_count: 1 } })[0], /internal review\/build metric/);
  assert.match(inspectPublicProjection(safe, '{"path":"C:\\private\\file"}')[0], /absolute Windows path/);
  console.log('PASS: strict-public projection preflight accepts minimal public metadata and rejects internal paths, audit counters, and Windows paths.');
} else {
  const raw = readFileSync(catalogPath, 'utf8');
  const catalog = JSON.parse(raw);
  const sha256 = createHash('sha256').update(raw, 'utf8').digest('hex');
  const issues = inspectPublicProjection(catalog, raw);
  console.log(`catalog_sha256=${sha256}`);
  if (issues.length) {
    console.error(`BLOCKED PUBLIC_PACKAGE_BLOCKED: ${issues.join('; ')}`);
    process.exitCode = 2;
  } else {
    console.log('PASS: strict-public package metadata contains no internal source or audit fields.');
  }
}
