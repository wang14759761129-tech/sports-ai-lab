import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const sourceRoot = new URL('../src/', import.meta.url);
const [app, cinema, demo, workbench, metadata, messages] = await Promise.all([
  readFile(new URL('App.tsx', sourceRoot), 'utf8'),
  readFile(new URL('LocalVideoReview.tsx', sourceRoot), 'utf8'),
  readFile(new URL('CinemaDemo.tsx', sourceRoot), 'utf8'),
  readFile(new URL('ProWorkbench.tsx', sourceRoot), 'utf8'),
  readFile(new URL('MetadataContent.tsx', sourceRoot), 'utf8'),
  readFile(new URL('i18n.ts', sourceRoot), 'utf8'),
]);

assert.match(cinema, /data-cinema-entry="local-video"[\s\S]*?data-cinema-entry="match-source"/, 'Cinema presents distinct local-video and external-source entry points');
assert.match(cinema, /data-cinema-entry="match-source"[\s\S]*?onBrowseMatches/, 'the source entry routes to the existing sourced match catalog');
assert.match(demo, /data-cinema-entry="simulated-review"/, 'the simulated review is a distinct entry, separate from real match sources');
assert.match(demo, /SIMULATED_ONLY[\s\S]*?data-demo-target[\s\S]*?data-load-golden/, 'the 19-point demo is visibly simulated and uses validated demo targets');
assert.match(demo, /t\('cinema\.demo\.noReplay'\)/, 'the demo explicitly describes zero replayable clips without bundled footage');
assert.match(messages, /'cinema\.demo\.noReplay': '当前可回看0段/, 'Chinese demo copy says no clip is currently replayable');
assert.match(messages, /'cinema\.demo\.noReplay': '0 currently replayable clips/, 'English demo copy says no clip is currently replayable');
assert.match(app, /<div hidden=\{page !== 'cinema' && page !== 'pro'\} data-persistent-workspace><ProWorkbench/, 'ProWorkbench remains mounted while Cinema, Insight and Review navigation changes');
assert.match(workbench, /<LocalVideoReview[^>]*active=\{active\}/, 'the persistent workspace forwards its active state to the player');
assert.match(cinema, /useEffect\(\(\) => \{ if \(!active\) \{ cancelPlaylist\(\); controllerRef\.current\?\.pause\(\); \} \}, \[active\]\)/, 'hiding the workspace pauses and cancels playback without unmounting the component');
assert.match(cinema, /useEffect\(\(\) => \{\s*if \(!hasSession \|\| !videoRef\.current\) return undefined;[\s\S]*?\}, \[hasSession\]\)/, 'navigation state does not tear down the video controller; its lifetime follows whether a local session exists');
assert.match(cinema, /useEffect\(\(\) => \{ setComparisonNote\(''\); \}, \[session\?\.session_id\]\)/, 'manual comparison notes are retained across navigation and cleared when the media session changes');
assert.match(cinema, /const playlistStatus = playbackSnapshot\.playlist\?\.status/, 'return UI derives queue controls from the latest playback snapshot');
assert.match(cinema, /playbackSnapshot\.is_playing \? t\('pro\.video\.pause'\) : t\('pro\.video\.play'\)/, 'play/pause action reflects the playback snapshot after navigation');
assert.match(cinema, /createReviewComparisonExport\(\{ report: targets, target: activeTarget, points, playbackBindings, note: comparisonNote, sessionId: session\.session_id \}\)/, 'comparison export binds current data identity and the user-entered note');
assert.equal((metadata.match(/data-review-guide-card=/g) ?? []).length, 3, 'Explore has exactly three review knowledge cards');
for (const key of ['metadata.boardCopy', 'metadata.sampleCopy', 'metadata.annotationCopy']) {
  assert.match(messages, new RegExp(`'${key}':`), `${key} is present in the bilingual dictionary`);
}
assert.match(messages, /'metadata\.boardCopy': '[^']*UNKNOWN[^']*不能推断技术/, 'Chinese coarse stages are not presented as technical diagnosis');
assert.match(messages, /'metadata\.boardCopy': '[^']*UNKNOWN[^']*do not establish technique/, 'English coarse stages are not presented as technical diagnosis');
assert.match(messages, /'metadata\.sampleCopy': '[^']*有效分母 N[^']*提示阈值/, 'Chinese sample card refers to report-provided denominator and threshold');
assert.match(messages, /'metadata\.sampleCopy': '[^']*valid denominator N[^']*caution threshold/, 'English sample card refers to report-provided denominator and threshold');
assert.match(messages, /'cinema\.source\.boundary': '[^']*不代表PTTI站内播放[^']*/, 'Chinese external-source copy avoids claiming embedded playback or authorization');
assert.match(messages, /'cinema\.source\.boundary': '[^']*does not mean PTTI playback[^']*/, 'English external-source copy avoids claiming embedded playback or authorization');

console.log('Cinema experience contracts PASS: distinct entrances, simulated-only demo, persistent player mount, pause-on-hide, exactly three bounded Explore guides, and zh/en evidence wording.');
