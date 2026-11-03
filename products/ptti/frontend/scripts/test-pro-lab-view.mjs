import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,writeFileSync,copyFileSync,rmSync,mkdirSync} from 'node:fs';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';
import {createElement,StrictMode} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

const folder=mkdtempSync(join(process.cwd(),'.ptti-pro-lab-view-'));
const oldWindow=globalThis.window;
try{
 const compile=spawnSync(process.execPath,['node_modules/typescript/bin/tsc','src/ProLab.tsx','--target','ES2022','--module','ES2022','--moduleResolution','bundler','--jsx','react-jsx','--strict','--skipLibCheck','--outDir',folder],{encoding:'utf8'});
 assert.equal(compile.status,0,compile.stdout+compile.stderr);
 const page=join(folder,'ProLab.js');
 writeFileSync(page,readFileSync(page,'utf8').replace("import './pro-lab.css';",'').replace("from './GexMomentRestore';","from './GexMomentRestore.js';"));
 copyFileSync(join('src','proLabNotes.mjs'),join(folder,'proLabNotes.mjs'));mkdirSync(join(folder,'gex-moment'));for(const f of ['evidence.mjs','moment-import.mjs','arena-events.mjs'])copyFileSync(join('src','gex-moment',f),join(folder,'gex-moment',f));
 writeFileSync(join(folder,'package.json'),'{"type":"module"}');
 const {default:ProLab}=await import(pathToFileURL(page));
 const legacy={id:'old-1',videoName:'<img src=x onerror=alert(1)>',seconds:754,tags:['<svg onload=alert(1)>'],coachNote:'<script>alert(1)</script>',createdAt:new Date(1).toISOString(),updatedAt:new Date(1).toISOString()};
 let writes=0;const bytes=JSON.stringify([legacy]);
 globalThis.window={localStorage:{getItem:key=>{assert.equal(key,'ptti-pro-lab-notes-v1');return bytes},setItem:()=>{writes++}},confirm:()=>false,setTimeout};
 for(let i=0;i<3;i++){
  const markup=renderToStaticMarkup(createElement(StrictMode,null,createElement(ProLab,{onBack:()=>{}})));
  assert.match(markup,/旧版未绑定文件身份笔记/,'old records remain visible and require explicit binding');
  assert.match(markup,/&lt;script&gt;/,'user notes are escaped by React');
  assert.doesNotMatch(markup,/<script|<img|<svg/,'stored text is never interpreted as HTML');
 }
 assert.equal(writes,0,'StrictMode/re-mount initialization does not overwrite existing records');
 globalThis.window={get localStorage(){throw Error('SecurityError')},confirm:()=>false,setTimeout};
 const blocked=renderToStaticMarkup(createElement(ProLab,{onBack:()=>{}}));
 assert.match(blocked,/本机存储不可用/);
 assert.doesNotMatch(blocked,/笔记已保存在本机/);
 console.log('Pro Lab React SSR: existing data, StrictMode repeated mount, escaping and unavailable storage PASS (browser interactions NOT_TESTED)');
}finally{globalThis.window=oldWindow;rmSync(folder,{recursive:true,force:true});}
