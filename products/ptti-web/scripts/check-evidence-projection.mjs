import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { consumeFanCatalog } from '../src/fan-catalog.mjs';

const input = JSON.parse(await readFile(new URL('../public/data/match-library-strict-public.json', import.meta.url), 'utf8'));
const targetSourceId = 'video-source:youtube:0QgbtsBWZhk';
const evidenceIds = new Set(input.evidence_sources.map((item) => item.source_id));

function consumeSource(sourceId = targetSourceId, mutate = () => {}) {
  const fixture = structuredClone(input);
  const source = fixture.video_sources.find((item) => item.source_id === sourceId);
  assert.ok(source, `fixture source exists: ${sourceId}`);
  mutate(source, fixture);
  return { source, projected: consumeFanCatalog(fixture).sources.find((item) => item.source_id === sourceId) };
}

// This real Main record is the original regression: evidence is present under rights,
// while provenance has no source_id. It must survive projection unchanged.
{
  const { source, projected } = consumeSource();
  assert.deepEqual(source.rights.evidence_source_ids, [
    'wtt-youtube-full-match-0QgbtsBWZhk',
    'youtube-share-link-help',
  ]);
  assert.deepEqual(projected.evidence_source_ids, source.rights.evidence_source_ids);
}

// Provenance IDs precede rights IDs, with stable first-seen deduplication.
{
  const { source, projected } = consumeSource(targetSourceId, (row) => {
    row.provenance[0].source_id = 'wtt-youtube-full-match-0QgbtsBWZhk';
    row.rights.evidence_source_ids = [
      'youtube-share-link-help',
      'wtt-youtube-full-match-0QgbtsBWZhk',
      'youtube-share-link-help',
    ];
  });
  assert.deepEqual(projected.evidence_source_ids, [
    'wtt-youtube-full-match-0QgbtsBWZhk',
    'youtube-share-link-help',
  ]);
  assert.equal(projected.evidence_source_ids.length, new Set(projected.evidence_source_ids).size);
  assert.equal(projected.external_viewing, source.rights.external_viewing);
  assert.equal(projected.embedding, source.rights.embedding);
  assert.equal(projected.current_session_eligibility, 'NOT_EVALUATED_CURRENT_SESSION');
  assert.equal(projected.recorded_playback_status, source.availability.latest_recorded_playback_status);
}

// Either contract location may be absent; the remaining valid location is projected.
{
  const { projected } = consumeSource(targetSourceId, (row) => {
    row.provenance[0].source_id = 'wtt-youtube-full-match-0QgbtsBWZhk';
    delete row.rights.evidence_source_ids;
  });
  assert.deepEqual(projected.evidence_source_ids, ['wtt-youtube-full-match-0QgbtsBWZhk']);
}
{
  const { projected } = consumeSource(targetSourceId, (row) => {
    delete row.provenance[0].source_id;
  });
  assert.deepEqual(projected.evidence_source_ids, [
    'wtt-youtube-full-match-0QgbtsBWZhk',
    'youtube-share-link-help',
  ]);
}

// A season/event-level highlight with both optional evidence-ID locations absent
// stays empty; other provenance fields are not guessed as a substitute.
{
  const highlight = input.video_sources.find((source) => source.content_type_claim === 'HIGHLIGHTS'
    && source.canonical_match_id === null);
  assert.ok(highlight, 'fixture contains an event-level highlight');
  const noEvidenceFixture = structuredClone(input);
  const noEvidenceHighlight = noEvidenceFixture.video_sources.find((source) => source.source_id === highlight.source_id);
  delete noEvidenceHighlight.rights.evidence_source_ids;
  for (const row of noEvidenceHighlight.provenance) delete row.source_id;
  const projected = consumeFanCatalog(noEvidenceFixture).sources.find((source) => source.source_id === highlight.source_id);
  assert.deepEqual(projected.evidence_source_ids, []);
}

// Present but malformed or unregistered IDs are rejected instead of silently ignored.
for (const invalid of [
  (source) => { source.rights.evidence_source_ids = 'wtt-youtube-full-match-0QgbtsBWZhk'; },
  (source) => { source.rights.evidence_source_ids = [42]; },
  (source) => { source.rights.evidence_source_ids = ['evidence:not-in-catalog']; },
  (source) => { source.provenance[0].source_id = 42; },
  (source) => { source.provenance[0].source_id = 'evidence:not-in-catalog'; },
  (source) => { source.provenance[0] = null; },
]) {
  assert.throws(() => consumeSource(targetSourceId, invalid), /invalid-source-provenance|invalid-source-evidence/);
}

assert(evidenceIds.has('wtt-youtube-full-match-0QgbtsBWZhk'));
assert(evidenceIds.has('youtube-share-link-help'));
console.log('PASS: real Main rights evidence is preserved; provenance and rights IDs merge in stable unique order.');
console.log('PASS: absent fields remain supported; event highlights do not gain invented evidence IDs.');
console.log('PASS: malformed and unregistered evidence references fail closed without changing playback or rights state.');
