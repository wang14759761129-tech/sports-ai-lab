import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import {projectSqliteFavorites} from '../src/userCollectionProjection.mjs';
import {mediaSourceToFoundation, validateFoundationBundle} from '../src/foundationContract.mjs';

const examples = JSON.parse(readFileSync(new URL('../../contracts/foundation-v0.1.examples.json', import.meta.url), 'utf8'));
const match = structuredClone(examples.find(record => record.kind === 'MatchIdentity'));
const source = (id = '0QgbtsBWZhk', overrides = {}) => mediaSourceToFoundation({
  video_id: id, provider: 'YOUTUBE_OFFICIAL', source_key: `YOUTUBE:${id}`,
  source_url: `https://www.youtube.com/watch?v=${id}`, match_id: match.identity.match_id,
  ...overrides,
}, {recordId: `record:source:${id}:${overrides.source_key ?? ''}`});
const project = (favoriteKeys, records = [match, source()], extra = {}) => projectSqliteFavorites({favoriteKeys, records, recordId:'record:favorites', collectionId:'collection:sqlite-favorites', ...extra});
const freeze = value => {if (value && typeof value === 'object') {Object.values(value).forEach(freeze);Object.freeze(value)}return value};

test('exact match key produces a valid read-only SQLite-owned collection', () => {
  const result = project([`match:${match.identity.match_id}`]);
  assert.equal(result.collection.storage_owner, 'EXISTING_SQLITE_FAVORITES');
  assert.equal(result.collection.collection_kind, 'FAVORITES');
  assert.deepEqual(result.collection.item_refs, [{record_kind:'MatchIdentity',record_id:match.record_id}]);
  assert.equal(validateFoundationBundle([match,source(),result.collection]),true);
  assert.equal(result.write_policy,'READ_ONLY_PROJECTION');
});
test('legacy official video key resolves registered provider identity, not a title or inferred match', () => {
  const result=project(['official:0QgbtsBWZhk']);
  assert.equal(result.resolved[0].target.record_kind,'MediaSource');
  assert.equal(result.collection.item_refs.some(ref=>ref.record_kind==='MatchIdentity'),false);
});
test('an exact registered source key resolves without rewriting the original key', () => {
  const result=project(['YOUTUBE:0QgbtsBWZhk']);
  assert.equal(result.resolved[0].favorite_key,'YOUTUBE:0QgbtsBWZhk');
  assert.equal(result.resolved[0].target.record_id,source().record_id);
});
test('Bilibili source identity remains independent from YouTube', () => {
  const bili=mediaSourceToFoundation({video_id:'BV1nb421H7jB',provider:'BILIBILI_OFFICIAL',source_key:'BILIBILI:BV1nb421H7jB',source_url:'https://www.bilibili.com/video/BV1nb421H7jB',match_id:null},{recordId:'record:bili'});
  const result=project(['official:BV1nb421H7jB'],[bili]);
  assert.deepEqual(result.collection.item_refs,[{record_kind:'MediaSource',record_id:'record:bili'}]);
});
test('missing and temporarily unavailable favorites stay in the original snapshot', () => {
  const unavailable={...source(),source_status:'UNAVAILABLE'};
  const keys=['official:missing','match:historical-missing','local:unbound-file', 'old unknown key'];
  const result=project(keys,[match,unavailable]);
  assert.deepEqual(result.input_keys,keys);
  assert.equal(result.unresolved.length,4);
  assert.deepEqual(result.collection.item_refs,[]);
  const known=project(['official:0QgbtsBWZhk'],[match,unavailable]);
  assert.equal(known.resolved.length,1,'unavailable playback does not delete exact saved source identity');
});
test('duplicate saved keys and aliases deduplicate refs but preserve input evidence', () => {
  const keys=['official:0QgbtsBWZhk','official:0QgbtsBWZhk','YOUTUBE:0QgbtsBWZhk'];
  const result=project(keys);assert.deepEqual(result.input_keys,keys);
  assert.equal(result.collection.item_refs.length,1);assert.equal(result.resolved.length,2);
});
test('ambiguous provider-video aliases do not select the first match', () => {
  const a=source(),b=source('0QgbtsBWZhk',{source_key:'reviewed:other-source'});
  const result=project(['official:0QgbtsBWZhk'],[match,a,b]);
  assert.deepEqual(result.unresolved,[{favorite_key:'official:0QgbtsBWZhk',reason:'AMBIGUOUS_TARGET'}]);
  assert.equal(result.collection.item_refs.length,0);
});
test('matching display titles and filename tuples never bind missing identities', () => {
  const result=project(['official:Same title','local:file.mp4','Same title']);
  assert.equal(result.resolved.length,0);assert.equal(result.unresolved.length,3);
});
test('input objects and stored snapshots are never mutated, including repeated calls', () => {
  const keys=freeze(['official:0QgbtsBWZhk','legacy:gone']);const records=freeze([match,source()]);
  const before=JSON.stringify({keys,records});
  for(let n=0;n<3;n++){const result=project(keys,records);result.input_keys.push('only-result');result.collection.item_refs.length=0;}
  assert.equal(JSON.stringify({keys,records}),before);
});
test('invalid snapshot, duplicate record identities and broken links fail closed', () => {
  assert.throws(()=>project([42]),/INVALID_FAVORITE_SNAPSHOT/);
  assert.throws(()=>project(['x'],[match,match]),/DUPLICATE/);
  assert.throws(()=>project(['x'],[source()]),/UNKNOWN_MATCH_REFERENCE/);
  assert.throws(()=>project(['x'],[match],{recordId:match.record_id}),/COLLECTION_RECORD_ID_CONFLICT/);
});
test('empty and unfamiliar historical strings are preserved rather than silently normalized', () => {
  const keys=['',' match:wrong ','match:'];const result=project(keys);
  assert.deepEqual(result.input_keys,keys);assert.equal(result.unresolved.length,3);
});
test('collection projection does not depend on fetch, storage, or database write helpers', () => {
  const text=readFileSync(new URL('../src/userCollectionProjection.mjs',import.meta.url),'utf8');
  assert.doesNotMatch(text,/\b(?:fetch|localStorage|persistFavoriteKeys)\s*\(/);
  assert.doesNotMatch(text,/\b(?:INSERT|DELETE|UPDATE)\s/i);
});

test('conflicting provider-prefixed source identity never binds an official favorite', () => {
 const wrong=structuredClone(source());wrong.identity.source_id='BILIBILI:BV1nb421H7jB';
 const result=project(['official:0QgbtsBWZhk'],[match,wrong]);assert.equal(result.resolved.length,0);assert.equal(result.unresolved[0].reason,'TARGET_NOT_FOUND');
});
