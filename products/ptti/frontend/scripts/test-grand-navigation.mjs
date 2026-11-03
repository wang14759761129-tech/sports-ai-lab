import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,writeFileSync,rmSync} from 'node:fs';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const dir=mkdtempSync(join(process.cwd(),'node_modules','.ptti-grand-nav-'));
try{
 const result=spawnSync(process.execPath,['node_modules/typescript/bin/tsc','src/GrandNavigation.tsx','--target','ES2022','--module','ES2022','--moduleResolution','bundler','--jsx','react-jsx','--strict','--skipLibCheck','--outDir',dir],{encoding:'utf8'});
 assert.equal(result.status,0,result.stdout+result.stderr);
 const file=join(dir,'GrandNavigation.js');writeFileSync(file,readFileSync(file,'utf8').replace("import './grand-experience.css';",''));
 writeFileSync(join(dir,'package.json'),'{"type":"module"}');
 const {default:Nav,GRAND_SPACES}=await import(pathToFileURL(file));
 for(const active of GRAND_SPACES.map(s=>s.id)){
  const html=renderToStaticMarkup(createElement(Nav,{active,onChange(){}}));
  assert.equal((html.match(/<button/g)||[]).length,4);
  assert.equal((html.match(/aria-current="page"/g)||[]).length,1);
  assert.match(html,new RegExp(`id="grand-nav-${active}"[^>]*aria-current="page"`));
  for(const space of GRAND_SPACES)assert.ok(html.includes(`aria-controls="grand-panel-${space.id}"`));
 }
 console.log('Grand Navigation: four named spaces, one active state and accessible panel associations PASS');
}finally{rmSync(dir,{recursive:true,force:true})}
