#!/usr/bin/env node
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const script = fileURLToPath(new URL('./verify-core-pin.mjs', import.meta.url));
const repo = path.resolve(path.dirname(script), '..', '..', '..', '..');
const commit = '304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe';
const wrongSha = `${commit.slice(0, -1)}0`;
const sourceHash = 'a59df06b688d75885bfb8ed51364e73edbaedaaa2b3746b5f7fd1d1edf67caf2';
const run = (...args) => spawnSync(process.execPath, [script, ...args], { encoding: 'utf8', windowsHide: true });

const gitObject = run('--repo', repo, '--commit', commit);
assert.equal(gitObject.status, 0, gitObject.stderr);
assert.match(gitObject.stdout, /"status":"PASS"/);
assert.match(gitObject.stdout, new RegExp(sourceHash));

const cleanWorktree = run('--worktree', repo);
const head = execFileSync('git', ['-C', repo, 'rev-parse', 'HEAD'], { encoding: 'utf8', windowsHide: true }).trim();
if (head === commit) {
  assert.equal(cleanWorktree.status, 0, cleanWorktree.stderr);
  assert.match(cleanWorktree.stdout, /clean-worktree/);
} else {
  assert.equal(cleanWorktree.status, 1);
  assert.match(cleanWorktree.stderr, /WORKTREE_COMMIT_MISMATCH/);
}

const sourceFile = path.join(repo, 'products', 'ptti', 'playback-core', 'src', 'index.ts');
const pinnedSource = run('--source', sourceFile);
assert.equal(pinnedSource.status, 0, pinnedSource.stderr);
assert.match(pinnedSource.stdout, /source-file/);

const wrongCommit = run('--repo', repo, '--commit', wrongSha);
assert.equal(wrongCommit.status, 1);
assert.match(wrongCommit.stderr, /CORE_COMMIT_MISMATCH/);

const temporary = await mkdtemp(path.join(os.tmpdir(), 'ptti-core-pin-test-'));
try {
  const tamperedSource = path.join(temporary, 'tampered-index.ts');
  await writeFile(tamperedSource, 'changed source');
  const wrongSource = run('--source', tamperedSource);
  assert.equal(wrongSource.status, 1);
  assert.match(wrongSource.stderr, /CORE_CONTENT_MISMATCH/);

  const manifestPath = path.join(temporary, 'manifest.json');
  const base = { playback: { commit, source_sha256: sourceHash, runtime_source_dependency: false } };
  await writeFile(manifestPath, JSON.stringify(base));
  const validManifest = run('--manifest', manifestPath);
  assert.equal(validManifest.status, 0, validManifest.stderr);
  assert.match(validManifest.stdout, /candidate-manifest/);

  await writeFile(manifestPath, JSON.stringify({ playback: { ...base.playback, commit: wrongSha } }));
  const wrongManifestCommit = run('--manifest', manifestPath);
  assert.equal(wrongManifestCommit.status, 1);
  assert.match(wrongManifestCommit.stderr, /MANIFEST_CORE_COMMIT_MISMATCH/);

  await writeFile(manifestPath, JSON.stringify({ playback: { ...base.playback, source_sha256: '0'.repeat(64) } }));
  const wrongManifestHash = run('--manifest', manifestPath);
  assert.equal(wrongManifestHash.status, 1);
  assert.match(wrongManifestHash.stderr, /MANIFEST_CORE_HASH_MISMATCH/);

  await writeFile(manifestPath, JSON.stringify({ playback: { ...base.playback, runtime_source_dependency: true } }));
  const mutableRuntime = run('--manifest', manifestPath);
  assert.equal(mutableRuntime.status, 1);
  assert.match(mutableRuntime.stderr, /RUNTIME_SOURCE_NOT_SNAPSHOTTED/);
} finally {
  await rm(temporary, { recursive: true, force: true });
}

console.log('Core pin regression PASS: Git object, worktree identity guard, source and Manifest checks; commit, hash and mutable-runtime negatives rejected.');
