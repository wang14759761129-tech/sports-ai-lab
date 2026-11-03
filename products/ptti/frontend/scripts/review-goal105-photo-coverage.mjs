// Read-only internal review of the existing cover-review contract. Never exports media grants.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {resolveEditorialMatchPhoto} from '../src/thumbnailPermission.mjs';
import {youtubeThumbnailSourceId} from '../src/youtubeThumbnailRuntime.mjs';
export const coveragePath=new URL('../../data/professional/cover_review/goal105-cover-review.v0.1.json',import.meta.url);
export function validatePhotoCoverage(review,catalog){
  assert.equal(review?.schema_version,'ptti.match-cover-review/0.1','Unsupported review version');
  assert.equal(review?.scope,'INTERNAL_ONLY_GOAL105_REMAINING_EIGHT_REGISTERED_SOURCES');
  assert.equal(review.records.length,8);
  const sources=new Set(),photos=new Set();let exact=0;
  for(const row of review.records){
    const source=catalog.videos.find(v=>v.video_id===row.video_id&&v.provider===row.provider);
    assert.ok(source,'Unknown source identity');
    const id=source.provider==='YOUTUBE_OFFICIAL'?youtubeThumbnailSourceId(source):source.source_key;
    assert.equal(row.source_id,id);assert.equal(row.match_id,source.match_id??null);
    assert.equal(row.watch_url,source.source_url);assert.equal(row.catalog_event,source.event_name);
    assert.equal(row.catalog_title,source.title);assert.equal(row.catalog_round,source.round_label??null);
    assert.deepEqual(row.athlete_names,source.athlete_names);
    assert.equal(row.admission_status,'INTERNAL_ONLY');assert.equal(row.actual_photo_display_this_sprint,'NOT_TESTED');
    assert.ok(!sources.has(id),'Duplicate source');sources.add(id);
    const photo=row.alternative_match_photo;if(!photo)continue;
    assert.ok(!photos.has(photo.photo_id),'Photo cannot be reused across matches without a separate review');photos.add(photo.photo_id);
    assert.equal(photo.source_id,id);assert.equal(photo.intended_match_id,row.match_id);
    assert.equal(photo.source_page_url,`https://www.flickr.com/photos/${photo.publisher_account}/${photo.photo_id}/`);
    assert.equal(photo.publisher_account_id,({wttglobal:'194208068@N05',ittfworld:'56089523@N02'})[photo.publisher_account],'Publisher account must be the reviewed official identity');
    const imageURL=new URL(photo.source_file_url);
    assert.equal(imageURL.protocol,'https:');assert.equal(imageURL.hostname,'live.staticflickr.com');
    assert.equal(imageURL.username+imageURL.password,'');
    assert.ok(imageURL.pathname.includes('/'+photo.photo_id+'_'),'Image URL must reference the exact reviewed photo ID');
    assert.equal(photo.flickr_license_id,0,'Selected observations report All Rights Reserved, not an open licence');
    assert.equal(photo.media_sha256,null,'No image-byte hash was obtained; page hash must not substitute');
    assert.equal(photo.image_bytes_obtained,false);assert.equal(photo.pixel_identity_review,'NOT_TESTED');
    for(const field of ['display_permission','distribution_permission','windows_packaging_permission'])assert.equal(photo[field],'NEEDS_PERMISSION_FOR_DISTRIBUTION');
    for(const field of ['web_display_permission','remote_display_permission','crop_permission','modification_permission','commercial_use_permission','local_storage_permission'])assert.equal(photo[field],'UNKNOWN');
    assert.equal(photo.written_permission,null);
    assert.equal(resolveEditorialMatchPhoto({...source,editorial_match_photo:photo}),null,'Research cannot authorize runtime display');
    if(photo.source_caption_match_status==='CONFIRMED_FROM_PUBLISHER_CAPTION'){
      assert.equal(photo.match_relationship,'PUBLISHER_CAPTION_EXACT_MATCH');
      assert.ok(photo.caption_identity_terms?.length>=5,'Need reviewed event, round, opponents and date terms');
      for(const term of photo.caption_identity_terms)assert.ok(photo.publisher_description?.includes(term),'Caption does not establish the reviewed match identity');
      exact++;
    }else assert.ok(['EVENT_PLAYER_DATE_CANDIDATE','PLAYER_DATE_ONLY_EVENT_PENDING'].includes(photo.match_relationship));
  }
  const summary={reviewed_sources:sources.size,specific_photo_candidates:photos.size,publisher_caption_exact_match:exact,identity_pending_candidates:photos.size-exact,distribution_approved:0,new_photos_displayed:0};
  assert.deepEqual(review.summary,summary,'Summary must reflect reviewed records');
  return {status:'PASS',scope:'INTERNAL_REVIEW_ONLY',...summary};
}
if(process.argv[1]&&pathToFileURL(resolve(process.argv[1])).href===import.meta.url){
  const review=JSON.parse(readFileSync(coveragePath,'utf8'));
  const catalog=JSON.parse(readFileSync(new URL('../../data/professional/official_video_sources.json',import.meta.url),'utf8'));
  console.log(JSON.stringify(validatePhotoCoverage(review,catalog),null,2));
}
