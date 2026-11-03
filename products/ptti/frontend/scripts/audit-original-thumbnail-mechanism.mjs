// Offline source audit only. Does not fetch images or grant display permission.
import {execFileSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {approvedOfficialThumbnail} from '../src/thumbnailPermission.mjs';

const baseline = '5cc753886b112305736fcc14ea77b37662726c9f';
const path = 'products/ptti/data/professional/official_video_sources.json';
const original = JSON.parse(execFileSync('git', ['show', `${baseline}:${path}`], {encoding:'utf8'})).videos;
const current = JSON.parse(readFileSync(new URL('../../data/professional/official_video_sources.json', import.meta.url), 'utf8')).videos;
assert.equal(original.length, 9);
assert.equal(original.filter(s => s.provider === 'YOUTUBE_OFFICIAL').length, 8);
const ids = new Set();
const rows = original.map(source => {
  assert.ok(!ids.has(source.video_id), 'duplicate video identity');
  ids.add(source.video_id);
  const matches = current.filter(s => s.provider === source.provider && s.video_id === source.video_id);
  assert.equal(matches.length, 1, 'current source identity must match exactly');
  const live = matches[0];
  assert.equal(live.source_url, source.source_url, 'registered watch URL changed');
  const youtube = source.provider === 'YOUTUBE_OFFICIAL';
  if (youtube) {
    const watch = new URL(source.source_url);
    assert.equal(watch.protocol, 'https:');
    assert.equal(watch.hostname, 'www.youtube.com');
    assert.equal(watch.searchParams.get('v'), source.video_id);
    assert.equal(source.thumbnail_url, `https://i.ytimg.com/vi/${source.video_id}/hqdefault.jpg`);
  } else {
    assert.equal(source.provider, 'BILIBILI');
    assert.equal(source.thumbnail_url, '');
  }
  return {
    provider: source.provider, video_id: source.video_id,
    source_key: source.source_key ?? null,
    registered_watch_url: source.source_url,
    historical_remote_image_url: source.thumbnail_url || null,
    historical_mode: youtube ? 'REMOTE_IMG_TAG' : 'MISSING_IMAGE_FALLBACK',
    current_direct_image_permission: approvedOfficialThumbnail(live) ? 'ALLOWED' : 'NOT_CLEARED',
    recorded_embed_permission: live.video_source?.embed_permission ?? 'UNKNOWN',
    recorded_embed_type: live.video_source?.playback_type ?? 'UNKNOWN',
    current_session_cover_render: 'NOT_TESTED',
    current_session_watch_click: 'NOT_TESTED',
    current_session_playback: 'NOT_TESTED',
  };
});
console.log(JSON.stringify({
  scope: 'INTERNAL_READ_ONLY_SOURCE_AUDIT_NOT_RUNTIME_MEDIA_MANIFEST',
  baseline, rows,
  checks: 'PASS: 9 exact source mappings; 8 historical CDN identities; 1 empty Bilibili image',
  browser_attempt: {status:'BLOCKED', reason:'CUA initialization: failed to write kernel assets (os error 3); page not opened'},
  granted_permissions: [],
}, null, 2));
