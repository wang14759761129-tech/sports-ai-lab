import {bindLegacyNote,createNote,createVideoIdentity,deleteNote,exportNotes,filterNotesByVideo,formatTimestamp,loadNotesState,parseTags,parseTimestamp,resolveSeek,saveNotes,updateNote} from '../../frontend/src/proLabNotes.mjs';
import {renderNotes} from './render.mjs';

const $=id=>document.getElementById(id),video=$('video');
let storageState;
try{storageState=loadNotesState(window.localStorage)}catch{storageState={notes:[],writable:false,error:'本机存储不可用；已有笔记未修改。'}}
let notes=storageState.notes,selection=null,videoUrl=null,editingId=null,loadedIdentityKey=null;
function message(error='',status=''){ $('err').textContent=error; $('status').textContent=status; }
function persist(next,success){
 if(!storageState.writable){message(storageState.error||'本机存储不可用，笔记未保存。');return false;}
 let localStorageApi;try{localStorageApi=window.localStorage}catch{message('本机存储不可用，笔记未保存。');return false;}
 const result=saveNotes(localStorageApi,next);
 if(!result.ok){message(result.error);return false;}
 notes=next;message('',success);render();return true;
}
function render(){renderNotes(document,$('list'),notes,selection?.identity||null,{
 onSeek(note){if(!selection||note.videoIdentity?.key!==selection.identity.key||loadedIdentityKey!==selection.identity.key){message('请重新选择与笔记身份一致的视频，未执行跳转。');return;}const target=resolveSeek(note.seconds,video.duration);if(target===null){message('时间点无效。');return;}video.currentTime=target;void video.play().catch(()=>message('已定位，但浏览器未能开始播放。'));},
 onEdit(note){if(!selection||note.videoIdentity?.key!==selection.identity.key)return;editingId=note.id;$('ts').value=formatTimestamp(note.seconds);$('tags').value=note.tags.join(', ');$('note').value=note.coachNote;message();},
 onDelete(note){if(confirm('确定删除这条笔记吗？'))persist(deleteNote(notes,note.id),'笔记已删除。');},
 onBindLegacy(note){if(!selection||!confirm(`仅将旧笔记 ${note.videoName} 关联到当前文件？`))return;const result=bindLegacyNote(notes,note.id,selection.identity);if(result.errors.length){message(result.errors.join('；'));return;}persist(result.notes,'旧笔记已手动关联。');}
});}
$('file').addEventListener('change',()=>{const file=$('file').files?.[0];if(!file)return;const identity=createVideoIdentity(file);if(!identity){message('文件身份无效。');return;}video.pause();if(videoUrl)URL.revokeObjectURL(videoUrl);videoUrl=URL.createObjectURL(file);selection={identity};loadedIdentityKey=null;video.src=videoUrl;$('vname').textContent=`当前视频：${identity.name} · ${identity.size} bytes`;message();render();});
video.addEventListener('loadstart',()=>{loadedIdentityKey=null;});
video.addEventListener('loadedmetadata',()=>{loadedIdentityKey=selection?.identity.key||null;});
video.addEventListener('error',()=>{loadedIdentityKey=null;message('当前浏览器无法解码此视频；笔记未改变。');});
$('capture').addEventListener('click',()=>{if(!selection||!videoUrl||loadedIdentityKey!==selection.identity.key||video.readyState<1||!Number.isFinite(video.currentTime)){message('请先选择并加载本机视频，再记录时间点。');return;}video.pause();$('ts').value=formatTimestamp(video.currentTime);message();});
$('save').addEventListener('click',()=>{if(!selection){message('请先选择本机视频。');return;}const input={videoIdentity:selection.identity,timestamp:$('ts').value,tags:parseTags($('tags').value),coachNote:$('note').value};const result=editingId?updateNote(notes,editingId,input):createNote(notes,input);if(result.errors.length){message(result.errors.join('；'));return;}if(persist(result.notes,'笔记已保存在本机。')){editingId=null;$('ts').value='';$('tags').value='';$('note').value='';}});
$('cancel').addEventListener('click',()=>{editingId=null;$('ts').value='';$('tags').value='';$('note').value='';message();});
$('export').addEventListener('click',()=>{const data=exportNotes(notes),blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='ptti-pro-lab-notes.json';a.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);message('',`已导出 ${data.noteCount} 条笔记，不含视频内容。`);});
$('back').addEventListener('click',()=>history.back());
render();
