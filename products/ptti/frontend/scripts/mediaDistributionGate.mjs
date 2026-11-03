import {readFileSync,readdirSync,lstatSync,existsSync,writeFileSync,openSync,readSync,closeSync} from 'node:fs';
import {resolve,relative,join,basename} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {resolveEditorialMatchPhoto} from '../src/thumbnailPermission.mjs';

export const manifestPath=fileURLToPath(new URL('../../data/professional/cover_review/public-match-cover-manifest.v0.2.json',import.meta.url));
export const artifactManifestName='media-distribution-manifest.json';
export const sha256=bytes=>createHash('sha256').update(bytes).digest('hex');
export function assertMediaBuildMode(command,mode){
  if(command==='build'&&mode==='founder-internal-qa')fail('INTERNAL QA mode cannot create a distributable build');
}
function fileHash(path){
  const descriptor=openSync(path,'r'),digest=createHash('sha256'),buffer=Buffer.alloc(65536);
  try{let count;while((count=readSync(descriptor,buffer,0,buffer.length,null))>0)digest.update(buffer.subarray(0,count));}
  finally{closeSync(descriptor);}
  return digest.digest('hex');
}
export function loadMediaManifest(){
  const bytes=readFileSync(manifestPath),expected=readFileSync(manifestPath+'.sha256','utf8').split(/\s+/)[0];
  if(sha256(bytes)!==expected)fail('active manifest SHA mismatch');
  const manifest=JSON.parse(bytes.toString('utf8'));
  validateManifest(manifest,'WEB');
  const catalog=JSON.parse(readFileSync(new URL('../../data/professional/official_video_sources.json',import.meta.url),'utf8'));
  for(const source of catalog.videos){
    const photo=source.editorial_match_photo;if(!photo)continue;
    if(photo.distribution_permission!=='ALLOWED'&&!manifest.withheld_assets.some(a=>a.media_sha256===photo.media_sha256&&a.source_id===photo.source_id))fail('catalog hold missing from manifest');
  }
  for(const asset of manifest.assets){
    const source=catalog.videos.find(s=>s.editorial_match_photo?.source_id===asset.source_id);
    const photo=resolveEditorialMatchPhoto(source);
    if(!photo||photo.media_sha256!==asset.media_sha256||photo.display_url!=='/'+asset.artifact_path||
       JSON.stringify(photo.written_permission)!==JSON.stringify(asset.written_permission))fail('catalog and distribution approval differ');
  }
  return manifest;
}
function fail(reason){throw Error('MEDIA_DISTRIBUTION_GATE: '+reason);}
export function validateManifest(manifest,target){
  if(!['WEB','WINDOWS_DESKTOP'].includes(target)||manifest?.schema_version!=='ptti.match-cover-manifest/0.2'||
      manifest.delivery_policy!=='EXPLICIT_WRITTEN_DISTRIBUTION_PERMISSION_REQUIRED'||
      !Array.isArray(manifest.assets)||!Array.isArray(manifest.withheld_assets))fail('invalid policy/version');
  const hashes=new Set(),paths=new Set();
  for(const asset of manifest.assets){
    const permission=asset.written_permission;
    if(asset.distribution_permission!=='ALLOWED'||!asset.distribution_targets?.includes(target)||
        !/^[a-f0-9]{64}$/.test(asset.media_sha256)||
        !/^media\/editorial\/[A-Za-z0-9_-]+\.(jpg|jpeg|png|webp|avif)$/.test(asset.artifact_path)||
        !permission?.evidence_id||! /^[a-f0-9]{64}$/.test(permission.evidence_sha256)||
        permission.local_packaging!=='ALLOWED'||!permission.targets?.includes(target)||
        !Number.isFinite(Date.parse(permission.valid_from))||!Number.isFinite(Date.parse(permission.valid_until))||
        Date.now()<Date.parse(permission.valid_from)||Date.now()>=Date.parse(permission.valid_until))fail('asset lacks current, explicit distribution permission');
    if(hashes.has(asset.media_sha256)||paths.has(asset.artifact_path))fail('duplicate media identity');
    hashes.add(asset.media_sha256);paths.add(asset.artifact_path);
  }
  for(const denied of manifest.withheld_assets){
    if(!/^[a-f0-9]{64}$/.test(denied.media_sha256)||denied.status!=='NEEDS_PERMISSION_FOR_DISTRIBUTION'||hashes.has(denied.media_sha256))fail('invalid/conflicting withheld record');
  }
}
function files(root){
  if(!existsSync(root)||!lstatSync(root).isDirectory())fail('artifact directory missing');
  const result=[];
  function visit(folder){for(const name of readdirSync(folder)){const path=join(folder,name),stat=lstatSync(path);if(stat.isSymbolicLink())fail('symlink in delivery tree');if(stat.isDirectory())visit(path);else if(stat.isFile())result.push(path);}}
  visit(root);return result;
}
export function verifyMediaTree(root,{manifest=loadMediaManifest(),target='WEB',requireManifest=true,packageTree=false}={}){
  root=resolve(root);validateManifest(manifest,target);
  const denied=new Set(manifest.withheld_assets.map(a=>a.media_sha256));
  const all=files(root);let frontendRoot=root;
  if(packageTree){
    const candidates=all.filter(p=>p.replaceAll('\\','/').endsWith('/frontend/dist/'+artifactManifestName));
    if(candidates.length!==1)fail('packaged frontend manifest missing/ambiguous');
    frontendRoot=resolve(candidates[0],'..');
    const catalogManifests=all.filter(p=>p.replaceAll('\\','/').endsWith('/data/professional/cover_review/'+basename(manifestPath)));
    if(catalogManifests.length!==1||JSON.stringify(JSON.parse(readFileSync(catalogManifests[0],'utf8')))!==JSON.stringify(manifest))fail('packaged catalog manifest missing or inconsistent');
  }
  for(const path of all){
    if(denied.has(fileHash(path)))fail('withheld image bytes included: '+relative(root,path));
    if(packageTree&&path.replaceAll('\\','/').includes('/data/professional/cover_review/')&&basename(path)!==basename(manifestPath))fail('historical/internal media manifest in package');
  }
  const expected=new Map(manifest.assets.map(a=>[a.artifact_path,a]));
  for(const path of files(frontendRoot)){
    const rel=relative(frontendRoot,path).replaceAll('\\','/');
    if(/\.(jpe?g|png|webp|avif|gif)$/i.test(rel)){
      const asset=expected.get(rel);
      if(!asset||fileHash(path)!==asset.media_sha256)fail('unlisted or altered image: '+rel);
    }
  }
  for(const asset of manifest.assets){const path=join(frontendRoot,asset.artifact_path);if(!existsSync(path)||fileHash(path)!==asset.media_sha256)fail('manifest asset missing or altered');}
  if(requireManifest){
    const path=join(frontendRoot,artifactManifestName);
    if(!existsSync(path)||JSON.stringify(JSON.parse(readFileSync(path,'utf8')))!==JSON.stringify(manifest))fail('artifact manifest differs from active policy');
  }
  return {status:'PASS',target,approvedAssets:manifest.assets.length};
}
export function mediaDistributionPlugin(){
  let outDir;
  return {name:'ptti-media-distribution-gate',apply:'build',
    configResolved(config){assertMediaBuildMode(config.command,config.mode);outDir=resolve(config.root,config.build.outDir);},
    buildStart(){verifyMediaTree(fileURLToPath(new URL('../public',import.meta.url)),{requireManifest:false});},
    closeBundle(){writeFileSync(join(outDir,artifactManifestName),JSON.stringify(loadMediaManifest(),null,2)+'\n');verifyMediaTree(outDir);}
  };
}
