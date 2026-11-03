import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolveEditorialMatchPhoto,approvedOfficialThumbnail} from '../src/thumbnailPermission.mjs';

const catalog=JSON.parse(readFileSync('../data/professional/official_video_sources.json','utf8'));
const review=JSON.parse(readFileSync('../data/professional/cover_review/goal104-cover-review.v0.1.json','utf8'));
const manifest=JSON.parse(readFileSync('../data/professional/cover_review/public-match-cover-manifest.v0.2.json','utf8'));
const source=catalog.videos.find(v=>v.video_id==='ekfCZiIEYi0');
const photo=source.editorial_match_photo;
const now=Date.parse(photo.reviewed_at)+1000;
assert.equal(review.records.length,9);
assert.equal(new Set(review.records.map(r=>r.source_id)).size,9);
assert.equal(review.approved_original_thumbnails,0);
assert.equal(manifest.assets.length,0,'No actual photograph has distribution permission');
assert.equal(photo.distribution_permission,'NEEDS_PERMISSION_FOR_DISTRIBUTION');
assert.equal(resolveEditorialMatchPhoto(source,now),null,'Real photo remains fail-closed');
// SIMULATED_ONLY permission contract; no written WTT grant has been received.
const approvedPhoto={...photo,display_permission:'APPROVED_FOR_SPECIFIC_DISPLAY',
 distribution_permission:'ALLOWED',distribution_targets:['WEB','WINDOWS_DESKTOP'],permission_basis:'WTT_WRITTEN_PERMISSION',
 written_permission:{evidence_id:'SIMULATED_ONLY_PERMISSION_FIXTURE',evidence_sha256:'0'.repeat(64),local_packaging:'ALLOWED',targets:['WEB','WINDOWS_DESKTOP'],valid_from:photo.reviewed_at,valid_until:photo.review_expires_at}};
const approvedSource={...source,editorial_match_photo:approvedPhoto};
assert.deepEqual(resolveEditorialMatchPhoto(approvedSource,now),approvedPhoto);
assert.equal(approvedOfficialThumbnail(source),false,'Editorial photo must not authorize historical YouTube CDN thumbnail');
const bytes=readFileSync('../docs/goal104-evidence/restricted-media/wtt-53034902256.jpg');
assert.equal(createHash('sha256').update(bytes).digest('hex'),photo.media_sha256,'Published rendition stays byte-identical to the reviewed photograph');
assert.equal(bytes.readUInt16BE(0),0xffd8,'Asset is actual JPEG bytes');
let dimensions;
for(let i=2;i<bytes.length;){
  assert.equal(bytes[i],0xff);const marker=bytes[i+1];i+=2;
  if(marker===0xda||marker===0xd9)break;
  const size=bytes.readUInt16BE(i);
  if([0xc0,0xc1,0xc2].includes(marker)){dimensions={width:bytes.readUInt16BE(i+5),height:bytes.readUInt16BE(i+3)};break;}
  i+=size;
}
assert.deepEqual(dimensions,photo.image_dimensions);
for(const patch of [
  {video_id:'0QgbtsBWZhk'}, {source_url:'https://example.com/other'},
  {event_name:'Another event'}, {round_label:'半决赛'}, {discipline:'WS'},
  {match_id:'pro:unverified'}, {athlete_names:['Another player']},
  {video_source:{source_id:'another'}},
  {source_key:'YOUTUBE:another'}, {video_source:{provider:'BILIBILI'}},
])assert.equal(resolveEditorialMatchPhoto({...approvedSource,...patch},now),null,'Source identity changes fail closed');
for(const patch of [
  {display_permission:'UNKNOWN'}, {purpose:'PROMOTIONAL_HERO'}, {permission_basis:'PUBLIC_PAGE'},
  {match_relationship:'ATHLETE_REFERENCE_ONLY'}, {attribution:''}, {binding:null},
  {display_url:'https://i.ytimg.com/vi/ekfCZiIEYi0/hqdefault.jpg'},
  {photo_page_url:'https://www.flickr.com/photos/someone/53034902256/'},
  {media_sha256:'PENDING'}, {crop_permission:'ALLOWED'}, {promotional_use:'ALLOWED'},
  {review_expires_at:'invalid'}, {schema_version:'ptti.editorial-match-photo/2.0'},
])assert.equal(resolveEditorialMatchPhoto({...approvedSource,editorial_match_photo:{...approvedPhoto,...patch}},now),null,'Permission, source and purpose defects fail closed');
assert.equal(resolveEditorialMatchPhoto(approvedSource,Date.parse(photo.review_expires_at)),null,'Expired review returns to fallback');
assert.equal(resolveEditorialMatchPhoto(approvedSource,Date.parse(photo.reviewed_at)-1),null,'Future review cannot grant permission');
assert.equal(resolveEditorialMatchPhoto(approvedSource,NaN),null,'Unknown clock cannot grant permission');
for(const unknown of [null,{},...catalog.videos.filter(v=>v!==source)])assert.equal(resolveEditorialMatchPhoto(unknown,now),null);
const feed=readFileSync('src/VideoFeed.tsx','utf8'),css=readFileSync('src/video-feed.css','utf8');
assert.match(feed,/feed-photo-credit[^\n]+v\.thumbnailCredit\.url/,'Credit links to the photo page outside the primary watch link');
assert.match(css,/\.feed-cover--editorial-photo img\{object-fit:contain/,'Full-frame photo and publisher watermark cannot be cropped');
assert.equal(source.local_analysis_allowed,false);
assert.equal(source.rights,'REFERENCE_ONLY_NOT_LICENSE_GRANTED','Editorial still-photo permission does not license the video');
console.log('GOAL104-R2: original photo/evidence preserved; actual distribution denied; SIMULATED_ONLY grant contract and identity negatives PASS');
