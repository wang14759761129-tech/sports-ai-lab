import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,readFileSync,writeFileSync,rmSync,existsSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {loadMediaManifest,verifyMediaTree,artifactManifestName,validateManifest,mediaDistributionPlugin} from './mediaDistributionGate.mjs';
const manifest=loadMediaManifest();
const founderQaBuildGate=mediaDistributionPlugin();
assert.throws(()=>founderQaBuildGate.configResolved({root:process.cwd(),build:{outDir:'dist'},command:'build',mode:'founder-internal-qa'}),/INTERNAL QA mode cannot create a distributable build/,'Founder QA mode must not produce Web or Windows package artifacts');
const original=readFileSync('../docs/goal104-evidence/restricted-media/wtt-53034902256.jpg');
assert.equal(existsSync('public/media/editorial/wtt-53034902256.jpg'),false,'Review-only photo cannot live in Vite public');
verifyMediaTree('public',{requireManifest:false});
assert.equal(manifest.assets.length,0);
const folder=mkdtempSync(join(tmpdir(),'ptti-distribution-'));
function emitManifest(path,value=manifest){writeFileSync(join(path,artifactManifestName),JSON.stringify(value));}
try{
  const web=join(folder,'web');mkdirSync(web);writeFileSync(join(web,'index.html'),'<p>QA</p>');emitManifest(web);
  assert.equal(verifyMediaTree(web).status,'PASS');
  writeFileSync(join(web,'renamed.bin'),original);
  assert.throws(()=>verifyMediaTree(web),/withheld image bytes/,'Renaming the pending JPEG cannot evade the gate');
  rmSync(join(web,'renamed.bin'));
  writeFileSync(join(web,'unlisted.jpg'),Buffer.from('SIMULATED_ONLY unlisted raster'));
  assert.throws(()=>verifyMediaTree(web),/unlisted or altered image/);
  rmSync(join(web,'unlisted.jpg'));
  emitManifest(web,{...manifest,withheld_assets:[]});
  assert.throws(()=>verifyMediaTree(web),/manifest differs/,'Artifact cannot silently erase the withheld list');emitManifest(web);
  assert.throws(()=>validateManifest({...manifest,schema_version:'unknown'},'WEB'),/invalid policy/);
  assert.throws(()=>validateManifest({...manifest,assets:[{distribution_permission:'UNKNOWN'}]},'WEB'),/permission/);
  assert.throws(()=>validateManifest({...manifest,assets:[{distribution_permission:'ALLOWED',distribution_targets:['WEB']}]},'WINDOWS_DESKTOP'),/permission/,'Web permission is not Windows permission');
  const pkg=join(folder,'windows'),dist=join(pkg,'_internal/frontend/dist');mkdirSync(dist,{recursive:true});emitManifest(dist);
  const history=join(pkg,'_internal/data/professional/cover_review');mkdirSync(history,{recursive:true});
  writeFileSync(join(history,'public-match-cover-manifest.v0.2.json'),JSON.stringify(manifest));
  assert.equal(verifyMediaTree(pkg,{target:'WINDOWS_DESKTOP',packageTree:true}).status,'PASS');
  writeFileSync(join(history,'old-v0.1.json'),'{}');
  assert.throws(()=>verifyMediaTree(pkg,{target:'WINDOWS_DESKTOP',packageTree:true}),/historical\/internal/);
  rmSync(join(history,'old-v0.1.json'));
  writeFileSync(join(pkg,'_internal','photo.dat'),original);
  assert.throws(()=>verifyMediaTree(pkg,{target:'WINDOWS_DESKTOP',packageTree:true}),/withheld image bytes/,'Package-wide hash scan catches photo outside the frontend tree');
  console.log('Media distribution: Web/Windows, withheld bytes, renamed assets, unlisted raster, version/scope, manifest drift and historical audit exclusion PASS');
}finally{rmSync(folder,{recursive:true,force:true});}
