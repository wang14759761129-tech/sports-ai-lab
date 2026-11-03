import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';import {join} from 'node:path';import {spawnSync} from 'node:child_process';import {pathToFileURL} from 'node:url';
const folder=mkdtempSync(join(tmpdir(),'ptti-feed-'));
try{
 const r=spawnSync(process.execPath,['node_modules/typescript/bin/tsc','src/feedCatalog.ts','--target','ES2022','--module','ES2022','--strict','--skipLibCheck','--outDir',folder],{encoding:'utf8'});assert.equal(r.status,0,r.stdout+r.stderr);writeFileSync(join(folder,'package.json'),' {"type":"module"}');
 const {feedVideos,filterFeed,officialAction,durationLabel}=await import(pathToFileURL(join(folder,'feedCatalog.js')));
 const official={video_id:'real',title:'Actual full match',full_match:true,athlete_names:['孙颖莎'],event_name:'WTT Macao 2024',discipline:'WS',playback_status:'EMBED_BLOCKED',watch_page_status:'NOT_TESTED',source_url:'https://www.youtube.com/watch?v=real'};
 const rows=feedVideos({videos:[{video_id:'local',title:'local',availability_status:'AVAILABLE',duration_ms:1000,last_opened_at:'now'},{video_id:'missing',availability_status:'MISSING_FILE'}],official_videos:[official,official,{...official,video_id:'highlight',full_match:false}]});
 assert.equal(rows.length,2,'No duplicate, missing media or highlights as full match');
 assert.equal(officialAction(rows[1]),'SOURCE_LINK','Known embedding failure must bypass iframe');
 assert.equal(filterFeed(rows,{category:'女单'}).length,1);
 assert.equal(filterFeed(rows,{athlete:'孙颖莎'}).length,1);
 assert.equal(filterFeed(rows,{category:'奥运'}).length,0,'No invented category content');
 assert.equal(filterFeed(rows,{view:'feedHistory'}).length,1,'Official link not a verified watch history');
 assert.equal(filterFeed(rows,{view:'feedFavorites',favorites:['official:real']}).length,1);
 assert.equal(durationLabel(null),'时长未核实');
 console.log('8 passed, 0 failed: feed source truth, duplicate filtering, role views and routing');
}finally{rmSync(folder,{recursive:true,force:true});}
