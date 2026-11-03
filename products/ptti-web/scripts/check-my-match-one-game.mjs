import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  calculateOneGame,
  createOneGameExport,
  expectedOneGameServer,
} from '../src/my-match-one-game.mjs';
import { createQuickPointId } from '../src/local-video-review.mjs';
import { fanLocationUrl, readFanLocation } from '../src/fan-location.mjs';

function point(number, winner, server = 'UNKNOWN') {
  return {
    point_id: `LOCAL_QUICK_MATCH:qa/g01/p${String(number).padStart(3, '0')}`,
    game_number: 1,
    point_number: number,
    winner,
    server,
    observed_tactics: { serve_side: 'unknown', serve_length: 'unknown', third_ball_attack: 'unknown' },
    start_seconds: null,
    end_seconds: null,
    bound_video_identity: '',
    start_confirmed: false,
    end_confirmed: false,
  };
}

const regularWinners = [...Array(10).fill('PLAYER_A'), ...Array(8).fill('PLAYER_B'), 'PLAYER_A'];
const regular = regularWinners.map((winner, index) => point(index + 1, winner, expectedOneGameServer('PLAYER_A', index + 1)));
const regularSummary = calculateOneGame(regular, 'PLAYER_A');
assert.equal(regularSummary.ok, true);
assert.deepEqual([regularSummary.score.player_a, regularSummary.score.player_b], [11, 8]);
assert.equal(regularSummary.is_complete, true, 'first to 11 with a two-point lead completes the game');
assert.equal(regularSummary.annotated_point_count, 19);
assert.equal(regularSummary.server_confirmed_point_count, 19);
assert.ok(regularSummary.service_stats, 'complete game and complete server observations support service outcome counts');
assert.deepEqual(regularSummary.service_stats.PLAYER_A, { points: 10, won: 6, lost: 4 });
assert.deepEqual(regularSummary.service_stats.PLAYER_B, { points: 9, won: 4, lost: 5 });
assert.equal(calculateOneGame(regular.map((item, index) => index === 4 ? { ...item, server: 'UNKNOWN' } : item), 'PLAYER_A').service_stats, null, 'a missing server observation is not counted as zero or inferred');

const deuceWinners = [...Array(10).fill('PLAYER_A'), ...Array(10).fill('PLAYER_B'), 'PLAYER_A', 'PLAYER_A'];
const deuce = deuceWinners.map((winner, index) => point(index + 1, winner, expectedOneGameServer('PLAYER_A', index + 1)));
const deuceSummary = calculateOneGame(deuce, 'PLAYER_A');
assert.equal(deuceSummary.ok, true);
assert.deepEqual([deuceSummary.score.player_a, deuceSummary.score.player_b], [12, 10]);
assert.equal(deuceSummary.is_complete, true, 'after 10:10 the game still requires a two-point lead');
assert.equal(expectedOneGameServer('PLAYER_A', 20), 'PLAYER_B');
assert.equal(expectedOneGameServer('PLAYER_A', 21), 'PLAYER_A');
assert.equal(expectedOneGameServer('PLAYER_A', 22), 'PLAYER_B');
assert.equal(expectedOneGameServer('UNKNOWN', 1), 'UNKNOWN', 'an unknown first server is never guessed');

assert.equal(calculateOneGame([point(1, 'PLAYER_A')], 'UNKNOWN').service_stats, null, 'incomplete game has no service insight');
assert.equal(calculateOneGame([point(1, 'UNKNOWN')], 'UNKNOWN').issue, 'winner-unknown');
assert.equal(calculateOneGame([point(2, 'PLAYER_A')], 'UNKNOWN').issue, 'point-sequence-gap');
assert.equal(calculateOneGame([...regular, point(20, 'PLAYER_A')], 'PLAYER_A').issue, 'points-after-game-end');
assert.equal(calculateOneGame([point(1, 'PLAYER_A', 'PLAYER_B')], 'PLAYER_A').issue, 'service-rotation-conflict');
assert.equal(calculateOneGame([point(1, 'PLAYER_A', 'PLAYER_A')], 'UNKNOWN').service_stats, null, 'unknown initial server keeps service statistics unavailable');

const session = {
  session_id: 'local-session:qa-only', dataset_id: 'HUMAN_QUICK_DRAFT:qa-only', dataset_class: 'HUMAN_QUICK_DRAFT',
  contract_version: 'ptti.quick-annotation/0.2', match_id: 'LOCAL_QUICK_MATCH:qa-only', source_id: null,
  binding_status: 'LOCAL_SESSION_ONLY', media_status: 'ready', duration_seconds: 90,
  file: { name: 'private-local-video.mp4', type: 'video/mp4', size: 1000, last_modified_ms: 1 },
};
const exportPoints = regular.map((item) => ({ ...item, point_id: createQuickPointId(session.match_id, 1, item.point_number) }));
const exported = createOneGameExport(session, exportPoints, { game_number: 1, coverage: 'COMPLETE_FROM_GAME_START', first_server: 'PLAYER_A' });
assert.equal(exported.ok, true);
assert.equal(exported.value.schema, 'ptti.my-match-one-game/0.1');
assert.equal(exported.value.source.type, 'USER_MANUAL');
assert.equal(exported.value.confirmation_status, 'USER_RECORDED_NOT_INDEPENDENTLY_VERIFIED');
assert.equal(exported.value.media_scope, 'LOCAL_SESSION_ONLY');
assert.equal(exported.value.score.player_a, 11);
assert.equal(exported.value.score.player_b, 8);
assert.equal(exported.value.points.length, 19);
assert.equal(exported.value.video_context.source_id, null);
const serialized = JSON.stringify(exported.value);
assert.doesNotMatch(serialized, /private-local-video|C:\\|file_path|absolute_path/i, 'export omits private filename and local paths');
assert.equal(createOneGameExport({ ...session, media_status: 'loading' }, regular, { game_number: 1, coverage: 'COMPLETE_FROM_GAME_START', first_server: 'PLAYER_A' }).ok, false);
assert.equal(createOneGameExport({ ...session, dataset_class: 'SIMULATED_ONLY', match_id: 'SIMULATED_ONLY:fake' }, regular, { game_number: 1, coverage: 'COMPLETE_FROM_GAME_START', first_server: 'PLAYER_A' }).ok, false, 'simulated dataset cannot be exported as a personal match');
assert.equal(createOneGameExport({ ...session, match_id: 'pro:wtt:real-match' }, regular, { game_number: 1, coverage: 'COMPLETE_FROM_GAME_START', first_server: 'PLAYER_A' }).issue, 'personal-local-identity-required', 'a public match is never inferred from a local file');
assert.equal(createOneGameExport({ ...session, source_id: 'video-source:youtube:unverified' }, regular, { game_number: 1, coverage: 'COMPLETE_FROM_GAME_START', first_server: 'PLAYER_A' }).issue, 'personal-local-identity-required', 'a local match remains unbound to a public video source');
assert.equal(createOneGameExport({ ...session, dataset_id: undefined }, regular, { game_number: 1, coverage: 'COMPLETE_FROM_GAME_START', first_server: 'PLAYER_A' }).issue, 'personal-local-identity-required', 'malformed session identity is rejected without throwing');
assert.equal(calculateOneGame('invalid', 'UNKNOWN').issue, 'invalid-points', 'malformed point input is rejected');
assert.equal(calculateOneGame([null], 'UNKNOWN').issue, 'invalid-point', 'malformed rows are rejected');
assert.equal(createOneGameExport(session, [], { game_number: 1, coverage: 'PARTIAL_OR_UNKNOWN', first_server: 'UNKNOWN' }).issue, 'no-points');

const app = await readFile(new URL('../src/App.tsx', import.meta.url), 'utf8');
const component = await readFile(new URL('../src/LocalVideoReview.tsx', import.meta.url), 'utf8');
const route = await readFile(new URL('../src/fan-location.mjs', import.meta.url), 'utf8');
const oneGameModule = await readFile(new URL('../src/my-match-one-game.mjs', import.meta.url), 'utf8');
const workbench = await readFile(new URL('../src/ProWorkbench.tsx', import.meta.url), 'utf8');
const i18n = await readFile(new URL('../src/i18n.ts', import.meta.url), 'utf8');
const oneGameRenderEnd = component.indexOf('return <section className="local-video-review" aria-labelledby="local-video-title"');
const oneGameRenderStart = component.lastIndexOf('if (oneGameMode)', oneGameRenderEnd);
assert.ok(oneGameRenderStart >= 0 && oneGameRenderEnd > oneGameRenderStart, 'dedicated One Game render branch is present');
const oneGameRender = component.slice(oneGameRenderStart, oneGameRenderEnd);
assert.match(oneGameRender, /data-one-game-empty/);
assert.doesNotMatch(oneGameRender, /<CinemaDemo|loadGolden/ , 'One Game entry has no simulated-match demo');
assert.match(app, /page === 'my-matches'/, 'My Matches is routed through the existing app shell');
assert.match(app, /hidden=\{page !== 'pro' && page !== 'my-matches'\}[\s\S]*data-persistent-workspace/, 'route changes retain the existing playback review component');
assert.match(app, /oneGameMode=\{page === 'my-matches'\}/, 'the existing workspace receives the One Game mode flag');
assert.match(component, /oneGameMode/, 'one-game UI is a mode of the existing local review component');
assert.match(route, /'my-matches'/, 'My Matches can be restored as an app route');
assert.equal(readFanLocation('http://127.0.0.1:4175/my-matches')?.page, 'my-matches', 'deep link restores My Matches');
assert.match(fanLocationUrl('http://127.0.0.1:4175/', { page: 'my-matches' }), /\/my-matches$/);
assert.match(component, /data-one-game-mode/, 'dedicated One Game view exists in the reused component');
assert.match(component, /session\.dataset_class === 'HUMAN_QUICK_DRAFT'/, 'personal game view accepts only local human sessions');
assert.match(component, /const result = oneGameMode\s*\?\s*createOneGameExport/, 'One Game export uses its own truthful summary contract');
assert.match(component, /if \(oneGameMode && \(!oneGameSessionCompatible \|\| !oneGameSummary\?\.ok \|\| oneGameSummary\.is_complete\)\) return;/, 'no additional points are accepted after a complete game');
assert.match(component, /if \(saveState === 'dirty' \|\| saveState === 'invalid'\) return;/, 'undo never discards a pending unsaved point');
assert.match(component, /points\.length > 0\) return;/, 'first server is locked after recording begins');
assert.match(component, /handleFileChange[\s\S]*?if \(!file\) return;[\s\S]*?const validExtension[\s\S]*?setFileIssueKey\('pro\.video\.fileTypeError'\);\s*return;/, 'cancelled selection and invalid media return before mutating the session');
assert.ok(component.indexOf("setFileIssueKey('pro.video.fileUnreadable')") < component.indexOf('resetPageAnnotations();', component.indexOf('function handleFileChange')), 'zero-byte or unreadable media is rejected before clearing annotations');
assert.match(component, /window\.addEventListener\('beforeunload'/, 'temporary annotations warn before page exit');
assert.match(component, /if \(!oneGameMode\) return;\s*cancelPlaylist\(\);\s*controllerRef\.current\?\.pause\(\)/, 'entering My Matches cancels an existing clip queue and pauses playback without releasing the session');
assert.doesNotMatch(component, /fetch\s*\(|XMLHttpRequest|sendBeacon|localStorage|sessionStorage/, 'local video review does not upload or persist One Game annotations');
assert.match(workbench, /if \(oneGameMode \|\| demoLoadedRef\.current\) \{[\s\S]*?return undefined;[\s\S]*?fetch\(DEMO_BUNDLE_URL/, 'One Game route skips simulated-data fetch and preserves a previously loaded Pro draft');
assert.equal((workbench.match(/<LocalVideoReview\b/g) ?? []).length, 1, 'Pro and One Game share one local video review/player instance');
for (const key of ['myMatch.chooseVideoTitle', 'myMatch.noUpload', 'myMatch.rules', 'myMatch.complete', 'myMatch.exportError', 'myMatch.resetOtherReview', 'myMatch.serviceLine']) {
  assert.equal((i18n.match(new RegExp(`'${key.replaceAll('.', '\\.')}'`, 'g')) ?? []).length, 2, `${key} exists in Chinese and English`);
}
assert.doesNotMatch(oneGameModule, /fetch\s*\(|XMLHttpRequest|sendBeacon|localStorage/i, 'one-game logic has no upload or persistent-storage path');

console.log('My Matches / One Game PASS: standard/deuce scoring, service rotation and unknown-server handling, invalid sequences, no post-game scoring, export identity/privacy, direct route, existing player reuse, invalid media preservation, bilingual copy, and no persistence/network path.');
