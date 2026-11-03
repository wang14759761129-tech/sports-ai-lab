// Read-only inventory. Never copies or changes another worktree or mounts a UI.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const root=process.argv[2];
if(!root)throw Error('Usage: node scripts/inspect-arena-reuse.mjs <existing-San-worktree>');
const cwd=resolve(root),git=(...args)=>execFileSync('git',['-C',cwd,...args],{encoding:'utf8'}).trim();
const names=['ArenaChallengePage.tsx','PersonalArenaChallenge.tsx','arena-challenge.mjs','arena-challenge.d.mts'];
const files=names.map(name=>{
 const path=`products/ptti-web/src/${name}`;
 assert.equal(git('status','--porcelain','--',path),'',`Cannot pin uncommitted source: ${path}`);
 const bytes=readFileSync(join(cwd,path));
 return {path,sha256:createHash('sha256').update(bytes).digest('hex')};
});
const arena=await import(pathToFileURL(join(cwd,'products/ptti-web/src/arena-challenge.mjs')));
let state=arena.createArenaChallengeState();
assert.equal(state.selectedChoice,null);
state=arena.reduceArenaChallenge(state,{type:'choose',choice:'active-flick'});
assert.equal(state.selectedChoice,'active-flick');
assert.equal(arena.createArenaLearningTakeaway('unregistered-choice'),null);
const takeaway=arena.createArenaLearningTakeaway('active-flick');
assert.ok(takeaway&&takeaway.simulated);
assert.ok(!Object.keys(takeaway).some(key=>/match_id|source_id|video|point_id/i.test(key)));
console.log(JSON.stringify({schema:'ptti.arena-reuse-inventory/0.1',audience:'INTERNAL_REVIEW_ONLY',source_commit:git('rev-parse','HEAD'),files,
 existing_capabilities:['three-choice hypothetical tactic exercise','retry','learning takeaway','copy recovery','SIMULATED_ONLY separation'],
 dependencies:['San i18n message/Locale/MessageKey','San arena CSS classes','optional onOpenJournal (leave disconnected in R4)'],
 r4_integration:{status:'NOT_INTEGRATED',mount:'secondary workspace under VideoFeed, reuse WorkspaceFrame',props:['onBack: () => void'],return_state:'same mounted VideoFeed query/filters/scroll; do not replace Cinema',blocked_on:'portable component and localized copy/style handoff; no source-tree copy'},
 safety:{real_match_binding:'NOT_ALLOWED_WITHOUT_VERIFIED_INPUT',media_or_journal_write:'NONE',new_persistence:'NONE'},
 checks:{existing_reducer:'PASS',unknown_choice:'PASS',simulated_takeaway:'PASS',gui:'NOT_TESTED'}},null,2));
