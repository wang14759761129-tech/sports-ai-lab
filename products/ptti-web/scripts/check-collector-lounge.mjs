import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { consumeFanCatalog } from '../src/fan-catalog.mjs';
import { applyGoal17MatchAdditions } from '../src/goal17-match-additions.mjs';
import { applyFanInspiration } from '../src/fan-inspiration.mjs';
import { createCollectorCards, removeCollectorMatch } from '../src/collector-lounge.mjs';
import { ATHLETE_JOURNAL_FIELDS, emptyFanLocalData, parseFanLocalDataBackup, readFanLocalData, serializeFanLocalDataBackup, writeFanLocalData } from '../src/fan-local-data.mjs';

const read = async (file) => JSON.parse(await readFile(new URL(`../public/data/${file}`, import.meta.url), 'utf8'));
const base = consumeFanCatalog(await read('match-library-strict-public.json'));
const catalog = applyFanInspiration(applyGoal17MatchAdditions(base, await read('goal17-official-match-video-additions.json')), await read('fan-inspiration-v0.1.json')).catalog;
const before = JSON.stringify(catalog);
const matchId = 'pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun';
const sourceId = 'video-source:youtube:0QgbtsBWZhk';
const saved = [matchId, 'match:synthetic-unlisted'];
const cards = createCollectorCards(catalog, saved);
assert.deepEqual(cards.map((card) => card.match_id), saved);
assert.equal(cards[0].match, catalog.matches.find((match) => match.match_id === matchId));
assert.equal(cards[0].watch_source.source_id, sourceId);
assert.equal(cards[0].watch_source.url, 'https://www.youtube.com/watch?v=0QgbtsBWZhk');
assert.deepEqual(cards[0].result, { player_a_games: 4, player_b_games: 0 });
assert.deepEqual(cards[0].watch_source.evidence_source_ids, ['wtt-youtube-full-match-0QgbtsBWZhk', 'youtube-share-link-help'], 'GOAL28 evidence stays intact');
assert.equal(cards[0].watch_source.embedding, 'UNKNOWN');
assert.equal(cards[0].watch_source.thumbnail_display, 'NOT_ALLOWED');
assert.equal(cards[0].watch_source.recorded_playback_status, 'EMBED_BLOCKED_HISTORICAL');
assert.equal(cards[0].watch_source.current_session_eligibility, 'NOT_EVALUATED_CURRENT_SESSION');
assert.deepEqual(cards[1], { match_id: saved[1], match: null, watch_source: null, result: null });
assert.deepEqual(createCollectorCards(catalog, []), []);
assert.equal(createCollectorCards(null, saved)[0].match_id, matchId, 'a loading/unavailable catalog never deletes saved identities');
assert.equal(createCollectorCards(catalog, catalog.matches.map((match) => match.match_id)).length, 7);

for (const mutate of [
  (source) => { source.canonical_match_id = 'match:wrong'; },
  (source) => { source.match_link_status = 'UNKNOWN'; },
  (source) => { source.external_viewing = 'UNKNOWN'; },
  (source) => { source.source_identity_status = 'UNKNOWN'; },
  (source) => { source.url = null; },
]) {
  const changed = structuredClone(catalog);
  mutate(changed.sources.find((source) => source.source_id === sourceId));
  assert.equal(createCollectorCards(changed, [matchId])[0].watch_source, null);
}
{
  const changed = structuredClone(catalog);
  changed.matches.find((match) => match.match_id === matchId).result_status = 'UNKNOWN';
  assert.equal(createCollectorCards(changed, [matchId])[0].result, null, 'unverified score is not displayed');
}
assert.equal(JSON.stringify(catalog), before);

// Synthetic storage only: exercise the same write/read/export APIs used by App and My Corner.
const storage = { values: new Map(), getItem(key) { return this.values.get(key) ?? null; }, setItem(key, value) { this.values.set(key, value); } };
const data = emptyFanLocalData();
data.saved_match_ids = saved;
data.followed_athlete_ids = ['athlete:121558'];
data.training_notes = [{ id: 'qa-journal', date: '2026-10-21', topic: 'Synthetic QA', technical_question: '', summary: 'Private synthetic note', next_goal: '', match_id: matchId,
  athlete_journal: { contract_version: 'ptti.athlete-journal/0.1', author: 'SELF', ...Object.fromEntries(ATHLETE_JOURNAL_FIELDS.map((field) => [field, `synthetic ${field}`])) } }];
writeFanLocalData(storage, data);
const removed = removeCollectorMatch(readFanLocalData(storage), matchId);
writeFanLocalData(storage, removed);
const restored = parseFanLocalDataBackup(serializeFanLocalDataBackup(readFanLocalData(storage)));
assert.deepEqual(restored.saved_match_ids, [saved[1]]);
assert.deepEqual(restored.training_notes, data.training_notes);
assert.deepEqual(restored.followed_athlete_ids, data.followed_athlete_ids);
assert.deepEqual(data.saved_match_ids, saved, 'removal does not mutate the previous state');
const legacy = parseFanLocalDataBackup(JSON.stringify({ contract_version: 'ptti.fan-local-data/1', saved_match_ids: saved, followed_athlete_ids: [], training_notes: [], fan_notes: [] }));
assert.deepEqual(legacy.saved_match_ids, saved);
assert.equal(createCollectorCards(catalog, legacy.saved_match_ids)[0].watch_source.source_id, sourceId);
console.log('PASS: Collector cards join exact real match/source IDs; official result gate, empty/missing catalog, five denied Watch cases and GOAL28 evidence preserved.');
console.log('PASS: synthetic save/remove/reload/JSON round-trip, legacy saved IDs, six Journal fields and follows preserved; catalog and previous state remain unchanged.');
