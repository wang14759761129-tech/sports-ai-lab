import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';
import { toRallyPlaybackBinding, toRallyPlaybackBindings, playbackIssueMessageKey } from '../src/playback-adapter.mjs';

let checks = 0;
function check(name, actual, expected) {
  assert.deepEqual(actual, expected, name);
  checks += 1;
}

const current = {
  current_video_identity: 'local-session:video-a',
  bound_video_identity: 'local-session:video-a',
  duration_seconds: 12,
  start_confirmed: true,
  end_confirmed: true,
};
const point = { point_id: 'LOCAL/g01/p001', rally_start_ms: 1250, rally_end_ms: 2875 };
const bound = toRallyPlaybackBinding(point, current);
check('contract ms convert to playback seconds only when explicitly confirmed', bound, {
  point_id: point.point_id, video_identity: 'local-session:video-a', start_time: 1.25, end_time: 2.875, binding_status: 'BOUND',
});
check('point list adapts each row', toRallyPlaybackBindings([point], current).length, 1);
check('unconfirmed end is not a playable binding', toRallyPlaybackBinding(point, { ...current, end_confirmed: false }).binding_status, 'PENDING_ANNOTATION');
check('unconfirmed start is not a playable binding', toRallyPlaybackBinding(point, { ...current, start_confirmed: false }).binding_status, 'PENDING_ANNOTATION');
check('a previous video session becomes stale', toRallyPlaybackBinding(point, { ...current, current_video_identity: 'local-session:video-b' }).binding_status, 'STALE');
check('missing media identity stays unbound', toRallyPlaybackBinding(point, { ...current, current_video_identity: null, bound_video_identity: null }).binding_status, 'UNBOUND');
check('null timestamps remain non-playable', toRallyPlaybackBinding({ ...point, rally_start_ms: null }, current).binding_status, 'PENDING_ANNOTATION');
check('fractional milliseconds are rejected', toRallyPlaybackBinding({ ...point, rally_start_ms: 1250.5 }, current).binding_status, 'PENDING_ANNOTATION');
check('negative timestamps are rejected', toRallyPlaybackBinding({ ...point, rally_start_ms: -1 }, current).binding_status, 'PENDING_ANNOTATION');
check('zero-width range is rejected', toRallyPlaybackBinding({ ...point, rally_end_ms: 1250 }, current).binding_status, 'PENDING_ANNOTATION');
check('duration overflow is rejected', toRallyPlaybackBinding({ ...point, rally_end_ms: 12001 }, current).binding_status, 'PENDING_ANNOTATION');
check('unknown duration fails closed', toRallyPlaybackBinding(point, { ...current, duration_seconds: null }).binding_status, 'PENDING_ANNOTATION');

const errorMappings = { 'play-rejected': 'playRejected', 'seek-failed': 'seekFailed', 'seek-timeout': 'seekTimeout', 'video-not-ready': 'videoNotReady', 'media-aborted': 'readAborted', 'file-read-error': 'readFailed', 'unsupported-media': 'unsupportedMedia', 'decode-error': 'decodeFailed', 'duration-unavailable': 'durationUnavailable', 'time-out-of-range': 'timeOutOfRange', 'video-mismatch': 'identityMismatch', 'identity-unavailable': 'identityUnavailable' };
for (const [code, key] of Object.entries(errorMappings)) {
  check(`Core ${code} retains its precise meaning`, playbackIssueMessageKey(code), `pro.video.${key}`);
}
check('unrecognized errors remain neutral', playbackIssueMessageKey('unknown-future-error'), 'pro.video.playbackFailed');
check('prototype names remain neutral', playbackIssueMessageKey('toString'), 'pro.video.playbackFailed');
check('user cancellation is not an error warning', playbackIssueMessageKey('cancelled'), '');
check('normal playlist replacement is not an error warning', playbackIssueMessageKey('playlist-replaced'), '');
check('external RESTRICTED is not a local media classification', playbackIssueMessageKey('RESTRICTED'), 'pro.video.playbackFailed');
const compiled = ts.transpileModule(await readFile(new URL('../src/i18n.ts', import.meta.url), 'utf8'), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const { message } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
for (const locale of ['zh-CN', 'en']) for (const code of Object.keys(errorMappings)) {
  const key = playbackIssueMessageKey(code);
  const copy = message(locale, key);
  check(`${locale} ${code} has actual localized copy`, typeof copy === 'string' && copy.length > 5 && copy !== key, true);
}
console.log(`Playback adapter checks PASS: ${checks} assertions; time units, confirmation gate, session identity, invalid ranges and Core error semantics.`);
