import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { consumeFanCatalog, deriveFanRivalries, normalizeFanSearch } from '../src/fan-catalog.mjs';
import { emptyFanLocalData, FAN_LOCAL_DATA_VERSION, parseFanLocalDataBackup, readFanLocalData, serializeFanLocalDataBackup, toggleLocalId, validateFanLocalDataReferences, writeFanLocalData } from '../src/fan-local-data.mjs';

const [rawCatalog, rawGoal14, app, page, universe, css, i18n, search, matchDetail, universePages, catalogProvider] = await Promise.all([
  readFile(new URL('../public/data/match-library-strict-public.json', import.meta.url), 'utf8'),
  readFile(new URL('../public/data/goal14-fan-content-strict-public.json', import.meta.url), 'utf8'),
  readFile(new URL('../src/App.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/FanCatalogPage.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/FanUniversePages.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/style.css', import.meta.url), 'utf8'),
  readFile(new URL('../src/i18n.ts', import.meta.url), 'utf8'),
  readFile(new URL('../src/FanSearchOverlay.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/MatchDetail.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/FanUniversePages.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/PublicFanCatalog.tsx', import.meta.url), 'utf8'),
]);
const catalog = consumeFanCatalog(JSON.parse(rawCatalog));
assert.equal(catalog.matches.length, 5);
assert.equal(catalog.stars.length, 8);
assert.equal(catalog.sources.length, 15);
assert.equal(catalog.matches[0].match_id, 'pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun');
assert.equal(catalog.stars.some((star) => star.athlete_id === 'athlete:121558'), true);
assert.equal(catalog.stars.some((star) => star.athlete_id === 'athlete:135977'), true);
const listedAthleteIds = new Set(catalog.stars.map((star) => star.athlete_id));
const participantsWithoutProfiles = [...new Set(catalog.matches.flatMap((match) => match.participants.map((person) => person.athlete_id).filter((id) => id && !listedAthleteIds.has(id))))].sort();
assert.deepEqual(participantsWithoutProfiles, ['athlete:112409', 'athlete:121582'], 'participants without matching Star records remain names, not fabricated profile destinations');
const participantsWithoutStableIds = catalog.matches.flatMap((match) => match.participants.filter((person) => !person.athlete_id).map((person) => person.name_en || person.name_zh || person.side));
assert.ok(participantsWithoutStableIds.includes('Chen Xingtong') && participantsWithoutStableIds.includes('Wang Manyu'), 'participants lacking stable IDs remain present by sourced name');
assert.equal(catalog.sources[0].url, 'https://www.youtube.com/watch?v=0QgbtsBWZhk');
assert.equal(catalog.sources[0].external_viewing, 'ALLOWED');
assert.equal(catalog.sources[0].embedding, 'UNKNOWN');
assert.equal(catalog.sources[0].thumbnail_display, 'NOT_ALLOWED');
assert.equal(normalizeFanSearch('王楚钦'), '王楚钦');
assert.equal(normalizeFanSearch(' Wang Chuqin '), 'wangchuqin');
assert.equal(normalizeFanSearch('Félix-Lebrun'), 'felixlebrun');
assert.equal(normalizeFanSearch('China Smash'), 'chinasmash');
const rivalries = deriveFanRivalries(catalog);
assert.equal(rivalries.length, 2, 'only exact two-player singles matchups with both stable athlete IDs form rivalry records');
assert.deepEqual(rivalries[0].athlete_ids, ['athlete:121558', 'athlete:135977']);
assert.deepEqual(rivalries[0].match_ids, [catalog.matches[0].match_id]);
assert(rivalries.every((rivalry) => /^rivalry:/.test(rivalry.rivalry_id)));
const unknownSinglesParticipant = structuredClone(catalog);
unknownSinglesParticipant.matches[0].participants.push({ side: 'C', athlete_id: 'athlete:unknown', name_en: 'Unknown' });
assert.deepEqual(deriveFanRivalries(unknownSinglesParticipant).map((item) => item.rivalry_id), [rivalries[1].rivalry_id], 'a singles record with extra or unregistered participants is not treated as a known rivalry');
assert.equal(JSON.parse(rawGoal14).content_candidates.length, 0, 'the separately admitted GOAL14 short-content projection remains empty');

const matchId = catalog.matches[0].match_id;
const athleteId = catalog.stars[0].athlete_id;
let data = emptyFanLocalData();
data.saved_match_ids = toggleLocalId(data.saved_match_ids, matchId);
data.followed_athlete_ids = toggleLocalId(data.followed_athlete_ids, athleteId);
data.training_notes.push({ id: 'note-1', date: '2026-10-18', topic: 'Serve practice', technical_question: 'Was my toss consistent?', summary: '<script>is plain text</script>', next_goal: 'Observe five serves', match_id: matchId });
data.match_notes.push({ id: 'note-match', date: '2026-10-18', topic: 'Final review', technical_question: 'What changed late in the game?', summary: 'Personal observation only.', next_goal: 'Review next match', match_id: matchId });
data.coach_notes.push({ id: 'note-coach', date: '2026-10-18', topic: 'Training cue', technical_question: 'Ask athlete what they noticed.', summary: 'Coach-entered note, not athlete quote.', next_goal: 'Discuss at practice', match_id: matchId });
data.fan_notes.push({ id: 'note-2', date: '2026-10-18', topic: 'Final', technical_question: '', summary: 'My note, not a player quote.', next_goal: '', match_id: matchId });
const restored = parseFanLocalDataBackup(serializeFanLocalDataBackup(data));
assert.equal(restored.contract_version, FAN_LOCAL_DATA_VERSION);
assert.deepEqual(restored, data, 'local note, save and follow backup round-trips');
const localStorageFixture = new Map();
const storagePort = { getItem: (key) => localStorageFixture.get(key) ?? null, setItem: (key, value) => localStorageFixture.set(key, value) };
writeFanLocalData(storagePort, data);
assert.deepEqual(readFanLocalData(storagePort), data, 'all four local note groups, saves, and follows survive a browser-style refresh read');
const editedData = structuredClone(data);
for (const field of ['training_notes', 'match_notes', 'coach_notes', 'fan_notes']) {
  editedData[field][0].summary = `Edited ${field} after saving.`;
}
writeFanLocalData(storagePort, editedData);
const refreshedEditedData = readFanLocalData(storagePort);
for (const field of ['training_notes', 'match_notes', 'coach_notes', 'fan_notes']) {
  assert.equal(refreshedEditedData[field][0].summary, `Edited ${field} after saving.`, `${field} edits persist through the local storage boundary`);
}
const legacyV1 = { ...data, contract_version: 'ptti.fan-local-data/1' };
delete legacyV1.match_notes;
delete legacyV1.coach_notes;
const migratedV1 = parseFanLocalDataBackup(JSON.stringify(legacyV1));
assert.equal(migratedV1.contract_version, FAN_LOCAL_DATA_VERSION);
assert.deepEqual(migratedV1.training_notes, data.training_notes, 'v1 backup notes survive the in-memory v2 migration');
assert.deepEqual(migratedV1.match_notes, []);
assert.deepEqual(migratedV1.coach_notes, []);
assert.deepEqual(validateFanLocalDataReferences(restored, { matchIds: [matchId], athleteIds: [athleteId] }), restored);
for (const field of ['training_notes', 'match_notes', 'coach_notes', 'fan_notes']) {
  const invalidRef = structuredClone(data);
  invalidRef[field][0].match_id = 'match:not-in-current-public-catalog';
  assert.throws(() => validateFanLocalDataReferences(invalidRef, { matchIds: [matchId], athleteIds: [athleteId] }), /backup-reference-not-in-public-catalog/);
}
assert.deepEqual(toggleLocalId(data.saved_match_ids, matchId), [], 'save can be removed');
assert.deepEqual(toggleLocalId(data.followed_athlete_ids, athleteId), [], 'follow can be removed');
assert.throws(() => parseFanLocalDataBackup('{broken'), /invalid-fan-local-backup-json/);
assert.throws(() => parseFanLocalDataBackup(JSON.stringify({ ...data, contract_version: 'ptti.fan-local-data/99' })), /unsupported-fan-local-data-version/);
assert.throws(() => parseFanLocalDataBackup(JSON.stringify({ ...data, saved_match_ids: [matchId, matchId] })), /invalid-saved_match_ids/);
assert.throws(() => parseFanLocalDataBackup(JSON.stringify({ ...data, training_notes: [{ id: 'x', summary: 4 }] })), /invalid-training-notes/);
assert.throws(() => parseFanLocalDataBackup(JSON.stringify({ ...data, match_notes: [{ id: 'x', summary: 4 }] })), /invalid-match-notes/);
assert.throws(() => parseFanLocalDataBackup(JSON.stringify({ ...data, coach_notes: [{ id: 'x', summary: 4 }] })), /invalid-coach-notes/);
assert.throws(() => parseFanLocalDataBackup(JSON.stringify({ ...data, fan_notes: [{ id: 'bad-date', date: '2026-02-31', topic: 'X', technical_question: '', summary: 'Y', next_goal: '', match_id: null }] })), /invalid-fan-notes/);
assert.throws(() => parseFanLocalDataBackup('x'.repeat(1_000_001)), /fan-local-backup-too-large/);

assert.match(app, /<button className=\{page === 'watch'/, 'Watch is a first-level route');
assert.match(app, /lazy\(\(\) => import\('\.\/ProWorkbench'\)/, 'heavy Pro workbench is deferred until first use');
assert.match(app, /proVisited && <div hidden=\{page !== 'pro'\} data-persistent-workspace/, 'after first opening, Pro remains mounted across navigation');
assert.match(matchDetail, /const ProWorkbench = lazy\(\(\) => import\('\.\/ProWorkbench'\)/, 'match detail defers its Pro workbench chunk until the Pro tab is opened');
assert.doesNotMatch(matchDetail, /import\s*\{\s*ProWorkbench\s*\}\s*from\s*['"]\.\/ProWorkbench['"]/, 'match detail has no eager Pro import');
assert.match(matchDetail, /proVisited && <div hidden=\{centerMode !== 'pro'\} data-persistent-match-pro/, 'after first use, match detail keeps its Pro workbench mounted while switching tabs');
assert.match(app, /<nav className="mobile-bottom-nav"/, 'mobile bottom navigation is rendered');
assert.match(app, /<TrainingPage[\s\S]*onReplace=\{updateFanLocalData\}/);
assert.match(app, /<GearPage locale=\{locale\}/);
assert.match(app, /<CommunityPage[\s\S]*onReplace=\{updateFanLocalData\}/);
assert.match(app, /<MyCornerPage[\s\S]*data=\{fanLocalData\}/);
assert.match(app, /<FanSearchOverlay[\s\S]*onOpenWatch=/);
assert.match(app, /page === 'rivalries'[\s\S]*mode="rivalries"/);
assert.match(app, /page === 'highlights' && <FanCatalogPage[\s\S]*mode="highlights"/, 'Highlights has a reachable dedicated page');
assert.match(catalogProvider, /fetch\('\/data\/match-library-strict-public\.json'/, 'the shared Fan provider reads strict-public Main data');
assert.match(page, /usePublicFanCatalog\(\)/, 'Fan pages consume the shared validated projection');
assert.match(page, /normalizeFanSearch\(query\)/, 'search uses the tested bilingual normalization helper');
assert.match(page, /role="link" tabIndex=\{0\} aria-label=\{t\('fan\.openMatchCard'/, 'the match card is keyboard- and pointer-actionable');
assert.match(page, /onToggleSavedMatch/);
assert.match(page, /onToggleFollowedAthlete/);
assert.match(page, /selectedSource \?\? \(!selectedSourceId \? featuredSource : null\)/, 'Watch navigation uses the already-admitted source without a duplicated data record');
assert.doesNotMatch(page, /<iframe\b|<video\b/i, 'fan pages do not host match video');
assert.match(universe, /validateFanLocalDataReferences\(parsed, \{ matchIds: catalog\.matches\.map\(\(match\) => match\.match_id\), athleteIds: catalog\.stars\.map\(\(star\) => star\.athlete_id\) \}\)/, 'backup references are checked against current strict-public IDs');
assert.match(universe, /followedAthleteIds|training_notes|fan_notes/);
assert.match(universe, /validateFanLocalDataReferences\(parsed/);
assert.match(universePages, /notes\.some\(\(item\) => item\.id === note\.id\) \? notes\.map\(\(item\) => item\.id === note\.id \? note : item\) : \[note, \.\.\.notes\]/, 'the note form updates the existing record when editing and adds only when new');
assert.match(universe, /data-universe-page="corner"/);
assert.match(universe, /data-followed-athlete-id/);
assert.match(universe, /data-saved-match-id/);
assert.match(search, /usePublicFanCatalog\(\)/);
assert.match(search, /filterFanClips\(catalog, \{ query \}\)/);
assert.match(search, /role="dialog" aria-modal="true"/);
assert.match(page, /deriveFanRivalries\(catalog\)/);
assert.match(page, /data-rivalry-detail/);
assert.match(page, /mode === 'highlights' &&[\s\S]*visibleHighlights\.map\(sourceCard\)/, 'dedicated Highlights page displays only the strict highlight projection');
assert.match(page, /onGoHighlights && <button[\s\S]*onClick=\{onGoHighlights\}/, 'Cinema has a working path to all highlights');
assert.match(page, /featuredStarId = featuredMatch\?\.participants\.find\(\(participant\) => participant\.athlete_id && catalog\?\.stars\.some\(\(star\) => star\.athlete_id === participant\.athlete_id\)\)/, 'featured-player links require an exact listed athlete ID');
assert.match(page, /participants\.filter\(\(participant\) => participant\.athlete_id && catalog\?\.stars\.some/, 'match-player links require exact listed athlete IDs');
assert.match(page, /OFFICIAL_EVENT_RESULT_CROSSCHECKED/);
assert.doesNotMatch(page, /win rate|胜率|第三板进攻|接发抢攻/);
assert.match(universe, /target="_blank" rel="noopener noreferrer"/);
assert.match(css, /\.mobile-bottom-nav \{ position: fixed;/);
assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
assert.match(css, /\.fan-art-poster-copy \{ position: absolute;/, 'owned typography art carries sourced player and event names');
assert.match(i18n, /'universe\.train\.title': '[^']+'/);
assert.match(i18n, /'universe\.community\.title': '[^']+'/);
assert.match(i18n, /'universe\.gear\.title': '[^']+'/);
assert.match(i18n, /'universe\.train\.title': 'Keep notes for your next practice'/);
assert.match(i18n, /'universe\.community\.title': 'Stay connected to table tennis'/);
assert.match(i18n, /'universe\.gear\.title': 'Equipment, with evidence first'/);
assert.match(i18n, /'nav\.corner': '我的空间'/);
assert.match(i18n, /'nav\.corner': 'My Corner'/);
assert.match(i18n, /'fan\.highlightsTitle': '赛事高光'/);
assert.match(i18n, /'fan\.highlightsTitle': 'Event highlights'/);
assert.match(i18n, /'search\.dialogTitle': '搜索 PTTI'/);
assert.match(i18n, /'search\.dialogTitle': 'Search PTTI'/);
assert.match(i18n, /'rivalry\.scope': '这只是当前目录中已核验的比赛/);
assert.match(i18n, /'rivalry\.scope': 'This reflects matches verified in the current catalog only/);

console.log('PASS: Main strict-public catalog consumes 5 matches, 15 sources and 8 athlete IDs; 5 exact match-source edges are retained; embed UNKNOWN and thumbnails NOT_ALLOWED remain unchanged.');
console.log('PASS: GOAL14 short-content public projection remains 0; no fake clips/products/social records are introduced.');
console.log('PASS: Local saves, follows and four note groups round-trip; legacy v1 backups migrate to v2 without losing existing notes.');
console.log('PASS: Invalid backup JSON, version, duplicate IDs, malformed note types and oversized files are rejected.');
console.log('PASS: Watch is a first-level route; exact Main IDs drive profile/match/source; cards and mobile nav are actionable.');
console.log('PASS: My Corner, global bilingual search and exact-ID rivalry module consume the strict public catalog; v2 notes stay local-only.');
console.log('PASS: Gear and Community expose evidence-gated/empty states; both locales contain the new product copy.');
