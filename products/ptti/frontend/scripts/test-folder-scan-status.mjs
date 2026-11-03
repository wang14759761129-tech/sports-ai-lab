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
const {folderScanCountText,pendingVideoReviews,canRegisterLocalVideo,selectFolderPreview,updateVideoReview}=module.exports;

assert.equal(folderScanCountText('QUEUED',0),'扫描尚未完成，媒体数量将在完成后显示');
assert.equal(folderScanCountText('RUNNING',0),'扫描尚未完成，媒体数量将在完成后显示');
assert.equal(folderScanCountText('COMPLETED',0),'发现 0 个支持的媒体文件');
assert.equal(folderScanCountText('COMPLETED',1),'发现 1 个支持的媒体文件');
assert.equal(folderScanCountText('FAILED',0),'预览未完成，请查看错误提示后重试');
assert.equal(folderScanCountText('INTERRUPTED',1),'预览已中断，保留 1 个已读取文件');
assert.equal(pendingVideoReviews({candidates:[{}, {registered_video_id:'v'}, {duplicate_of_candidate_id:'c'}]}),1);
assert.equal(pendingVideoReviews({}),0);
assert.equal(canRegisterLocalVideo({rights_confirmed:true,rights_status:'PERSONAL_VIEW_ONLY',source_note:'本人制作的测试录像'}),true);
assert.equal(canRegisterLocalVideo({rights_confirmed:false,rights_status:'LICENSED_FOR_ANALYSIS',source_note:'获授权'}),false);
assert.equal(canRegisterLocalVideo({rights_confirmed:true,rights_status:'PENDING_REVIEW',source_note:'待核实'}),false);
assert.equal(canRegisterLocalVideo({rights_confirmed:true,rights_status:'LICENSED_FOR_ANALYSIS',source_note:'来源待逐条核实'}),false);
assert.equal(canRegisterLocalVideo({rights_confirmed:true,rights_status:'INVENTED',source_note:'说明'}),false);
assert.equal(canRegisterLocalVideo({rights_confirmed:true,rights_status:'LICENSED_FOR_ANALYSIS',source_note:'  '}),false);
const empty={scan_id:'new',status:'COMPLETED',candidates:[]},pending={scan_id:'old',status:'COMPLETED',candidates:[{}]};
assert.equal(selectFolderPreview([empty,pending],'').scan_id,'old','Older unregistered preview must remain reachable');
assert.equal(selectFolderPreview([empty,pending],'new').scan_id,'new','Explicit selection must be respected');
assert.equal(selectFolderPreview([],''),undefined);
assert.equal(updateVideoReview({rights_confirmed:true},{rights_status:'LICENSED_FOR_ANALYSIS'}).rights_confirmed,false);
assert.equal(updateVideoReview({rights_confirmed:true},{source_note:'新的许可说明'}).rights_confirmed,false);
assert.equal(updateVideoReview({rights_confirmed:true},{title:'标题'}).rights_confirmed,true);
console.log('20 passed, 0 failed: scan status, recovery selection and explicit rights confirmation');
