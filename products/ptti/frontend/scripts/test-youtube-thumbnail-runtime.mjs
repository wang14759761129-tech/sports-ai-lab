import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createYoutubeThumbnailRuntime, resolveYoutubeThumbnail, youtubeThumbnailSourceId} from '../src/youtubeThumbnailRuntime.mjs';

const videoId = 'AbCdEfGhI12';
const source = {
  provider: 'YOUTUBE_OFFICIAL',
  video_id: videoId,
  source_url: `https://www.youtube.com/watch?v=${videoId}`,
  thumbnail_url: `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`,
  video_source: {embed_permission: 'NOT_ALLOWED'},
  provenance: {verified_youtube_channel_id: 'UCWTTVerified'},
};
const retrievedAt = Date.parse('2026-10-24T00:00:00.000Z');
const apiResponse = {
  items: [{
    id: videoId,
    snippet: {
      title: 'Official title from API',
      channelId: 'UCWTTVerified',
      channelTitle: 'World Table Tennis fixture',
      thumbnails: {high: {url: `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`, width: 480, height: 360}},
    },
  }],
};
const approvedClient = {api_client_review: 'APPROVED', click_target: 'YOUTUBE_APP_OR_SYSTEM_BROWSER'};
const fixtureLabel = 'SIMULATED_ONLY — synthetic videos.list response, not an API request or rights clearance';

assert.match(fixtureLabel, /^SIMULATED_ONLY/);
assert.equal(youtubeThumbnailSourceId(source), `video-source:youtube:${videoId}`);
assert.equal(youtubeThumbnailSourceId({...source, source_key: `YOUTUBE_OFFICIAL:${videoId}`}), `video-source:youtube:${videoId}`, 'A feed grouping key cannot replace the GOAL96 source_id');

const notApproved = createYoutubeThumbnailRuntime(source, apiResponse, {api_client_review: 'CONDITIONAL_APPROVAL'}, retrievedAt);
assert.equal(notApproved.status, 'NOT_CONFIGURED');
assert.equal(resolveYoutubeThumbnail(source, notApproved, retrievedAt).thumbnail, null, 'Unapproved client never renders a thumbnail');

const current = createYoutubeThumbnailRuntime(source, apiResponse, approvedClient, retrievedAt);
assert.equal(current.provider, 'YOUTUBE_DATA_API');
assert.equal(current.status, 'CURRENT');
assert.equal(current.api_client_review, 'APPROVED');
assert.equal(current.source_id, `video-source:youtube:${videoId}`);
assert.equal(current.provider_video_id, videoId);
assert.equal(current.youtube_title, apiResponse.items[0].snippet.title, 'API title remains unchanged');
assert.equal(current.channel_id, 'UCWTTVerified');
assert.equal(current.channel_title, apiResponse.items[0].snippet.channelTitle);
assert.deepEqual(current.thumbnail, {url: apiResponse.items[0].snippet.thumbnails.high.url, key: 'high', width: 480, height: 360});
assert.equal(current.attribution_required, true);
assert.equal(current.click_target, 'YOUTUBE_APP_OR_SYSTEM_BROWSER');
assert.equal(current.embed_permission, 'NOT_ALLOWED', 'Thumbnail display does not upgrade embed permission');
const resolved = resolveYoutubeThumbnail(source, current, retrievedAt);
assert.equal(resolved.status, 'CURRENT');
assert.equal(resolved.thumbnail.url, apiResponse.items[0].snippet.thumbnails.high.url);

assert.equal(createYoutubeThumbnailRuntime(source, {items: []}, approvedClient, retrievedAt).status, 'UNAVAILABLE');
assert.equal(createYoutubeThumbnailRuntime(source, {items: [{id: 'ZzYyXxWwVvU', snippet: apiResponse.items[0].snippet}]}, approvedClient, retrievedAt).status, 'ID_MISMATCH');
assert.equal(createYoutubeThumbnailRuntime(source, {items: [{id: videoId, snippet: {...apiResponse.items[0].snippet, channelId: 'UCWrong'}}]}, approvedClient, retrievedAt).status, 'PUBLISHER_MISMATCH');
assert.equal(createYoutubeThumbnailRuntime({...source, provenance: {}}, apiResponse, approvedClient, retrievedAt).status, 'PUBLISHER_MISMATCH');
assert.equal(createYoutubeThumbnailRuntime(source, {items: [apiResponse.items[0], apiResponse.items[0]]}, approvedClient, retrievedAt).status, 'UNAVAILABLE', 'Ambiguous results fail closed');
assert.equal(createYoutubeThumbnailRuntime(source, {items: [{id: videoId, snippet: {...apiResponse.items[0].snippet, title: ''}}]}, approvedClient, retrievedAt).status, 'UNAVAILABLE');
assert.equal(createYoutubeThumbnailRuntime(source, {items: [{id: videoId, snippet: {...apiResponse.items[0].snippet, thumbnails: {}}}]}, approvedClient, retrievedAt).status, 'UNAVAILABLE');
assert.equal(createYoutubeThumbnailRuntime(source, apiResponse, {...approvedClient, click_target: undefined}, retrievedAt).status, 'UNAVAILABLE');
assert.equal(createYoutubeThumbnailRuntime({...source, source_url: `https://www.youtube.com/watch?v=OtherId1234`}, apiResponse, approvedClient, retrievedAt).status, 'UNAVAILABLE');
assert.equal(createYoutubeThumbnailRuntime({...source, video_id: 'short'}, apiResponse, approvedClient, retrievedAt).status, 'UNAVAILABLE');
assert.equal(resolveYoutubeThumbnail(source, {...current, source_id: 'video-source:youtube:OtherId1234'}, retrievedAt).status, 'SOURCE_OR_VIDEO_ID_MISMATCH');
assert.equal(resolveYoutubeThumbnail(source, {...current, provider_video_id: 'OtherId1234'}, retrievedAt).status, 'SOURCE_OR_VIDEO_ID_MISMATCH');
assert.equal(resolveYoutubeThumbnail(source, {...current, status: 'STALE'}, retrievedAt).status, 'STALE_OR_NOT_CURRENT');
assert.equal(resolveYoutubeThumbnail(source, current, retrievedAt + 31 * 24 * 60 * 60 * 1000).status, 'STALE_OR_NOT_CURRENT');
assert.equal(resolveYoutubeThumbnail(source, {...current, delete_or_refresh_by: '2026-10-24T00:00:00.000Z'}, retrievedAt).status, 'STALE_OR_NOT_CURRENT');
assert.equal(resolveYoutubeThumbnail(source, {...current, channel_id: 'UCWrong'}, retrievedAt).status, 'PUBLISHER_MISMATCH');
assert.equal(resolveYoutubeThumbnail({...source, source_url: `https://www.youtube.com/watch?v=OtherId1234`}, current, retrievedAt).status, 'SOURCE_URL_MISMATCH');
assert.equal(resolveYoutubeThumbnail(source, {...current, thumbnail: {...current.thumbnail, url: 'http://insecure.example/t.jpg'}}, retrievedAt).status, 'RUNTIME_CONTRACT_INVALID');
assert.equal(resolveYoutubeThumbnail(source, {...current, attribution_required: false}, retrievedAt).status, 'RUNTIME_CONTRACT_INVALID');

const catalog = JSON.parse(readFileSync('../data/professional/official_video_sources.json', 'utf8'));
const youtubeRows = catalog.videos.filter(video => video.provider === 'YOUTUBE_OFFICIAL');
assert.equal(youtubeRows.length, 8, 'Current review scope has eight YouTube sources');
assert.equal(youtubeRows.filter(video => !video.provenance?.verified_youtube_channel_id).length, 8, 'No source has an independently verified channel ID yet');
assert.equal(youtubeRows.filter(video => video.provenance?.thumbnail_display_permission === 'ALLOWED').length, 0, 'No static thumbnail permission was promoted');
for (const video of youtubeRows) {
  assert.match(video.video_id, /^[A-Za-z0-9_-]{11}$/, 'YouTube source has an exact video ID');
  assert.equal(new URL(video.source_url).searchParams.get('v'), video.video_id, 'Official watch URL matches the source ID');
  assert.match(video.thumbnail_url, new RegExp(`/vi/${video.video_id}/`), 'Legacy thumbnail URL matches the video ID but is not thereby authorized');
}
assert.equal(catalog.videos.filter(video => video.provider === 'BILIBILI').length, 1, 'The non-YouTube source stays outside the YouTube API route');

console.log('GOAL96 YouTubeThumbnailRuntime/0.1: fail-closed and identity assertions passed (positive path is SIMULATED_ONLY)');
