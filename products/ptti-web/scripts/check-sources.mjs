import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const matches = JSON.parse(await readFile(resolve(root, 'public/data/cinema.json'), 'utf8'));
const contentSource = await readFile(resolve(root, 'src/data/content.ts'), 'utf8');
const appSource = await readFile(resolve(root, 'src/App.tsx'), 'utf8');
const allowedHosts = new Set([
  'worldtabletennis.com',
  'www.worldtabletennis.com',
  'youtube.com',
  'www.youtube.com',
  'weibo.com',
]);
let checked = 0;
const failures = [];

function check(condition, label) {
  checked += 1;
  if (!condition) failures.push(label);
}

function checkUrl(value, label) {
  if (!value) return;
  try {
    const url = new URL(value);
    check(url.protocol === 'https:', `${label}: URL must use HTTPS`);
    check(allowedHosts.has(url.hostname.toLowerCase()), `${label}: unexpected host ${url.hostname}`);
  } catch {
    check(false, `${label}: invalid URL`);
  }
}

check(Array.isArray(matches) && matches.length > 0, 'Cinema source list must be a non-empty array');
const ids = new Set();
for (const [index, match] of matches.entries()) {
  const label = `match[${index}]`;
  check(typeof match.id === 'string' && !ids.has(match.id), `${label}: id must be unique`);
  ids.add(match.id);
  check(['MS', 'WS', 'MD', 'WD', 'XD'].includes(match.discipline), `${label}: unsupported discipline`);
  check(Array.isArray(match.players) && match.players.length >= 2, `${label}: at least two players are required`);
  check(Array.isArray(match.sourceEvidence) && match.sourceEvidence.length > 0, `${label}: evidence URL is required`);
  check(match.playbackTested === false, `${label}: do not mark playback tested without a recorded test`);
  check(match.embedAllowed !== true, `${label}: this pilot must not embed media`);
  check(['event-page', 'video-page', 'source-only'].includes(match.routeType), `${label}: route type must be explicit`);
  for (const url of [match.platformUrl, match.videoOriginalUrl, ...match.sourceEvidence]) checkUrl(url, `${label} URL`);
  if (match.routeType === 'event-page') {
    check(Boolean(match.platformUrl) && !match.videoOriginalUrl, `${label}: event route must point to an official event page`);
  } else if (match.routeType === 'video-page') {
    check(Boolean(match.videoOriginalUrl) && match.platformUrl === match.videoOriginalUrl, `${label}: video route must point directly to its original video page`);
    check(match.sourceEvidence.includes(match.videoOriginalUrl), `${label}: direct video page must be recorded as source evidence`);
  } else if (match.routeType === 'source-only') {
    check(!match.platformUrl && !match.videoOriginalUrl, `${label}: no-route status cannot have a watch URL`);
  } else {
    check(false, `${label}: unknown route type`);
  }
  if (match.sourceStatus === 'official-listing-found') {
    check(match.routeType !== 'source-only', `${label}: source-only records cannot claim a watch route`);
  } else if (match.sourceStatus === 'no-verified-route') {
    check(match.routeType === 'source-only', `${label}: a no-route record must be source-only`);
  } else {
    check(false, `${label}: unknown source status`);
  }
}

check(!/playbackTested:\s*true/.test(contentSource), 'Do not mark Pulse playback tested without a recorded test');
check(appSource.includes('target="_blank" rel="noopener noreferrer"'), 'External links must use safe new-tab attributes');

for (const file of [contentSource, appSource]) {
  check(!/<iframe\b|<video\b/i.test(file), 'Do not embed or host media in this pilot');
  check(!/http:\/\//i.test(file), 'External links must use HTTPS');
  for (const value of file.matchAll(/https:\/\/[^\s'"<>`]+/g)) {
    checkUrl(value[0].replace(/[),.;]+$/, ''), 'content source URL');
  }
}

if (failures.length) {
  console.error(`Source/security checks failed (${failures.length}/${checked}):`);
  for (const failure of failures) console.error(`- ${failure}`);
  process.exitCode = 1;
} else {
  console.log(`Source/security checks passed: ${checked} checks across ${matches.length} match records.`);
}
