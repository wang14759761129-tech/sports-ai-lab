import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { applyDemoEditsWithLineage, createAnalysisResult, DEMO_BUNDLE_URL, updateDemoPoint } from '../src/pro-demo.mjs';

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const defaultIntegrationRoot = path.resolve(webRoot, '..', '..', '..', 'integration-preview-sprint-0-1');
const integrationRoot = process.env.PTTI_INTEGRATION_WORKTREE || defaultIntegrationRoot;
const engineDirectory = path.join(integrationRoot, 'products', 'ptti-integration');
const engineCall = "import json,sys; sys.path.insert(0,sys.argv[1]); from match_intelligence import analyze_bundle; print(json.dumps(analyze_bundle(json.load(sys.stdin)),ensure_ascii=False,sort_keys=True,separators=(',',':')))";
const fixture = JSON.parse(await readFile(new URL(`../public${DEMO_BUNDLE_URL}`, import.meta.url), 'utf8'));

function pythonReference(bundle) {
  const run = spawnSync(process.env.PTTI_PYTHON || 'python', ['-c', engineCall, engineDirectory], {
    cwd: integrationRoot,
    input: JSON.stringify(bundle),
    encoding: 'utf8',
    windowsHide: true,
  });
  if (run.error) throw run.error;
  assert.equal(run.status, 0, `MainDex Python analysis failed: ${run.stderr}`);
  return JSON.parse(run.stdout);
}

const serveEdit = await applyDemoEditsWithLineage(fixture, updateDemoPoint(fixture, { ...fixture.points[0], serve_length: 'long' }), [fixture]);
const attackRow = fixture.points[0];
const attackEdit = await applyDemoEditsWithLineage(fixture, updateDemoPoint(fixture, {
  ...attackRow, third_ball_attack: 'no', third_ball_side: 'not_applicable', third_ball_outcome: 'not_applicable',
}), [fixture]);
const cases = [
  ['original fixture', fixture],
  ['serve-length derived snapshot', serveEdit.record],
  ['third-ball derived snapshot', attackEdit.record],
];

for (const [label, bundle] of cases) {
  const browserResult = await createAnalysisResult(bundle);
  const pythonResult = pythonReference(bundle);
  assert.deepEqual(browserResult, pythonResult, `${label}: Web analysis must exactly match MainDex Python output`);
}

console.log(`Pro cross-language PASS: ${cases.length} exact full-result comparisons against MainDex match_intelligence.analyze_bundle (original, serve edit, third-ball edit); canonical SHA-256, denominators, status thresholds, source/provenance and point references match.`);
