import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import vm from 'node:vm';

const require=createRequire(import.meta.url);
const ts=require('typescript');
const source=readFileSync(new URL('../src/folderScanStatus.ts',import.meta.url),'utf8');
const code=ts.transpileModule(source,{
 compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}
}).outputText;
const module={exports:{}};
vm.runInNewContext(code,{module,exports:module.exports});
const {folderScanCountText}=module.exports;

assert.equal(folderScanCountText('QUEUED',0),'扫描尚未完成，媒体数量将在完成后显示');
assert.equal(folderScanCountText('RUNNING',0),'扫描尚未完成，媒体数量将在完成后显示');
assert.equal(folderScanCountText('COMPLETED',0),'发现 0 个支持的媒体文件');
assert.equal(folderScanCountText('COMPLETED',1),'发现 1 个支持的媒体文件');
console.log('4 passed, 0 failed: pending scans do not appear as zero-file results');
