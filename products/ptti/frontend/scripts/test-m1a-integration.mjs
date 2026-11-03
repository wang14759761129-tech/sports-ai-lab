import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {prepareLocalSession,projectLocalSession,confirmedLocalRights,projectImportedMoment,seekImportedMoment} from '../src/localPlaybackFoundationBridge.mjs';
import {PROGRESS_KEY,writeProgress,readProgress,resumeDecision,guardedPlay} from '../src/localPlayback.mjs';
import {KEY,emptyEvidence} from '../src/gex-moment/evidence.mjs';
import {previewImport,confirmImportAndSave} from '../src/gex-moment/moment-import.mjs';
import {projectSqliteFavorites} from '../src/userCollectionProjection.mjs';
import {mediaSourceToFoundation,videoAssetFromMediaSource,validateFoundationBundle} from '../src/foundationContract.mjs';

const fixturePath=process.argv[2], backupPath=process.argv[3];
if(!fixturePath||!backupPath)throw Error('Pass the synthetic rally.mp4 and roundtrip-example.json paths explicitly');
const videoBytes=readFileSync(fixturePath), backup=readFileSync(backupPath,'utf8');
const makeStorage=()=>{const values=new Map();return {values,getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,String(value))}};

test('same synthetic local bytes retain the exact content identity across selection', async () => {
  const storage = makeStorage();
  const first = await prepareLocalSession({file: new Blob([videoBytes]), duration: 12, storage});
  const second = await prepareLocalSession({file: new Blob([videoBytes]), duration: 12, storage});
  assert.equal(first.gexAsset.id, second.gexAsset.id);
  assert.equal(first.gexAsset.id,JSON.parse(backup).video_asset.id,'actual synthetic fixture matches its backup');
  assert.equal(first.videoAsset.identity.video_asset_id, `asset:${first.gexAsset.id}`);
  assert.equal(first.projection.continuation.status, 'NOT_ELIGIBLE');
});

test('one Playback store drives reselect, duration checks and rights-scoped continuation',async()=>{
 const storage=makeStorage(), file=new File([videoBytes],'same-name.mp4',{type:'video/mp4',lastModified:1});
 const first=await prepareLocalSession({file,duration:12,storage});
 writeProgress(storage,first.gexAsset.id,6.345,12,'synthetic-rally.mp4');
 const same=await prepareLocalSession({file:new Blob([videoBytes]),duration:12,storage});
 assert.equal(readProgress(storage,first.gexAsset.id,12),6.345);
 assert.equal(same.projection.savedProgress.position_ms,6345);
 assert.equal(same.projection.continuation.reason,'RIGHTS_EVIDENCE_MISSING');
 assert.throws(()=>confirmedLocalRights(same.videoAsset,{confirmed:false,evidenceId:'synthetic-confirmation'}));
 const rights=confirmedLocalRights(same.videoAsset,{confirmed:true,evidenceId:'synthetic-user-confirmation'});
 const permitted=projectLocalSession(same,{rightsEvidence:rights,now:Date.parse('2026-10-28T00:00:00Z')});
 assert.equal(permitted.continuation.status,'ELIGIBLE');
 assert.equal(permitted.playbackState.observation,'NOT_TESTED');
 assert.equal(permitted.playbackState.embed_permission,'UNKNOWN');
 assert.equal(rights.permissions.embed.status,'UNKNOWN');assert.equal(rights.permissions.package_distribution.status,'UNKNOWN');
 assert.equal(validateFoundationBundle([same.videoAsset,rights,permitted.playbackState]),true);
 const expired=structuredClone(rights);expired.permissions.web_display.valid_until='2026-10-27T00:00:00Z';
 assert.equal(projectLocalSession(same,{rightsEvidence:expired,now:Date.parse('2026-10-28T00:00:00Z')}).continuation.status,'NOT_ELIGIBLE');
 assert.deepEqual(resumeDecision(6.345,12,false),{action:'RESTORE',seconds:6.345});
 assert.equal(resumeDecision(6.345,12,true).action,'PRESERVE_CURRENT');
 assert.deepEqual([...storage.values.keys()],[PROGRESS_KEY]);
 const changed=Buffer.from(videoBytes);changed[changed.length-1]^=1;
 const sameMetadataOtherFile=new File([changed],'same-name.mp4',{type:'video/mp4',lastModified:1});
 assert.equal(sameMetadataOtherFile.name,file.name);assert.equal(sameMetadataOtherFile.size,file.size);assert.equal(sameMetadataOtherFile.lastModified,file.lastModified);
 const other=await prepareLocalSession({file:sameMetadataOtherFile,duration:12,storage});
 assert.notEqual(other.gexAsset.id,first.gexAsset.id);assert.equal(other.projection.savedProgress.status,'EMPTY');
 const mismatch=await prepareLocalSession({file,duration:13,storage});
 assert.equal(mismatch.projection.savedProgress.status,'UNVERIFIABLE');
 assert.equal(readProgress(storage,first.gexAsset.id,12),6.345,'failed recovery preserved original bytes');
});

test('Moment import binds the selected content and projects precise milliseconds',async()=>{
 const storage=makeStorage(), session=await prepareLocalSession({file:new Blob([videoBytes]),duration:12,storage});
 const current=emptyEvidence(),store={schema:KEY,assets:{}};
 const plan=previewImport(backup,session.gexAsset,current);assert.ok(plan.added>0);
 const result=confirmImportAndSave(storage,store,null,plan,session.gexAsset,current);
 const item=result.merged.moments[0];
 const projection=projectImportedMoment(session.gexAsset,item,'explicit-synthetic-import-confirmation');
 assert.equal(projection.timeline_anchor.timestamp_ms,Math.round(item.time*1000));
 assert.equal(projection.identity.video_asset_id,session.videoAsset.identity.video_asset_id);
 assert.equal(validateFoundationBundle([session.videoAsset,projection]),true);
 const fraction={...item,id:'fraction-test',time:2.3455};
 assert.equal(projectImportedMoment(session.gexAsset,fraction,'explicit-synthetic-confirmation').timeline_anchor.timestamp_ms,2346);
  const video={currentSrc:'blob:synthetic-a',readyState:1,duration:12,currentTime:0};
  seekImportedMoment(video,'blob:synthetic-a',session.gexAsset,fraction,'explicit-replay-confirmation');
  assert.equal(video.currentTime,2.346);
  assert.throws(()=>seekImportedMoment(video,'blob:synthetic-b',session.gexAsset,fraction,'explicit-replay-confirmation'));
  assert.equal(video.currentTime,2.346,'mismatched selection must not change the playback position');
 assert.throws(()=>projectImportedMoment(session.gexAsset,{...item,video_id:'sha256-chunks-v1:'+'0'.repeat(64)},'explicit-confirmation'));
 assert.throws(()=>projectImportedMoment(session.gexAsset,item,''));
 const modified=Buffer.from(videoBytes);modified[modified.length-1]^=1;
 const other=await prepareLocalSession({file:new Blob([modified]),duration:12,storage});
 assert.throws(()=>previewImport(backup,other.gexAsset,emptyEvidence()));
 assert.throws(()=>projectImportedMoment(other.gexAsset,item,'explicit-confirmation'));
  const otherVideo={currentSrc:'blob:synthetic-b',readyState:1,duration:12,currentTime:1};
  assert.throws(()=>seekImportedMoment(otherVideo,'blob:synthetic-b',other.gexAsset,item,'explicit-confirmation'));
  assert.equal(otherVideo.currentTime,1,'Moment A never seeks video B');
 assert.equal(storage.values.has(KEY),true);
});

test('SQLite favorite keys map only exact registered source and match records',()=>{
 const records=JSON.parse(readFileSync(new URL('../../contracts/foundation-v0.1.examples.json',import.meta.url),'utf8'));
 const match=records.find(x=>x.kind==='MatchIdentity');
 const source=mediaSourceToFoundation({video_id:'0QgbtsBWZhk',provider:'YOUTUBE_OFFICIAL',source_key:'YOUTUBE:0QgbtsBWZhk',source_url:'https://www.youtube.com/watch?v=0QgbtsBWZhk',match_id:match.identity.match_id},{recordId:'source:m1a-test'});
  const officialAsset=videoAssetFromMediaSource(source,{recordId:'official-asset:m1a-test'});
  assert.throws(()=>confirmedLocalRights(officialAsset,{confirmed:true,evidenceId:'synthetic-confirmation'}),/LOCAL_ASSET_REQUIRED/);
 const keys=[`match:${match.identity.match_id}`,'official:0QgbtsBWZhk','official:unrelated'];
 const output=projectSqliteFavorites({favoriteKeys:keys,records:[match,source],recordId:'collection:m1a-test',collectionId:'collection:m1a'});
 assert.equal(output.write_policy,'READ_ONLY_PROJECTION');assert.equal(output.resolved.length,2);assert.equal(output.unresolved.length,1);
 assert.deepEqual(output.input_keys,keys);assert.equal(validateFoundationBundle([match,source,output.collection]),true);
});

test('inactive playback cannot keep playing and storage read failure remains unverified',async()=>{
 const storage={getItem(){throw Error('read failure')}};
 const session=await prepareLocalSession({file:new Blob([videoBytes]),duration:12,storage});
 assert.equal(session.progressSnapshot.status,'UNVERIFIABLE');assert.equal(session.projection.continuation.status,'NOT_ELIGIBLE');
 let active=true,paused=false;
 const video={async play(){active=false},pause(){paused=true}};
 assert.equal(await guardedPlay(video,()=>active),'inactive');assert.equal(paused,true);
 await assert.rejects(prepareLocalSession({file:new Blob([videoBytes]),duration:12,storage:makeStorage(),isCurrent:()=>false}),/CANCELLED/);
});
