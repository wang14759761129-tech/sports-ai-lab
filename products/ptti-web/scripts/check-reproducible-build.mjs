import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readdir, readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('..', import.meta.url));
async function snapshot(directory, prefix = '') {
  const result = {};
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const relative = prefix + entry.name;
    if (entry.isDirectory()) Object.assign(result, await snapshot(new URL(entry.name + '/', directory), relative + '/'));
    else result[relative] = createHash('sha256').update(await readFile(new URL(entry.name, directory))).digest('hex');
  }
  return Object.fromEntries(Object.entries(result).sort());
}
function build() {
  execFileSync(process.execPath, ['node_modules/typescript/bin/tsc', '-b'], { cwd: root, stdio: 'inherit' });
  execFileSync(process.execPath, ['node_modules/vite/bin/vite.js', 'build'], { cwd: root, stdio: 'inherit' });
}
build();
const first = await snapshot(new URL('../dist/', import.meta.url));
build();
const second = await snapshot(new URL('../dist/', import.meta.url));
assert.deepEqual(second, first, 'file set and every byte must match on successive local builds');
console.log('Reproducible local build PASS (same installed toolchain; not a cross-machine guarantee):');
console.log(JSON.stringify({ node: process.version, files: second }, null, 2));
