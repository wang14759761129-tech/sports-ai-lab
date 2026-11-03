import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,rmSync,readFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';

const folder=mkdtempSync(join(tmpdir(),'ptti-official-playback-'));
try{
 const compiled=spawnSync(process.execPath,['node_modules/typescript/bin/tsc','src/officialPlayback.ts','--target','ES2022','--module','ES2022','--strict','--skipLibCheck','--outDir',folder],{encoding:'utf8'});
 assert.equal(compiled.status,0,compiled.stdout+compiled.stderr);
 writeFileSync(join(folder,'package.json'),' {"type":"module"}');
 const {officialPlaybackMessages,openOfficialLink,copyOfficialUrl}=await import(pathToFileURL(join(folder,'officialPlayback.js')));

 const limitation='该视频可能需要登录或受到地区限制';
 const liveError='官方播放不可用（150），请打开官方来源';
 const messages=officialPlaybackMessages({playback_limitation:limitation},liveError);
 assert.equal(messages.status,liveError,'The live player failure must remain visible when a source limitation exists');
 assert.equal(messages.limitation,limitation,'The static source limitation must remain available separately');

 let prevented=false;
 const failed=await openOfficialLink({preventDefault(){prevented=true}},'https://www.youtube.com/watch?v=WoqgXTjZNSk',async()=>false);
 assert.equal(failed,'FAILED');
 assert.equal(prevented,true,'A failed desktop handoff is detected after intercepting the anchor');
 prevented=false;
 assert.equal(await openOfficialLink({preventDefault(){prevented=true}},'https://www.youtube.com/watch?v=WoqgXTjZNSk'), 'BROWSER_DEFAULT');
 assert.equal(prevented,false,'Without the desktop bridge the official anchor remains browser-operable');
 assert.equal(await openOfficialLink({preventDefault(){}},'https://www.youtube.com/watch?v=WoqgXTjZNSk',async()=>{throw Error('browser unavailable')}),'FAILED');

 let copied='';
 assert.equal(await copyOfficialUrl('https://www.youtube.com/watch?v=WoqgXTjZNSk',async value=>{copied=value},()=>false),true);
 assert.equal(copied,'https://www.youtube.com/watch?v=WoqgXTjZNSk');
 let fallback='';
 assert.equal(await copyOfficialUrl('https://www.bilibili.com/video/BV1nb421H7jB/',async()=>{throw Error('clipboard unavailable')},value=>{fallback=value;return true}),true);
 assert.equal(fallback,'https://www.bilibili.com/video/BV1nb421H7jB/');
 assert.equal(await copyOfficialUrl('https://example.invalid/',async()=>{throw Error('clipboard unavailable')},()=>false),false,'Manual link selection remains necessary if clipboard APIs are unavailable');
 const player=readFileSync('src/OfficialVideoPlayer.tsx','utf8');
 assert.match(player,/officialPlaybackMessages\(source,status\)/,'The player must render dynamic playback status separately from static limitations');
 assert.match(player,/OfficialLinkRecovery url=\{source\.source_url\}/,'The official watch page must offer a copy-link recovery action');
 assert.doesNotMatch(player,/source\.playback_limitation\s*\|\|\s*status/,'Static limitations must not mask current playback errors');
 const feed=readFileSync('src/VideoFeed.tsx','utf8');
 assert.match(feed,/OfficialLinkRecovery url=\{v\.source\.source_url\}/,'External-only feed cards must expose a copy-link recovery action');
 console.log('official playback tests passed');
}finally{rmSync(folder,{recursive:true,force:true});}
