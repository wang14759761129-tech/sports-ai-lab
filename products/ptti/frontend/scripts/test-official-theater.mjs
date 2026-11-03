import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {reviewedOfficialSource} from '../src/reviewedOfficialEmbed.mjs';
const catalog=JSON.parse(readFileSync(new URL('../../data/professional/official_video_sources.json',import.meta.url),'utf8'));
const source=catalog.videos.find(s=>s.video_id==='0QgbtsBWZhk');
const canonical={...source,video_source:{provider:'YOUTUBE',source_id:source.video_id,match_id:source.match_id,embed_permission:'DENIED',playback_type:'OFFICIAL_PAGE'}};
const observed=reviewedOfficialSource(canonical);
assert.equal(observed,canonical,'An observation-only review must not mutate the source');
assert.equal(observed.video_source.embed_permission,'DENIED','0Q remains denied after playback observation');
assert.equal(observed.playback_status,'EMBED_BLOCKED','The source catalog prohibition is preserved');
assert.equal(observed.native_playback_test.result,'FAILED','historical Native error 150 evidence is preserved');
assert.equal(observed.official_embed_review.decision,'ALLOW_OFFICIAL_PLAYER_ATTEMPT','Attempt observation stays distinct from embed authorization');
const noGrant=reviewedOfficialSource(source);
assert.equal(noGrant,source,'The real catalog source is never upgraded by the observation record');
for(const patch of [
 {video_id:'vYsJLPTEIaI'}, {provider:'BILIBILI'}, {match_id:'wrong'},
 {source_url:'https://www.youtube.com/watch?v=another0000'},
 {channel_url:'https://www.youtube.com/@impostor'}, {official_embed_review:null},
 {official_embed_review:{...source.official_embed_review,scope:'THUMBNAIL'}},
 {official_embed_review:{...source.official_embed_review,decision:'UNKNOWN'}},
 {official_embed_review:{...source.official_embed_review,channel_id:'impostor'}},
 {video_source:{...canonical.video_source,source_id:'different00'}},
 {video_source:{...canonical.video_source,match_id:'wrong'}},
]){
 const invalid={...canonical,...patch};assert.equal(reviewedOfficialSource(invalid),invalid,'conflicting/unreviewed identity rejected');
}
for(const other of catalog.videos.filter(s=>s.video_id!==source.video_id))assert.equal(reviewedOfficialSource(other),other);
const player=readFileSync(new URL('../src/OfficialVideoPlayer.tsx',import.meta.url),'utf8');
assert.ok(player.indexOf('official-theater-actions')<player.indexOf('official-theater-viewport'),'Official page fallback appears before the embed area');
assert.ok(!player.includes('source.playback_limitation||status'),'historical text must not mask live errors');
assert.match(player,/autoplay=0&controls=1&enablejsapi=1&origin=/);
assert.match(player,/referrerPolicy='strict-origin-when-cross-origin'/);
assert.match(player,/if\(!live\)return/,'late API completion must not re-create removed iframe');
assert.match(player,/player\?\.destroy\(\).*finally\{container.replaceChildren\(\)\}/);
assert.match(player,/<OfficialLinkRecovery url=\{source.source_url\}/);
assert.match(player,/\[source.video_id,iframeUrl\]/);
console.log('Official theater: scoped admission, conflicting identities, historical evidence and lifecycle contracts PASS');
