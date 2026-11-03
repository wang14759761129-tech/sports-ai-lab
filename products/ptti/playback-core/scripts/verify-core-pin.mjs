#!/usr/bin/env node
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const pin = JSON.parse(await readFile(path.resolve(here, '..', 'CORE_PIN.json'), 'utf8'));
const expectedPin = {
  core_commit: '304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe',
  source_path: 'products/ptti/playback-core/src/index.ts',
  git_blob_sha1: '4ec9fd9f2c03b9cb8d7afb3ecb3679044567e0a9',
  source_sha256: 'a59df06b688d75885bfb8ed51364e73edbaedaaa2b3746b5f7fd1d1edf67caf2',
  source_bytes: 26345,
};
const args = process.argv.slice(2);
const value = (name) => {
  const index = args.indexOf(name);
  return index < 0 ? null : args[index + 1] ?? null;
};
const fail = (code) => {
  console.error(JSON.stringify({ status: 'FAIL', code }));
  process.exitCode = 1;
};
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');

try {
  if (Object.entries(expectedPin).some(([key, expected]) => pin[key] !== expected)) {
    fail('PIN_METADATA_MISMATCH');
  }
  const repo = value('--repo');
  const worktree = value('--worktree');
  const sourcePath = value('--source');
  const manifestPath = value('--manifest');
  const requestedCommit = value('--commit') ?? pin.core_commit;
  if (process.exitCode) {
    // The committed JSON pin must match the reviewed values above.
  } else if (!repo && !worktree && !sourcePath && !manifestPath) {
    fail('USAGE: pass --repo, --worktree, --source, and/or --manifest');
  } else if (requestedCommit !== pin.core_commit) {
    fail('CORE_COMMIT_MISMATCH');
  } else {
    const verified = [];
    if (repo) {
      const git = (...gitArgs) => execFileSync('git', ['-C', path.resolve(repo), ...gitArgs], { windowsHide: true });
      const blob = git('rev-parse', `${pin.core_commit}:${pin.source_path}`).toString('utf8').trim();
      const source = git('show', `${pin.core_commit}:${pin.source_path}`);
      if (blob !== pin.git_blob_sha1 || source.length !== pin.source_bytes || sha256(source) !== pin.source_sha256) {
        fail('CORE_CONTENT_MISMATCH');
      } else {
        verified.push('git-object');
      }
    }
    if (!process.exitCode && worktree) {
      const root = path.resolve(worktree);
      const git = (...gitArgs) => execFileSync('git', ['-C', root, ...gitArgs], { windowsHide: true });
      const head = git('rev-parse', 'HEAD').toString('utf8').trim();
      if (head !== pin.core_commit) fail('WORKTREE_COMMIT_MISMATCH');
      else {
        let clean = true;
        try { git('diff', '--quiet', 'HEAD', '--', pin.source_path); }
        catch { clean = false; }
        if (!clean) fail('WORKTREE_SOURCE_DIRTY');
        else {
          const source = await readFile(path.join(root, pin.source_path));
          if (source.length !== pin.source_bytes || sha256(source) !== pin.source_sha256) fail('WORKTREE_SOURCE_DIRTY');
          else verified.push('clean-worktree');
        }
      }
    }
    if (!process.exitCode && sourcePath) {
      let source;
      try { source = await readFile(path.resolve(sourcePath)); }
      catch { fail('CORE_SOURCE_UNREADABLE'); }
      if (source && (source.length !== pin.source_bytes || sha256(source) !== pin.source_sha256)) fail('CORE_CONTENT_MISMATCH');
      else if (source) verified.push('source-file');
    }
    if (!process.exitCode && manifestPath) {
      let manifest;
      try { manifest = JSON.parse(await readFile(path.resolve(manifestPath), 'utf8')); }
      catch { fail('MANIFEST_UNREADABLE'); }
      if (manifest) {
        if (manifest.playback?.commit !== pin.core_commit) fail('MANIFEST_CORE_COMMIT_MISMATCH');
        else if (manifest.playback?.source_sha256 !== pin.source_sha256) fail('MANIFEST_CORE_HASH_MISMATCH');
        else if (manifest.playback?.runtime_source_dependency !== false) fail('RUNTIME_SOURCE_NOT_SNAPSHOTTED');
        else verified.push('candidate-manifest');
      }
    }
    if (!process.exitCode) {
      console.log(JSON.stringify({
        status: 'PASS',
        verified,
        core_commit: pin.core_commit,
        source_path: pin.source_path,
        git_blob_sha1: pin.git_blob_sha1,
        source_sha256: pin.source_sha256,
      }));
    }
  }
} catch {
  fail('PIN_VERIFICATION_FAILED');
}
