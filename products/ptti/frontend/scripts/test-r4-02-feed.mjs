import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';
const compiler=process.argv[2];if(!compiler)throw Error('Pass TypeScript compiler path');
const folder=mkdtempSync(join(tmpdir(),'r4-02-feed-'));
try {
 const run=spawnSync(process.execPath,[compiler,'src/feedCatalog.ts','src/onlinePlayers.ts','--target','ES2022','--module','ES2022','--strict','--skipLibCheck','--outDir',folder],{encoding:'utf8'});assert.equal(run.status,0,run.stderr+run.stdout);
 // Node requires explicit relative extensions for emitted ESM.
 const fs=await import('node:fs');const path=join(folder,'feedCatalog.js');fs.writeFileSync(path,fs.readFileSync(path,'utf8').replace("from './onlinePlayers'","from './onlinePlayers.js'"));writeFileSync(join(folder,'package.json'),'{"type":"module"}');
 const {feedVideos,filterFeed,officialAction}=await import(pathToFileURL(path));
 const source={provider:'YOUTUBE',video_id:'0QgbtsBWZhk',title:'Test',full_match:true,thumbnail_url:'https://i.ytimg.com/x',source_url:'https://www.youtube.com/watch?v=0QgbtsBWZhk',playback_status:'EMBED_BLOCKED',discipline:'MS',video_source:{provider:'YOUTUBE',source_id:'0QgbtsBWZhk',embed_permission:'ALLOWED',playback_type:'OFFICIAL_EMBED'}};
 const [row]=feedVideos({official_videos:[source],videos:[],matches:[],athletes:[]});assert.equal(row.thumbnail,'');assert.equal(officialAction(row),'SOURCE_LINK');assert.equal(filterFeed([row],{category:'男单'}).length,1);assert.equal(filterFeed([row],{query:'Test'}).length,1);assert.equal(filterFeed([row],{view:'feedFavorites',favorites:[row.key]}).length,1);
 assert.equal(officialAction({...row,source:{...source,playback_status:'UNKNOWN',video_source:{...source.video_source,source_id:'H77vNFk3neg'}}}),'SOURCE_LINK');
 assert.equal(officialAction({...row,source:{...source,playback_status:'UNKNOWN'}}),'EMBED');
 console.log('R4-02 feed identity, search, category, favorites and embed checks PASS');
} finally {rmSync(folder,{recursive:true,force:true})}
