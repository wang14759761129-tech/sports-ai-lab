import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { consumeFanCatalog } from '../src/fan-catalog.mjs';
import { discoverFanContent } from '../src/fan-discovery.mjs';
import { ATHLETE_JOURNAL_FIELDS, consumeAthleteJournal, consumeFanLocalData, emptyFanLocalData, parseFanLocalDataBackup, readFanLocalData, serializeFanLocalDataBackup, writeFanLocalData } from '../src/fan-local-data.mjs';
import { appendFeedback, readFeedback } from '../src/feedback-storage.mjs';

const catalog = consumeFanCatalog(JSON.parse(await readFile(new URL('../public/data/match-library-strict-public.json', import.meta.url), 'utf8')));
const highlights = catalog.sources.filter((source) => source.content_type_claim === 'HIGHLIGHTS');
assert.equal(discoverFanContent(catalog).length, 10);
assert.deepEqual(discoverFanContent(catalog).map((row) => row.source_id), highlights.map((row) => row.source_id));
assert.equal(discoverFanContent(catalog, { contentType: 'CLIP' }).length, 0);
assert.equal(discoverFanContent(catalog, { contentType: 'FULL_MATCH' }).length, 0);
assert.equal(discoverFanContent(catalog, { platform: 'YOUTUBE' }).length, 10);
assert.equal(discoverFanContent(catalog, { platform: 'X' }).length, 0);
for (const event of new Set(highlights.map((row) => row.event))) {
  assert.deepEqual(discoverFanContent(catalog, { event }).map((row) => row.source_id), highlights.filter((row) => row.event === event).map((row) => row.source_id));
}
for (const player of catalog.stars) assert.equal(discoverFanContent(catalog, { athleteId: player.athlete_id }).length, 0, 'event highlights cannot be assigned to a player through event participation');
for (const trainingType of ['serve', 'receive', 'technique', 'mindset', 'invented']) assert.equal(discoverFanContent(catalog, { trainingType }).length, 0);
assert.equal(discoverFanContent(catalog, { trainingType: 'UNKNOWN' }).length, 10);
assert(discoverFanContent(catalog, { query: highlights[0].event }).length > 0);
assert.equal(discoverFanContent(catalog, { query: 'not-a-real-title' }).length, 0);
// Synthetic contract case stays in the test: association needs an exact, reciprocal, human-verified edge.
const synthetic = structuredClone(catalog);
const row = synthetic.sources.find((source) => source.source_id === highlights[0].source_id);
const match = synthetic.matches[0];
row.canonical_match_id = match.match_id;
row.match_link_status = 'HUMAN_VERIFIED';
match.video_source_ids.push(row.source_id);
const athleteId = match.participants.find((person) => person.athlete_id)?.athlete_id;
assert.equal(discoverFanContent(synthetic, { athleteId }).length, 1);
row.match_link_status = 'TITLE_MATCH_ASSOCIATION';
assert.equal(discoverFanContent(synthetic, { athleteId }).length, 0);
row.match_link_status = 'HUMAN_VERIFIED';
match.video_source_ids = [];
assert.equal(discoverFanContent(synthetic, { athleteId }).length, 0);
row.external_viewing = 'UNKNOWN';
assert(!discoverFanContent(synthetic).some((source) => source.source_id === row.source_id));

const journal = consumeAthleteJournal({ contract_version: 'ptti.athlete-journal/0.1', author: 'SELF', ...Object.fromEntries(ATHLETE_JOURNAL_FIELDS.map((field) => [field, `My own ${field}: <script>plain text</script>`])) });
assert.equal(ATHLETE_JOURNAL_FIELDS.length, 6);
const data = emptyFanLocalData();
data.training_notes.push({ id: 'self-journal', date: '2026-10-20', topic: 'My practice', technical_question: journal.technical_issue, summary: 'Personal observations only', next_goal: journal.next_improvement, match_id: null, athlete_journal: journal });
const storage = new Map();
const local = { getItem: (key) => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) };
writeFanLocalData(local, data);
assert.deepEqual(readFanLocalData(local), data, 'restart reads all six journal fields');
const edited = readFanLocalData(local);
edited.training_notes[0].athlete_journal.training_goal = 'Updated goal';
assert.equal(data.training_notes[0].athlete_journal.training_goal, journal.training_goal, 'editing a read copy does not mutate existing data');
writeFanLocalData(local, edited);
assert.equal(readFanLocalData(local).training_notes[0].athlete_journal.training_goal, 'Updated goal');
assert.deepEqual(parseFanLocalDataBackup(serializeFanLocalDataBackup(edited)), edited, 'backup/import keeps the original personal text');
assert.deepEqual(consumeFanLocalData({ ...data, training_notes: [{ ...data.training_notes[0], athlete_journal: undefined }] }).training_notes[0].athlete_journal, undefined, 'old notes require no journal migration');
for (const invalid of [{ ...journal, author: 'Wang Chuqin' }, { ...journal, contract_version: 'future' }, { ...journal, training_goal: 3 }, { ...journal, training_goal: 'x'.repeat(1001) }, { ...journal, extra: 'not in the contract' }]) {
  assert.throws(() => consumeAthleteJournal(invalid), /invalid-athlete-journal/);
  const invalidData = structuredClone(data); invalidData.training_notes[0].athlete_journal = invalid;
  assert.throws(() => parseFanLocalDataBackup(JSON.stringify(invalidData)), /invalid-athlete-journal/);
}
const deleted = readFanLocalData(local); deleted.training_notes = []; writeFanLocalData(local, deleted);
assert.equal(readFanLocalData(local).training_notes.length, 0);
assert.throws(() => writeFanLocalData({ getItem() { return null; }, setItem() { throw Error('quota'); } }, data), /quota/);
appendFeedback(local, { id: 'test-local-feedback', createdAt: '2026-10-20T00:00:00Z', context: { page: 'watch', source_id: catalog.sources[0].source_id, match_id: catalog.matches[0].match_id, athlete_id: null }, friction: 'My own feedback' });
assert.deepEqual(JSON.parse(JSON.stringify(readFeedback(local)))[0].context.source_id, catalog.sources[0].source_id);
console.log('PASS: GOAL22 real-catalog discovery, exact source association, unknown training filters, six-field SELF journal CRUD/restart/backup, legacy notes, invalid-input rejection and local feedback context. Browser NOT_TESTED.');
