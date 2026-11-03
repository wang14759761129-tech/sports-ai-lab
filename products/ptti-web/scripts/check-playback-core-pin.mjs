import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFile, readdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { consumeMatchLibrary } from '../src/match-library.mjs';
import { consumeReadonlyProjection } from '../src/readonly-catalog.mjs';
import { verifyPinnedPlaybackCore, verifyPinnedPlaybackCoreBytes } from '../src/playback-core-pin.mjs';

const scriptPath = fileURLToPath(import.meta.url);
const projectRoot = path.resolve(path.dirname(scriptPath), '..');
const repoRoot = path.resolve(projectRoot, '../..');
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');

export function assertBuildManifestMatchesCorePin(manifest, pin) {
  if (manifest.playback_core_commit !== pin.coreCommit || manifest.playback_core_source_sha256 !== pin.sourceHash
      || manifest.playback_core_archive_sha256 !== pin.pin.archive_sha256) {
    throw new Error('Build manifest Playback Core identity does not match the verified SOURCE_PIN and source bytes.');
  }
  return true;
}

function verifyCorePinNegativeCases(pin, archiveBytes, sourceBytes) {
  const good = verifyPinnedPlaybackCoreBytes(pin, archiveBytes, sourceBytes, sourceBytes);
  assert.equal(good.coreCommit, '304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe');
  const validManifest = { playback_core_commit: good.coreCommit, playback_core_source_sha256: good.sourceHash, playback_core_archive_sha256: pin.archive_sha256 };
  assert.equal(assertBuildManifestMatchesCorePin(validManifest, { ...good, pin }), true);
  assert.throws(() => assertBuildManifestMatchesCorePin({ ...validManifest, playback_core_commit: '0'.repeat(40) }, { ...good, pin }), /manifest Playback Core identity/);
  assert.throws(() => assertBuildManifestMatchesCorePin({ ...validManifest, playback_core_source_sha256: '0'.repeat(64) }, { ...good, pin }), /manifest Playback Core identity/);
  assert.throws(() => verifyPinnedPlaybackCoreBytes({ ...pin, core_commit: '0'.repeat(40) }, archiveBytes, sourceBytes), /unexpected Core commit/);
  const changedSource = Buffer.from(sourceBytes);
  changedSource[0] ^= 1;
  assert.throws(() => verifyPinnedPlaybackCoreBytes(pin, archiveBytes, changedSource), /vendored source does not match/);
  assert.throws(() => verifyPinnedPlaybackCoreBytes({ ...pin, source_sha256: '0'.repeat(64) }, archiveBytes, sourceBytes), /extracted source SHA-256 mismatch/);
  const changedArchive = Buffer.from(archiveBytes);
  changedArchive[0] ^= 1;
  assert.throws(() => verifyPinnedPlaybackCoreBytes(pin, changedArchive, sourceBytes), /archive SHA-256 mismatch/);
  assert.throws(() => verifyPinnedPlaybackCoreBytes(pin, archiveBytes, sourceBytes, changedSource), /configured Vite source differs/);
  return 7;
}

async function outputFiles(directory, prefix = '') {
  const result = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    assert.equal(entry.isSymbolicLink(), false, `Build output contains symlink: ${prefix}${entry.name}`);
    const relative = `${prefix}${entry.name}`;
    if (entry.isDirectory()) result.push(...await outputFiles(path.join(directory, entry.name), `${relative}/`));
    else result.push(relative);
  }
  return result;
}

export async function writeAndVerifyPublicBuildManifest(outputDirectory, verifiedPin = verifyPinnedPlaybackCore(projectRoot)) {
  const output = path.resolve(outputDirectory);
  const sanCommit = execFileSync('git', ['-C', repoRoot, 'rev-parse', 'HEAD'], { encoding: 'utf8', windowsHide: true }).trim();
  const status = execFileSync('git', ['-C', repoRoot, 'status', '--porcelain', '--', 'products/ptti-web'], { encoding: 'utf8', windowsHide: true }).trim();
  const files = await outputFiles(output);
  const forbiddenName = /(^|\/)(?:cinema-source-review-internal|featured-sources-internal-review|match-library-internal-review|web-internal-review)(?:\.|\/|$)/i;
  assert.equal(files.some((file) => forbiddenName.test(file)), false, 'Public artifact contains an internal-review source file');

  for (const file of files.filter((name) => /\.(?:html|js|css|json|svg|txt)$/i.test(name))) {
    const content = await readFile(path.join(output, file), 'utf8');
    for (const marker of ['ptti.cinema-source-review/0.1', 'INTERNAL_REVIEW_ONLY', 'featured-sources-internal-review.json']) {
      assert.equal(content.includes(marker), false, `Public artifact includes internal review marker ${marker} in ${file}`);
    }
  }

  const matchLibraryPath = path.join(output, 'data', 'match-library-strict-public.json');
  const matchLibrary = consumeMatchLibrary(JSON.parse(await readFile(matchLibraryPath, 'utf8')), 'STRICT_PUBLIC');
  assert.equal(matchLibrary.source_count, 0, 'strict-public match-library must remain empty');
  const webCatalogPath = path.join(output, 'data', 'web-strict-public.json');
  const webCatalog = consumeReadonlyProjection(JSON.parse(await readFile(webCatalogPath, 'utf8')));
  assert.equal(webCatalog.matches.length, 0, 'strict-public web catalog must remain empty');

  const manifest = {
    contract_version: 'ptti.web-build-manifest/0.1',
    san_commit: sanCommit,
    san_worktree_state: status ? 'DIRTY_WORKING_TREE' : 'CLEAN_COMMIT',
    playback_core_commit: verifiedPin.coreCommit,
    playback_core_source_sha256: verifiedPin.sourceHash,
    playback_core_archive_sha256: verifiedPin.pin.archive_sha256,
    strict_public_video_source_count: matchLibrary.source_count,
    strict_public_web_match_count: webCatalog.matches.length,
    internal_cinema_source_review_included: false,
    file_sha256: Object.fromEntries(await Promise.all(files.filter((file) => file !== 'ptti-build-manifest.json').sort().map(async (file) => [file, sha256(await readFile(path.join(output, file)))]))),
  };
  await writeFile(path.join(output, 'ptti-build-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  const written = JSON.parse(await readFile(path.join(output, 'ptti-build-manifest.json'), 'utf8'));
  assert.equal(written.playback_core_commit, verifiedPin.coreCommit);
  assert.equal(written.playback_core_source_sha256, verifiedPin.sourceHash);
  assert.equal(written.playback_core_archive_sha256, verifiedPin.pin.archive_sha256);
  assertBuildManifestMatchesCorePin(written, verifiedPin);
  assert.equal(written.strict_public_video_source_count, 0);
  assert.equal(written.strict_public_web_match_count, 0);
  assert.equal(written.internal_cinema_source_review_included, false);
  return written;
}

async function main() {
  const verified = verifyPinnedPlaybackCore(projectRoot, process.env.PTTI_PLAYBACK_CORE_SOURCE ?? null);
  const pin = JSON.parse(await readFile(path.join(projectRoot, 'vendor/playback-core-304eb661/SOURCE_PIN.json'), 'utf8'));
  const archive = await readFile(path.join(projectRoot, 'vendor/playback-core-304eb661', pin.archive_file));
  const source = await readFile(path.join(projectRoot, 'vendor/playback-core-304eb661/src/index.ts'));
  let negativeCases = 0;
  if (process.argv.includes('--self-test')) negativeCases = verifyCorePinNegativeCases(pin, archive, source);
  console.log(`Playback Core pin PASS: commit=${verified.coreCommit}, source_sha256=${verified.sourceHash}, archive_sha256=${pin.archive_sha256}${negativeCases ? `, negative_cases=${negativeCases} PASS` : ''}`);

  const postbuildIndex = process.argv.indexOf('--postbuild');
  if (postbuildIndex >= 0) {
    const directory = process.argv[postbuildIndex + 1] ?? path.join(projectRoot, 'dist');
    const manifest = await writeAndVerifyPublicBuildManifest(directory, verified);
    console.log(`Public build manifest PASS: san=${manifest.san_commit}, playback=${manifest.playback_core_commit}, strict_public=0, internal_review_included=false`);
  }
}

if (process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url) {
  main().catch((error) => {
    console.error(error?.stack ?? String(error));
    process.exitCode = 1;
  });
}
