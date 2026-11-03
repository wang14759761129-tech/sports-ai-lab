import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readdir, readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { consumeFanCatalog } from '../src/fan-catalog.mjs';
import { applyGoal17MatchAdditions } from '../src/goal17-match-additions.mjs';
import { createWatchabilityEvidenceIndex } from '../src/watchability-evidence.mjs';
import { buildWatchFollowUpQueue, indexUserReportedPlaybackEvidence, mergeLocalUserFeedbackSources, USER_WATCH_PLAYBACK_REPORTS_SHA256 } from '../src/watch-follow-up.mjs';
import {
  appendUserWatchFeedback,
  createUserWatchFeedbackReport,
  parseUserWatchFeedbackExport,
  readUserWatchFeedback,
  serializeUserWatchFeedback,
  USER_WATCH_FEEDBACK_KEY,
} from '../src/watch-user-feedback.mjs';

const evidencePath = resolve('src/internal-review/goal19-watchability-evidence-v0.1.json');
const schemaPath = resolve('scripts/contracts/goal19-1-watchability-evidence-v0.1.schema.json');
const feedbackSchemaPath = resolve('scripts/contracts/user-watch-feedback-v0.1.schema.json');
const userPlaybackReportsPath = resolve('src/internal-review/goal19.3-user-playback-reports-v0.1.json');
const userPlaybackReportsSchemaPath = resolve('scripts/contracts/user-watch-playback-reports-v0.1.schema.json');
const expectedEvidenceSha = '8ba35a9575d2c731a55262c5edf7b8ea7477319f2d1fd7160c36de6ff09ff2f5';
const expectedSchemaSha = '849361982b20ed1b37bffbec1c38e1c3ddc55a0bb2bdee3b3cf4f41b44ad6666';
const expectedFeedbackSchemaSha = '85a1ddd9bdcf9473556963092b2571836dc030ad864dcb3d134cd2258674a5e0';
const expectedUserPlaybackSchemaSha = '15b96a911993b8cc2158135c5ed021309e650a2f9976a97958c489a9683bd512';
const evidenceBytes = await readFile(evidencePath);
const schemaBytes = await readFile(schemaPath);
const feedbackSchemaBytes = await readFile(feedbackSchemaPath);
const userPlaybackReportsBytes = await readFile(userPlaybackReportsPath);
const userPlaybackReportsSchemaBytes = await readFile(userPlaybackReportsSchemaPath);
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');
assert.equal(sha256(evidenceBytes), expectedEvidenceSha, 'Main GOAL19.1 evidence bytes must match the handed-off SHA-256');
assert.equal(sha256(schemaBytes), expectedSchemaSha, 'Copied Main schema must match its reviewed byte identity');
assert.equal(sha256(feedbackSchemaBytes), expectedFeedbackSchemaSha, 'San USER_REPORTED feedback schema bytes changed without updating this pin');
assert.equal(sha256(userPlaybackReportsBytes), USER_WATCH_PLAYBACK_REPORTS_SHA256, 'User-provided playback report bytes changed without updating the pinned identity');
assert.equal(sha256(userPlaybackReportsSchemaBytes), expectedUserPlaybackSchemaSha, 'USER_REPORTED playback evidence schema changed without updating its pin');
const evidence = JSON.parse(evidenceBytes.toString('utf8'));
const schema = JSON.parse(schemaBytes.toString('utf8'));
const feedbackSchema = JSON.parse(feedbackSchemaBytes.toString('utf8'));
const userPlaybackReports = JSON.parse(userPlaybackReportsBytes.toString('utf8'));
const userPlaybackReportsSchema = JSON.parse(userPlaybackReportsSchemaBytes.toString('utf8'));

function validateSchema(node, value, path = '$') {
  if (Object.hasOwn(node, 'const')) assert.deepEqual(value, node.const, `${path} const`);
  if (node.enum) assert(node.enum.includes(value), `${path} enum`);
  if (node.type) {
    const types = Array.isArray(node.type) ? node.type : [node.type];
    const matches = types.some((type) => type === 'null' ? value === null
      : type === 'object' ? value !== null && typeof value === 'object' && !Array.isArray(value)
        : type === 'array' ? Array.isArray(value)
          : type === 'integer' ? Number.isInteger(value)
            : type === 'number' ? typeof value === 'number' && Number.isFinite(value)
              : typeof value === type);
    assert(matches, `${path} expected ${types.join('|')}`);
  }
  if (typeof value === 'string') {
    if (node.minLength !== undefined) assert(value.length >= node.minLength, `${path} minLength`);
    if (node.pattern) assert(new RegExp(node.pattern).test(value), `${path} pattern`);
    if (node.format === 'uri') assert.doesNotThrow(() => new URL(value), `${path} URI`);
    if (node.format === 'date') assert(/^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(`${value}T00:00:00Z`)), `${path} date`);
    if (node.format === 'date-time') assert(Number.isFinite(Date.parse(value)) && value.includes('T'), `${path} date-time`);
  }
  if (Array.isArray(value)) {
    if (node.minItems !== undefined) assert(value.length >= node.minItems, `${path} minItems`);
    if (node.maxItems !== undefined) assert(value.length <= node.maxItems, `${path} maxItems`);
    if (node.items) value.forEach((item, index) => validateSchema(node.items, item, `${path}[${index}]`));
  }
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    for (const key of node.required ?? []) assert(Object.hasOwn(value, key), `${path}.${key} required`);
    const properties = node.properties ?? {};
    for (const [key, item] of Object.entries(value)) {
      if (Object.hasOwn(properties, key)) validateSchema(properties[key], item, `${path}.${key}`);
      else if (node.additionalProperties === false) assert.fail(`${path}.${key} additional property`);
      else if (node.additionalProperties && typeof node.additionalProperties === 'object') validateSchema(node.additionalProperties, item, `${path}.${key}`);
    }
  }
}

validateSchema(schema, evidence);
assert.equal(schema.$id, evidence.contract_version);
validateSchema(userPlaybackReportsSchema, userPlaybackReports);
assert.equal(userPlaybackReportsSchema.$id, userPlaybackReports.contract_version);
const base = consumeFanCatalog(JSON.parse(await readFile('public/data/match-library-strict-public.json', 'utf8')));
const goal17Delta = JSON.parse(await readFile('public/data/goal17-official-match-video-additions.json', 'utf8'));
const catalog = applyGoal17MatchAdditions(base, goal17Delta);
assert.deepEqual([catalog.matches.length, catalog.sources.length, catalog.stars.length], [7, 17, 8]);
const index = createWatchabilityEvidenceIndex(evidence, catalog.sources);
const userPlaybackIndex = indexUserReportedPlaybackEvidence(userPlaybackReports, catalog.sources);
assert.deepEqual(userPlaybackReports.reports.map((row) => row.source_id), [
  'video-source:youtube:0QgbtsBWZhk',
  'video-source:youtube:ttUevnAZSEY',
  'youtube:ywX9mUJ8NtI',
]);
assert.equal(userPlaybackIndex.size, 3);
for (const report of userPlaybackIndex.values()) {
  const source = catalog.sources.find((row) => row.source_id === report.source_id);
  const independent = index.get(report.source_id);
  assert.equal(report.official_target_url, source.url);
  assert.equal(report.evidence_type, 'USER_REPORTED');
  assert.equal(report.conclusion, 'STARTED_PLAYBACK');
  assert.equal(report.feedback_source, 'USER_PROVIDED_IN_REQUEST');
  assert.equal(report.recorded_on, '2026-10-19');
  assert.equal(report.tested_at, null, 'no exact test timestamp was supplied');
  assert.equal(independent.verification_levels.video_started, 'NOT_TESTED', 'user report must never upgrade independent playback evidence');
  assert.equal(independent.verification_levels.complete_watch, 'UNVERIFIED');
}
const followUpQueue = buildWatchFollowUpQueue(catalog.sources, index, userPlaybackIndex);
assert.equal(followUpQueue.length, 14);
assert.deepEqual(followUpQueue.filter((row) => row.priority === 1).length, 3);
assert.deepEqual(followUpQueue.filter((row) => row.priority === 2).length, 1);
assert.deepEqual(followUpQueue.filter((row) => row.priority === 3).length, 10);
assert.equal(followUpQueue.filter((row) => row.priority === 1 && row.source.content_type_claim === 'UNKNOWN').length, 2);
assert(followUpQueue.every(({ source, evidence }) => source.url === evidence.official_target_url));
assert(followUpQueue.every(({ source }) => !userPlaybackIndex.has(source.source_id)), 'the three user-reported sources are not in the pending queue');
assert(followUpQueue.filter((row) => row.priority === 3).every(({ source, evidence }) => source.canonical_match_id === null && evidence.video_type_claim === 'EVENT_HIGHLIGHTS_TITLE_CLAIM'));
assert.equal(index.size, 17);
for (const source of catalog.sources) {
  const row = index.get(source.source_id);
  assert(row, `exact source_id should join: ${source.source_id}`);
  assert.equal(row.official_target_url, source.url, `evidence must not replace source URL: ${source.source_id}`);
  assert.equal(row.match_id, source.canonical_match_id, `match identity remains unchanged: ${source.source_id}`);
}
assert.deepEqual(
  [catalog.sources.filter((source) => source.match_link_status === 'HUMAN_VERIFIED').length,
    catalog.sources.filter((source) => source.match_link_status === 'OFFICIAL_TITLE_ASSOCIATED_VISUAL_NOT_TESTED').length,
    catalog.sources.filter((source) => source.canonical_match_id === null).length],
  [5, 2, 10],
  'Preserve five human-confirmed links, two title-only Doha associations, and ten event-level/unlinked sources',
);
assert.equal(evidence.summary.current_fetch_title_surfaced_count, 1);
assert.equal(evidence.summary.current_fetch_throttled_count, 4);
assert.equal(evidence.summary.current_fetch_not_attempted_count, 12);
assert.equal(evidence.summary.video_type_claim_counts.FULL_MATCH_TITLE_CLAIM, 5);
assert.equal(evidence.summary.video_type_claim_counts.EVENT_HIGHLIGHTS_TITLE_CLAIM, 10);
assert.equal(evidence.summary.video_type_claim_counts.MATCH_SPECIFIC_TYPE_UNKNOWN, 2);
assert.equal(catalog.sources.filter((source) => source.canonical_match_id === null && index.get(source.source_id).video_type_claim === 'EVENT_HIGHLIGHTS_TITLE_CLAIM').length, 10);
for (const row of evidence.sources) {
  assert.equal(row.verification_levels.external_system_browser_open, 'NOT_TESTED');
  assert.equal(row.verification_levels.video_started, 'NOT_TESTED');
  assert.equal(row.verification_levels.complete_watch, 'UNVERIFIED');
  if (row.video_type_claim === 'FULL_MATCH_TITLE_CLAIM') assert.notEqual(row.claimed_full_match_completeness, 'VERIFIED_COMPLETE');
  if (row.current_page_fetch.status === 'BLOCKED_FETCH_THROTTLED') assert.equal(row.verification_levels.page_exists, 'BLOCKED');
}

assert.throws(() => createWatchabilityEvidenceIndex({ ...evidence, sources: evidence.sources.slice(1) }, catalog.sources), /goal19-invalid-counts/);
const wrongUrl = structuredClone(evidence);
wrongUrl.sources[0].official_target_url = 'https://www.youtube.com/watch?v=wrong';
assert.throws(() => createWatchabilityEvidenceIndex(wrongUrl, catalog.sources), /goal19-target-url-mismatch/);
const wrongMatch = structuredClone(evidence);
wrongMatch.sources[0].match_id = 'other-match';
assert.throws(() => createWatchabilityEvidenceIndex(wrongMatch, catalog.sources), /goal19-match-identity-mismatch/);
const duplicateId = structuredClone(evidence);
duplicateId.sources[1].source_id = duplicateId.sources[0].source_id;
assert.throws(() => createWatchabilityEvidenceIndex(duplicateId, catalog.sources), /goal19-duplicate-source-id/);
const wrongId = structuredClone(evidence);
wrongId.sources[0].source_id = 'source:not-in-catalog';
assert.throws(() => createWatchabilityEvidenceIndex(wrongId, catalog.sources), /goal19-source-id-set-mismatch/);

const wrongReportUrl = structuredClone(userPlaybackReports);
wrongReportUrl.reports[0].official_target_url = 'https://www.youtube.com/watch?v=wrong';
assert.throws(() => indexUserReportedPlaybackEvidence(wrongReportUrl, catalog.sources), /user-playback-source-url-mismatch/);
const wrongReportId = structuredClone(userPlaybackReports);
wrongReportId.reports[0].source_id = 'youtube:unknown';
assert.throws(() => indexUserReportedPlaybackEvidence(wrongReportId, catalog.sources), /user-playback-source-id-mismatch/);
const duplicateReport = structuredClone(userPlaybackReports);
duplicateReport.reports[1].source_id = duplicateReport.reports[0].source_id;
assert.throws(() => indexUserReportedPlaybackEvidence(duplicateReport, catalog.sources), /duplicate-user-playback-report/);
const madeUpTimestamp = structuredClone(userPlaybackReports);
madeUpTimestamp.reports[0].tested_at = '2026-10-19T12:00:00Z';
assert.throws(() => indexUserReportedPlaybackEvidence(madeUpTimestamp, catalog.sources), /invalid-user-playback-report/);
const missingEvidence = new Map(index);
missingEvidence.delete(followUpQueue[0].source.source_id);
assert.throws(() => buildWatchFollowUpQueue(catalog.sources, missingEvidence, userPlaybackIndex), /watch-follow-up-evidence-mismatch/);

const memory = new Map();
const storage = { getItem: (key) => memory.get(key) ?? null, setItem: (key, value) => memory.set(key, value) };
const source = catalog.sources[0];
const before = structuredClone(source);
const report = createUserWatchFeedbackReport({
  reportId: 'test-report-001', source, testedAt: '2026-10-19T12:00:00.000Z',
  playbackStarted: 'YES', loginRequired: 'UNKNOWN', territoryRestricted: 'UNKNOWN',
});
assert.equal(report.evidence_class, 'USER_REPORTED');
assert.deepEqual(Object.keys(report).sort(), ['evidence_class', 'login_required', 'playback_started', 'report_id', 'source_id', 'source_url', 'territory_restricted', 'tested_at'].sort(), 'user feedback must not contain or upgrade independent verification fields');
assert.equal(report.source_id, source.source_id);
assert.equal(report.source_url, source.url);
assert.deepEqual(source, before, 'a user report must not mutate catalog verification or playback state');
assert.deepEqual(appendUserWatchFeedback(storage, report), [report]);
assert.deepEqual(readUserWatchFeedback(storage), [report]);
const exported = parseUserWatchFeedbackExport(serializeUserWatchFeedback(readUserWatchFeedback(storage)));
validateSchema(feedbackSchema, exported);
assert.equal(feedbackSchema.$id, exported.contract_version);
assert.equal(exported.contract_version, 'ptti.user-watch-feedback/0.1');
assert.equal(exported.evidence_class, 'USER_REPORTED');
assert.deepEqual(exported.reports, [report]);
assert.throws(() => appendUserWatchFeedback(storage, report), /duplicate-user-watch-feedback-id/);
assert.throws(() => createUserWatchFeedbackReport({ reportId: 'bad-url', source: { source_id: 'x', url: 'http://example.test' }, testedAt: '2026-10-19T12:00:00Z', playbackStarted: 'YES', loginRequired: 'NO', territoryRestricted: 'NO' }), /invalid-user-watch-feedback-url/);
assert.throws(() => createUserWatchFeedbackReport({ reportId: 'bad-state', source, testedAt: '2026-10-19T12:00:00Z', playbackStarted: 'VERIFIED', loginRequired: 'NO', territoryRestricted: 'NO' }), /invalid-user-watch-feedback-report/);
const rawBeforeTamper = JSON.stringify([{ ...report, evidence_class: 'INDEPENDENTLY_VERIFIED' }]);
storage.setItem(USER_WATCH_FEEDBACK_KEY, rawBeforeTamper);
assert.throws(() => readUserWatchFeedback(storage), /invalid-user-watch-feedback-report/);
assert.equal(memory.get(USER_WATCH_FEEDBACK_KEY), rawBeforeTamper, 'malformed local reports fail closed without overwriting the user record');
const localFollowUpSource = followUpQueue[0].source;
const mergedLocalReports = mergeLocalUserFeedbackSources(userPlaybackIndex, catalog.sources, [{ evidence_class: 'USER_REPORTED', source_id: localFollowUpSource.source_id, source_url: localFollowUpSource.url }]);
assert.equal(buildWatchFollowUpQueue(catalog.sources, index, mergedLocalReports).length, 13, 'a locally recorded source leaves the pending queue');
assert.throws(() => mergeLocalUserFeedbackSources(userPlaybackIndex, catalog.sources, [{ evidence_class: 'USER_REPORTED', source_id: localFollowUpSource.source_id, source_url: 'https://www.youtube.com/watch?v=wrong' }]), /local-watch-feedback-source-url-mismatch/);

const localeSource = await readFile('src/i18n.ts', 'utf8');
for (const key of ['watchEvidence.title', 'watchEvidence.matchLink', 'watchEvidence.pageThrottled', 'watchEvidence.videoStart', 'watchEvidence.completeWatch', 'watchEvidence.feedbackIntro', 'watchEvidence.saveReport', 'watchEvidence.feedbackError', 'watchEvidence.reportedStarted', 'watchEvidence.reportedOn', 'watchEvidence.reportedTimeNotProvided', 'watchEvidence.followUpQueue', 'watchEvidence.openWatchRecord', 'fan.matchLinkTitleOnly', 'fan.copyOfficialUrl', 'fan.officialUrlCopied', 'fan.officialUrlManualCopy', 'fan.officialUrlLabel']) {
  const hits = localeSource.match(new RegExp(`'${key.replaceAll('.', '\\.')}':`, 'g')) ?? [];
  assert.equal(hits.length, 2, `${key} must be translated in both supported locales`);
}
const watchPageSource = await readFile('src/FanCatalogPage.tsx', 'utf8');
assert(watchPageSource.includes('data-watchability-evidence') && watchPageSource.includes('data-user-watch-feedback'));
assert(watchPageSource.includes('data-user-provided-playback') && watchPageSource.includes('data-watch-follow-up-queue'));
assert(watchPageSource.includes('navigator.clipboard?.writeText') && watchPageSource.includes('await navigator.clipboard.writeText(activeWatchSource.url)')
  && watchPageSource.includes("setWatchUrlCopyState('manual')") && watchPageSource.includes('readOnly value={activeSource.url}'), 'official URL copy has an accessible manual fallback');
assert(watchPageSource.includes("import.meta.env.DEV"), 'Main addendum must be loaded only by the local development Watch view');

if (process.argv.includes('--built')) {
  const dist = resolve('dist');
  async function listFiles(directory) {
    const items = await readdir(directory, { withFileTypes: true });
    return (await Promise.all(items.map((item) => item.isDirectory() ? listFiles(join(directory, item.name)) : [join(directory, item.name)]))).flat();
  }
  const files = await listFiles(dist);
  const forbidden = [
    'ptti.goal19.1-watchability-evidence/0.1',
    'SAN_INTERNAL_REVIEW_ADDENDUM',
    'current_fetch_throttled_count',
    'supplemental_event_page_fetches',
    'ptti.user-watch-playback-reports/0.1',
    'USER_PROVIDED_IN_REQUEST',
    'goal19.3-user-playback-reports-v0.1.json',
  ];
  for (const file of files) {
    if (!/\.(?:js|css|html|json|svg|txt|map)$/i.test(file)) continue;
    const text = await readFile(file, 'utf8');
    for (const marker of forbidden) assert(!text.includes(marker), `internal watch evidence leaked into ${file}: ${marker}`);
  }
  const evidenceAssets = files.filter((file) => /goal19-watchability-evidence/i.test(file));
  assert.deepEqual(evidenceAssets, [], 'the internal evidence source and its chunks must not ship in dist');
  const userReportAssets = files.filter((file) => /goal19\.3-user-playback-reports/i.test(file));
  assert.deepEqual(userReportAssets, [], 'user-provided playback reports must remain outside production dist');
  console.log('PASS: production dist contains no Goal19 internal addendum, review-only fields, or evidence chunks.');
}

console.log('PASS: GOAL19 schema and SHA; exact 17/17 source_id, URL, and match identity joins; 5 HUMAN_VERIFIED + 2 title-only + 10 event-level; throttling and FULL_MATCH titles remain non-playback evidence.');
console.log('PASS: USER_REPORTED feedback local storage, JSON export contract, HTTPS source binding, and fail-closed validation.');
console.log('PASS: USER_REPORTED feedback JSON Schema and bilingual Watch copy.');
console.log('PASS: 3 exact user-reported playback starts are isolated from independent verification; remaining 14-source queue is exact, prioritized, and fails closed.');
