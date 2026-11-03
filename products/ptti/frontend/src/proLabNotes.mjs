// User-owned local notes for a local video. This module stores metadata only;
// it never reads, hashes, uploads, copies, or packages video bytes.
export const PRO_LAB_STORAGE_KEY = 'ptti-pro-lab-notes-v1';
export const PRO_LAB_TACTICAL_TAGS = ['发球','接发球','第三板','相持','关键分','落点观察','节奏观察','自定义'];

function basename(value) {
  return String(value ?? '').split(/[\\/]/).filter(Boolean).at(-1) ?? '';
}

export function createVideoIdentity(file) {
  const name = basename(file?.name).trim();
  const size = Number(file?.size);
  const lastModified = Number(file?.lastModified);
  const type = typeof file?.type === 'string' ? file.type.trim().toLowerCase().slice(0,128) : '';
  if (!name || name.length > 255 || !Number.isSafeInteger(size) || size < 0 ||
      !Number.isFinite(lastModified) || lastModified < 0) return null;
  const tuple = [name,size,Math.floor(lastModified),type];
  return {version:1,key:`local-file:v1:${encodeURIComponent(JSON.stringify(tuple))}`,name,size,lastModified:Math.floor(lastModified),type};
}

function normalizedIdentity(value) {
  if (!value || value.version !== 1 || typeof value.name !== 'string' ||
      !Number.isSafeInteger(value.size) || !Number.isFinite(value.lastModified) ||
      typeof value.type !== 'string') return null;
  if (value.name !== basename(value.name)) return null;
  const identity = createVideoIdentity(value);
  return identity && identity.key === value.key ? identity : null;
}

export function parseTimestamp(input) {
  if (typeof input === 'number' && Number.isFinite(input)) return input >= 0 && input < 86400 ? Math.floor(input) : null;
  if (typeof input !== 'string' || !input.trim()) return null;
  const parts = input.trim().split(':').map(value=>value.trim());
  if ((parts.length !== 2 && parts.length !== 3) || !parts.every(value=>/^\d+$/.test(value))) return null;
  const numbers = parts.map(Number);
  let seconds;
  if (numbers.length === 2) {
    const [minutes, rest] = numbers;
    if (rest > 59) return null;
    seconds = minutes * 60 + rest;
  } else {
    const [hours, minutes, rest] = numbers;
    if (minutes > 59 || rest > 59) return null;
    seconds = hours * 3600 + minutes * 60 + rest;
  }
  return seconds < 86400 ? seconds : null;
}

export function formatTimestamp(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return '';
  const value=Math.floor(seconds), hours=Math.floor(value/3600), minutes=Math.floor((value%3600)/60), rest=value%60;
  return hours ? `${hours}:${String(minutes).padStart(2,'0')}:${String(rest).padStart(2,'0')}` : `${minutes}:${String(rest).padStart(2,'0')}`;
}

export function parseTags(input) {
  const raw=Array.isArray(input)?input:typeof input==='string'?input.split(/[,，、\s]+/):[];
  return [...new Set(raw.map(value=>String(value).trim().replace(/^#+/,'')).filter(Boolean))].filter(tag=>tag.length<=60).slice(0,10);
}

export function validateNote(input) {
  const errors=[];
  const videoIdentity=normalizedIdentity(input?.videoIdentity);
  if (!videoIdentity) errors.push('请先选择有效的本机视频文件');
  const seconds=parseTimestamp(input?.timestamp);
  if (seconds===null) errors.push('时间点格式不对，例如 12:34 或 1:02:03');
  const tags=parseTags(input?.tags??'');
  if (!tags.length) errors.push('请至少选择一个技战术标签');
  const coachNote=typeof input?.coachNote==='string'?input.coachNote.trim():'';
  if (coachNote.length>500) errors.push('备注不能超过 500 字');
  if (errors.length) return {errors,cleaned:null};
  return {errors:[],cleaned:{videoIdentity,videoName:videoIdentity.name,seconds,tags,coachNote}};
}

export function createNote(list,input,now=Date.now()) {
  const {errors,cleaned}=validateNote(input);
  if (errors.length) return {errors,notes:list};
  const note={id:`prolab-${now}-${Math.random().toString(36).slice(2,8)}`,...cleaned,createdAt:new Date(now).toISOString(),updatedAt:new Date(now).toISOString()};
  return {errors:[],notes:sortNotes([...list,note]),note};
}

export function updateNote(list,id,input,now=Date.now()) {
  const {errors,cleaned}=validateNote(input);
  if (errors.length) return {errors,notes:list};
  if (!list.some(note=>note.id===id)) return {errors:['找不到这条笔记'],notes:list};
  return {errors:[],notes:sortNotes(list.map(note=>note.id===id?{...note,...cleaned,updatedAt:new Date(now).toISOString()}:note))};
}

export function deleteNote(list,id) { return list.filter(note=>note.id!==id); }
export function sortNotes(list) { return [...list].sort((a,b)=>(a.seconds-b.seconds)||(a.createdAt<b.createdAt?-1:1)); }
export function isNoteBoundToVideo(note,identity) {
  const candidate=normalizedIdentity(identity);
  return Boolean(candidate && note?.videoIdentity?.key===candidate.key && normalizedIdentity(note.videoIdentity));
}
export function filterNotesByVideo(list,identity) {
  if (!normalizedIdentity(identity)) return [];
  return list.filter(note=>isNoteBoundToVideo(note,identity));
}
export function legacyNotes(list) { return list.filter(note=>!note?.videoIdentity).map(note=>({...note,videoName:basename(note.videoName)})); }

// Legacy v0.1 notes keyed only by filename remain visible for manual review.
// They are attached to a file only after an explicit user action.
export function bindLegacyNote(list,id,identity,now=Date.now()) {
  const videoIdentity=normalizedIdentity(identity);
  const existing=list.find(note=>note.id===id);
  if (!existing) return {errors:['找不到这条旧版笔记'],notes:list};
  if (!videoIdentity) return {errors:['当前文件身份无效，未关联旧笔记'],notes:list};
  if (existing.videoIdentity) return {errors:['该笔记已绑定文件身份'],notes:list};
  const notes=list.map(note=>note.id===id?{...note,videoIdentity,videoName:videoIdentity.name,updatedAt:new Date(now).toISOString()}:note);
  return {errors:[],notes:sortNotes(notes)};
}

export function resolveSeek(seconds,duration) {
  if (!Number.isFinite(seconds)||seconds<0) return null;
  if (Number.isFinite(duration)&&duration>0) return Math.min(seconds,duration);
  return seconds;
}

function validNote(note) {
  if (!note||typeof note.id!=='string'||!note.id||note.id.length>128||
      typeof note.videoName!=='string'||!note.videoName||note.videoName.length>1024||!Number.isInteger(note.seconds)||note.seconds<0||note.seconds>=86400||
      !Array.isArray(note.tags)||note.tags.length>10||!note.tags.every(tag=>typeof tag==='string'&&tag.length>0&&tag.length<=60)||
      typeof note.coachNote!=='string'||note.coachNote.length>500||
      typeof note.createdAt!=='string'||!Number.isFinite(Date.parse(note.createdAt))||
      typeof note.updatedAt!=='string'||!Number.isFinite(Date.parse(note.updatedAt))) return false;
  if (note.videoIdentity===undefined) return true; // readable old v0.1 record
  const identity=normalizedIdentity(note.videoIdentity);
  return Boolean(identity&&identity.name===note.videoName);
}

export function loadNotesState(storage) {
  const failed=error=>({notes:[],writable:false,error});
  try {
    if (typeof storage?.getItem!=='function'||typeof storage?.setItem!=='function') return failed('本机存储当前不可用，已有笔记保持原样。');
    const raw=storage.getItem(PRO_LAB_STORAGE_KEY);
    if (raw===null) return {notes:[],writable:true,error:''};
    const parsed=JSON.parse(raw);
    if (!Array.isArray(parsed)||!parsed.every(validNote)||new Set(parsed.map(note=>note.id)).size!==parsed.length) return failed('已有笔记格式异常；原始内容未覆盖，暂不能写入。');
    return {notes:sortNotes(parsed),writable:true,error:''};
  } catch { return failed('无法读取本机笔记；原始内容未覆盖，暂不能写入。'); }
}

export function loadNotes(storage) { return loadNotesState(storage).notes; }

export function writeNotes(storage,notes) {
  try {
    if (typeof storage?.setItem!=='function') return {ok:false,error:'本机存储不可用，笔记未保存。'};
    if (!Array.isArray(notes)||!notes.every(validNote)||new Set(notes.map(note=>note.id)).size!==notes.length) return {ok:false,error:'笔记数据校验失败，未保存。'};
    storage.setItem(PRO_LAB_STORAGE_KEY,JSON.stringify(notes));
    return {ok:true,error:''};
  } catch (error) {
    return {ok:false,error:error?.name==='QuotaExceededError'?'本机存储空间不足，笔记未保存；请保留当前输入。':'本机存储写入失败，笔记未保存；请保留当前输入。'};
  }
}
export function saveNotes(storage,notes) { return writeNotes(storage,notes); }

export function exportNotes(list,now=Date.now()) {
  return {version:'ptti.pro-lab-notes/0.2',exportedAt:new Date(now).toISOString(),noteCount:list.length,
    notes:sortNotes(list).map(note=>({id:note.id,videoName:basename(note.videoName),videoIdentity:normalizedIdentity(note.videoIdentity)||null,
      seconds:note.seconds,timestamp:formatTimestamp(note.seconds),tags:[...note.tags],coachNote:note.coachNote,createdAt:note.createdAt,updatedAt:note.updatedAt}))};
}
