import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  calculateOneGame,
  createOneGameExport,
  expectedOneGameServer,
  importOneGameEvidenceDraft,
} from '../src/my-match-one-game.mjs';
import { createQuickPointId } from '../src/local-video-review.mjs';
import { fanLocationUrl, readFanLocation } from '../src/fan-location.mjs';
import { parseTrainingReviewJson } from '../src/training-review.mjs';

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

const pointIntelligenceWinners = [
  ...Array.from({ length: 14 }, (_, index) => index % 2 === 0 ? 'PLAYER_A' : 'PLAYER_B'),
  'PLAYER_A', 'PLAYER_B', 'PLAYER_B', 'PLAYER_A', 'PLAYER_A', 'PLAYER_B', 'PLAYER_B', 'PLAYER_A', 'PLAYER_A', 'PLAYER_A',
];
const pointIntelligencePoints = pointIntelligenceWinners.map((winner, index) => point(index + 1, winner, expectedOneGameServer('PLAYER_A', index + 1)));
const pointIntelligence = calculateOneGame(pointIntelligencePoints, 'PLAYER_A');
assert.equal(pointIntelligence.ok, true);
assert.deepEqual(pointIntelligence.final, {
  score: { player_a: 13, player_b: 11 }, winner: 'PLAYER_A', status: 'GAME_COMPLETE',
});
assert.deepEqual(pointIntelligence.score_progression[13].score_after, { player_a: 7, player_b: 7 });
assert.deepEqual(pointIntelligence.score_progression[17].score_after, { player_a: 9, player_b: 9 });
assert.deepEqual(pointIntelligence.score_progression[19].score_after, { player_a: 10, player_b: 10 });
assert.ok(pointIntelligence.score_progression[16].events.includes('OVERTAKE'), 'the score path marks an actual comeback/lead change');
assert.ok(pointIntelligence.score_progression.at(-1).events.includes('GAME_END'), 'the terminal point is identified as the game end');
assert.equal(pointIntelligence.score_progression[20].phase, 'DEUCE');
assert.deepEqual(pointIntelligence.key_score_stages.map((stage) => [stage.id, stage.status, stage.after_point_count]), [
  ['AFTER_7_7', 'REACHED', 10], ['AFTER_9_9', 'REACHED', 6], ['AFTER_10_10', 'REACHED', 4],
]);
assert.deepEqual(pointIntelligence.key_score_stages[0].outcomes, {
  PLAYER_A: { won: 6, lost: 4 }, PLAYER_B: { won: 4, lost: 6 },
});
assert.deepEqual(pointIntelligence.key_score_stages[2].outcomes, {
  PLAYER_A: { won: 3, lost: 1 }, PLAYER_B: { won: 1, lost: 3 },
});
assert.equal(pointIntelligence.training_observation.status, 'DATA_BACKED');
assert.equal(pointIntelligence.training_observation.focus_stage, 'AFTER_10_10');
assert.equal(pointIntelligence.serve_receive.status, 'AVAILABLE');
assert.deepEqual(pointIntelligence.serve_receive.players.PLAYER_A, {
  serve: { won: 6, total: 12, rate: 0.5 }, receive: { won: 7, total: 12, rate: 7 / 12 },
});
assert.deepEqual(pointIntelligence.serve_receive.players.PLAYER_B, {
  serve: { won: 5, total: 12, rate: 5 / 12 }, receive: { won: 6, total: 12, rate: 0.5 },
});
const shutout = calculateOneGame(Array.from({ length: 11 }, (_, index) => point(index + 1, 'PLAYER_A', expectedOneGameServer('PLAYER_A', index + 1))), 'PLAYER_A');
assert.equal(shutout.is_complete, true);
assert.equal(shutout.serve_receive.players.PLAYER_B.serve.total, 5, 'serve denominators follow the recorded rule-based rotation, even in a shutout');

const partialIntelligencePoints = Array.from({ length: 8 }, (_, index) => point(index + 1, index % 2 === 0 ? 'PLAYER_A' : 'PLAYER_B'));
const partialIntelligence = calculateOneGame(partialIntelligencePoints, 'UNKNOWN');
assert.equal(partialIntelligence.final.status, 'IN_PROGRESS');
assert.equal(partialIntelligence.final.winner, null, 'an unfinished one-game record has no winner conclusion');
assert.ok(partialIntelligence.key_score_stages.every((stage) => stage.status === 'NOT_REACHED' && stage.outcomes === null));
assert.equal(partialIntelligence.serve_receive.status, 'FIRST_SERVER_UNKNOWN');
assert.equal(partialIntelligence.serve_receive.players, null);
assert.equal(partialIntelligence.training_observation.status, 'NO_RECORDED_CLOSE_SCORE_STAGE');
const explicitServersUnknownFirst = calculateOneGame(regular, 'UNKNOWN');
assert.equal(explicitServersUnknownFirst.serve_receive.status, 'FIRST_SERVER_UNKNOWN');
assert.equal(explicitServersUnknownFirst.service_stats, null, 'explicit point server labels do not replace an unknown initial server/rotation proof');

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
assert.equal(createOneGameExport({ ...session, match_id: 'LOCAL_QUICK_MATCH:another-session' }, exportPoints, { game_number: 1, first_server: 'PLAYER_A' }).ok, false, 'old-session point IDs cannot be exported under a new match identity');
assert.equal('score_progression' in exported.value, false, 'point intelligence stays derived in-session and does not change the One Game export contract');
assert.equal('key_score_stages' in exported.value, false, 'derived score stages are not silently added to the versioned export');
assert.equal('serve_receive' in exported.value, false, 'derived serve/receive presentation does not fork the evidence schema');
const serialized = JSON.stringify(exported.value);
assert.doesNotMatch(serialized, /private-local-video|C:\\|file_path|absolute_path/i, 'export omits private filename and local paths');
const bridged = importOneGameEvidenceDraft(exported.value);
assert.equal(bridged.ok, true, 'My Matches evidence is accepted through the explicit Pro Quick Annotation adapter');
assert.equal(bridged.value.identity.match_id, session.match_id, 'the exact private local match identity is retained');
assert.equal(bridged.value.identity.source_id, null, 'the local session remains unbound to public video sources');
assert.equal(bridged.value.identity.evidence_origin.confirmation_status, 'USER_RECORDED_NOT_INDEPENDENTLY_VERIFIED');
assert.equal(bridged.value.points.length, exported.value.annotated_point_count);
assert.ok(bridged.value.points.every((item) => item.bound_video_identity === '' && !item.start_confirmed && !item.end_confirmed), 'imported time values are provisional until re-confirmed in a newly selected local video session');
const reExported = createOneGameExport(session, bridged.value.points, { game_number: 1, coverage: 'COMPLETE_FROM_GAME_START', first_server: 'PLAYER_A' });
assert.equal(reExported.ok, true, 'the Pro Lab local-review path can export the same evidence envelope without promoting its status');
assert.equal(reExported.value.confirmation_status, exported.value.confirmation_status);
assert.equal(reExported.value.video_context.source_id, null);
assert.equal(reExported.value.dataset_identity.match_id, exported.value.dataset_identity.match_id);
assert.throws(() => parseTrainingReviewJson(serialized), /Unsupported training review version/, 'My Matches evidence is not promoted into the strict training-review report contract');

const timedPoints = exportPoints.map((item, index) => index === 0 ? {
  ...item, start_seconds: 1, end_seconds: 2, bound_video_identity: session.session_id,
  start_confirmed: true, end_confirmed: true,
} : item);
const timedExport = createOneGameExport(session, timedPoints, { game_number: 1, coverage: 'COMPLETE_FROM_GAME_START', first_server: 'PLAYER_A' });
assert.equal(timedExport.ok, true);
const timedBridge = importOneGameEvidenceDraft(timedExport.value);
assert.equal(timedBridge.ok, true);
assert.deepEqual([timedBridge.value.points[0].start_seconds, timedBridge.value.points[0].end_seconds], [1, 2]);
assert.equal(timedBridge.value.points[0].start_confirmed, false, 'exported time values require a fresh human confirmation against the selected video');
const partialExport = createOneGameExport(session, exportPoints.slice(0, 7), { game_number: 1, coverage: 'COMPLETE_FROM_GAME_START', first_server: 'PLAYER_A' });
assert.equal(partialExport.ok, true);
assert.equal(partialExport.value.score.status, 'IN_PROGRESS');
assert.equal(importOneGameEvidenceDraft(partialExport.value).ok, true, 'an incomplete game stays a valid partial evidence draft');
const unknownServerExport = createOneGameExport(session, exportPoints.map((item) => ({ ...item, server: 'UNKNOWN' })), { game_number: 1, coverage: 'PARTIAL_OR_UNKNOWN', first_server: 'UNKNOWN' });
assert.equal(unknownServerExport.ok, true);
assert.equal(unknownServerExport.value.service_stats, null);
const explicitServersUnknownFirstExport = createOneGameExport(session, exportPoints, { game_number: 1, coverage: 'PARTIAL_OR_UNKNOWN', first_server: 'UNKNOWN' });
assert.equal(explicitServersUnknownFirstExport.ok, true);
assert.equal(explicitServersUnknownFirstExport.value.service_stats, null, 'confirmed point server labels do not produce rotation-derived service stats without the first server');
const unknownServerBridge = importOneGameEvidenceDraft(unknownServerExport.value);
assert.equal(unknownServerBridge.ok, true);
assert.equal(unknownServerBridge.value.game_contexts[1].first_server, 'UNKNOWN');
assert.ok(unknownServerBridge.value.points.every((item) => item.server === 'UNKNOWN'), 'unknown first server and per-point serve data are not inferred');
const reorderedStats = { ...exported.value, service_stats: { PLAYER_B: exported.value.service_stats.PLAYER_B, PLAYER_A: exported.value.service_stats.PLAYER_A } };
assert.equal(importOneGameEvidenceDraft(reorderedStats).ok, true, 'JSON object key order does not change a valid evidence record');
assert.equal(importOneGameEvidenceDraft({ ...exported.value, path: 'C:\\private\\video.mp4' }).ok, false, 'unexpected private path fields are rejected');
assert.equal(importOneGameEvidenceDraft({ ...exported.value, score: { ...exported.value.score, player_a: 99 } }).ok, false, 'tampered summary fields are rejected');
assert.equal(importOneGameEvidenceDraft({ ...exported.value, video_context: { ...exported.value.video_context, source_id: 'video-source:youtube:fake' } }).ok, false, 'a local media export cannot gain a public source binding');
assert.equal(importOneGameEvidenceDraft({ ...exported.value, dataset_identity: { ...exported.value.dataset_identity, match_id: 'pro:wtt:guessed' } }).ok, false, 'a local export cannot acquire a guessed public match identity');
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
const reportComponent = await readFile(new URL('../src/PersonalMatchReport.tsx', import.meta.url), 'utf8');
const analysisView = component + reportComponent;
const route = await readFile(new URL('../src/fan-location.mjs', import.meta.url), 'utf8');
const oneGameModule = await readFile(new URL('../src/my-match-one-game.mjs', import.meta.url), 'utf8');
const workbench = await readFile(new URL('../src/ProWorkbench.tsx', import.meta.url), 'utf8');
const i18n = await readFile(new URL('../src/i18n.ts', import.meta.url), 'utf8');
const modeEffect = component.match(/useEffect\(\(\) => \{(\s*(?:if \(!oneGameMode\) return;\s*)?cancelPlaylist\(\);[\s\S]*?)\}, \[oneGameMode\]\);/);
assert.ok(modeEffect, 'the mode transition effect exists');
const runModeEffect = new Function('oneGameMode', 'cancelPlaylist', 'controllerRef', 'setPlaylistIssueKey', modeEffect[1]);
for (const oneGameMode of [false, true]) {
  const calls = [];
  runModeEffect(oneGameMode, () => calls.push('cancel'), { current: { pause: () => calls.push('pause') } }, (issue) => calls.push(issue));
  assert.deepEqual(calls, ['cancel', 'pause', ''], 'both directions stop old playback work without resetting annotations');
}
assert.doesNotMatch(modeEffect[1], /setSession|setPoints|setDraft|setGameContexts|resetPageAnnotations|release\(/, 'mode transitions do not clear records, pending edits, identity, or the player');
assert.match(component, /data-return-my-matches onClick=\{onReturnMyMatches\}/, 'the Pro Lab bridge has an explicit return action');
assert.match(workbench, /onReturnMyMatches=\{onReturnMyMatches\}/, 'return uses the existing shared workspace');
assert.match(app, /onReturnMyMatches=\{openMyMatches\}/, 'return reuses the existing My Matches route');
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
assert.match(analysisView, /row\.rate === null/, 'missing samples remain unknown in report rate rendering');
assert.match(component, /data-one-game-mode/, 'dedicated One Game view exists in the reused component');
assert.match(component, /data-one-game-final-result/, 'a completed game shows its manually recorded winner');
assert.match(analysisView, /data-point-intelligence/, 'the existing One Game view exposes the derived point-intelligence panel');
assert.match(analysisView, /data-score-calculations/, 'the score progression and key-score calculations have a stable test hook');
assert.match(analysisView, /data-key-score-stage=\{stage\.id\}/, 'key-score stages are rendered from the calculated record');
assert.match(analysisView, /data-serve-receive-status=\{results\.serve_receive\.status\}/, 'serve/receive availability is explicit in the view');
assert.match(analysisView, /data-training-observation="TRAINING_QUESTION"/, 'the training prompt declares whether it is data-backed');
assert.match(analysisView, /myMatch\.intel\.scorePath/, 'the view explicitly labels point order separately from video time');
assert.match(i18n, /point order, not a video timeline/i, 'English explicitly separates point order from video time');
assert.match(i18n, /不是视频时间轴/, 'Chinese explicitly separates point order from video time');
assert.match(analysisView, /myMatch\.intel\.limitations/, 'the view limits interpretation to recorded point winners');
assert.match(component, /session\.dataset_class === 'HUMAN_QUICK_DRAFT'/, 'personal game view accepts only local human sessions');
assert.match(component, /keepOneGameEvidenceEnvelope[\s\S]*?createOneGameExport\(session, points/, 'the Pro Lab path keeps the One Game evidence envelope for a single local game');
assert.match(component, /data-my-match-pro-bridge-active/, 'Pro Lab visibly retains the manual, local-only evidence status');
assert.match(component, /data-my-match-pro-bridge[\s\S]*?onClick=\{onOpenProLab\}/, 'a valid manual One Game summary can continue in the existing Pro Lab workspace');
assert.match(component, /importOneGameEvidenceDraft\(payload\)/, 'the existing Pro draft import recognizes the validated My Matches export adapter');
assert.match(component, /data-imported-one-game-evidence/, 'Pro Lab labels the original manual evidence and verification status');
assert.match(component, /if \(oneGameMode && \(!oneGameSessionCompatible \|\| !oneGameSummary\?\.ok \|\| oneGameSummary\.is_complete\)\) return;/, 'no additional points are accepted after a complete game');
assert.match(component, /if \(saveState === 'dirty' \|\| saveState === 'invalid'\) return;/, 'undo never discards a pending unsaved point');
assert.match(component, /points\.length > 0\) return;/, 'first server is locked after recording begins');
assert.match(component, /handleFileChange[\s\S]*?if \(!file\) return;[\s\S]*?const validExtension[\s\S]*?setFileIssueKey\('pro\.video\.fileTypeError'\);\s*return;/, 'cancelled selection and invalid media return before mutating the session');
assert.ok(component.indexOf("setFileIssueKey('pro.video.fileUnreadable')") < component.indexOf('resetPageAnnotations();', component.indexOf('function handleFileChange')), 'zero-byte or unreadable media is rejected before clearing annotations');
assert.match(component, /window\.addEventListener\('beforeunload'/, 'temporary annotations warn before page exit');
assert.doesNotMatch(component, /fetch\s*\(|XMLHttpRequest|sendBeacon|localStorage|sessionStorage/, 'local video review does not upload or persist One Game annotations');
assert.match(workbench, /if \(oneGameMode \|\| demoLoadedRef\.current\) \{[\s\S]*?return undefined;[\s\S]*?fetch\(DEMO_BUNDLE_URL/, 'One Game route skips simulated-data fetch and preserves a previously loaded Pro draft');
assert.equal((workbench.match(/<LocalVideoReview\b/g) ?? []).length, 1, 'Pro and One Game share one local video review/player instance');
assert.match(app, /data-persistent-workspace[\s\S]*<ProWorkbench[\s\S]*oneGameMode=\{page === 'my-matches'\}[\s\S]*onOpenProLab=\{\(\) => openPro\('review'\)\}/, 'the existing persistent Pro route preserves and opens the shared One Game state');
assert.match(workbench, /onOpenProLab\?: \(\) => void[\s\S]*<LocalVideoReview[\s\S]*onOpenProLab=\{onOpenProLab\}/, 'the existing workbench passes the bridge action through without a second player');
for (const key of ['myMatch.chooseVideoTitle', 'myMatch.noUpload', 'myMatch.rules', 'myMatch.complete', 'myMatch.finalWinner', 'myMatch.exportError', 'myMatch.resetOtherReview', 'myMatch.serviceLine', 'myMatch.proBridgeTitle', 'myMatch.proBridgeDescription', 'myMatch.proBridgeAction', 'myMatch.proBridgeReturn', 'myMatch.proBridgeActiveDescription', 'myMatch.proBridgeImportedStatus', 'myMatch.intel.title', 'myMatch.intel.scope', 'myMatch.intel.recordedFacts', 'myMatch.intel.calculatedFacts', 'myMatch.intel.scorePath', 'myMatch.intel.stageAfter7', 'myMatch.intel.stageAfter9', 'myMatch.intel.stageAfter10', 'myMatch.intel.notReached', 'myMatch.intel.serveReceive', 'myMatch.intel.serveUnknownFirst', 'myMatch.intel.serveIncompleteGame', 'myMatch.intel.serveUnknownPoints', 'myMatch.intel.serve', 'myMatch.intel.receive', 'myMatch.intel.noSampleRate', 'myMatch.intel.trainingPrompt', 'myMatch.intel.trainingNoStage', 'myMatch.intel.limitations']) {
  assert.equal((i18n.match(new RegExp(`'${key.replaceAll('.', '\\.')}'`, 'g')) ?? []).length, 2, `${key} exists in Chinese and English`);
}
assert.doesNotMatch(oneGameModule, /fetch\s*\(|XMLHttpRequest|sendBeacon|localStorage/i, 'one-game logic has no upload or persistent-storage path');

console.log('My Matches / Point Intelligence → Pro Lab PASS: score path and lead changes, 7:7/9:9/10:10 stages, guarded serve/receive rates, incomplete/unknown states, unchanged export schema, manual evidence round-trip, strict report separation, privacy boundary, shared session route, bilingual UI contract, and no persistence/network path.');
