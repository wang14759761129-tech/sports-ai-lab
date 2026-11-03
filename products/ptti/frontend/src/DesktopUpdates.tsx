import {useEffect,useState} from 'react';

export default function DesktopUpdates({versions}:{versions:any}){
 const [state,setState]=useState<any>(null),[release,setRelease]=useState<any>(null),[busy,setBusy]=useState(false);
 useEffect(()=>{let live=true;const load=()=>fetch('/api/desktop-updates').then(r=>{if(!r.ok)throw Error();return r.json()}).then(v=>{if(live)setState(v)}).catch(()=>{if(live)setState({integrity:'UNKNOWN'})});load();const t=window.setInterval(load,60000);return()=>{live=false;clearInterval(t)}},[]);
 async function check(){setBusy(true);try{const r=await fetch('/api/desktop-updates/check?channel=preview');if(!r.ok)throw Error();setRelease(await r.json())}catch{setRelease({status:'OFFLINE_OR_UNAVAILABLE'})}finally{setBusy(false)}}
 return <section aria-label="关于与更新"><h2>关于 / 更新</h2><p>{versions.product_name} · {versions.version} · Preview</p><p>当前构建：{versions.build_commit||'未记录'}</p><p>构建时间：{versions.built_at||'旧包未记录'}</p><p>桌面激活版本：{state?.deployed_commit||'尚未接入固定启动器'}</p><p>{state?.restart_pending?'新版本已就绪，下次启动使用；当前视频不会被中断':state?.integrity==='VERIFIED'?'固定启动器版本完整性已校验':'部署状态待核验'}</p><button disabled={busy} onClick={check}>{busy?'正在检查…':'检查更新'}</button>{release&&<p>{release.status==='OFFLINE_OR_UNAVAILABLE'?'更新服务暂不可用，仍可使用当前版本':release.release?'发现已发布版本，尚未批准安装':'没有可安装的 PTTI Release'}{release.release&&<> · <a href={release.release} target="_blank" rel="noreferrer">更新日志</a></>}</p>}<p>提交源码不会自动成为安装包。远程 Preview 未建立可信签名链，禁止静默安装。</p></section>;
}
