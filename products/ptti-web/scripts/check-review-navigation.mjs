import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const src = readFileSync(new URL('../src/LocalVideoReview.tsx', import.meta.url), 'utf8').replace(/\r\n/g, '\n');
const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8').replace(/\r\n/g, '\n');
assert.match(app, /navigationKey=\{`\$\{page\}:\$\{proFocus\}`\}/);
const body = src.match(/useEffect\(\(\) => \{\n(    if \(previousNavigationRef[\s\S]*?)\n  \}, \[navigationKey\]\)/)?.[1];
assert.ok(body, 'execute the actual navigation effect body');
const run = new Function('previousNavigationRef','navigationKey','cancelPlaylist','controllerRef','setNavigationPaused',body);
const ref={current:'cinema:insight'}, calls=[];
let hint=false; const controller={current:{getSnapshot(){return {is_playing:true};},pause(){calls.push('pause');}}};
const setHint=value=>{hint=value;};
const cancel=()=>calls.push('cancel');
run(ref,'cinema:insight',cancel,controller,setHint); assert.deepEqual(calls,[]);
for (const key of ['pro:insight','pro:review','cinema:review']) {
 calls.length=0; run(ref,key,cancel,controller,setHint); assert.deepEqual(calls,['cancel','pause']); assert.equal(ref.current,key); assert.equal(hint,true);
}
controller.current.getSnapshot=()=>({is_playing:false});
run(ref,'pro:review',cancel,controller,setHint); assert.equal(hint,false);
assert.doesNotMatch(body,/setComparisonNote|setSession|revokeObjectURL|destroy/);
const exportBody=src.match(/function exportComparisonNotes\(\) \{([\s\S]*?)\n  \}\n\n  function pausePlaylist/)?.[1];
assert.ok(exportBody);
let issue=''; const note='<script>plain text</script>'; const session={session_id:'local-session:test'}; const targets={};
const invoke=new Function('targetsActive','targetsRef','targets','activeTarget','session','points','playbackBindings','comparisonNote','createReviewComparisonExport','setPlaylistIssueKey',exportBody);
invoke(true,{current:targets},targets,{},session,[],[],note,()=>{throw Error('download unavailable');},v=>{issue=v;});
assert.equal(issue,'pro.targets.exportError'); assert.doesNotMatch(exportBody,/setComparisonNote/);
console.log('GOAL12.5 PASS: unchanged route no-op; Cinema/Insight/Review cancel then pause; media and notes preserved; export failure visible without clearing note. Node checks, not browser evidence.');
