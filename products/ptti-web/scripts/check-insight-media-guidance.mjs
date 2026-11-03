import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import ts from 'typescript';
import { renderToStaticMarkup } from 'react-dom/server';
import { createElement } from 'react';
const require=createRequire(import.meta.url);
const root=new URL('../src/',import.meta.url);
function loadTs(name, imports={}) {
 const source=fs.readFileSync(new URL(name,root),'utf8');
 const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022}}).outputText;
 const module={exports:{}}; new Function('require','module','exports',js)(id=>imports[id]??require(id),module,module.exports); return module.exports;
}
const i18n=loadTs('i18n.ts');const {LocalMediaEmptyState}=loadTs('LocalMediaEmptyState.tsx',{'./i18n':i18n});
let clicks=0,returns=0;const input={click(){clicks++;}};
const buttons=node=>!node||typeof node!=='object'?[]:[...(node.type==='button'?[node]:[]),...[node.props?.children].flat(Infinity).flatMap(buttons)];
for(const locale of ['zh-CN','en']) {
 const props={locale,simulated:true,onSelect:()=>input.click(),onCinema:()=>returns++};
 const html=renderToStaticMarkup(createElement(LocalMediaEmptyState,props));
 assert.match(html,/SIMULATED_ONLY/);assert.doesNotMatch(html,/<video/);assert.match(html,/data-return-cinema/);
 assert(html.includes(i18n.message(locale,'pro.media.demoNoVideo'))); assert(html.includes(i18n.message(locale,'pro.media.demoBinding')));
 const [select,back]=buttons(LocalMediaEmptyState(props));select.props.onClick();back.props.onClick();
 const normal=renderToStaticMarkup(createElement(LocalMediaEmptyState,{...props,simulated:false}));assert.doesNotMatch(normal,/SIMULATED_ONLY|data-return-cinema/);
}
assert.equal(clicks,2);assert.equal(returns,2);
// Execute the actual existing file-change handler. Cancelling must return before
// referencing any session/data/notes setters, which are deliberately not supplied.
const source=fs.readFileSync(new URL('LocalVideoReview.tsx',root),'utf8');
const ast=ts.createSourceFile('LocalVideoReview.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);let handler;
function visit(node){if(ts.isFunctionDeclaration(node)&&node.name?.text==='handleFileChange')handler=node;ts.forEachChild(node,visit);}visit(ast);assert(handler);
const handlerJS=ts.transpileModule(handler.getText(ast),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText;
const handle=new Function(handlerJS+'; return handleFileChange;')();
for(const files of [null,[]]){const target={files,value:'old'};assert.doesNotThrow(()=>handle({currentTarget:target}));assert.equal(target.value,'');}
assert.match(source,/simulated=\{importedDraft\?\.dataset_class === 'SIMULATED_ONLY'\}/);
assert.match(source,/onSelect=\{\(\) => fileInputRef\.current\?\.click\(\)\}/);
const css=fs.readFileSync(new URL('style.css',root),'utf8');assert.match(css,/local-media-empty-actions[\s\S]*flex-wrap: wrap/);assert.match(css,/min-height: 44px/);
console.log('PASS: zh/en simulated and ordinary empty-state React rendering; no video element; select/return actions invoke callbacks; actual cancelled-file handler has no data/session/note mutations; responsive CSS contract. Browser chooser and390px geometry NOT_TESTED.');

// Use the actual imported Golden records with the new visibility condition.
const {importQuickAnnotationDraft}=await import('../src/local-video-review.mjs');
const golden=JSON.parse(fs.readFileSync(new URL('fixtures/review-targets/quick-input.json',import.meta.url),'utf8'));
const imported=importQuickAnnotationDraft(golden);assert.equal(imported.ok,true);
const show=source.match(/\{\((session \|\| points\.length > 0)\) && <div className=\{`local-video-player-layout/);assert(show);
const visible=new Function('session','points','return Boolean('+show[1]+');');
assert.equal(visible(null,imported.value.points),true);assert.equal(visible(null,[]),false);
assert.match(source,/\{session && <div className="local-video-player-column">/);
assert.match(source,/data-review-targets-panel[\s\S]*?data-insight-media-guidance/);
console.log('PASS: actual19-point Golden import keeps analysis visible without session; video column remains session-gated; guidance exists at Insight scroll destination.');
