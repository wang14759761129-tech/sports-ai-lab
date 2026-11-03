import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { deflateSync } from 'node:zlib';
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import mediaIndex from '../src/approved-public-media.json' with { type: 'json' };
import { consumeFanCatalog } from '../src/fan-catalog.mjs';
import { createPublicMediaIndex, evaluateGoal16Candidate, validatePublicMediaAsset } from '../src/fan-media.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const manifestPath = join(root, 'scripts/fixtures/goal16-media/main-public-media-review.json');
const schemaPath = join(root, 'scripts/fixtures/goal16-media/main-public-media-schema.json');
const expectedManifestSha = 'e533ceeae42138a1bcf45099f0ea53180a29a7f21366e5f59d6ce8bebd837a49';
const expectedSchemaSha = '4eb14ddc583bf1f5bd15db298d6ca93d07a59e0d70f212788a713d51aabb8a6a';
const catalogPath = join(root, 'public/data/match-library-strict-public.json');
const catalog = consumeFanCatalog(JSON.parse(readFileSync(catalogPath, 'utf8')));
const manifestBytes = readFileSync(manifestPath);
const schemaBytes = readFileSync(schemaPath);
const manifest = JSON.parse(manifestBytes.toString('utf8'));
const schema = JSON.parse(schemaBytes.toString('utf8'));

function verifyIndexBytes(index, publicRoot) {
  const issues = [];
  const safeRoot = resolve(publicRoot);
  for (const asset of index.assets) for (const rendition of asset.renditions) {
    const file = resolve(safeRoot, `.${rendition.src}`);
    if (!file.startsWith(`${safeRoot}${sep}`)) { issues.push(`${asset.asset_id}:MEDIA_PATH_ESCAPES_PUBLIC_ROOT`); continue; }
    try {
      const bytes = readFileSync(file);
      const digest = createHash('sha256').update(bytes).digest('hex');
      if (digest !== rendition.sha256.toLowerCase()) issues.push(`${asset.asset_id}:MEDIA_SHA256_MISMATCH:${rendition.src}`);
      if (!matchesMime(bytes, rendition.mime_type) || !extensionMatches(file, rendition.mime_type)) issues.push(`${asset.asset_id}:MEDIA_MIME_MISMATCH:${rendition.src}`);
    } catch {
      issues.push(`${asset.asset_id}:MEDIA_FILE_MISSING:${rendition.src}`);
    }
  }
  return issues;
}

function matchesMime(bytes, mime) {
  if (mime === 'image/png') return bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
  if (mime === 'image/jpeg') return bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
  if (mime === 'image/webp') return bytes.length >= 12 && bytes.toString('ascii', 0, 4) === 'RIFF' && bytes.toString('ascii', 8, 12) === 'WEBP';
  if (mime === 'image/avif') return bytes.length >= 12 && bytes.toString('ascii', 4, 8) === 'ftyp' && /avif|avis/.test(bytes.toString('ascii', 8, Math.min(bytes.length, 64)));
  return false;
}

function extensionMatches(path, mime) {
  const extension = path.slice(path.lastIndexOf('.')).toLowerCase();
  return (mime === 'image/png' && extension === '.png')
    || (mime === 'image/jpeg' && ['.jpg', '.jpeg'].includes(extension))
    || (mime === 'image/webp' && extension === '.webp')
    || (mime === 'image/avif' && extension === '.avif');
}

function pngChunk(type, data) {
  const name = Buffer.from(type, 'ascii');
  const length = Buffer.alloc(4); length.writeUInt32BE(data.length);
  const crcInput = Buffer.concat([name, data]);
  let crc = 0xffffffff;
  for (const byte of crcInput) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  const crcBuffer = Buffer.alloc(4); crcBuffer.writeUInt32BE((crc ^ 0xffffffff) >>> 0);
  return Buffer.concat([length, crcInput, crcBuffer]);
}

function selfAuthoredTestPng() {
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const header = Buffer.alloc(13);
  header.writeUInt32BE(1, 0); header.writeUInt32BE(1, 4); header[8] = 8; header[9] = 6;
  const pixel = Buffer.from([0, 239, 51, 64, 255]);
  return Buffer.concat([signature, pngChunk('IHDR', header), pngChunk('IDAT', deflateSync(pixel)), pngChunk('IEND', Buffer.alloc(0))]);
}

assert.equal(createHash('sha256').update(manifestBytes).digest('hex'), expectedManifestSha, 'Main GOAL16 manifest snapshot identity changed');
assert.equal(createHash('sha256').update(schemaBytes).digest('hex'), expectedSchemaSha, 'Main GOAL16 schema snapshot identity changed');
assert.equal(schema.$id, 'https://ptti.invalid/contracts/public-media-manifest-v0.1.schema.json');
assert.equal(schema.properties.contract_version.const, 'ptti.public-media-manifest/0.1');
assert.equal(schema.properties.view.const, 'INTERNAL_MEDIA_RIGHTS_REVIEW');
assert.equal(schema.$defs.asset.properties.display_permission.const, 'NOT_CLEARED');
assert.equal(manifest.contract_version, 'ptti.public-media-manifest/0.1');
assert.equal(manifest.view, 'INTERNAL_MEDIA_RIGHTS_REVIEW');
assert.equal(manifest.assets.length, 9);
assert.deepEqual(manifest.strict_public_projection.eligible_asset_ids, []);
assert.equal(manifest.strict_public_projection.count, 0);
assert(manifest.assets.every((asset) => asset.display_permission === 'NOT_CLEARED'));
assert(manifest.assets.every((asset) => asset.match_id === null && asset.match_link_status.startsWith('NOT_LINKED_')));
assert(manifest.assets.every((asset) => asset.media_sha256 === null && asset.media_sha256_status === 'NOT_COMPUTED_NO_DOWNLOAD'));

const publicIndex = createPublicMediaIndex(mediaIndex, catalog);
assert.equal(publicIndex.assets.length, 0, 'no GOAL16 review candidate is eligible for ordinary Fan rendering');
assert.equal(publicIndex.athletes.size, 0);
assert.equal(publicIndex.matches.size, 0);
assert.deepEqual(verifyIndexBytes(publicIndex, join(root, 'public')), [], 'every released rendition must exist locally and match its file SHA-256');
assert.deepEqual(validatePublicMediaAsset(manifest.assets[0], catalog).includes('DISPLAY_PERMISSION_NOT_CLEARED'), true);

// Candidate-level negative cases exercise each critical fail-closed rule with Main-shaped input.
const candidate = structuredClone(manifest.assets.find((asset) => asset.athlete_ids.includes('athlete:121558')));
const candidateResult = evaluateGoal16Candidate(candidate, { catalog, localAsset: null });
assert.equal(candidateResult.eligible, false);
assert(candidateResult.reasons.includes('DISPLAY_PERMISSION_NOT_CLEARED'));
assert(candidateResult.reasons.includes('MEDIA_SHA256_NOT_VERIFIED'));
assert(candidateResult.reasons.includes('DEPICTION_NOT_VISUALLY_VERIFIED'));
{
  const missingCredit = structuredClone(candidate);
  missingCredit.attribution = '';
  assert(evaluateGoal16Candidate(missingCredit, { catalog }).reasons.includes('ATTRIBUTION_OR_LICENSE_INCOMPLETE'));
}
{
  const wrongPerson = structuredClone(candidate);
  wrongPerson.athlete_ids = ['athlete:not-in-catalog'];
  assert(evaluateGoal16Candidate(wrongPerson, { catalog }).reasons.includes('ATHLETE_IDENTITY_MISMATCH'));
}
{
  const wrongMatch = structuredClone(candidate);
  wrongMatch.match_id = 'pro:wtt:unrelated-match';
  wrongMatch.match_link_status = 'HUMAN_VERIFIED';
  const result = evaluateGoal16Candidate(wrongMatch, { catalog, intendedKind: 'MATCH_PHOTOGRAPH' });
  assert(result.reasons.includes('MATCH_IDENTITY_NOT_EXACT'));
  const wrongEvent = structuredClone(candidate);
  wrongEvent.match_id = catalog.matches[0].match_id;
  wrongEvent.match_link_status = 'HUMAN_VERIFIED';
  wrongEvent.actual_event = 'Unrelated event';
  assert(evaluateGoal16Candidate(wrongEvent, { catalog, intendedKind: 'MATCH_PHOTOGRAPH' }).reasons.includes('MATCH_EVENT_MISMATCH'));
}
{
  const unverifiedHash = structuredClone(candidate);
  unverifiedHash.media_sha256 = 'a'.repeat(64);
  unverifiedHash.media_sha256_status = 'NOT_COMPUTED_NO_DOWNLOAD';
  const result = evaluateGoal16Candidate(unverifiedHash, { catalog, localAsset: { sha256: 'b'.repeat(64) } });
  assert(result.reasons.includes('MEDIA_SHA256_NOT_VERIFIED'));
  assert(result.reasons.includes('LOCAL_MEDIA_SHA256_MISMATCH'));
}

// A self-authored temporary SVG validates the *San delivery index* and byte-hash path only; it is never copied to public/ or dist/.
const testBytes = selfAuthoredTestPng();
const testHash = createHash('sha256').update(testBytes).digest('hex');
const temporaryPublic = join(tmpdir(), `ptti-goal16-media-${process.pid}-${Date.now()}`);
const testImagePath = join(temporaryPublic, 'media/goal16/test-owned.png');
const testCatalog = {
  stars: [{ athlete_id: 'athlete:test-owned' }],
  matches: [{ match_id: 'pro:wtt:test-match', event: 'Test event only', event_id: 'test-event', evidence_source_ids: ['test-match-photo-evidence'] }],
};
try {
  mkdirSync(dirname(testImagePath), { recursive: true });
  writeFileSync(testImagePath, testBytes);
  const testAsset = {
    asset_id: 'test-owned:poster-1', kind: 'ATHLETE_PORTRAIT', subject_id: 'athlete:test-owned',
    display_permission: 'ALLOWED', source_page_url: 'https://example.test/source', photographer: 'PTTI test fixture',
    attribution: 'PTTI self-authored test fixture; not a player photo.', license: 'Test fixture only',
    license_url: 'https://example.test/license', derivative_status: 'PERMITTED', derivative_license: 'Test fixture only',
    derivative_license_url: 'https://example.test/license', derivative_notice: 'Self-authored one-pixel test image; no edits beyond PNG test encoding.',
    actual_event: 'Not a real event; test fixture only',
    alt: 'Self-authored test graphic for validation only; not a person or photo', sizes: '(max-width: 600px) 100vw, 400px',
    object_position: '50% 50%', renditions: [{ src: '/media/goal16/test-owned.png', width: 1, height: 1, mime_type: 'image/png', sha256: testHash }],
    depicted_athlete_ids: ['athlete:test-owned'], match_evidence: null,
  };
  // This one-pixel original is not a person image, is keyed only to a test ID and is always deleted.
  const index = createPublicMediaIndex({ contract_version: 'ptti.web-public-media-index/0.1', assets: [testAsset] }, testCatalog);
  assert(index.athletes.has('athlete:test-owned'));
  assert.deepEqual(verifyIndexBytes(index, temporaryPublic), []);
  writeFileSync(testImagePath, Buffer.concat([testBytes, Buffer.from([0])]));
  assert.deepEqual(verifyIndexBytes(index, temporaryPublic), ['test-owned:poster-1:MEDIA_SHA256_MISMATCH:/media/goal16/test-owned.png']);
  writeFileSync(testImagePath, testBytes);

  const match = testCatalog.matches[0];
  const matchAsset = {
    ...testAsset, asset_id: 'test-owned:match-1', kind: 'MATCH_PHOTOGRAPH', subject_id: match.match_id,
    actual_event: match.event, depicted_athlete_ids: ['athlete:test-owned'],
    match_evidence: { match_id: match.match_id, evidence_source_id: match.evidence_source_ids[0] },
  };
  assert.equal(validatePublicMediaAsset(matchAsset, testCatalog).length, 0, 'exact match ID, event and evidence source are accepted by the San delivery index');
  assert(validatePublicMediaAsset({ ...matchAsset, match_evidence: { match_id: 'pro:wtt:wrong', evidence_source_id: match.evidence_source_ids[0] } }, testCatalog).includes('MATCH_ASSOCIATION_EVIDENCE_MISSING'));
  assert(validatePublicMediaAsset({ ...matchAsset, actual_event: 'Wrong event' }, testCatalog).includes('MATCH_EVENT_IDENTITY_MISMATCH'));
  assert(validatePublicMediaAsset({ ...testAsset, attribution: '' }, testCatalog).includes('MEDIA_ATTRIBUTION_MISSING'));
  assert(validatePublicMediaAsset({ ...testAsset, derivative_status: 'UNKNOWN' }, testCatalog).includes('MEDIA_DERIVATIVE_REVIEW_INCOMPLETE'));
  assert(validatePublicMediaAsset({ ...testAsset, license: 'CC BY-SA 4.0', license_url: 'https://creativecommons.org/licenses/by-sa/4.0/' }, testCatalog).includes('SHARE_ALIKE_DERIVATIVE_LICENSE_MISMATCH'));
  assert(validatePublicMediaAsset({ ...testAsset, subject_id: 'athlete:wrong', depicted_athlete_ids: ['athlete:test-owned'] }, testCatalog).includes('ATHLETE_IDENTITY_NOT_EXACT'));
} finally {
  rmSync(temporaryPublic, { recursive: true, force: true });
}

if (process.argv.includes('--built')) {
  const dist = join(root, 'dist');
  const files = [];
  function walk(directory) {
    for (const name of readdirSync(directory)) {
      const path = join(directory, name);
      if (statSync(path).isDirectory()) walk(path);
      else files.push(path);
    }
  }
  assert(existsSync(dist), 'production dist exists');
  walk(dist);
  const textFiles = files.filter((path) => /\.(?:js|css|json|html|svg|map)$/i.test(path));
  const emitted = textFiles.map((path) => readFileSync(path, 'utf8')).join('\n');
  const privateMarkers = [
    expectedManifestSha,
    'public-media-manifest.json',
    'source_file_url',
    'NOT_COMPUTED_NO_DOWNLOAD',
    'PENDING_LIKENESS_AND_PROMOTIONAL_CONTEXT',
    'commons:2018-yog:',
  ];
  for (const marker of privateMarkers) assert.equal(emitted.includes(marker), false, `internal GOAL16 review material leaked into dist: ${marker}`);
  for (const asset of manifest.assets) {
    assert.equal(emitted.includes(asset.asset_id), false, `internal candidate ID leaked into dist: ${asset.asset_id}`);
    assert.equal(emitted.includes(asset.source_page_url), false, `internal candidate page URL leaked into dist: ${asset.asset_id}`);
    assert.equal(emitted.includes(asset.source_file_url), false, `internal candidate file URL leaked into dist: ${asset.asset_id}`);
  }
  assert.equal(files.some((path) => /goal16-media\\main-public-media-(?:review|schema)\.json$/i.test(path)), false);
  assert.equal(files.some((path) => /media\\goal16\\.*\.(?:avif|webp|jpe?g|png)$/i.test(path)), false, 'no unapproved image bytes should ship while public media index is empty');
  console.log(`PASS: production scan checked ${files.length} emitted files; no internal GOAL16 records or image binaries leaked.`);
}

console.log('PASS: Main GOAL16 manifest SHA/schema and all 9 NOT_CLEARED candidates verified; San public media index remains empty; rejection, exact-ID/event, attribution, and byte-hash regression vectors passed.');
