const element=(document,tag,text='')=>{const node=document.createElement(tag);node.textContent=String(text);return node;};

export function renderNotes(document,container,notes,identity,{onSeek=()=>{},onEdit=()=>{},onDelete=()=>{},onBindLegacy=()=>{}}={}){
 const fragment=document.createDocumentFragment();
 const matching=notes.filter(note=>identity&&note.videoIdentity?.key===identity.key);
 if(!matching.length)fragment.append(element(document,'p','当前视频暂无已绑定笔记。'));
 for(const note of matching){
  const card=element(document,'article');card.className='card';
  const time=element(document,'button',`${Math.floor(note.seconds/60)}:${String(note.seconds%60).padStart(2,'0')} ▶`);time.type='button';time.onclick=()=>onSeek(note);card.append(time);
  const tags=element(document,'p',note.tags.map(tag=>`#${tag}`).join(' '));tags.className='tag';card.append(tags);
  card.append(element(document,'p',note.coachNote||''));
  for(const [label,handler] of [['编辑',onEdit],['删除',onDelete]]){const button=element(document,'button',label);button.type='button';button.onclick=()=>handler(note);card.append(button);}
  fragment.append(card);
 }
 const old=notes.filter(note=>!note.videoIdentity);
 if(old.length){const legacy=element(document,'section');legacy.append(element(document,'h3',`旧版未绑定身份笔记 · ${old.length}`));legacy.append(element(document,'p','文件名不足以识别录像；仅在用户明确操作时绑定。'));
  for(const note of old){const row=element(document,'article',`${note.videoName} · ${note.seconds}s · ${(note.tags||[]).join(', ')} · ${note.coachNote||''}`);const button=element(document,'button','确认绑定当前文件');button.type='button';button.disabled=!identity;button.onclick=()=>onBindLegacy(note);row.append(button);legacy.append(row);}
  fragment.append(legacy);
 }
 container.replaceChildren(fragment);
}
