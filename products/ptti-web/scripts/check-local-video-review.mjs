import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import {
  createQuickAnnotationInput,
  createQuickPointId,
  expectedServerForPoint,
  importQuickAnnotationDraft,
  nextUnannotatedPointNumber,
  QUICK_ANNOTATION_VERSION,
  QUICK_ANNOTATION_VERSION_V02,
  QUICK_ANNOTATION_RALLY_STAGES_V02,
  quickMillisecondsToLocalSeconds,
  localSecondsToQuickMilliseconds,
  suggestedLocalServerForPoint,
  summarizeLocalQuickPoints,
  validateQuickAnnotationInput,
  validateQuickAnnotationPoint,
  validateQuickAnnotationPoints,
} from '../src/local-video-review.mjs';

const integrationRoot = process.env.PTTI_INTEGRATION_WORKTREE || 'C:\\PTTI-Worktrees\\integration-preview-sprint-0-1';
const mainDexV02 = JSON.parse(readFileSync(path.join(integrationRoot, 'products', 'ptti-integration', 'fixtures', 'quick-annotation-v0.2-valid-simulated.json'), 'utf8'));

const session = {
  session_id: 'qa-session-001',
  dataset_id: 'HUMAN_QUICK_DRAFT:qa-session-001',
  match_id: 'LOCAL_QUICK_MATCH:qa-session-001',
  contract_version: QUICK_ANNOTATION_VERSION,
  binding_status: 'LOCAL_SESSION_ONLY',
  media_status: 'ready',
  duration_seconds: 12.345,
  file: { name: 'synthetic-test.mp4', type: 'video/mp4', size: 1024, last_modified_ms: 1 },
};
const gameContexts = { 1: { game_number: 1, coverage: 'PARTIAL_OR_UNKNOWN', first_server: 'UNKNOWN' } };
const basePoint = {
  point_id: createQuickPointId(session.match_id, 1, 1),
  game_number: 1,
  point_number: 1,
  winner: 'PLAYER_A',
  server: 'PLAYER_B',
  observed_tactics: { serve_side: 'forehand', serve_length: 'short', third_ball_attack: 'yes' },
  start_seconds: 1.234,
  end_seconds: 2.345,
  bound_video_identity: 'qa-session-001',
  start_confirmed: true,
  end_confirmed: true,
};

assert.match(basePoint.point_id, /^LOCAL_QUICK_MATCH%3Aqa-session-001\/g01\/p001$/);
assert.deepEqual(validateQuickAnnotationPoint(basePoint, 12345, gameContexts, [], null, session.match_id), { ok: true });
assert.deepEqual(validateQuickAnnotationPoints(session, [basePoint], gameContexts), { ok: true });

const created = createQuickAnnotationInput(session, [basePoint], gameContexts);
assert.equal(created.ok, true);
const exported = created.value;
assert.equal(exported.contract_version, QUICK_ANNOTATION_VERSION);
assert.equal(exported.dataset_class, 'HUMAN_QUICK_DRAFT');
assert.equal(exported.dataset_id, session.dataset_id);
assert.equal(exported.match_id, session.match_id);
assert.equal(exported.video_context.duration_ms, 12345);
assert.equal(exported.video_context.duration_status, 'PLAYER_METADATA_REPORTED');
assert.equal(exported.video_context.source_id, null);
assert.equal(exported.points[0].rally_start_ms, 1234);
assert.equal(exported.points[0].rally_end_ms, 2345);
assert.equal(exported.points[0].server, 'opponent');
assert.equal(exported.points[0].winner, 'player');
assert.equal(exported.points[0].observed_tactics.serve_spin, 'unknown');
assert.equal(exported.points[0].observed_tactics.third_ball_attack, 'yes');
assert.equal(validateQuickAnnotationInput(exported).ok, true);

const imported = importQuickAnnotationDraft(exported);
assert.equal(imported.ok, true);
assert.equal(imported.value.identity.dataset_id, exported.dataset_id);
assert.equal(imported.value.identity.dataset_class, 'HUMAN_QUICK_DRAFT');
assert.equal(imported.value.identity.contract_version, QUICK_ANNOTATION_VERSION);
assert.equal(imported.value.points[0].point_id, exported.points[0].point_id);
assert.equal(imported.value.points[0].start_seconds, 1.234);
assert.equal(imported.value.points[0].end_seconds, 2.345);
assert.equal(imported.value.points[0].start_confirmed, false, 'imported time is provisional until reconfirmed against a fresh local video session');
assert.equal(imported.value.points[0].end_confirmed, false);
assert.equal(imported.value.points[0].bound_video_identity, '', 'imported JSON never restores an old browser-session media binding');
const reexportedV01 = createQuickAnnotationInput(session, [{ ...imported.value.points[0], bound_video_identity: session.session_id, start_confirmed: true, end_confirmed: true }], imported.value.game_contexts);
assert.equal(reexportedV01.ok, true);
assert.equal(reexportedV01.value.contract_version, QUICK_ANNOTATION_VERSION, 'a v0.1 import remains a v0.1 export');
assert.equal(Object.hasOwn(reexportedV01.value.points[0], 'observed_rally_stage'), false, 'v0.1 never receives a v0.2 stage field');

assert.deepEqual(QUICK_ANNOTATION_RALLY_STAGES_V02, ['END_AFTER_1_2_CONTACTS', 'END_AFTER_3_4_CONTACTS', 'END_AFTER_5_PLUS_CONTACTS', 'UNKNOWN']);
assert.equal(quickMillisecondsToLocalSeconds(1234), 1.234);
assert.equal(quickMillisecondsToLocalSeconds(1234.5), null, 'fractional milliseconds are rejected');
assert.equal(localSecondsToQuickMilliseconds(1.234), 1234);
assert.equal(localSecondsToQuickMilliseconds(Number.POSITIVE_INFINITY), null);
assert.equal(localSecondsToQuickMilliseconds(-0.001), null);

const importedV02 = importQuickAnnotationDraft(mainDexV02);
assert.equal(importedV02.ok, true, 'the exact MainDex v0.2 golden fixture is accepted');
assert.equal(importedV02.value.identity.contract_version, QUICK_ANNOTATION_VERSION_V02);
assert.equal(importedV02.value.points[0].observed_rally_stage, 'END_AFTER_1_2_CONTACTS');
assert.equal(importedV02.value.points[1].observed_rally_stage, 'UNKNOWN');
assert.equal(Object.hasOwn(importedV02.value.points[4], 'observed_rally_stage'), false, 'an omitted optional stage remains omitted on import');
assert.equal(importedV02.value.points[0].start_confirmed, false, 'import never revives a playback boundary confirmation');

const v02Session = {
  ...session,
  session_id: 'qa-session-v02',
  dataset_id: mainDexV02.dataset_id,
  dataset_class: mainDexV02.dataset_class,
  match_id: mainDexV02.match_id,
  source_id: mainDexV02.video_context.source_id,
  contract_version: QUICK_ANNOTATION_VERSION_V02,
  duration_seconds: 30,
};
const v02Points = importedV02.value.points.map((point, index) => ({
  ...point,
  bound_video_identity: index < 2 ? v02Session.session_id : '',
  start_confirmed: index < 2,
  end_confirmed: index < 2,
}));
const createdV02 = createQuickAnnotationInput(v02Session, v02Points, importedV02.value.game_contexts);
assert.equal(createdV02.ok, true);
assert.equal(createdV02.value.contract_version, QUICK_ANNOTATION_VERSION_V02);
assert.equal(createdV02.value.points[0].rally_start_ms, 1000);
assert.equal(createdV02.value.points[0].observed_rally_stage, 'END_AFTER_1_2_CONTACTS');
assert.equal(createdV02.value.points[1].observed_rally_stage, 'UNKNOWN');
assert.equal(createdV02.value.points[2].rally_start_ms, null, 'an unconfirmed range is omitted from the contract times');
assert.equal(createdV02.value.points[4].observed_rally_stage, undefined, 'an omitted optional v0.2 stage stays omitted');
assert.equal(validateQuickAnnotationInput({ ...createdV02.value, points: [{ ...createdV02.value.points[0], observed_rally_stage: 'THIRD_BALL_ATTACK' }] }).issue, 'invalid-rally-stage');
assert.equal(validateQuickAnnotationInput({ ...exported, points: [{ ...exported.points[0], observed_rally_stage: 'UNKNOWN' }] }).issue, 'invalid-contract-point-fields', 'v0.1 rejects the v0.2-only stage field');
assert.equal(importQuickAnnotationDraft({ ...mainDexV02, contract_version: 'ptti.quick-annotation/0.3' }).issue, 'unsupported-contract-version');

const provisionalExport = createQuickAnnotationInput(session, [{ ...basePoint, start_confirmed: false, end_confirmed: false }], gameContexts);
assert.equal(provisionalExport.ok, true);
assert.equal(provisionalExport.value.points[0].rally_start_ms, null, 'provisional values are never exported as confirmed range input');
assert.equal(provisionalExport.value.points[0].rally_end_ms, null);
assert.equal(importQuickAnnotationDraft({ ...exported, contract_version: 'ptti.quick-annotation/9.9' }).issue, 'unsupported-contract-version');
assert.equal(importQuickAnnotationDraft({ ...exported, points: [{ ...exported.points[0], point_id: 'broken' }] }).issue, 'invalid-point-id');
assert.equal(importQuickAnnotationDraft({ ...exported, points: [{ ...exported.points[0], winner: 4 }] }).issue, 'invalid-point-side');
assert.equal(importQuickAnnotationDraft({ ...exported, points: [{ ...exported.points[0], extra: true }] }).issue, 'invalid-contract-point-fields');
const simulatedMatchId = 'SIMULATED_ONLY:qa-import';
const simulatedPayload = {
  ...exported,
  dataset_id: 'SIMULATED_ONLY:qa-import-dataset',
  dataset_class: 'SIMULATED_ONLY',
  match_id: simulatedMatchId,
  video_context: { ...exported.video_context, source_id: 'SIMULATED_ONLY:declared-but-unverified-source' },
  points: exported.points.map((point) => ({ ...point, point_id: createQuickPointId(simulatedMatchId, 1, 1) })),
};
const simulatedImport = importQuickAnnotationDraft(simulatedPayload);
assert.equal(simulatedImport.ok, true);
assert.equal(simulatedImport.value.identity.dataset_class, 'SIMULATED_ONLY');
assert.equal(simulatedImport.value.identity.source_id, 'SIMULATED_ONLY:declared-but-unverified-source');
const simulatedSession = { ...session, dataset_id: simulatedPayload.dataset_id, dataset_class: 'SIMULATED_ONLY', match_id: simulatedMatchId, source_id: 'SIMULATED_ONLY:declared-but-unverified-source' };
const simulatedExport = createQuickAnnotationInput(simulatedSession, simulatedImport.value.points, simulatedImport.value.game_contexts);
assert.equal(simulatedExport.ok, true);
assert.equal(simulatedExport.value.dataset_class, 'SIMULATED_ONLY', 're-export cannot promote SIMULATED_ONLY into a human draft');
assert.equal(simulatedExport.value.match_id, simulatedMatchId);
assert.equal(simulatedExport.value.video_context.source_id, 'SIMULATED_ONLY:declared-but-unverified-source', 'a declared source reference is preserved as data, not independently verified');

const twentyPointSample = Array.from({ length: 20 }, (_, index) => ({
  ...basePoint,
  point_id: createQuickPointId(session.match_id, 1, index + 1),
  point_number: index + 1,
  winner: index % 2 === 0 ? 'PLAYER_A' : 'PLAYER_B',
  observed_tactics: { ...basePoint.observed_tactics, serve_side: index < 4 ? 'forehand' : 'unknown', third_ball_attack: index < 2 ? 'yes' : 'unknown' },
}));
const separatedCounts = summarizeLocalQuickPoints(twentyPointSample, twentyPointSample.slice(0, 12).map((point) => point.point_id));
assert.equal(separatedCounts.total_points, 20);
assert.equal(separatedCounts.known_winner_points, 20);
assert.deepEqual(separatedCounts.score_by_winner, { PLAYER_A: 10, PLAYER_B: 10 }, 'score observations are counted without requiring video timestamps');
assert.equal(separatedCounts.reviewable_points, 12, 'playback eligibility is reported as a separate count');
assert.equal(separatedCounts.independently_verified_media_points, 0, 'a page-local video session never counts as independently verified media');
assert.equal(separatedCounts.known_serve_side, 4, 'technical field sample denominator comes from explicitly observed values');
assert.equal(separatedCounts.known_third_ball_attack, 2);
const noSampleCounts = summarizeLocalQuickPoints([{ ...basePoint, observed_tactics: { serve_side: 'unknown', third_ball_attack: 'unknown' } }]);
assert.equal(noSampleCounts.known_serve_side, 0);
assert.equal(noSampleCounts.known_third_ball_attack, 0, 'no observed tactics yields no technical sample and is presented as UNKNOWN');

const editedWinner = { ...basePoint, winner: 'PLAYER_B' };
assert.equal(editedWinner.point_id, basePoint.point_id, 'editing a point retains its stable point_id');
const duplicate = validateQuickAnnotationPoints(session, [basePoint, { ...basePoint }], gameContexts);
assert.equal(duplicate.ok, false);
assert.equal(duplicate.issue, 'duplicate-point-id');
assert.equal(validateQuickAnnotationPoint({ ...basePoint, point_id: 'qa-session-001:point-001' }, 12345, gameContexts, [], null, session.match_id).issue, 'invalid-point-id');

for (const [candidate, issue] of [
  [{ ...basePoint, start_seconds: -0.001 }, 'time-out-of-range'],
  [{ ...basePoint, start_seconds: -0.0004 }, 'time-out-of-range'],
  [{ ...basePoint, end_seconds: 12.346 }, 'time-out-of-range'],
  [{ ...basePoint, start_seconds: 2.345, end_seconds: 2.3454 }, 'start-after-end'],
  [{ ...basePoint, start_seconds: 1.234, end_seconds: null }, 'incomplete-time-range'],
  [{ ...basePoint, start_seconds: Number.NaN }, 'incomplete-time-range'],
  [{ ...basePoint, winner: 'Fan Zhendong' }, 'invalid-winner'],
  [{ ...basePoint, server: 'PLAYER_C' }, 'invalid-server'],
  [{ ...basePoint, observed_tactics: { ...basePoint.observed_tactics, serve_length: 'very-long' } }, 'invalid-tactics'],
]) {
  const result = validateQuickAnnotationPoint(candidate, 12345, gameContexts, [], null, session.match_id);
  assert.equal(result.ok, false, `expected rejection for ${issue}`);
  assert.equal(result.issue, issue);
}

const missingDurationSession = { ...session, duration_seconds: null };
const unknownTimePoint = { ...basePoint, start_seconds: null, end_seconds: null };
assert.deepEqual(validateQuickAnnotationPoints(missingDurationSession, [unknownTimePoint], gameContexts), { ok: true });
const unknownDurationExport = createQuickAnnotationInput(missingDurationSession, [unknownTimePoint], gameContexts);
assert.equal(unknownDurationExport.ok, true);
assert.equal(unknownDurationExport.value.video_context.duration_status, 'UNKNOWN');
assert.equal(unknownDurationExport.value.video_context.duration_ms, null);
assert.equal(unknownDurationExport.value.points[0].rally_start_ms, null);
assert.equal(validateQuickAnnotationPoint(basePoint, null, gameContexts, [], null, session.match_id).issue, 'duration-unknown');
assert.equal(validateQuickAnnotationInput({ ...exported, contract_version: 'ptti.quick-annotation/9.9' }).issue, 'unsupported-contract-version');
assert.equal(validateQuickAnnotationInput({ ...exported, extra: 'not allowed' }).issue, 'invalid-contract-fields');
assert.equal(validateQuickAnnotationPoints({ ...session, file: { ...session.file, type: 'video/webm' } }, [basePoint], gameContexts).issue, 'unbound-video');
assert.equal(validateQuickAnnotationPoints({ ...session, file: { ...session.file, name: 'unsupported.webm' } }, [basePoint], gameContexts).issue, 'unbound-video');

assert.equal(expectedServerForPoint('player', 1), 'player');
assert.equal(expectedServerForPoint('player', 20), 'opponent');
assert.equal(expectedServerForPoint('player', 21), 'player');
assert.equal(expectedServerForPoint('player', 22), 'opponent');
assert.equal(expectedServerForPoint('player', 23), 'player');
const completeFromStart = { 1: { game_number: 1, coverage: 'COMPLETE_FROM_GAME_START', first_server: 'PLAYER_A' } };
const point21 = { ...basePoint, point_id: createQuickPointId(session.match_id, 1, 21), point_number: 21, server: 'PLAYER_A', start_seconds: null, end_seconds: null };
const point22WrongServe = { ...point21, point_id: createQuickPointId(session.match_id, 1, 22), point_number: 22, server: 'PLAYER_A' };
assert.equal(validateQuickAnnotationPoint(point21, 12345, completeFromStart, [], null, session.match_id).ok, true, 'first server returns for point 21 after 10:10');
assert.equal(validateQuickAnnotationPoint({ ...point22WrongServe, server: 'PLAYER_B' }, 12345, completeFromStart, [], null, session.match_id).ok, true, 'one-point service rotation switches after point 21');
assert.equal(validateQuickAnnotationPoint(point22WrongServe, 12345, completeFromStart, [], null, session.match_id).issue, 'service-rotation-conflict');
assert.equal(suggestedLocalServerForPoint(completeFromStart[1], 20), 'PLAYER_B');
assert.equal(suggestedLocalServerForPoint(completeFromStart[1], 21), 'PLAYER_A');
assert.equal(suggestedLocalServerForPoint(completeFromStart[1], 22), 'PLAYER_B');
assert.equal(suggestedLocalServerForPoint(gameContexts[1], 22), 'UNKNOWN', 'partial game coverage never suggests a server');
assert.equal(suggestedLocalServerForPoint({ ...completeFromStart[1], first_server: 'UNKNOWN' }, 22), 'UNKNOWN', 'unknown first server never suggests a server');

const gapPoints = [basePoint, { ...basePoint, point_id: createQuickPointId(session.match_id, 1, 3), point_number: 3, start_seconds: null, end_seconds: null }];
assert.equal(validateQuickAnnotationPoints(session, gapPoints, gameContexts).ok, true, 'a gap remains representable as an incomplete draft and is checked by MainDex CLI');
assert.equal(nextUnannotatedPointNumber(gapPoints, 1), 2, 'new point fills the earliest missing annotation without renumbering existing points');
assert.equal(nextUnannotatedPointNumber(gapPoints, 2), 1, 'point numbering stays independent for each game');

console.log('Quick Annotation input checks PASS (contract fields, stable IDs, millisecond conversion, UNKNOWN values, edits, duplicates, time bounds, unknown duration, media format, gap filling, and 10:10 service rotation).');
