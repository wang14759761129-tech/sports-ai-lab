import assert from 'node:assert/strict';
import {createYoutubeThumbnailRuntime, classifyYoutubeApiFreshness} from '../src/youtubeThumbnailRuntime.mjs';
import {readFile} from 'node:fs/promises';
import {
  chooseApiThumbnail,
  classifyMetadataFreshness,
  keepFreshMetadataAfterRefreshFailure,
  mapYoutubeVideosList,
  resolveMetadataCoverState,
} from '../src/youtubeVideoMetadata.mjs';

const root = new URL('../../', import.meta.url);
const readJson = async path => JSON.parse(await readFile(new URL(path, root), 'utf8'));
const catalog = await readJson('data/professional/official_video_sources.json');
const mock = await readJson('frontend/scripts/youtube-videos-list-8.mock.json');
const schema = await readJson('data/schemas/youtube-video-metadata-poc-0.1.schema.json');
const moduleSource = await readFile(new URL('../src/youtubeVideoMetadata.mjs', import.meta.url), 'utf8');
const now = Date.parse('2026-10-27T00:00:00Z');
const rows = mapYoutubeVideosList(catalog.videos, mock, new Date(now).toISOString(), {dataOrigin: 'MOCK'});
const youtubeCatalog = catalog.videos.filter(row => row.provider === 'YOUTUBE_OFFICIAL');

assert.equal(mock.fixture_type, 'MOCK');
assert.match(mock.warning, /SIMULATED_ONLY/);
assert.equal(rows.length, 8);
assert.deepEqual(rows.map(row => row.video_id).sort(), mock.items.map(item => item.id).sort());
assert.ok(rows.every(row => row.identity_status === 'VIDEO_ID_MATCH'));
assert.ok(rows.every(row => row.display_state === 'NO_IMAGE_FALLBACK'));
assert.ok(rows.every(row => row.channel_identity_status === 'UNVERIFIED'));
assert.ok(rows.every(row => row.data_origin === 'MOCK'));
assert.ok(rows.every(row => row.embedding_evidence_status === 'API_FIELD_ONLY_NOT_PERMISSION'));
assert.deepEqual(Object.keys(schema.properties).sort(), schema.required.slice().sort());
assert.ok(rows.every(row => Object.keys(row).sort().join('|') === schema.required.slice().sort().join('|')));
assert.doesNotMatch(moduleSource, /localStorage|indexedDB|favoritePersistence|momentStore|proLabStore/i);

for (const row of rows) {
  const source = youtubeCatalog.find(item => item.video_id === row.video_id);
  assert.equal(row.source_id, `video-source:youtube:${source.video_id}`);
  assert.equal(row.match_id, source.match_id ?? null, 'only the catalog match binding is carried through');
  assert.equal(row.source_url, source.source_url, 'watch URL remains the catalog value');
  assert.equal(new URL(source.thumbnail_url).pathname, `/vi/${source.video_id}/hqdefault.jpg`, 'historical ID correspondence only; not display permission');
  assert.equal(row.title, mock.items.find(item => item.id === row.video_id).snippet.title);
  assert.equal(row.channel_id, mock.items.find(item => item.id === row.video_id).snippet.channelId);
  assert.equal(row.duration, mock.items.find(item => item.id === row.video_id).contentDetails.duration);
  assert.equal(row.privacy_status, 'public');
  assert.equal(row.embeddable, mock.items.find(item => item.id === row.video_id).status.embeddable);
  assert.equal(row.embedding_evidence_status, 'API_FIELD_ONLY_NOT_PERMISSION');
  const selected = chooseApiThumbnail(row.thumbnails, 480);
  assert.equal(selected.url, `https://mock.invalid/${row.video_id}/high.jpg`);
  assert.equal(selected.width, 480);
  assert.equal(selected.height, 360);
  assert.equal(selected.aspect_ratio_is_16_9, false, '4:3 is reported, never cropped');
  const cover = resolveMetadataCoverState({metadata: row, source, manifest: {assets: []}, mode: 'INTERNAL_FOUNDER_REVIEW', now});
  assert.deepEqual(cover, {state: 'NO_IMAGE_FALLBACK', url: null, source_id: row.source_id});
  assert.equal(resolveMetadataCoverState({
    metadata: {...row, display_review: 'APPROVED_FOR_SPECIFIC_DISPLAY'},
    source,
    manifest: {assets: []},
    mode: 'INTERNAL_FOUNDER_REVIEW',
    now,
  }).state, 'NO_IMAGE_FALLBACK', 'MOCK data cannot be promoted by adding a review label');
  assert.equal(resolveMetadataCoverState({
    metadata: row,
    source,
    manifest: {assets: [{source_id: row.source_id, video_id: row.video_id, source_url: source.source_url,
      status: 'NEEDS_PERMISSION_FOR_DISTRIBUTION', display_url: '/media/editorial/unreviewed.jpg'}]},
    now,
  }).state, 'NO_IMAGE_FALLBACK', 'withheld/permission-incomplete media cannot pass the asset gate');
}

const missing = mapYoutubeVideosList(youtubeCatalog, {items: mock.items.filter(x => x.id !== '0QgbtsBWZhk')}, new Date(now).toISOString(), {dataOrigin: 'MOCK'});
assert.equal(missing.find(row => row.video_id === '0QgbtsBWZhk').identity_status, 'NOT_RETURNED');
assert.equal(missing.find(row => row.video_id === '0QgbtsBWZhk').title, null);

const mismatched = mapYoutubeVideosList(youtubeCatalog, {items: [...mock.items, {...mock.items[0]}]}, new Date(now).toISOString(), {dataOrigin: 'MOCK'});
assert.equal(mismatched.find(row => row.video_id === mock.items[0].id).identity_status, 'DUPLICATE_API_ID');

const fresh = rows[0];
assert.equal(classifyMetadataFreshness(fresh, now), 'FRESH');
assert.equal(keepFreshMetadataAfterRefreshFailure(fresh, now), fresh);
assert.equal(classifyMetadataFreshness(fresh, now + 30 * 24 * 60 * 60 * 1000), 'STALE');
assert.equal(keepFreshMetadataAfterRefreshFailure(fresh, now + 30 * 24 * 60 * 60 * 1000), null);
assert.equal(classifyMetadataFreshness({...fresh, fetched_at: '2099-01-01T00:00:00Z'}, now), 'INVALID');

const emptyCoverManifest = await readJson('data/professional/cover_review/public-match-cover-manifest.v0.2.json');
assert.equal(emptyCoverManifest.assets.length, 0);
for (const row of rows) {
  const source = youtubeCatalog.find(item => item.video_id === row.video_id);
  assert.equal(resolveMetadataCoverState({metadata: row, source, manifest: emptyCoverManifest, now}).state, 'NO_IMAGE_FALLBACK');
}

// Expiry helpers are pure; no user store APIs are present in this adapter.
assert.equal(keepFreshMetadataAfterRefreshFailure(fresh, now + 31 * 24 * 60 * 60 * 1000), null);
console.log('PASS: 8 MOCK mappings, output schema shape, exact IDs/URLs, thumbnail passthrough, expiry, fail-closed states, no user-store coupling');

// Reconciliation negatives: response field types must match the shared raw contract.
for (const change of [
  item => {item.status.embeddable = 'true';},
  item => {item.contentDetails.duration = 123;},
  item => {item.snippet.publishedAt = 'not-a-date';},
  item => {item.snippet.thumbnails.high.width = -1;},
  item => {item.status.privacyStatus = 'unknown';},
]) {
  const broken = structuredClone(mock);
  change(broken.items[0]);
  assert.throws(() => mapYoutubeVideosList(youtubeCatalog, broken, new Date(now).toISOString()), /contract/);
}
for (const offset of [-1, 0, 1]) {
  const edge = now + 30 * 24 * 60 * 60 * 1000 + offset;
  assert.equal(classifyMetadataFreshness(fresh, edge), classifyYoutubeApiFreshness(fresh.fetched_at, fresh.refresh_or_delete_by, edge));
}
assert.equal(classifyMetadataFreshness({...fresh, refresh_or_delete_by:'bad'}, now), 'INVALID');
assert.equal(classifyMetadataFreshness({...fresh, refresh_or_delete_by:new Date(now+31*24*60*60*1000).toISOString()}, now), 'INVALID');

// SIMULATED_ONLY canonical runtime: these are test approvals, never catalog grants.
const sample = mock.items[0];
const sampleSource = {...youtubeCatalog.find(x=>x.video_id===sample.id), provenance:{verified_youtube_channel_id:sample.snippet.channelId}};
const sampleMetadata = mapYoutubeVideosList([sampleSource], {items:[sample]}, new Date(now).toISOString(), {dataOrigin:'LIVE_API_TRANSPORT'})[0];
const sampleRuntime = createYoutubeThumbnailRuntime(sampleSource, {items:[sample]}, {api_client_review:'APPROVED',click_target:'YOUTUBE_APP_OR_SYSTEM_BROWSER'}, now);
const resolve = (metadata=sampleMetadata, runtime=sampleRuntime, mode='INTERNAL_FOUNDER_REVIEW') => resolveMetadataCoverState({metadata,source:sampleSource,manifest:{assets:[]},runtime,mode,now});
assert.equal(resolve().state,'YOUTUBE_API_THUMBNAIL','existing reviewed runtime is the sole API image gate');
assert.equal(resolve({...sampleMetadata,data_origin:'MOCK'}).state,'NO_IMAGE_FALLBACK');
assert.equal(resolve(sampleMetadata,null).state,'NO_IMAGE_FALLBACK','a review label without canonical runtime cannot grant display');
assert.equal(resolve(sampleMetadata,sampleRuntime,'DISTRIBUTABLE').state,'NO_IMAGE_FALLBACK');
assert.equal(resolve({...sampleMetadata,channel_id:'wrong'}).state,'NO_IMAGE_FALLBACK');
assert.equal(resolve({...sampleMetadata,thumbnails:{}}).state,'NO_IMAGE_FALLBACK');
assert.equal(resolve(sampleMetadata,{...sampleRuntime,channel_id:'wrong'}).state,'NO_IMAGE_FALLBACK');
assert.equal(sampleRuntime.embed_permission,'UNKNOWN','API embeddable does not promote embed rights');


assert.equal(resolve({...sampleMetadata,privacy_status:'private'}).state,'NO_IMAGE_FALLBACK');
assert.equal(resolve({...sampleMetadata,channel_identity_status:'UNVERIFIED'}).state,'NO_IMAGE_FALLBACK');
assert.equal(classifyMetadataFreshness({...fresh,fetched_at:'2026-02-31T00:00:00Z'},now),'INVALID');
assert.equal(classifyMetadataFreshness({...fresh,fetched_at:'2026-10-27'},now),'INVALID');
assert.equal(mapYoutubeVideosList([{...sampleSource,source_url:sampleSource.source_url+'#wrong'}],{items:[sample]},new Date(now).toISOString())[0].identity_status,'CATALOG_ID_OR_URL_INVALID');

const invalidCatalogId = mapYoutubeVideosList([{...sampleSource,video_id:12345678901}],{items:[sample]},new Date(now).toISOString())[0];
assert.equal(invalidCatalogId.video_id,null);
assert.equal(invalidCatalogId.identity_status,'CATALOG_ID_OR_URL_INVALID');
console.log('PASS: shared runtime gate, transport field negatives, expiry boundaries; mock/forged review cannot grant display');
