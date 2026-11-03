import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  bindLegacyNote, createNote, createVideoIdentity, deleteNote, exportNotes, filterNotesByVideo,
  formatTimestamp, legacyNotes, loadNotes, loadNotesState, parseTimestamp, resolveSeek,
  saveNotes, updateNote, writeNotes,
} from '../src/proLabNotes.mjs';

assert.equal(parseTimestamp('12:34'), 754);
assert.equal(parseTimestamp('1:02:03'), 3723);
assert.equal(parseTimestamp('12:60'), null);
assert.equal(formatTimestamp(754), '12:34');
assert.equal(resolveSeek(781, 600), 600);
assert.equal(resolveSeek(100, 600), 100);
assert.equal(resolveSeek(-1, 600), null);

const fileA = {name:'training.mp4',size:120000,lastModified:1761450000000,type:'video/mp4'};
const fileB = {name:'training.mp4',size:180000,lastModified:1761450000000,type:'video/mp4'};
const identityA = createVideoIdentity(fileA);
const identityB = createVideoIdentity(fileB);
assert.notEqual(identityA.key,identityB.key,'same-name files with different metadata have distinct identities');

const memory = new Map();
const store = {getItem:k=>memory.get(k)??null,setItem:(k,v)=>memory.set(k,v)};
let r=createNote([],{videoIdentity:identityA,timestamp:'12:34',tags:'发球, 关键分',coachNote:'备注 <b>保留为文本</b>'});
assert.equal(r.errors.length,0);
assert.equal(r.notes[0].seconds,754);
assert.equal(r.notes[0].videoIdentity.key,identityA.key);
assert.equal(filterNotesByVideo(r.notes,identityA).length,1);
assert.equal(filterNotesByVideo(r.notes,identityB).length,0,'notes do not cross-link to a different same-name recording');
assert.equal(saveNotes(store,r.notes).ok,true);
assert.equal(loadNotes(store).length,1);

const bad=createNote(r.notes,{videoIdentity:identityA,timestamp:'12:34',tags:'',coachNote:''});
assert.ok(bad.errors.length>=1,'a note without a tactical tag is rejected');
let edited=updateNote(r.notes,r.notes[0].id,{videoIdentity:identityA,timestamp:'13:01',tags:'关键分',coachNote:'修改后的观察'});
assert.equal(edited.notes[0].seconds,781);
assert.equal(edited.notes[0].coachNote,'修改后的观察');
const exported=exportNotes(edited.notes);
assert.equal(exported.version,'ptti.pro-lab-notes/0.2');
assert.equal(exported.noteCount,1);
assert.equal(exported.notes[0].timestamp,'13:01');
assert.equal(exported.notes[0].videoIdentity.key,identityA.key);
assert.ok(!JSON.stringify(exported).includes('data:video'),'export excludes video bytes');
assert.ok(!JSON.stringify(exported).includes('C:\\\\'),'export excludes filesystem paths');
assert.equal(deleteNote(edited.notes,edited.notes[0].id).length,0);

const oldNote={id:'legacy-1',videoName:'training.mp4',seconds:20,tags:['发球'],coachNote:'旧版文件名笔记',createdAt:new Date(1).toISOString(),updatedAt:new Date(1).toISOString()};
assert.equal(legacyNotes([oldNote]).length,1);
assert.equal(filterNotesByVideo([oldNote],identityA).length,0,'legacy filename-only notes are never silently attached');
const rebound=bindLegacyNote([oldNote],oldNote.id,identityA);
assert.equal(rebound.errors.length,0);
assert.equal(filterNotesByVideo(rebound.notes,identityA).length,1,'user-confirmed rebind is exact');

let writes=0;
const counted={getItem:k=>memory.get(k)??null,setItem:(k,v)=>{writes++;memory.set(k,v)}};
const initial=loadNotesState(counted);
const strictModeRerun=loadNotesState(counted);
assert.equal(initial.notes.length,1);
assert.equal(strictModeRerun.notes.length,1);
assert.equal(writes,0,'initialization/re-mount reads do not overwrite existing records');
assert.equal(loadNotesState({getItem:()=>'{bad',setItem:()=>{}}).writable,false,'corrupt raw storage closes writes');
assert.equal(writeNotes(undefined,[]).ok,false,'missing storage reports failure');
assert.match(writeNotes({setItem:()=>{const e=Error('quota');e.name='QuotaExceededError';throw e}},r.notes).error,/空间不足/);
assert.equal(writeNotes({setItem:()=>{throw Error('blocked')}},r.notes).ok,false);
assert.equal(saveNotes({setItem:()=>{throw Error('blocked')}},r.notes).ok,false);

const component=readFileSync(new URL('../src/ProLab.tsx',import.meta.url),'utf8');
assert.ok(component.includes('video.pause()'),'capture action pauses the actual media element');
assert.ok(component.includes('readyState'),'capture requires loaded media metadata');
assert.ok(component.includes('isNoteBoundToVideo(note,selection.identity)'),'seek/edit actions require exact selected-file metadata');
assert.ok(component.includes('loadedIdentityKey.current!==selection.identity.key'),'seek rejects a file that has not loaded as the current selection');
assert.ok(component.includes("if(!result.ok){setError(result.error);setStatus('');return false;}"),'failed persistence leaves the saved view state unchanged');
assert.ok(component.includes('setStorage(current=>({...current,notes:next'),'view state changes only after persistence succeeds');
assert.ok(!component.includes('useEffect(()=>{try{setNotes'),'initial notes are not loaded after an empty render');
assert.ok(!component.includes('useEffect(()=>{try{saveNotes'),'mount does not auto-save initial state');
assert.ok(component.includes('笔记已保存在本机。'),'successful persistence is explicit');
assert.ok(component.includes('role="alert"'),'storage and validation failures are announced');
assert.ok(!component.includes('fetch('),'local video is not uploaded');
const demo=readFileSync(new URL('../../qa/pro-lab-demo/render.mjs',import.meta.url),'utf8');
assert.ok(!demo.includes('innerHTML'),'QA renderer has no HTML sink');
assert.ok(demo.includes('textContent'),'QA renderer inserts untrusted fields as text');
const {renderNotes}=await import('../../qa/pro-lab-demo/render.mjs');
class FakeElement{constructor(tag){this.tagName=tag;this.children=[];this.textContent='';this.className='';}append(...nodes){this.children.push(...nodes)}replaceChildren(...nodes){this.children=nodes}}
const document={createElement:tag=>new FakeElement(tag),createDocumentFragment:()=>new FakeElement('#fragment')};
const hostile=createNote([],{videoIdentity:identityA,timestamp:'00:20',tags:['<svg/onload=alert(1)>'],coachNote:'<img src=x onerror=alert(1)>'}).notes;
const host=new FakeElement('div');renderNotes(document,host,hostile,identityA);
const rendered=[];function walk(node){rendered.push(node);node.children.forEach(walk)}walk(host);
assert.ok(rendered.some(node=>node.textContent==='<img src=x onerror=alert(1)>'));
assert.ok(rendered.some(node=>node.textContent==='#<svg/onload=alert(1)>'));
assert.ok(!rendered.some(node=>['script','img','svg'].includes(node.tagName)),'hostile note fields remain text nodes');

console.log('Pro Lab notes: file identity, legacy compatibility, safe initialization, persistence failures, pause, CRUD, seek and export PASS');
