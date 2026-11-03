import {buildOfficialJump,formatTimestamp} from '../../frontend/src/momentCards.mjs';

export function renderCards(document, container, moments, seeds, onEdit, onDelete) {
  const by = new Map(seeds.map(seed=>[seed.key,seed]));
  const element = (tag,text) => {const node=document.createElement(tag);node.textContent=text;return node;};
  const cards = moments.map(moment=>{
    const card=element('article','');card.className='card';
    const video=by.get(moment.videoKey);
    card.append(element('b',formatTimestamp(moment.seconds)),element('h2',moment.title),
      element('span',video?`${video.event} · ${video.title}`:'比赛已不在当前目录'),element('p',moment.note));
    for(const tag of moment.tags){const node=element('span',`#${tag}`);node.className='tag';card.append(node);}
    const jump=video?buildOfficialJump(video,moment.seconds):{url:null};
    if(jump.url){const link=element('a',jump.precise?'在官方页面定位此时刻 ↗':'打开官方页面 ↗');link.href=jump.url;link.target='_blank';link.rel='noopener noreferrer';card.append(link);}
    const edit=element('button','编辑');edit.onclick=()=>onEdit(moment);
    const remove=element('button','删除');remove.onclick=()=>onDelete(moment);
    card.append(edit,remove);return card;
  });
  container.replaceChildren(...(cards.length?cards:[element('p','还没有时刻卡片。')]));
}
