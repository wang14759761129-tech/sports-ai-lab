import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  filterMatchRecords,
  getMatchDestination,
  getWatchFilterCounts,
  hasVerifiedVisualPlayback,
} from '../src/watch-filter.mjs';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const matches = JSON.parse(await readFile(resolve(root, 'public/data/cinema.json'), 'utf8'));
const [eventMatch, fanLin, wangSun, sourceOnly] = matches;

assert.equal(matches.length, 4, 'the test fixture should remain the four reviewed records');
assert.equal(hasVerifiedVisualPlayback(fanLin), true, 'verified official video should pass the strict gate');
assert.equal(hasVerifiedVisualPlayback(wangSun), true, 'second verified official video should pass the strict gate');
assert.equal(hasVerifiedVisualPlayback(eventMatch), false, 'an event page is never a verified video page');
assert.equal(hasVerifiedVisualPlayback(sourceOnly), false, 'source-only evidence is never a verified video page');

const counts = getWatchFilterCounts(matches);
assert.deepEqual(counts, { all: 4, 'verified-video': 2, 'event-page': 1, 'source-only': 1, unverified: 2 });
assert.deepEqual(getWatchFilterCounts(matches, { discipline: 'WS' }), { all: 2, 'verified-video': 1, 'event-page': 0, 'source-only': 1, unverified: 1 }, 'chips should update with the current non-watch filters');
assert.deepEqual(filterMatchRecords(matches, { watchFilter: 'verified-video' }).map(({ id }) => id), [fanLin.id, wangSun.id]);
assert.deepEqual(filterMatchRecords(matches, { watchFilter: 'event-page' }).map(({ id }) => id), [eventMatch.id]);
assert.deepEqual(filterMatchRecords(matches, { watchFilter: 'source-only' }).map(({ id }) => id), [sourceOnly.id]);
assert.deepEqual(filterMatchRecords(matches, { watchFilter: 'unverified' }).map(({ id }) => id), [eventMatch.id, sourceOnly.id]);
assert.equal(counts.unverified, counts['event-page'] + counts['source-only'], 'no-playback-evidence is an independent axis that overlaps event/source route types');
assert.equal(filterMatchRecords(matches, { query: '樊振东' }).some(({ id }) => id === fanLin.id), true, 'Chinese alias search should find the match');
assert.equal(filterMatchRecords(matches, { query: 'Fan Zhendong' }).some(({ id }) => id === fanLin.id), true, 'English player search should find the match');
assert.equal(filterMatchRecords(matches, { discipline: 'WS' }).length, 2, 'discipline filtering should still work');
assert.equal(filterMatchRecords(matches, { query: 'no-such-player' }).length, 0, 'no-match search should be empty');
assert.equal(filterMatchRecords(matches).length, matches.length, 'clearing all filters should restore every record');

assert.deepEqual(getMatchDestination(eventMatch), { type: 'event-page', url: eventMatch.platformUrl });
assert.deepEqual(getMatchDestination(fanLin), { type: 'video-page', url: fanLin.videoOriginalUrl });
assert.deepEqual(getMatchDestination(sourceOnly), { type: 'source-only', url: sourceOnly.sourceEvidence[0] });
assert.equal(getMatchDestination({ ...eventMatch, platformUrl: null }), null, 'missing event route should not create a button');
assert.equal(getMatchDestination({ ...sourceOnly, platformUrl: sourceOnly.sourceEvidence[0] }), null, 'source-only record cannot acquire a watch URL');

const invalidPasses = [
  { ...fanLin, routeType: 'event-page' },
  { ...fanLin, videoOriginalUrl: null },
  { ...fanLin, platformUrl: 'https://www.youtube.com/watch?v=wrong' },
  { ...fanLin, playbackEvidence: { ...fanLin.playbackEvidence, timeAtFinalObservationSeconds: 6 } },
  { ...fanLin, playbackEvidence: { ...fanLin.playbackEvidence, visualFramesChanged: false } },
  { ...fanLin, playbackEvidence: { ...fanLin.playbackEvidence, finalUrl: 'https://www.youtube.com/watch?v=wrong' } },
  { ...fanLin, playbackEvidence: { ...fanLin.playbackEvidence, regionPromptSeen: true } },
  { ...fanLin, playbackEvidence: undefined },
];
for (const [index, match] of invalidPasses.entries()) {
  assert.equal(hasVerifiedVisualPlayback(match), false, `malformed or mismatched playback evidence ${index + 1} must not pass`);
}

const [appSource, cssSource, i18nSource] = await Promise.all([
  readFile(resolve(root, 'src/App.tsx'), 'utf8'),
  readFile(resolve(root, 'src/style.css'), 'utf8'),
  readFile(resolve(root, 'src/i18n.ts'), 'utf8'),
]);
for (const key of ['filter.watchStatus', 'filter.watch.all', 'filter.watch.verified', 'filter.watch.event', 'filter.watch.source', 'filter.watch.unverified', 'filter.watchOverlapHint']) {
  assert.equal(i18nSource.match(new RegExp(`'${key.replaceAll('.', '\\.')}'\\s*:`, 'g'))?.length, 2, `${key} must have both Chinese and English copy`);
}
assert.match(appSource, /filter\.watchOverlapHint/, 'route and playback-status overlap must be explained in the visible UI');
assert.match(cssSource, /\.match-art\s*\{[^}]*aspect-ratio:\s*16\s*\/\s*9/s, 'match art must retain a 16:9 branded placeholder');
assert.doesNotMatch(appSource, /<img\b|<iframe\b|<video\b/i, 'Cinema must not introduce unlicensed imagery or embedded media');
assert.doesNotMatch(cssSource, /url\(\s*https?:/i, 'CSS must not fetch unreviewed external cover art');
assert.match(appSource, /target="_blank" rel="noopener noreferrer"/, 'official destinations must retain safe new-tab behavior');

console.log('Watch filter checks passed: strict visual-playback gate, route mapping, Chinese/English search, status filters, reset, safe links, and branded 16:9 placeholder.');
