import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { consumeGoal14StrictPublic } from '../src/fan-content-delivery.mjs';
import { inspectPublicProjection } from '../src/public-projection.mjs';

const dist = resolve(process.cwd(), 'dist');
const publicDataPath = resolve(dist, 'data/goal14-fan-content-strict-public.json');
const strictData = JSON.parse(readFileSync(publicDataPath, 'utf8'));
consumeGoal14StrictPublic(strictData);
const goal15Path = resolve(dist, 'data/match-library-strict-public.json');
const goal15 = JSON.parse(readFileSync(goal15Path, 'utf8'));
assert.equal(goal15.contract_version, 'ptti.match-library-index/0.1');
assert.equal(goal15.view, 'STRICT_PUBLIC');
assert.deepEqual(goal15.source_manifest, [], 'the public catalog must not publish internal provenance paths');
const goal15Raw = readFileSync(goal15Path, 'utf8');
const projectionIssues = inspectPublicProjection(goal15, goal15Raw);
assert.deepEqual(projectionIssues, [], `GOAL15 public projection contains internal-only metadata: ${projectionIssues.join('; ')}`);
assert.deepEqual([goal15.matches.length, goal15.video_sources.length, goal15.stars.length], [5, 15, 8]);
assert.equal(goal15.video_sources.filter((source) => source.content_type_claim === 'HIGHLIGHTS').length, 10);
assert.equal(goal15.video_sources.filter((source) => source.content_type_claim === 'CLIP').length, 0);
function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}
const files = walk(dist);
assert.ok(!files.some((path) => path.toLowerCase().includes('.alpha-qa') || /(?:internal-review|candidate-review-internal)\.json/i.test(path)));
const emittedText = files.filter((path) => /\.(?:js|css|json|html)$/.test(path)).map((path) => readFileSync(path, 'utf8')).join('\n');
assert.equal(/5\s*场\s*\/\s*3\s*位\s*\/\s*20\s*条|5-event\s*\/\s*3-player\s*\/\s*20-candidate/i.test(emittedText), false, 'public assets must not contain internal review counts');
assert.equal(emittedText.includes('ca714727ebe43fd091b7e52a2c8e31225c6deba65fde30765e9da6f360c12ee2'), false, 'superseded v0.1 artifact identity must not remain in the new build');
assert.equal(files.some((path) => /(?:internal-review|candidate-review-internal)\.json$/i.test(path)), false, 'internal candidate JSON must not enter the public build');
assert.equal(files.some((path) => /\.(?:mp4|webm|mov|m4v|jpg|jpeg)$/i.test(path)), false, 'no video or unlicensed JPEG artwork may be copied into the public build');
const explicitlyAdmittedMarkers = new Set(goal15.video_sources.flatMap((source) => [source.source_id, source.video_id, source.official_url]));
for (const marker of ['event:wtt:3094', 'clip-candidate:yokohama-2025', 'watch:youtube:DRWntK5EJj0']) {
  assert.equal(emittedText.includes(marker), false, `public artifact does not contain internal marker ${marker}`);
}
let internalCandidateScan = 'NOT_TESTED: internal local snapshot not present';
const internalPath = resolve(process.cwd(), '.alpha-qa/goal14/fan-content-delivery-internal-review.json');
if (existsSync(internalPath)) {
  const internal = JSON.parse(readFileSync(internalPath, 'utf8'));
  let checked = 0;
  for (const clip of internal.clips ?? []) {
    for (const marker of [clip.clip_id, clip.watch_source_id, clip.official_video_url].filter((value) => typeof value === 'string' && value.length > 0)) {
    if (explicitlyAdmittedMarkers.has(marker)) continue;
    assert.equal(emittedText.includes(marker), false, `public artifact contains INTERNAL_ONLY candidate material: ${marker}`);
      checked++;
    }
  }
  internalCandidateScan = `PASS: ${checked} internal clip/source/url markers absent from public artifact`;
}
console.log(`PASS: ${files.length} static files checked; Goal15 strict-public catalog is 5/15/8 with 10 event highlights and 0 clips. The separate GOAL14 strict-public projection remains empty. ${internalCandidateScan}.`);
