// Offline evidence checks only. No image requests and no permission mutation.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {approvedOfficialThumbnail} from '../../frontend/src/thumbnailPermission.mjs';
const observation=JSON.parse(readFileSync(new URL('../../build/reports/goal109/0Q-oembed-observation.json',import.meta.url),'utf8'));
const bytes=readFileSync(new URL('../../build/reports/goal109/0Q-oembed-response.json',import.meta.url));
const response=JSON.parse(bytes);
const catalog=JSON.parse(readFileSync(new URL('../../data/professional/official_video_sources.json',import.meta.url),'utf8'));
const first=catalog.videos.find(row=>row.video_id==='0QgbtsBWZhk');
function verifyIdentity(source, data){
 assert.equal(data.type,'video');assert.equal(data.version,'1.0');
 assert.equal(data.provider_name,'YouTube');assert.equal(data.provider_url,'https://www.youtube.com/');
 assert.equal(data.author_url,source.channel_url);assert.equal(data.author_name,source.channel);
 assert.equal(data.title,source.title);
 assert.equal(new URL(source.source_url).searchParams.get('v'),source.video_id);
 assert.equal(new URL(data.thumbnail_url).protocol,'https:');
 assert.equal(new URL(data.thumbnail_url).hostname,'i.ytimg.com');
 assert.equal(new URL(data.thumbnail_url).pathname,`/vi/${source.video_id}/hqdefault.jpg`);
 assert.ok(data.html.includes(`/embed/${source.video_id}?`));
 assert.equal(data.thumbnail_width,480);assert.equal(data.thumbnail_height,360);
}
assert.equal(createHash('sha256').update(bytes).digest('hex'),observation.response_sha256);
assert.deepEqual(response,observation.response);
assert.equal(observation.http_status,200);
assert.equal(observation.image_requested,false);
assert.equal(observation.standalone_thumbnail_admission,'NOT_CLEARED');
verifyIdentity(first,response);
for(const patch of [
 {title:'Different match'}, {author_url:'https://www.youtube.com/@other'},
 {provider_name:'Other'}, {type:'photo'},
 {thumbnail_url:'https://i.ytimg.com/vi/another0000/hqdefault.jpg'},
 {thumbnail_url:'https://not-youtube.example/vi/0QgbtsBWZhk/hqdefault.jpg'},
 {html:'<iframe src="https://www.youtube.com/embed/another0000?feature=oembed"></iframe>'},
])assert.throws(()=>verifyIdentity(first,{...response,...patch}));
const youtube=catalog.videos.filter(row=>row.provider==='YOUTUBE_OFFICIAL');
assert.equal(youtube.length,8);
for(const source of youtube){
 assert.equal(approvedOfficialThumbnail(source),false,'identity/URL existence must not grant permission');
 assert.equal(new URL(source.source_url).searchParams.get('v'),source.video_id);
}
assert.equal(approvedOfficialThumbnail({...first,thumbnail_url:response.thumbnail_url}),false,'a genuine oEmbed response does not change the existing permission gate');
assert.equal(catalog.videos.filter(row=>row.provider==='BILIBILI').length,1);
console.log('PASS: real response SHA/shape/identity; 7 identity negatives; 8 unchanged thumbnail gates; Bilibili separate. No image/render/playback PASS implied.');
