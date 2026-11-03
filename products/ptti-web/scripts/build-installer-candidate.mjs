import { readFile, writeFile, mkdir, copyFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const project=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const source=path.join(process.env.USERPROFILE,'PTTI/Release-Candidates/san-00933e351edc-core-304eb661b8a1-rc1');
const output=path.join(process.env.USERPROFILE,'PTTI/Installer-Candidates/goal11-3-rc1');
try { await stat(output); throw new Error('Output exists; no overwrite.'); } catch(e) { if(e.code!=='ENOENT') throw e; }
const hash=b=>createHash('sha256').update(b).digest('hex');
const bytes=await readFile(path.join(source,'manifest.json')); const original=JSON.parse(bytes);
if(original.san.commit!=='00933e351edc47a8d2b7c819c0eea6078ac596d6'||original.playback.commit!=='304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe'||original.catalog.internal_sources_included!==0) throw new Error('Unexpected RC1 baseline');
const stage=path.join(output,'PTTI-Installer-Candidate'); const payload=path.join(stage,'payload'); await mkdir(payload,{recursive:true});
const files={};
async function put(name,bytes,bom=false){const dest=path.join(payload,name); await mkdir(path.dirname(dest),{recursive:true}); const b=Buffer.isBuffer(bytes)?bytes:Buffer.from((bom?'\ufeff':'')+bytes); await writeFile(dest,b); files[name]=hash(b);}
for(const [name,expected] of Object.entries(original.files)) {const b=await readFile(path.join(source,name)); if(hash(b)!==expected) throw new Error('RC1 changed: '+name); await put(name,b);}
await put('original-rc1-manifest.json',bytes);
const launcher=(await readFile(path.join(source,'Start-PTTI-RC.ps1'),'utf8')).replace(/^\ufeff/,'').replace('Port = 4176','Port = 4177').replace("'app\\server.mjs'","'app\\installed-service.mjs'");
if(!launcher.includes('installed-service.mjs')) throw new Error('Launcher overlay failed');
await put('Start-PTTI-RC.ps1',launcher,true);
await put('app/stop.mjs',await readFile(path.join(project,'scripts/installer/stop.mjs')));
const lifecycle=`
// Installer lifecycle overlay: no HTTP stop API; per-process random local pipe/token.
const net = await import('node:net');
const fs = await import('node:fs/promises');
const crypto = await import('node:crypto');
const pipe = ${JSON.stringify('\\\\.\\pipe\\ptti-ic-')} + crypto.randomBytes(16).toString('hex');
const token = crypto.randomBytes(32).toString('hex');
let stopping = false;
const control = net.createServer({allowHalfOpen:true},socket => {
 let input = ''; socket.setTimeout(3000,()=>socket.destroy());
 socket.on('error',()=>{});
 socket.on('data',chunk=>{
  input+=chunk; if(input.length>65){socket.destroy();return;}
  if(!input.endsWith('\\n'))return;
  if(input!==token+'\\n'||stopping){socket.end('REFUSED');return;}
  socket.setTimeout(0);
  stopping=true;
  server.close(async()=>{
   await fs.unlink(path.join(root,'logs/control.json')).catch(()=>{});
   socket.end('STOPPED'); control.close(); await log('STOPPED');
  });
  server.closeAllConnections();
 });
});
server.once('listening',()=>control.listen(pipe,async()=>{
 await fs.writeFile(path.join(root,'logs/control.json'),JSON.stringify({artifact:manifest.artifact_id,pipe,token}),{mode:0o600});
}));
`;
await put('app/installed-service.mjs',(await readFile(path.join(source,'app/server.mjs'),'utf8'))+lifecycle);
await put('Uninstall.ps1',(await readFile(path.join(project,'scripts/installer/Uninstall.ps1'),'utf8')),true);
const cmd=name=>`@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0${name}.ps1" %*\r\n`;
await put('Uninstall.cmd',cmd('Uninstall'));
await put('Stop-PTTI.cmd','@echo off\r\n"%~dp0runtime\\node.exe" "%~dp0app\\stop.mjs"\r\nif errorlevel 1 pause\r\n');
await put('START-HERE.txt','PTTI Installer Candidate / 安装候选\r\nStart-PTTI-RC.cmd: 打开本机4177候选；Stop-PTTI.cmd: 停止候选；Uninstall.cmd: 卸载候选程序文件。\r\n仅用户级安装；不更改原桌面入口，不覆盖4174、4176或R4。\r\n视频和笔记默认只在内存，关闭或刷新前请主动导出。先导出再停止。\r\nNode随包；需要Windows x64、PowerShell5.1和浏览器。未签名、非原生EXE安装器。\r\nSIMULATED_ONLY数据不是真实比赛，公开目录0。\r\n');
const manifest={...original,artifact_id:original.artifact_id+'-installed-rc1',default_port:4177,installer_overlay:{original_manifest_sha256:hash(bytes),purpose:'user-level lifecycle only; original site/Core/demo bytes unchanged'},files:{...files}};
await put('manifest.json',JSON.stringify(manifest,null,2));
const pkg={contract:'ptti.windows-installer/0.1',application_san:original.san.commit,playback:original.playback.commit,original_manifest_sha256:hash(bytes),installer_source:execFileSync('git',['rev-parse','HEAD'],{cwd:project,encoding:'utf8'}).trim(),port:4177,files};
await writeFile(path.join(stage,'package.json'),JSON.stringify(pkg,null,2));
await copyFile(path.join(project,'scripts/installer/Install.ps1'),path.join(stage,'Install.ps1'));
// PowerShell 5.1 requires a BOM for Chinese error/UI strings.
const installText=await readFile(path.join(stage,'Install.ps1'),'utf8'); await writeFile(path.join(stage,'Install.ps1'),'\ufeff'+installText.replace(/^\ufeff/,''));
await writeFile(path.join(stage,'Install.cmd'),cmd('Install'));
await writeFile(path.join(stage,'README.txt'),'Extract this entire ZIP, then run Install.cmd. No administrator privileges required. This is a script-based installer candidate, not a signed EXE/MSI. No application is launched during installation.\r\n解压整个ZIP后运行Install.cmd，安装到当前用户LocalAppData。安装不会自动打开浏览器或修改桌面。\r\n');
const zip=path.join(output,'PTTI-Web-Pro-Installer-Candidate-rc1.zip');
execFileSync('C:\\Program Files\\7-Zip\\7z.exe',['a','-tzip','-mx1','-mmt1',zip,'PTTI-Installer-Candidate'],{cwd:output,windowsHide:true,stdio:'pipe'});
const zipHash=hash(await readFile(zip)); await writeFile(zip+'.sha256',zipHash+'  '+path.basename(zip)+'\n');
await writeFile(path.join(output,'build-receipt.json'),JSON.stringify({package:zip,sha256:zipHash,package_bytes:(await stat(zip)).size,...pkg,files:undefined,licenses:{node:'Node MIT + bundled third-party notices; payload/licenses/NODE-LICENSE.txt',react:'MIT; payload/licenses',packager:'Existing 7-Zip build tool only; not redistributed. LGPL/BSD/unRAR notices in installed License.txt',powershell:'Windows system component, not redistributed'},signed:false},null,2));
console.log(JSON.stringify({zip,sha256:zipHash,stage},null,2));
