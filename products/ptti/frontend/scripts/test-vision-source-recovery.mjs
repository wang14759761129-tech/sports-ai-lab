import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import vm from 'node:vm';

// Execute the actual component with a tiny deterministic hook host. This tests
// source loading/rendering, not browser media decoding or native GUI acceptance.
const require=createRequire(process.env.PTTI_FRONTEND_DEPENDENCIES_ROOT
 ? `${process.env.PTTI_FRONTEND_DEPENDENCIES_ROOT}/package.json` : import.meta.url);
const ts=require('typescript');
const code=ts.transpileModule(readFileSync('src/VisionPlayer.tsx','utf8'),{
 compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022}
}).outputText;
function host(fetch){
 const slots=[],effects=[],pending=[];let cursor=0;
 const hooks={useState(initial){const i=cursor++;if(!(i in slots))slots[i]=initial;return [slots[i],value=>{slots[i]=typeof value==='function'?value(slots[i]):value}]},
 useRef(value){const i=cursor++;return slots[i]??(slots[i]={current:value})},
 useEffect(fn,deps){const i=cursor++;if(!effects[i]||deps.some((v,j)=>v!==effects[i].deps[j]))pending.push(()=>{effects[i]?.cleanup?.();effects[i]={deps,cleanup:fn()}})}};
 const jsx=(type,props)=>({type,props});const module={exports:{}};
 vm.runInNewContext(code,{module,exports:module.exports,AbortController,fetch,
 require(name){if(name==='react')return hooks;if(name==='react/jsx-runtime')return {jsx,jsxs:jsx};if(name==='./ui')return {Modal:'modal'};throw Error(name)}});
 return {render(){cursor=0;const tree=module.exports.default({onCinema(){}});pending.splice(0).forEach(fn=>fn());return tree},unmount(){effects.forEach(e=>e?.cleanup?.())}};
}
function nodes(tree){if(!tree||typeof tree!=='object')return [];return [tree,...[tree.props?.children].flat(Infinity).flatMap(nodes)]}
function texts(tree){if(Array.isArray(tree))return tree.map(texts).join(' ');if(tree&&typeof tree==='object')return texts(tree.props?.children);return typeof tree==='string'?tree:''}
const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve()};
const game={video_id:'authorized-game-1',title:'game_1',rights_status:'RESEARCH_NONCOMMERCIAL',availability_status:'AVAILABLE',source_sha256:'1297b3db91f2e3e160337643695dff07eabf9785ea2d88c2f7b59687ba511148',hash_status:'VERIFIED',fps:120};
const evidence=JSON.parse(readFileSync('../reports/PLAYBACK_SPRINT_0_3_SOURCE_EVIDENCE.json','utf8'));
const captured=host(async()=>({ok:true,json:async()=>evidence.videos}));captured.render();await flush();
assert(nodes(captured.render()).some(n=>n.type==='option'&&n.props.value==='35d991ea-e610-487c-985a-7d5bf949ba5f'),'Actual isolated QA API source must appear in the Vision component');captured.unmount();
let resolve;const loading=host(()=>new Promise(r=>{resolve=r}));
assert.doesNotMatch(texts(loading.render()),/当前没有已登记/,'Pending request must not claim there are no registered sources');
resolve({ok:true,json:async()=>[game,{...game,video_id:'watch-only',rights_status:'REFERENCE_ONLY'}]});await flush();
let tree=loading.render();assert(nodes(tree).some(n=>n.type==='option'&&n.props.value===game.video_id));
assert(!nodes(tree).some(n=>n.type==='option'&&n.props.value==='watch-only'),'Rights gate must stay intact');
const selector=nodes(tree).find(n=>n.type==='select');selector.props.onChange({target:{value:game.video_id}});
tree=loading.render();assert.equal(nodes(tree).find(n=>n.type==='video').props.src,`/api/video-evidence/videos/${game.video_id}/media`);
assert(nodes(tree).some(n=>n.type==='button'&&n.props.disabled&&texts(n)==='Analysis View · 暂不可用'));
for(const failure of [async()=>({ok:false,status:403}),async()=>{throw Error('Network unavailable')},async()=>({ok:true,json:async()=>({videos:[game]})})]){
 let calls=0;const failed=host((...args)=>{calls++;return calls===1?failure(...args):Promise.resolve({ok:true,json:async()=>[game]})});
 failed.render();await flush();tree=failed.render();assert.doesNotMatch(texts(tree),/当前没有已登记/,'Failed request must not be rendered as an empty database');
 assert(nodes(tree).some(n=>n.props?.role==='alert'));
 if(calls===1&&(await failure().catch(()=>null))?.status===403)assert.match(texts(tree),/HTTP 403/);
 const retry=nodes(tree).find(n=>n.type==='button'&&texts(n)==='重试来源');assert(retry,'Fetch failure needs an explicit recovery action');retry.props.onClick();failed.render();await flush();tree=failed.render();
 assert(nodes(tree).some(n=>n.type==='option'&&n.props.value===game.video_id));failed.unmount();
}
const empty=host(async()=>({ok:true,json:async()=>[]}));empty.render();await flush();assert.match(texts(empty.render()),/当前没有已登记/);empty.unmount();
let finish,signal;const departed=host((_url,options)=>{signal=options.signal;return new Promise(resolve=>{finish=resolve})});departed.render();departed.unmount();assert.equal(signal.aborted,true);finish({ok:true,json:async()=>[game]});await flush();assert(!nodes(departed.render()).some(n=>n.type==='option'&&n.props.value===game.video_id),'Late response after unmount must not update source state');
loading.unmount();console.log('Vision source recovery: loading, authorized selection, rights/analysis gates, HTTP/network/schema errors, retry and confirmed empty passed');
