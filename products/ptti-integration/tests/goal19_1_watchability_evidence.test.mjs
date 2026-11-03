import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { buildEvidenceReport, validateEvidenceReport } from '../scripts/build_goal19_1_watchability_evidence.mjs';

const root = new URL('../', import.meta.url);
const basePath = new URL('generated/goal15-main-fan-universe-public-v0.2/match-library-strict-public.json', root);
const deltaPath = new URL('generated/goal17-1-real-content-v0.1/public/official-match-video-additions.json', root);
const digest = (bytes) => createHash('sha256').update(bytes).digest('hex');

async function fixtures() {
  const [baseBytes, deltaBytes] = await Promise.all([readFile(basePath), readFile(deltaPath)]);
  return {
    baseBytes, deltaBytes,
    base: JSON.parse(baseBytes.toString('utf8')),
    delta: JSON.parse(deltaBytes.toString('utf8'))
  };
}

test('reconciles all 17 public sources without duplicate IDs or URLs', async () => {
  const input = await fixtures();
  const report = buildEvidenceReport({ ...input, generatedAt: '2026-10-19T10:30:00.000Z' });
  assert.equal(report.sources.length, 17);
  assert.equal(new Set(report.sources.map((source) => source.source_id)).size, 17);
  assert.equal(new Set(report.sources.map((source) => source.official_target_url)).size, 17);
  assert.equal(report.summary.source_match_link_count, 7);
  assert.equal(report.summary.event_level_or_unlinked_count, 10);
  assert.deepEqual(report.summary.video_type_claim_counts, {
    FULL_MATCH_TITLE_CLAIM: 5,
    MATCH_SPECIFIC_TYPE_UNKNOWN: 2,
    EVENT_HIGHLIGHTS_TITLE_CLAIM: 10
  });
  assert.equal(report.summary.match_link_baseline_counts.HUMAN_VERIFIED, 5);
  assert.equal(report.summary.match_link_baseline_counts['OFFICIAL_VIDEO_TITLE_MATCH_ASSOCIATION; VISUAL_MATCH_NOT_TESTED'], 2);
  assert.equal(report.summary.match_link_baseline_counts.UNKNOWN, 10);
  assert.equal(report.supplemental_event_page_fetches.length, 2);
  assert.equal(validateEvidenceReport(report).valid, true);
});

test('separates one title-surfaced page, four throttled fetches, and twelve untested sources', async () => {
  const input = await fixtures();
  const report = buildEvidenceReport({ ...input, generatedAt: '2026-10-19T10:30:00.000Z' });
  assert.equal(report.summary.current_fetch_title_surfaced_count, 1);
  assert.equal(report.summary.current_fetch_throttled_count, 4);
  assert.equal(report.summary.current_fetch_not_attempted_count, 12);
  assert.equal(report.summary.external_system_browser_open_count, 0);
  assert.equal(report.summary.direct_video_start_count, 0);
  assert.equal(report.summary.complete_watch_count, 0);
  const surfaced = report.sources.find((source) => source.source_id === 'video-source:youtube:0QgbtsBWZhk');
  assert.equal(surfaced.verification_levels.page_exists, 'PARTIAL_PAGE_TITLE_SURFACED');
  assert.equal(surfaced.verification_levels.video_started, 'NOT_TESTED');
  for (const sourceId of ['video-source:youtube:ttUevnAZSEY', 'video-source:youtube:cDccQqVlMnc', 'youtube:ywX9mUJ8NtI', 'youtube:Kbhf47vb3eE']) {
    const source = report.sources.find((item) => item.source_id === sourceId);
    assert.equal(source.current_page_fetch.status, 'BLOCKED_FETCH_THROTTLED');
    assert.equal(source.verification_levels.page_exists, 'BLOCKED');
  }
});

test('FULL MATCH titles do not establish completeness or playback', async () => {
  const input = await fixtures();
  const report = buildEvidenceReport({ ...input, generatedAt: '2026-10-19T10:30:00.000Z' });
  for (const source of report.sources.filter((item) => item.video_type_claim === 'FULL_MATCH_TITLE_CLAIM')) {
    assert.equal(source.claimed_full_match_completeness === 'VERIFIED_COMPLETE', false);
    assert.equal(source.verification_levels.video_started, 'NOT_TESTED');
    assert.equal(source.verification_levels.complete_watch, 'UNVERIFIED');
  }
});

test('event-level highlights remain unbound and access permissions do not escalate', async () => {
  const input = await fixtures();
  const report = buildEvidenceReport({ ...input, generatedAt: '2026-10-19T10:30:00.000Z' });
  const highlights = report.sources.filter((source) => source.video_type_claim === 'EVENT_HIGHLIGHTS_TITLE_CLAIM');
  assert.equal(highlights.length, 10);
  assert.ok(highlights.every((source) => source.match_id === null));
  assert.ok(report.sources.every((source) => source.access.current_embed_permission !== 'ALLOWED'));
  assert.ok(report.sources.every((source) => source.access.thumbnail_display_permission !== 'ALLOWED'));
  assert.ok(report.sources.every((source) => source.access.download_permission !== 'ALLOWED'));
  assert.ok(report.sources.every((source) => source.access.redistribution_permission !== 'ALLOWED'));
});

test('validator rejects duplicate identity and attempted evidence escalation', async () => {
  const input = await fixtures();
  const report = buildEvidenceReport({ ...input, generatedAt: '2026-10-19T10:30:00.000Z' });
  const duplicate = structuredClone(report);
  duplicate.sources[1].source_id = duplicate.sources[0].source_id;
  assert.equal(validateEvidenceReport(duplicate).valid, false);
  const escalated = structuredClone(report);
  escalated.sources[0].verification_levels.video_started = 'PASS';
  assert.equal(validateEvidenceReport(escalated).errors.includes('playback_evidence_escalated:video-source:youtube:0QgbtsBWZhk'), true);
  const highlightMisbound = structuredClone(report);
  const highlight = highlightMisbound.sources.find((source) => source.video_type_claim === 'EVENT_HIGHLIGHTS_TITLE_CLAIM');
  highlight.match_id = 'invented-match-id';
  assert.equal(validateEvidenceReport(highlightMisbound).errors.includes(`event_highlights_bound_to_match:${highlight.source_id}`), true);
  const badCount = structuredClone(report);
  badCount.summary.source_match_link_count += 1;
  assert.equal(validateEvidenceReport(badCount).errors.includes('summary_match_link_count_mismatch'), true);
});

test('versioned schema is readable and pins the additive contract identifier', async () => {
  const schemaUrl = new URL('../contracts/goal19-1-watchability-evidence-v0.1.schema.json', import.meta.url);
  const schema = JSON.parse(await readFile(schemaUrl, 'utf8'));
  assert.equal(schema.$id, 'ptti.goal19.1-watchability-evidence/0.1');
  assert.equal(schema.additionalProperties, false);
  assert.ok(schema.required.includes('verification_definitions'));
});

test('input byte identities are reported without mutating the stable source packages', async () => {
  const input = await fixtures();
  const originalBaseSha = digest(input.baseBytes);
  const originalDeltaSha = digest(input.deltaBytes);
  const report = buildEvidenceReport({ ...input, generatedAt: '2026-10-19T10:30:00.000Z' });
  assert.equal(report.input_identity.base_sha256, originalBaseSha);
  assert.equal(report.input_identity.goal17_1_delta_sha256, originalDeltaSha);
  assert.equal(digest(await readFile(basePath)), originalBaseSha);
  assert.equal(digest(await readFile(deltaPath)), originalDeltaSha);
});
