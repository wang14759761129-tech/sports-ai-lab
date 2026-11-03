import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { consumeFanCatalog } from '../src/fan-catalog.mjs';
import { applyGoal17MatchAdditions } from '../src/goal17-match-additions.mjs';
import { applyFanInspiration, consumeFanInspiration, FAN_INSPIRATION_SHA } from '../src/fan-inspiration.mjs';
import { buildFanWatchRouteCandidates } from '../src/fan-watch-routing.mjs';
import { discoverFanContent } from '../src/fan-discovery.mjs';
import { ATHLETE_JOURNAL_FIELDS, FAN_LOCAL_DATA_KEY, FAN_LOCAL_RECOVERY_KEY, emptyFanLocalData, prepareFanLocalDataImport, commitFanLocalDataImport, parseFanLocalDataBackup, readFanImportRecovery, serializeFanLocalDataBackup, writeFanLocalData } from '../src/fan-local-data.mjs';

const root = new URL('../', import.meta.url);
const read = async (path) => readFile(new URL(path, root));
const hash = (bytes) => createHash('sha256').update(bytes).digest('hex');
const bytes = await read('public/data/fan-inspiration-v0.1.json');
assert.equal(hash(bytes), FAN_INSPIRATION_SHA);
assert.equal(hash(await read('src/contracts/fan-inspiration-v0.1.schema.json')), 'cc6459865ee230fd6218bd720a5d6f24cd4d42647346a93378d81d7577e19949');
const input = JSON.parse(bytes);
const base = applyGoal17MatchAdditions(consumeFanCatalog(JSON.parse(await read('public/data/match-library-strict-public.json'))), JSON.parse(await read('public/data/goal17-official-match-video-additions.json')));
const before = JSON.stringify(base);
const result = applyFanInspiration(base, input);
assert.equal(JSON.stringify(base), before, 'Main baseline is not mutated');
assert.deepEqual([result.catalog.matches.length, result.catalog.sources.length, result.catalog.stars.length], [7, 18, 8]);
assert.equal(applyFanInspiration(result.catalog, input).catalog.sources.length, 18, 'stable IDs prevent double insertion');
assert.deepEqual(result.catalog.sources.slice(0, 17), base.sources, 'existing sources, permissions and verification levels remain unchanged');
const added = result.catalog.sources.filter((source) => !base.sources.some((old) => old.source_id === source.source_id));
assert.equal(added.length, 1);
assert.equal(added[0].source_id, input.clips.find((source) => source.video_category === 'SEASON_HIGHLIGHTS_TITLE_CLAIM').source_id);
assert.equal(added[0].canonical_match_id, null);
assert.equal(added[0].recorded_playback_status, 'NOT_TESTED');
assert.equal(discoverFanContent(result.catalog).length, 11);
assert.equal(discoverFanContent(result.catalog, { athleteId: 'athlete:121558' }).length, 0);
assert.equal(result.inspiration.international_reactions.length, 1);
assert.equal(result.inspiration.gear_dossiers.length, 3);
assert(result.inspiration.gear_dossiers.every((d) => d.participants.every((p) => p.items.length === 4 && p.items.every((i) => i.model === null && i.brand === null && i.status === 'UNKNOWN'))));
const routes = buildFanWatchRouteCandidates(added[0]);
assert.equal(routes.find((r) => r.mode === 'OFFICIAL_PAGE').viewingPermission, 'PUBLIC_PLATFORM_PAGE');
assert.equal(routes.find((r) => r.mode === 'OFFICIAL_EMBED').embedPermission, 'UNKNOWN');
for (const mutate of [
  d => { d.view = 'INTERNAL_REVIEW'; }, d => { d.input_identity.base_sha256 = '0'.repeat(64); },
  d => { d.internal_path = 'C:/private'; }, d => { d.clips[0].rights.embed = 'ALLOWED'; },
  d => { d.clips[0].match_id = base.matches[0].match_id; }, d => { d.clips[0].athlete_ids = ['athlete:121558']; },
  d => { d.clips[1].source_id = d.clips[0].source_id; }, d => { d.clips[0].original_url = 'https://www.youtube.com/watch?v=wrongtarget'; },
  d => { d.international_reactions[0].source_url = 'https://unverified.example/report'; },
  d => { d.gear_dossiers[0].participants[0].items[0].model = 'guessed-model'; },
  d => { d.gear_dossiers[0].participants[0].athlete_id = 'athlete:131163'; },
  d => { d.generated_at = '2026-02-31T00:00:00Z'; },
  d => { d.clips[0].publisher_url = 'https://unverified.example/channel'; },
]) { const bad = structuredClone(input); mutate(bad); assert.throws(() => consumeFanInspiration(bad, base)); }
const publicText = bytes.toString();
assert.doesNotMatch(publicText, /(?:^|["\s])[A-Z]:[\\/]|source_manifest|review-register|INTERNAL_ONLY|internal_review/i);

// Every storage object below is an isolated synthetic store. No browser storage is accessed.
function memory(initial, failKey) {
  const map = new Map(initial === null ? [] : [[FAN_LOCAL_DATA_KEY, initial]]); const writes = [];
  return { map, writes, getItem: (key) => map.get(key) ?? null, setItem(key, value) { if (key === failKey) throw Error('quota'); writes.push(key); map.set(key, value); } };
}
const current = emptyFanLocalData();
const journal = { contract_version: 'ptti.athlete-journal/0.1', author: 'SELF', ...Object.fromEntries(ATHLETE_JOURNAL_FIELDS.map((key) => [key, `Synthetic personal text ${key} <script>inert</script>`])) };
current.training_notes.push({ id: 'synthetic-note', date: '2026-10-20', topic: 'Original', technical_question: '', summary: 'Original summary', next_goal: '', match_id: null, athlete_journal: journal });
current.training_notes.push({ ...structuredClone(current.training_notes[0]), id: 'removed-note' });
current.saved_match_ids = [base.matches[0].match_id]; current.followed_athlete_ids = [base.stars[0].athlete_id];
const replacement = structuredClone(current); replacement.training_notes.pop(); replacement.training_notes[0].topic = 'Edited import'; replacement.saved_match_ids = []; replacement.followed_athlete_ids = [];
const raw = serializeFanLocalDataBackup(current); const incoming = serializeFanLocalDataBackup(replacement);
const refs = { matchIds: base.matches.map((m) => m.match_id), athleteIds: base.stars.map((s) => s.athlete_id) };
for (const invalid of ['{', JSON.stringify({ ...replacement, extra_unknown_field: true }), JSON.stringify({ ...replacement, training_notes: [{ ...replacement.training_notes[0], future_field: 'must not drop' }] }), JSON.stringify({ ...replacement, saved_match_ids: ['unlisted'] })]) {
  const store = memory(raw); assert.throws(() => prepareFanLocalDataImport(store, invalid, refs));
  assert.equal(store.getItem(FAN_LOCAL_DATA_KEY), raw); assert.equal(store.writes.length, 0);
}
const store = memory(raw); const plan = prepareFanLocalDataImport(store, incoming, refs);
store.map.set('synthetic-unrelated-storage', 'keep');
assert.deepEqual([plan.conflicts, plan.removed, plan.savedRemoved, plan.followedRemoved], [1, 1, 1, 1]);
assert.equal(store.writes.length, 0, 'preview is read-only');
assert.throws(() => commitFanLocalDataImport(store, plan), /confirmation-required/);
assert.equal(store.writes.length, 0, 'cancel/no confirmation performs no writes');
const imported = commitFanLocalDataImport(store, plan, true);
assert.deepEqual(store.writes, [FAN_LOCAL_RECOVERY_KEY, FAN_LOCAL_DATA_KEY], 'recovery always precedes replacement');
assert.deepEqual(imported, replacement);
assert.equal(store.getItem('synthetic-unrelated-storage'), 'keep', 'only the Fan data key and its recovery copy are written');
assert.equal(readFanImportRecovery(store), raw, 'pre-import copy keeps exact original bytes');
assert.deepEqual(parseFanLocalDataBackup(readFanImportRecovery(store)), current);
assert.deepEqual(parseFanLocalDataBackup(store.getItem(FAN_LOCAL_DATA_KEY)).training_notes[0].athlete_journal, journal);
const allFieldsEdited = structuredClone(imported);
for (const field of ATHLETE_JOURNAL_FIELDS) allFieldsEdited.training_notes[0].athlete_journal[field] = `Edited ${field}`;
assert.deepEqual(parseFanLocalDataBackup(serializeFanLocalDataBackup(allFieldsEdited)).training_notes[0].athlete_journal, allFieldsEdited.training_notes[0].athlete_journal);
for (const key of [FAN_LOCAL_RECOVERY_KEY, FAN_LOCAL_DATA_KEY]) {
  const blocked = memory(raw, key); const p = prepareFanLocalDataImport(blocked, incoming, refs);
  assert.throws(() => commitFanLocalDataImport(blocked, p, true), /quota/);
  assert.equal(blocked.getItem(FAN_LOCAL_DATA_KEY), raw, 'storage failure leaves original unchanged');
}
const stale = memory(raw); const stalePlan = prepareFanLocalDataImport(stale, incoming, refs);
stale.map.set(FAN_LOCAL_DATA_KEY, incoming);
assert.throws(() => commitFanLocalDataImport(stale, stalePlan, true), /current-data-changed/);
assert.equal(stale.writes.length, 0);
const unknownCurrent = memory(JSON.stringify({ ...current, future_field: 1 }));
assert.throws(() => prepareFanLocalDataImport(unknownCurrent, incoming, refs)); assert.equal(unknownCurrent.writes.length, 0);
assert.throws(() => writeFanLocalData(unknownCurrent, emptyFanLocalData()), /cannot-overwrite-unreadable-fan-data/);
assert.equal(unknownCurrent.writes.length, 0, 'an empty UI fallback must never overwrite unreadable or future local notes');
const badJournal = structuredClone(replacement); badJournal.training_notes[0].athlete_journal.coach_observation = 3;
const journalStore = memory(raw); assert.throws(() => prepareFanLocalDataImport(journalStore, JSON.stringify(badJournal), refs));
assert.equal(journalStore.getItem(FAN_LOCAL_DATA_KEY), raw); assert.equal(journalStore.writes.length, 0);
const legacy = { ...current, contract_version: 'ptti.fan-local-data/1' }; delete legacy.match_notes; delete legacy.coach_notes;
assert.deepEqual(parseFanLocalDataBackup(JSON.stringify(legacy)).training_notes, current.training_notes);

if (process.argv.includes('--built')) {
  assert.equal(hash(await read('dist/data/fan-inspiration-v0.1.json')), FAN_INSPIRATION_SHA);
  const scripts = (await readdir(new URL('dist/assets/', root))).filter((name) => name.endsWith('.js'));
  const emitted = (await Promise.all(scripts.map((name) => read(`dist/assets/${name}`)))).join('\n');
  assert(emitted.includes(FAN_INSPIRATION_SHA), 'public client pins this actual data version');
  assert.doesNotMatch(emitted, /review-register\.json|goal22-main-inspiration-v0\.1[\\/]internal/);
}
console.log('PASS: pinned Main JSON/schema, 7/18/8 stable-ID merge, 11 unbound highlights, one report, three UNKNOWN dossiers; rejected unsafe mutations. Synthetic-only Journal import confirms before write, backs up first, rejects invalid/unknown/stale inputs and survives quota failures with six fields intact. Browser NOT_TESTED.');
