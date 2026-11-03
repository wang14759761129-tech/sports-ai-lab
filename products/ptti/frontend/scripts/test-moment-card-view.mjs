import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,writeFileSync,copyFileSync,rmSync} from 'node:fs';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';
import {createElement,StrictMode} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createMoment,MOMENT_STORAGE_KEY} from '../src/momentCards.mjs';

const folder=mkdtempSync(join(process.cwd(),'node_modules','.ptti-moment-view-'));
const priorWindow=globalThis.window;
try{
 const compile=spawnSync(process.execPath,['node_modules/typescript/bin/tsc','src/MomentCardsPage.tsx','--target','ES2022','--module','ES2022','--moduleResolution','bundler','--jsx','react-jsx','--strict','--skipLibCheck','--outDir',folder],{encoding:'utf8'});
 assert.equal(compile.status,0,compile.stdout+compile.stderr);
 // Node SSR has no CSS loader or bundler extension resolution; only adapt those imports.
 const page=join(folder,'MomentCardsPage.js');
 writeFileSync(page,readFileSync(page,'utf8').replace("import './moment-cards.css';",'').replace("'./OfficialLinkRecovery'","'./OfficialLinkRecovery.js'"));
 for(const name of ['momentCards.mjs','officialPlayback.mjs'])copyFileSync(join('src',name),join(folder,name));
 writeFileSync(join(folder,'package.json'),'{"type":"module"}');
 const {default:MomentCards}=await import(pathToFileURL(page));
 const evil='<img src=x onerror=alert(1)>';
 const records=createMoment([],{videoKey:'official:0QgbtsBWZhk',title:evil,timestamp:'12:34',note:'<script>alert(1)</script>',tags:['<svg/onload=alert(1)>']}).moments;
 const bytes=JSON.stringify(records);let writes=0;
 globalThis.window={localStorage:{getItem:key=>{assert.equal(key,MOMENT_STORAGE_KEY);return bytes},setItem:()=>writes++}};
 const props={videos:[{key:'official:0QgbtsBWZhk',event:'QA',title:'Registered',watchUrl:'https://www.youtube.com/watch?v=0QgbtsBWZhk',source:{provider:'YOUTUBE_OFFICIAL',video_id:'0QgbtsBWZhk'}}],onBack:()=>{}};
 for(let mount=0;mount<3;mount++){
  const markup=renderToStaticMarkup(createElement(StrictMode,null,createElement(MomentCards,props)));
  assert.match(markup,/12:34/,'Existing records are visible on the first render');
  assert.match(markup,/&lt;img/);
  assert.doesNotMatch(markup,/<img|<script|<svg/,'User fields never become HTML elements');
  assert.match(markup,/watch\?v=0QgbtsBWZhk&amp;t=754"/,'YouTube links retain the exact registered video ID and integer-second timestamp');
 }
 assert.equal(writes,0,'Initial renders/remounts perform no persistence writes');
 globalThis.window={get localStorage(){throw Error('SecurityError')}};
 const unavailable=renderToStaticMarkup(createElement(MomentCards,props));
 assert.match(unavailable,/role="alert"/);
 assert.match(unavailable,/存储不可用/);
 assert.doesNotMatch(unavailable,/已保存在此浏览器/);
 console.log('Moment Cards React SSR: initial records, repeated renders, escaped user fields and unavailable storage PASS (not browser Strict Mode lifecycle QA)');
}finally{
 globalThis.window=priorWindow;
 rmSync(folder,{recursive:true,force:true});
}
