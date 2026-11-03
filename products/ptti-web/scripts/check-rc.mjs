import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createShareText } from '../src/match-share.mjs';
import { consumeReadonlyProjection } from '../src/readonly-catalog.mjs';
const copy = { players: ['A & <script>', 'B'], event: 'Event', meta: 'MS', route: 'Official event page', status: 'NOT_TESTED', checked: '2026-10-12', footer: 'Not a video', verified: false };
assert(createShareText({ ...copy, pageUrl: 'http://127.0.0.1:4174/?match=x', officialUrl: 'https://official.example/video', scope: 'External visual only', localHint: 'Local link only' }).includes('Local link only'));
const payload = { contract_version: 'ptti.match-media/0.2', local_video_assets: [], timeline_mappings: [], matches: [{ match_id: 'known', identity_status: 'UNKNOWN', event: { event_id: null, name: 'Sample', year: 2023 }, participants: [], participant_names_unassigned: ['A','B'] }], video_sources: [{ source_id: 'source', match_id: 'known', match_link_status: 'UNKNOWN', resource_kind: 'ARTICLE', rights: { metadata_listing: 'UNKNOWN', external_viewing: 'UNKNOWN' }, evidence: { external_video_page: { status: 'EXTERNAL_VIDEO_PAGE_VISUAL_PASS' }, embed_playback: { status: 'NOT_TESTED' }, desktop_native_playback: { status: 'NOT_TESTED' } }, territory: { status: 'UNKNOWN' } }] };
const original = JSON.stringify(payload);
assert.equal(consumeReadonlyProjection(payload).matches.length, 0);
assert.throws(() => consumeReadonlyProjection(payload, { view: 'review' }));
const review = consumeReadonlyProjection(payload, { view: 'review', localReview: true });
assert.equal(review.matches[0].sources[0].kind, 'ARTICLE');
assert.equal(review.matches[0].sources[0].evidence.desktop_native_playback.status, 'NOT_TESTED');
review.matches[0].sources[0].rights.metadata_listing = 'ALLOWED';
assert.equal(JSON.stringify(payload), original);
assert.throws(() => consumeReadonlyProjection({ ...payload, contract_version: 'ptti.match-media/0.1' }));
assert.throws(() => consumeReadonlyProjection({ ...payload, local_video_assets: [{}] }));
assert.throws(() => consumeReadonlyProjection({ ...payload, video_sources: [{ ...payload.video_sources[0], match_id: 'missing' }] }));
const data = JSON.parse(await readFile(new URL('./fixtures/cinema-legacy.json', import.meta.url)));
assert.equal(data.length, 4);
console.log('RC unit PASS: share text with explicit scope, cautious status, immutable v0.2 seam, public UNKNOWN blocked, explicit local review, no evidence promotion. Synthetic test input is not a real producer sample.');

const projectionIndex = process.argv.indexOf('--projection');
if (projectionIndex !== -1) {
  if (!process.argv.includes('--local-review')) throw new Error('Local sample inspection requires --local-review');
  const sample = JSON.parse(await readFile(process.argv[projectionIndex + 1], 'utf8'));
  const before = JSON.stringify(sample);
  const local = consumeReadonlyProjection(sample, { view: 'review', localReview: true });
  const publicView = consumeReadonlyProjection(sample);
  assert.equal(local.matches.length, 4, 'current four-match review snapshot');
  assert.equal(publicView.matches.length, 0, 'current UNKNOWN rights cannot reach public catalog');
  for (const match of local.matches) for (const source of match.sources) {
    assert.equal(source.rights.metadata_listing, 'UNKNOWN');
    assert.equal(source.evidence.desktop_native_playback.status, 'NOT_TESTED');
  }
  assert.equal(JSON.stringify(sample), before);
  console.log('Local producer snapshot PASS: four review matches, zero public, no mutation or native promotion.');
}
