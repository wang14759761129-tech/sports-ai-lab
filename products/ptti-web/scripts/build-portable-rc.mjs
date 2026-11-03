import assert from 'node:assert/strict';
import { spawnSync, execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { mkdir, readFile, writeFile, copyFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { prepareQuickSource, validateReviewTargets } from '../src/review-targets.mjs';
import { consumeMatchLibrary } from '../src/match-library.mjs';
import { consumeReadonlyProjection } from '../src/readonly-catalog.mjs';
const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repo = path.resolve(project, '../..');
function arg(name) { const index = process.argv.indexOf(name); return index === -1 ? null : process.argv[index + 1]; }
const coreRepo = path.resolve(arg('--core-worktree') || path.resolve(repo, '../playback-recovery-sprint-0-3'));
const coreCommit = arg('--core-commit') || '304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe';
const nodeLicense = arg('--node-license');
assert(nodeLicense, 'Pass the official matching Node LICENSE file with --node-license');
const git = (cwd, ...args) => execFileSync('git', ['-C', cwd, ...args], { encoding: 'utf8', windowsHide: true }).trim();
const san = git(repo, 'rev-parse', 'HEAD');
assert.equal(git(repo, 'status', '--porcelain', '--', 'products/ptti-web'), '', 'RC must be built from a clean committed San tree');
assert.match(coreCommit, /^[a-f0-9]{40}$/);
const snapshot = execFileSync('git', ['-C', coreRepo, 'show', `${coreCommit}:products/ptti/playback-core/src/index.ts`], { windowsHide: true });
assert(!/^import\s/m.test(snapshot.toString()), 'Review additional Core imports before snapshotting');
const hashBytes = bytes => createHash('sha256').update(bytes).digest('hex');
async function hashFile(file) { const hash = createHash('sha256'); for await (const part of createReadStream(file)) hash.update(part); return hash.digest('hex'); }
const artifactId = `san-${san.slice(0,12)}-core-${coreCommit.slice(0,12)}-rc1`;
const output = path.resolve(arg('--output') || path.join(process.env.USERPROFILE, 'PTTI', 'Release-Candidates', artifactId));
assert(output.toLowerCase().startsWith(path.join(process.env.USERPROFILE, 'PTTI', 'Release-Candidates').toLowerCase() + path.sep), 'Use a dedicated user Release-Candidates directory');
try { await stat(output); throw new Error('Candidate already exists; no overwrite permitted'); } catch (error) { if (error.code !== 'ENOENT') throw error; }
const free = Number(spawnSync('powershell', ['-NoProfile', '-Command', '(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'], { encoding: 'utf8', windowsHide: true }).stdout.trim()) / 1048576;
assert(free >= 2.5, `BLOCKED build RAM ${free.toFixed(2)} GiB < 2.5 GiB`);
const nodeVersion = process.version;
const licenseText = await readFile(nodeLicense, 'utf8');
assert(licenseText.includes('Node.js') && licenseText.includes('Permission is hereby granted'), 'Official Node license content required');
const stage = path.join(project, '.alpha-qa', 'portable-build', artifactId);
await mkdir(stage, { recursive: true });
const coreSnapshot = path.join(stage, 'playback-core.ts'); await writeFile(coreSnapshot, snapshot);
const strictMatches = JSON.parse(await readFile(path.join(project, 'public/data/web-strict-public.json'), 'utf8'));
assert.equal(consumeReadonlyProjection(strictMatches).matches.length, 0);
assert.equal(consumeMatchLibrary(JSON.parse(await readFile(path.join(project, 'public/data/match-library-strict-public.json'), 'utf8')), 'STRICT_PUBLIC').source_count, 0);
const quick = JSON.parse(await readFile(path.join(project, 'scripts/fixtures/review-targets/quick-input.json'), 'utf8'));
const targets = JSON.parse(await readFile(path.join(project, 'scripts/fixtures/review-targets/targets.json'), 'utf8'));
assert.equal(quick.dataset_class, 'SIMULATED_ONLY'); assert.equal(quick.video_context.source_id, null);
validateReviewTargets(targets, await prepareQuickSource(JSON.stringify(quick)));
assert.equal(targets.evidence_status, 'SIMULATED_ONLY'); assert.equal(targets.sample.point_count, 19);
const env = { ...process.env, PTTI_PLAYBACK_CORE_SOURCE: coreSnapshot, PTTI_RC_BUILD_OUT: path.join(output, 'site') };
for (const args of [['node_modules/typescript/bin/tsc','-b','--pretty','false'], ['node_modules/vite/bin/vite.js','build','--mode','local-rc']]) {
  const result = spawnSync(process.execPath, args, { cwd: project, env, stdio: 'inherit', windowsHide: true }); assert.equal(result.status, 0, args.join(' '));
}
for (const directory of ['runtime','app','licenses']) await mkdir(path.join(output, directory), { recursive: true });
await copyFile(process.execPath, path.join(output, 'runtime/node.exe'));
await copyFile(nodeLicense, path.join(output, 'licenses/NODE-LICENSE.txt'));
await copyFile(path.join(project, 'scripts/portable/server.mjs'), path.join(output, 'app/server.mjs'));
await writeFile(path.join(output, 'app/demo-review.json'), JSON.stringify({ quick, targets }));
const launcher = await readFile(path.join(project, 'scripts/portable/Start-PTTI-RC.ps1'), 'utf8');
await writeFile(path.join(output, 'Start-PTTI-RC.ps1'), '\ufeff' + launcher.replace(/^\ufeff/, ''));
await writeFile(path.join(output, 'Start-PTTI-RC.cmd'), '@echo off\r\n"%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-PTTI-RC.ps1" %*\r\nexit /b %errorlevel%\r\n');
const dependencies = {};
for (const name of ['react','react-dom','scheduler']) {
  dependencies[name] = JSON.parse(await readFile(path.join(project, 'node_modules', name, 'package.json'), 'utf8')).version;
  await copyFile(path.join(project, 'node_modules', name, 'LICENSE'), path.join(output, 'licenses', `${name}-LICENSE.txt`));
}
await copyFile(path.join(process.env.USERPROFILE, 'PTTI/Web-Pro/ptti-cinema.ico'), path.join(output, 'ptti.ico'));
await writeFile(path.join(output, 'START-HERE.txt'), '\ufeff' + `PTTI Cinema Portable RC\r\n\r\n双击本目录 Start-PTTI-RC.cmd。仅本机 http://127.0.0.1:4176/。\r\nDouble-click Start-PTTI-RC.cmd. Bundled Node ${nodeVersion}; Windows PowerShell 5.1 required.\r\nThe optional .lnk is specific to this folder location; after moving the folder use the relative-path .cmd entry.\r\nNo installed npm, Vite, Codex or worktree is used at runtime. Keep this folder intact.\r\nPublic match/source catalogs: 0. Original 19-point SIMULATED_ONLY demo: no match footage and no automatic replay authorization.\r\nImport your own authorized local MP4 and confirm both rally boundaries before replay. Export drafts/notes explicitly; no automatic uploads.\r\nLogs: logs/launcher.log, logs/server.log, logs/stderr.log. No R4 or desktop-stable entry is changed.\r\nVersion: ${artifactId}\r\n`);
async function files(directory, prefix = '') { const result = []; for (const entry of await readdir(directory, { withFileTypes: true })) { assert(!entry.isSymbolicLink(), 'No RC symlinks'); const name = prefix + entry.name; if (entry.isDirectory()) result.push(...await files(path.join(directory, entry.name), name + '/')); else result.push(name); } return result; }
const entries = await files(output);
for (const name of entries) {
  assert(!/internal-review|\.db$|\.sqlite|\.mp4$|\.env$|\.map$/i.test(name), `Forbidden candidate resource ${name}`);
  if (name.startsWith('site/')) { const text = await readFile(path.join(output, name), 'utf8'); assert(!text.includes('C:\\PTTI-Worktrees') && !text.includes('LocalCache'), 'Runtime bundle must not contain machine source paths'); }
}
const manifest = {
  contract_version: 'ptti.web-rc-manifest/0.1', artifact_id: artifactId, created_at: new Date().toISOString(), default_port: 4176,
  san: { commit: san, clean: true, package_lock_sha256: await hashFile(path.join(project,'package-lock.json')) },
  playback: { commit: coreCommit, source_sha256: hashBytes(snapshot), runtime_source_dependency: false },
  runtime: { node_version: nodeVersion, node_sha256: await hashFile(process.execPath), bundled: true, installed_node_required: false, platform: process.platform, architecture: process.arch, windows_powershell: '5.1', license_origin: `https://raw.githubusercontent.com/nodejs/node/${nodeVersion}/LICENSE` },
  build_tools: Object.fromEntries(await Promise.all(['vite','typescript'].map(async name => [name, JSON.parse(await readFile(path.join(project,'node_modules',name,'package.json'),'utf8')).version]))),
  dependencies, catalog: { real_matches: 0, video_sources: 0, internal_sources_included: 0, synthetic_points: 19 },
  synthetic_demo: { dataset_id: targets.dataset.dataset_id, canonical_input_sha256: targets.canonical_input_sha256, evidence_status: 'SIMULATED_ONLY' },
  files: Object.fromEntries(await Promise.all(entries.sort().map(async name => [name, await hashFile(path.join(output,name))])))
};
await writeFile(path.join(output, 'manifest.json'), JSON.stringify(manifest, null, 2));
const linkScript = String.raw`$r=$env:PTTI_RC_DIRECTORY; $w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut((Join-Path $r 'PTTI Cinema RC.lnk')); $s.TargetPath=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'; $s.Arguments='-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+$r+'\Start-PTTI-RC.ps1"'; $s.WorkingDirectory=$r; $s.IconLocation=(Join-Path $r 'ptti.ico')+',0'; $s.Save()`;
const link = spawnSync('powershell', ['-NoProfile','-Command',linkScript], { env: { ...process.env, PTTI_RC_DIRECTORY: output }, encoding: 'utf8', windowsHide: true }); assert.equal(link.status, 0, link.stderr);
await writeFile(path.join(stage, 'result.json'), JSON.stringify({ output, artifact_id: artifactId, san, core: coreCommit, manifest_sha256: await hashFile(path.join(output,'manifest.json')) }, null, 2));
console.log(`PORTABLE_RC_READY ${output}`);
