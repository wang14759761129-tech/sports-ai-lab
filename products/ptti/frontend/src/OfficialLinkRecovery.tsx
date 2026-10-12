import {useState} from 'react';
import {copyOfficialUrl} from './officialPlayback';

export default function OfficialLinkRecovery({url}:{url:string}){
 const [manualCopy,setManualCopy]=useState(false),[message,setMessage]=useState('');
 async function copy(){
  const copied=await copyOfficialUrl(url);
  setManualCopy(!copied);
  setMessage(copied?'官方链接已复制':'请从下方选择并复制官方链接');
 }
 return <div className="official-link-recovery">
  <button type="button" onClick={copy}>复制官方链接</button>
  {message&&<span role="status">{message}</span>}
  {manualCopy&&<label>官方链接<input aria-label="官方链接" readOnly value={url} onFocus={event=>event.currentTarget.select()} onClick={event=>event.currentTarget.select()}/></label>}
 </div>;
}
