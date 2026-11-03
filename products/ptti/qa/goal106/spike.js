const watchURL='https://www.youtube.com/watch?v=0QgbtsBWZhk';
const fields={preview:'真实预览画面',attribution:'官方来源/控件可见',playback:'真实比赛画面与时间推进',embed_rejection:'观察到禁止嵌入',network_failure:'断网后失败反馈',official_navigation:'官方页面实际打开',copy_link:'复制链接可粘贴且准确'};
const status=document.querySelector('#status');
let timer;
for(const [key,label] of Object.entries(fields)){
 const row=document.createElement('label');row.textContent=label+'：';
 const select=document.createElement('select');select.id=key;
 for(const value of ['NOT_TESTED','OBSERVED','NOT_OBSERVED','BLOCKED']){const option=document.createElement('option');option.value=value;option.textContent=value;select.append(option)}
 row.append(select);document.querySelector('#observations').append(row);
}
function unload(){clearTimeout(timer);document.querySelector('#viewport').replaceChildren()}
document.querySelector('#load').onclick=()=>{
 unload();const frame=document.createElement('iframe');frame.title='YouTube 官方播放器 · 0QgbtsBWZhk';frame.width='640';frame.height='360';
 frame.src='https://www.youtube.com/embed/0QgbtsBWZhk?autoplay=0&controls=1&playsinline=1';
 frame.referrerPolicy='strict-origin-when-cross-origin';frame.allow='encrypted-media; picture-in-picture; fullscreen';frame.allowFullscreen=true;
 frame.onload=()=>{status.textContent='iframe load 事件已到达；可能仍是错误页面。画面、归属与播放均需人工观察，不自动升级状态。'};
 frame.onerror=()=>{clearTimeout(timer);status.textContent='播放器加载异常；请使用官方页面链接。跨域网络失败也可能不触发此事件。'};
 document.querySelector('#viewport').append(frame);
 status.textContent='正在请求官方播放器；若不可用，请查看播放器错误并使用官方外链。';
 timer=setTimeout(()=>{status.textContent+=' 等待窗口已达15秒；无法据此判断加载或播放成功。可卸载并使用官方页面。'},15000);
};
document.querySelector('#stop').onclick=()=>{unload();status.textContent='已卸载 iframe；不代表媒体释放已独立测量。'};
document.querySelector('#copy').onclick=async()=>{try{await navigator.clipboard.writeText(watchURL);status.textContent='已执行复制，请粘贴核对。'}catch{document.querySelector('#url').select();status.textContent='自动复制不可用，请在已选中的链接上按 Ctrl+C。'}};
document.querySelector('#export').onclick=()=>{
 const result={experiment:'ptti.goal106.single-video-qa/0.1',video_id:'0QgbtsBWZhk',match_id:'pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun',watch_url:watchURL,evidence_type:'MANUAL_OBSERVATION_NOT_INDEPENDENTLY_VERIFIED',recorded_at:new Date().toISOString(),observations:Object.fromEntries(Object.keys(fields).map(key=>[key,document.getElementById(key).value])),notes:document.querySelector('#notes').value,native_playback:'NOT_TESTED',media_permission_changes:[]};
 const json=JSON.stringify(result,null,2);document.querySelector('#result').textContent=json;
 const url=URL.createObjectURL(new Blob([json],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='goal106-manual-observation.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
