import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync, copyFileSync, rmSync } from 'node:fs';
import { resolve, dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadOptionalReviewEvidence } from '../products/ptti-web/src/optional-review-evidence.mjs';
import { verifyPlaybackSnapshot } from '../products/ptti-web/scripts/verify-playback-snapshot.mjs';
import { verifyReviewedText } from '../products/ptti-web/scripts/verify-reviewed-text.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
test('missing private provider degrades to unavailable without loading a file', async () => {
  assert.equal(await loadOptionalReviewEvidence(), null);
});
test('provider errors and incomplete payloads fail closed', async () => {
  await assert.rejects(loadOptionalReviewEvidence(async () => { throw Error('missing'); }), /missing/);
  await assert.rejects(loadOptionalReviewEvidence(async () => ({ evidenceRaw: '{}' })), /invalid-optional-review/);
  await assert.rejects(loadOptionalReviewEvidence(async () => ({ evidenceRaw: '{}', reportsRaw: 42 })), /invalid-optional-review/);
});
test('synthetic optional payload is preserved without promoting it to verified evidence', async () => {
  const data = { evidenceRaw: '{"classification":"SIMULATED_ONLY"}', reportsRaw: '{"classification":"SIMULATED_ONLY"}' };
  assert.deepEqual(await loadOptionalReviewEvidence(async () => data), data);
});
test('browser source has no import of private JSON', () => {
  const text = readFileSync(join(root, 'products/ptti-web/src/FanCatalogPage.tsx'), 'utf8');
  assert.doesNotMatch(text, /import\(['"]\.\/internal-review\//);
  assert.match(text, /loadOptionalReviewEvidence/);
});
test('real snapshot preserves pinned Playback source identity', () => {
  const identity = verifyPlaybackSnapshot(root);
  assert.equal(identity.source_commit, 'b54e1546b7e6c1edc69406582ed68e90988a1910');
  assert.equal(identity.identity_mode, 'VERIFIED_SOURCE_SNAPSHOT');
});

function fixture(change, action) {
  const qa = join(root, '.qa'); mkdirSync(qa, { recursive: true });
  const dir = mkdtempSync(join(qa, 'identity-'));
  try {
    const manifest = JSON.parse(readFileSync(join(root, 'provenance/playback-identity.json'), 'utf8'));
    for (const path of ['provenance/playback-identity.json', ...Object.keys(manifest.files)]) {
      mkdirSync(dirname(join(dir, path)), { recursive: true }); copyFileSync(join(root, path), join(dir, path));
    }
    change(dir); action(dir);
  } finally {
    assert(!relative(qa, dir).startsWith('..')); rmSync(dir, { recursive: true, force: true });
  }
}
test('changed Core rejects', () => fixture(d => writeFileSync(join(d, 'products/ptti/playback-core/src/index.ts'), '// changed'), d => assert.throws(() => verifyPlaybackSnapshot(d), /hash-mismatch/)));
test('changed routing adapter rejects', () => fixture(d => writeFileSync(join(d, 'products/ptti/playback-core/adapters/watchRoutingContract.ts'), '// changed'), d => assert.throws(() => verifyPlaybackSnapshot(d), /hash-mismatch/)));
test('missing source rejects', () => fixture(d => rmSync(join(d, 'products/ptti/playback-core/src/index.ts')), d => assert.throws(() => verifyPlaybackSnapshot(d))));
test('forged origin commit rejects', () => fixture(d => {
  const p = join(d, 'provenance/playback-identity.json'); const m = JSON.parse(readFileSync(p)); m.source_commit = '0'.repeat(40); writeFileSync(p, JSON.stringify(m));
}, d => assert.throws(() => verifyPlaybackSnapshot(d), /manifest-identity/)));
test('tampered hash manifest rejects', () => fixture(d => {
  const p = join(d, 'provenance/playback-identity.json'); const m = JSON.parse(readFileSync(p)); m.files['../../escape.ts'] = '0'.repeat(64); writeFileSync(p, JSON.stringify(m));
}, d => assert.throws(() => verifyPlaybackSnapshot(d), /manifest-identity/)));

function textFixture(change, action) {
  const qa = join(root, '.qa'); mkdirSync(qa, { recursive: true });
  const dir = mkdtempSync(join(qa, 'text-'));
  const logical = 'public/data/goal14-fan-content-strict-public.json';
  const manifestPath = 'provenance/public-text-identities.json';
  const manifest = JSON.parse(readFileSync(join(root, manifestPath)));
  const web = join(dir, 'products/ptti-web');
  try {
    mkdirSync(dirname(join(dir, manifestPath)), { recursive: true });
    copyFileSync(join(root, manifestPath), join(dir, manifestPath));
    mkdirSync(dirname(join(web, logical)), { recursive: true });
    copyFileSync(join(root, 'products/ptti-web', logical), join(web, logical));
    change(join(web, logical), dir);
    action(web, logical, manifest.files[logical].legacy_expected_sha256);
  } finally { assert(!relative(qa, dir).startsWith('..')); rmSync(dir, { recursive: true, force: true }); }
}
test('explicit LF and CRLF public JSON identities pass', () => {
  textFixture(() => {}, (w, p, h) => assert.equal(verifyReviewedText(w, p, h), true));
  textFixture(p => writeFileSync(p, readFileSync(p, 'utf8').replace(/\r?\n/g, '\r\n')), (w, p, h) => assert.equal(verifyReviewedText(w, p, h), true));
});
test('public text content modification rejects', () => textFixture(p => writeFileSync(p, readFileSync(p, 'utf8') + ' '), (w, p, h) => assert.throws(() => verifyReviewedText(w, p, h), /byte-mismatch/)));
test('invalid UTF-8 rejects', () => textFixture(p => writeFileSync(p, Buffer.from([0xff, 0xfe])), (w, p, h) => assert.throws(() => verifyReviewedText(w, p, h))));
test('missing public text rejects', () => textFixture(p => rmSync(p), (w, p, h) => assert.throws(() => verifyReviewedText(w, p, h))));
test('wrong or unregistered public pin rejects', () => textFixture(() => {}, (w, p) => {
  assert.throws(() => verifyReviewedText(w, p, '0'.repeat(64)), /unregistered/);
  assert.throws(() => verifyReviewedText(w, '../escape', '0'.repeat(64)), /unregistered/);
}));
