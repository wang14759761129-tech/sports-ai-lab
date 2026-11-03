import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { Children, createElement } from 'react';
const root = new URL('../', import.meta.url);
const out = new URL('.alpha-qa/goal61-64/', root); await mkdir(out, {recursive:true});
const hooks = `let values=[], cursor=0; export function reset(clear=false){cursor=0;if(clear)values=[]} export function useState(initial){const i=cursor++;if(!(i in values))values[i]=initial;return [values[i], v=>values[i]=typeof v==='function'?v(values[i]):v]} export function useRef(){return {current:null}} export function useId(){return 'qa-secondary'}`;
const result = await build({stdin:{contents:`export {PrivateTheaterFrame} from './src/PrivateTheaterFrame'; export {MomentumRiver} from './src/MomentumRiver'; export {createSimulatedDemoReport} from './src/personal-match-report.mjs'; export {reset} from 'react';`,resolveDir:fileURLToPath(root),loader:'tsx'},bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',write:false,plugins:[{name:'controlled-hooks',setup(b){b.onResolve({filter:/^react$/},()=>({path:'hooks',namespace:'qa'}));b.onLoad({filter:/.*/,namespace:'qa'},()=>({contents:hooks,loader:'js'}));}}]});
const target = new URL('kit.mjs',out);await writeFile(target,result.outputFiles[0].contents);
const {PrivateTheaterFrame, MomentumRiver,createSimulatedDemoReport,reset}=await import(target.href+'?'+Date.now());
function walk(node, predicate){if(!node || typeof node!=='object')return null;if(predicate(node))return node;for(const child of Children.toArray(node.props?.children)){const found=walk(child,predicate);if(found)return found;}return null;}
for(const locale of ['zh-CN','en']){
 reset(true);const main=createElement('div',{'data-stable-source':'same'},'unchanged source');const props={locale,sourceId:'synthetic-test',main,secondary:createElement('input',{defaultValue:'unsaved'}),onBack(){}};
 const render=()=>{reset();return PrivateTheaterFrame(props)};let view=render();
 const button=value=>walk(view.props.main,n=>n.type==='button' && n.props.children===value);
 button('Cinema').props.onClick();view=render();assert.equal(view.props.focused,true);assert.equal(walk(view.props.main,n=>n.type==='input').props.disabled,true);assert(walk(view.props.main,n=>n.props?.className==='theater-booth-hint'));
 view.props.onExitFocus();view=render();assert.equal(view.props.focused,false);
 button('Intelligence').props.onClick();view=render();assert.equal(walk(view.props.main,n=>n.type==='aside').props.hidden,false);
 walk(view.props.main,n=>n.type==='input').props.onChange({target:{checked:false}});view=render();assert.equal(walk(view.props.main,n=>n.type==='aside').props.hidden,true);
 const selectors=[];function collect(n){if(!n||typeof n!=='object')return;if(n.type==='select')selectors.push(n);Children.toArray(n.props?.children).forEach(collect)}collect(view.props.main);
 selectors[0].props.onChange({target:{value:'balanced'}});selectors[1].props.onChange({target:{value:'before'}});view=render();assert.equal(view.props.main.props['data-panel-ratio'],'balanced');assert.equal(view.props.main.props['data-panel-position'],'before');
 assert.equal(walk(view.props.main,n=>n.props?.className==='theater-main').props.children,main);assert.equal(view.props.secondary,props.secondary);
 walk(view.props.main,n=>n.type==='button' && n.props.children===(locale==='zh-CN'?'恢复默认布局':'Reset layout')).props.onClick();view=render();assert.equal(view.props.main.props['data-layout-mode'],'fan');assert.equal(view.props.main.props['data-panel-position'],'after');assert.equal(view.props.main.props['data-panel-ratio'],'wide');
 reset(true);view=render();assert.equal(view.props.main.props['data-panel-position'],'after');
 const report=createSimulatedDemoReport();const river=MomentumRiver({report,locale});assert.equal(river.props['data-evidence'],'SIMULATED_DEMO');
 const manual=structuredClone(report);manual.source.type='USER_MANUAL';manual.calculated_results.score_progression=[];
 const empty=MomentumRiver({report:manual,locale});assert.equal(empty.props['data-evidence'],'MANUAL_NOT_VERIFIED');assert.equal(walk(empty,n=>n.type==='svg'),null);
 const polygon=walk(river,n=>n.type==='polygon');assert.equal(polygon.props.points.split(' ').length,report.calculated_results.score_progression.length+2);assert(walk(river,n=>n.type==='linearGradient'));
 const polyline=walk(river,n=>n.type==='polyline');assert.equal(polyline.props.points.split(' ').length,report.calculated_results.score_progression.length+1);
}
console.log('PASS GOAL61–64: bilingual controlled-hook layout events, Cinema exit, panel visibility/ratio/order/reset, stable main/secondary identity; synthetic/manual labels, empty river and exact point count. DOM focus, responsive visuals and playback NOT_TESTED.');

const css=await readFile(new URL('src/fan-gold.css',root),'utf8');for(const token of ['--ptti-cinema-gold','max-aspect-ratio:8/5','max-width:440px','prefers-reduced-motion:reduce'])assert(css.includes(token));console.log('PASS GOAL72: bilingual layout reset, exact score-derived river fill, preserved source identity and scoped responsive/reduced-motion tokens. Actual visuals NOT_TESTED.');
