import { verifyReviewedText } from './verify-reviewed-text.mjs';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { consumeFanCatalog } from '../src/fan-catalog.mjs';
import { applyGoal17MatchAdditions } from '../src/goal17-match-additions.mjs';
import { applyFanInspiration, FAN_INSPIRATION_SHA } from '../src/fan-inspiration.mjs';
import { consumeMatchReportEvidence, getLinkedReportAthletes, MATCH_REPORT_EVIDENCE_SHA, MATCH_REPORT_SOURCE_COMMIT } from '../src/match-report-evidence.mjs';

const root = new URL('../', import.meta.url);
const read = async (path) => readFile(new URL(path, root));
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');
const baseBytes = await read('public/data/match-library-strict-public.json');
const additionsBytes = await read('public/data/goal17-official-match-video-additions.json');
const inspirationBytes = await read('public/data/fan-inspiration-v0.1.json');
const reportBytes = await read('public/data/match-reports-v0.1.json');
assert.equal(verifyReviewedText(fileURLToPath(root), 'public/data/match-reports-v0.1.json', MATCH_REPORT_EVIDENCE_SHA), true);
if (process.argv.includes('--built')) {
  const builtReportBytes = await read('dist/data/match-reports-v0.1.json');
  assert.equal(sha256(builtReportBytes), sha256(reportBytes), 'production report bytes must match the verified source byte identity');
}
assert.equal(sha256(inspirationBytes), FAN_INSPIRATION_SHA);

const base = applyGoal17MatchAdditions(consumeFanCatalog(JSON.parse(baseBytes)), JSON.parse(additionsBytes));
const input = JSON.parse(inspirationBytes);
const catalog = applyFanInspiration(base, input).catalog;
const reports = consumeMatchReportEvidence(JSON.parse(reportBytes), catalog);
assert.equal(MATCH_REPORT_SOURCE_COMMIT, '8036a37ff6af5ae5c7924b5c26d3290e640bf607');
assert.equal(reports.length, 1);
const report = reports[0];
assert.equal(report.match_id, 'pro:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final');
assert.equal(catalog.matches.some((match) => match.match_id === report.match_id), true);
assert.equal(catalog.sources.length, 18, 'report reuse does not add a video source');
assert.equal(catalog.sources.some((source) => source.source_id === report.linked_video.source_id), true);
assert.deepEqual(getLinkedReportAthletes(report, catalog).map((star) => star.athlete_id), ['athlete:121558']);
assert.equal(report.article.published_at, null);
assert.equal(report.article.content_observation, 'OFFICIAL_DOMAIN_SEARCH_EXCERPT_SURFACED');
assert.equal(report.article.direct_page_status, 'COOKIE_CONSENT_SHELL_ONLY');
assert.equal(report.linked_video.external_system_browser_open, 'NOT_TESTED');
assert.equal(report.linked_video.video_started, 'NOT_TESTED');
assert.equal(report.linked_video.complete_watch, 'UNVERIFIED');

for (const mutate of [
  (value) => { value.input_identity.match_library_sha256 = '0'.repeat(64); },
  (value) => { value.match_reports[0].match_id = 'wrong-match'; },
  (value) => { value.match_reports[0].game_scores[0] = [11, 1]; },
  (value) => { value.match_reports[0].article.published_at = '2026-03-01'; },
  (value) => { value.match_reports[0].linked_video.video_started = 'VERIFIED'; },
  (value) => { value.match_reports[0].rights.image_reuse = 'ALLOWED'; },
]) {
  const bad = structuredClone(JSON.parse(reportBytes));
  mutate(bad);
  assert.throws(() => consumeMatchReportEvidence(bad, catalog));
}

const page = (await readFile(new URL('../src/FanCatalogPage.tsx', import.meta.url))).toString();
const locale = (await readFile(new URL('../src/i18n.ts', import.meta.url))).toString();
assert.match(page, /data-match-report-id/);
assert.match(page, /getLinkedReportAthletes/);
for (const key of ['fan.matchReportTitle', 'fan.matchReportDateUnknown', 'fan.openOfficialMatchReport', 'fan.matchReportSourceObservation']) {
  assert.equal((locale.match(new RegExp(`'${key.replaceAll('.', '\\.')}'`, 'g')) ?? []).length, 2, `${key} must have Chinese and English copy`);
}

console.log('PASS: Main match-report SHA and fixed San/Main identities; exact match, participant, score, article, and existing-video joins.');
console.log('PASS: 18-source count remains unchanged; only existing profiled athletes link; date and playback stay unknown/not tested.');
console.log('PASS: altered identity, match, score, date, playback, and rights fail closed; UI copy covers both locales.');
