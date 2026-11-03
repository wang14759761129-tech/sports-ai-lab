import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {loadMediaManifest,verifyMediaTree,mediaDistributionPlugin} from './mediaDistributionGate.mjs';
import {approvedOfficialThumbnail,resolveEditorialMatchPhoto,resolveInternalFounderQaThumbnail} from '../src/thumbnailPermission.mjs';
import {reviewedOfficialSource} from '../src/reviewedOfficialEmbed.mjs';
const manifest=loadMediaManifest(); assert.equal(manifest.assets.length,0);
verifyMediaTree('public',{requireManifest:false});
const folder=mkdtempSync(join(tmpdir(),'r4-02-media-'));
try {
 assert.throws(()=>verifyMediaTree(join(folder,'missing'),{requireManifest:false}),/artifact directory missing/);
 const out=join(folder,'out');mkdirSync(out);writeFileSync(join(out,'unapproved.jpg'),'not authorized');
 assert.throws(()=>verifyMediaTree(out,{requireManifest:false}),/unlisted or altered image/);
 assert.throws(()=>mediaDistributionPlugin().configResolved({root:folder,build:{outDir:'dist'},command:'build',mode:'founder-internal-qa'}),/INTERNAL QA/);
 const source={video_id:'0QgbtsBWZhk',provider:'YOUTUBE_OFFICIAL',playback_status:'EMBED_BLOCKED',thumbnail_url:'https://i.ytimg.com/vi/0QgbtsBWZhk/hqdefault.jpg'};
 assert.equal(approvedOfficialThumbnail(source),false);assert.equal(resolveEditorialMatchPhoto(source),null);
 assert.equal(resolveInternalFounderQaThumbnail(source),null);assert.equal(reviewedOfficialSource(source).playback_status,'EMBED_BLOCKED');
 console.log('R4-02 media gate negative checks PASS');
} finally {rmSync(folder,{recursive:true,force:true})}
