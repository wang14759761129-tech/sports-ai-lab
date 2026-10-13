import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import vm from 'node:vm';

// Deterministic hook/timer host runs the actual TSX component and request chain.
// It proves preview rendering, not native media decoding or Windows GUI success.
const require=createRequire(import.meta.url),ts=require('typescript');
const evidence=JSON.parse(readFileSync('../reports/CINEMA_GOAL06_1_EVIDENCE.json','utf8'));
const completed=evidence.folders_fixture[0];
const catalog={videos:[],matches:[],athletes:[],collections:[],summary:{matches:0,playable_professional:0,local_playable:0}};
const clone=value=>JSON.parse(JSON.stringify(value));
function host(fetcher){
 let now=0,cursor=0,dirty=true,tree,active=true,nextTimer=0;
 const slots=[],effects=[],pending=[],timers=new Map(),calls=[];
 const schedule=(fn,delay,repeat=0)=>{const id=++nextTimer;timers.set(id,{fn,at:now+delay,repeat});return id};
 const hooks={
  useState(initial){const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;return [slots[i],value=>{const next=typeof value==='function'?value(slots[i]):value;if(!Object.is(next,slots[i])){slots[i]=next;dirty=true}}]},
  useRef(initial){const i=cursor++;return slots[i]??=( {current:initial} )},
  useEffect(fn,deps){const i=cursor++;if(!effects[i]||!deps||deps.some((d,j)=>!Object.is(d,effects[i].deps?.[j])))pending.push(()=>{effects[i]?.cleanup?.();effects[i]={deps,cleanup:fn()}})}
 };
 const jsx=(type,props)=>({type,props}),cache=new Map();
 function load(name){
  if(cache.has(name))return cache.get(name);
  const source=readFileSync(`src/${name}`,'utf8');
  const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022}}).outputText;
  const module={exports:{}};cache.set(name,module.exports);
  vm.runInNewContext(code,{module,exports:module.exports,AbortController,
   fetch(url,options){calls.push({url,options,time:now});const response=fetcher(url,options,calls);return new Promise((resolve,reject)=>{const finish=()=>response.error?reject(response.error):resolve({ok:response.status!==403&&response.status!==400,status:response.status||200,json:async()=>clone(response.value)});if(response.delay)schedule(finish,response.delay);else finish()})},
   window:{pywebview:{api:{select_evidence_video:async()=>completed.selected_file}},confirm:()=>true},
   setInterval:(fn,ms)=>schedule(fn,ms,ms),clearInterval:id=>timers.delete(id),
   setTimeout:(fn,ms)=>schedule(fn,ms),clearTimeout:id=>timers.delete(id),
   require(name){if(name==='react')return hooks;if(name==='react/jsx-runtime')return {jsx,jsxs:jsx};if(name==='./ui')return {Card:'card',Empty:'empty',Modal:'modal',PageHeader:'header'};
    if(name.endsWith('.css'))return {};if(['./VideoDiscovery','./MatchSourcePanel'].includes(name))return {default:'unused-child'};return load(name.slice(2)+'.ts')}
  });cache.set(name,module.exports);return module.exports;
 }
 const component=load('MatchVideoLibrary.tsx').default;
 const props={page:'libraryTools',revision:0,onOpenVideo(){},onOpenScore(){},onScorePlaylist(){},navigate(){}};
 function render(){if(!active)return;cursor=0;dirty=false;tree=component(props);pending.splice(0).forEach(fn=>fn())}
 async function settle(){for(let i=0;i<30;i++){await Promise.resolve();if(active&&dirty)render()}return tree}
 return {
  calls,tree:()=>tree,settle,
  async start(){render();return settle()},
  async advance(ms){const end=now+ms;for(;;){const entry=[...timers].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];if(!entry)break;const [id,t]=entry;now=t.at;if(t.repeat)t.at+=t.repeat;else timers.delete(id);t.fn();await settle()}now=end;await settle()},
  async revise(){props.revision++;dirty=true;await settle()},
  unmount(){active=false;effects.forEach(e=>e?.cleanup?.())},
  activeIntervals(){return [...timers.values()].filter(t=>t.repeat).length}
 };
}
function nodes(tree){if(Array.isArray(tree))return tree.flatMap(nodes);if(!tree||typeof tree!=='object')return [];return [tree,...nodes(tree.props?.children)]}
function text(tree){if(Array.isArray(tree))return tree.map(text).join(' ');return tree&&typeof tree==='object'?text(tree.props?.children):typeof tree==='string'?tree:''}
function button(h,label){return nodes(h.tree()).find(n=>n.type==='button'&&text(n)===label)}
async function open(h){button(h,'继续已有预览 / 批量导入').props.onClick();await h.settle()}

// Native snapshot: /folders finishes quickly, the unrelated catalog takes >2s.
let rows=[{...completed,status:'RUNNING',candidates:[]}],summaryCalls=0;
const h=host(url=>url.endsWith('/folders')?{value:rows}:{value:catalog,delay:summaryCalls++?3240:0});
await h.start();await open(h);assert.match(text(h.tree()),/正在扫描/);
rows=[completed];await h.advance(10000);
assert(nodes(h.tree()).some(n=>n.type==='h3'&&text(n)==='预览完成'),
 'COMPLETED + REVIEW_REQUIRED must render despite a catalog response slower than the polling interval');
assert(nodes(h.tree()).some(n=>n.type==='h4'&&text(n)==='synthetic-review.mp4'),'Actual captured candidate must be visible for human review');
assert(!h.calls.some(c=>c.url.endsWith('/confirm')),'Preview must not auto-register');
h.unmount();

// A full remount (same QA session) restores the persisted preview without POST.
const restored=host(url=>({value:url.endsWith('/folders')?[completed]:catalog}));
await restored.start();await open(restored);
assert.match(text(restored.tree()),/synthetic-review\.mp4/);
assert(button(restored,'确认授权并登记播放').props.disabled,'Saved preview cannot grant human consent');
assert(!restored.calls.some(c=>c.options?.method==='POST'),'Refresh must not start a new scan or registration');
const readsAfterRestore=restored.calls.length;await restored.advance(10000);
assert.equal(restored.calls.length,readsAfterRestore,'COMPLETED must stop polling');restored.unmount();

// Slow /folders responses are serialized too, never accumulating duplicate polls.
let slowReads=0;
const slow=host(url=>url.endsWith('/folders')
 ?{value:slowReads++?[completed]:[{...completed,status:'QUEUED',candidates:[]}],delay:slowReads>1?6000:0}
 :{value:catalog});
await slow.start();await open(slow);assert.match(text(slow.tree()),/等待扫描/);
await slow.advance(7000);assert.equal(slowReads,2,'One scan request at a time');
await slow.advance(10000);assert.match(text(slow.tree()),/预览完成/);assert.equal(slowReads,2);slow.unmount();

// FAILED is a terminal failure, not a completed empty scan or auto registration.
let failedRows=[{...completed,status:'RUNNING',candidates:[]}];
const failed=host(url=>({value:url.endsWith('/folders')?failedRows:catalog}));
await failed.start();await open(failed);
failedRows=[{...completed,status:'FAILED',candidates:[],errors:['所选视频已移动或路径改变'],message:'读取失败'}];
await failed.advance(2000);assert.match(text(failed.tree()),/扫描失败/);
assert.match(text(failed.tree()),/所选视频已移动或路径改变/);assert.doesNotMatch(text(failed.tree()),/发现 0 个/);
const afterFailure=failed.calls.length;await failed.advance(8000);assert.equal(failed.calls.length,afterFailure);failed.unmount();

// A late response from the departed page cannot overwrite the recovered terminal state.
let raceReads=0;
const race=host(url=>url.endsWith('/folders')
 ?{value:++raceReads<3?[{...completed,status:'RUNNING',candidates:[]}]:[completed],delay:raceReads===2?6000:0}
 :{value:catalog});
await race.start();await open(race);await race.advance(2000);await race.revise();
assert.match(text(race.tree()),/预览完成/);await race.advance(10000);
assert(nodes(race.tree()).some(n=>n.type==='h3'&&text(n)==='预览完成'),'Old RUNNING must not replace new COMPLETED');
race.unmount();const afterUnmount=race.calls.length;await race.advance(10000);assert.equal(race.calls.length,afterUnmount);

// A rejected refresh is visible, retried serially, and cannot claim an empty list.
let denied=false,permissionRows=[{...completed,status:'RUNNING',candidates:[]}];
const permission=host(url=>url.endsWith('/folders')&&denied
 ?{status:403,value:{detail:'HTTP 403：预览读取被拒绝'}}:{value:url.endsWith('/folders')?permissionRows:catalog});
await permission.start();await open(permission);denied=true;await permission.advance(2000);
assert.match(text(permission.tree()),/HTTP 403/);assert.doesNotMatch(text(permission.tree()),/发现 0 个/);
denied=false;permissionRows=[completed];await permission.advance(2000);assert.match(text(permission.tree()),/预览完成/);permission.unmount();

function inputInLabel(h,pattern,type){const label=nodes(h.tree()).find(n=>n.type==='label'&&pattern.test(text(n)));assert(label,`Missing label ${pattern}`);return nodes(label).find(n=>n.type===type)}
// Drive the real single-file picker, POST /files, preview and explicit review gate.
let importRows=[],confirmCalls=0,denyConfirmation=true;
const imported=host((url,options)=>{
 if(url.endsWith('/files')){assert.equal(options.method,'POST');assert.equal(JSON.parse(options.body).path,completed.selected_file);importRows=[{...completed,status:'QUEUED',candidates:[]}];return {value:importRows[0]}}
 if(url.endsWith('/confirm')){confirmCalls++;return denyConfirmation?{status:400,value:{detail:'录像路径已改变，请重新核对'}}:{value:{video_id:'synthetic-registered'}}}
 return {value:url.endsWith('/folders')?importRows:catalog};
});
await imported.start();button(imported,'选择本地视频').props.onClick();await imported.settle();
inputInLabel(imported,/我确认可以在本机读取/,'input').props.onChange({target:{checked:true}});await imported.settle();
const readButton=button(imported,'读取视频并预览');const reading=readButton.props.onClick();readButton.props.onClick();await reading;await imported.settle();
assert.equal(imported.calls.filter(c=>c.url.endsWith('/files')).length,1,'Repeated click must not start two scans');
assert.match(text(imported.tree()),/等待扫描/);importRows=[{...completed,status:'RUNNING',candidates:[]}];await imported.advance(2000);
assert.match(text(imported.tree()),/正在扫描/);importRows=[completed];await imported.advance(2000);
assert.match(text(imported.tree()),/预览完成/);assert.match(text(imported.tree()),/synthetic-review\.mp4/);
assert.equal(confirmCalls,0);assert(button(imported,'确认授权并登记播放').props.disabled);
inputInLabel(imported,/^权利状态/,'select').props.onChange({target:{value:'LICENSED_FOR_ANALYSIS'}});await imported.settle();
inputInLabel(imported,/^来源 \/ 许可说明/,'textarea').props.onChange({target:{value:'本人制作，允许本机分析'}});await imported.settle();
assert(button(imported,'确认授权并登记播放').props.disabled,'Rights text is not consent');
inputInLabel(imported,/我确认上述来源/,'input').props.onChange({target:{checked:true}});await imported.settle();
assert.equal(button(imported,'确认授权并登记播放').props.disabled,false);
await button(imported,'确认授权并登记播放').props.onClick();await imported.settle();
assert.match(text(imported.tree()),/录像路径已改变/);assert.equal(confirmCalls,1);
// Rights changes revoke consent; the failed confirmation cannot count as registered.
inputInLabel(imported,/^权利状态/,'select').props.onChange({target:{value:'PERSONAL_VIEW_ONLY'}});await imported.settle();
assert(button(imported,'确认授权并登记播放').props.disabled);
inputInLabel(imported,/我确认上述来源/,'input').props.onChange({target:{checked:true}});await imported.settle();denyConfirmation=false;
const registerButton=button(imported,'确认授权并登记播放'),registering=registerButton.props.onClick();registerButton.props.onClick();await registering;await imported.settle();
assert.equal(confirmCalls,2,'Double click while registration is pending must issue only one new confirmation');imported.unmount();

// Batch folder entry uses the same transition/recovery path as a single file.
let folderRows=[];
const folder=host((url,options)=>{
 if(url.endsWith('/folders')&&options?.method==='POST'){folderRows=[{...completed,selected_file:undefined,status:'RUNNING',candidates:[]}];return {value:folderRows[0]}}
 return {value:url.endsWith('/folders')?folderRows:catalog};
});
await folder.start();await open(folder);
inputInLabel(folder,/文件夹完整路径/,'input').props.onChange({target:{value:'C:/isolated-synthetic-fixture'}});await folder.settle();
inputInLabel(folder,/我确认可以在本机读取/,'input').props.onChange({target:{checked:true}});await folder.settle();
await button(folder,'读取视频并预览').props.onClick();await folder.settle();folderRows=[{...completed,selected_file:undefined}];await folder.advance(2000);
assert.match(text(folder.tree()),/预览完成/);assert.match(text(folder.tree()),/synthetic-review\.mp4/);folder.unmount();
console.log('8 component scenarios PASS: slow catalog, restore, serialized polling, FAILED, stale response/unmount, HTTP error, single-file/consent/path failure/duplicate click, folder parity');
