import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {activeStoryMatch} from '../src/storyRoute.mjs';

const story = {matchId: 'match:verified-001', page: 'home', revision: 4};

assert.equal(activeStoryMatch(story, 'home', 4), 'match:verified-001');
assert.equal(
  activeStoryMatch(story, 'feedFavorites', 5),
  null,
  'Top navigation to Favorites must leave Story and render the favorites list',
);
assert.equal(
  activeStoryMatch(story, 'home', 5),
  null,
  'Returning to the video wall must not resurrect a Story from an older navigation revision',
);
assert.equal(activeStoryMatch(story, 'professionalMatches', 5), null);
assert.equal(activeStoryMatch(null, 'home', 4), null);
assert.equal(
  activeStoryMatch({matchId: 'match:verified-002', page: 'home', revision: 6}, 'home', 6),
  'match:verified-002',
  'A new Story entered after returning to the wall uses its newly selected exact match ID',
);

const videoFeed = readFileSync(new URL('../src/VideoFeed.tsx', import.meta.url), 'utf8');
const feedCatalog = readFileSync(new URL('../src/feedCatalog.ts', import.meta.url), 'utf8');
const catalogImport = readFileSync(new URL('../../backend/catalog_import.py', import.meta.url), 'utf8');
assert.match(videoFeed, /activeStoryMatch\(storyRoute,page,revision\)/);
assert.match(videoFeed, /setStoryRoute\(\{matchId:feedMatchId\(v\)!,page,revision\}\)/);
assert.match(videoFeed, /setOfficial\(null\);setStoryRoute\(null\)/);
assert.match(videoFeed, /data\.matches\.find\(\(match:any\)=>match\.match_id===activeStoryId\)/);
assert.match(videoFeed, /page==='feedFavorites'\?uniqueFavoriteRows\(filtered,favorites\):filtered/);
assert.match(videoFeed, /href=\{v\.source\.source_url\} target="_blank" rel="noopener noreferrer"/);
assert.match(videoFeed, /OfficialLinkRecovery url=\{v\.source\.source_url\}/);
assert.match(feedCatalog, /s\?\.embed_permission==='ALLOWED'&&s\?\.playback_type==='OFFICIAL_EMBED'/);
assert.match(catalogImport, /u\.scheme != "https"/);
assert.match(catalogImport, /parse_qs\(u\.query\) != \{"v": \[self\.video_id\]\}/);

console.log('story route regression passed');
