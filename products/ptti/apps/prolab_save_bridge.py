"""Restricted native save bridge for the verified local Founder Preview only."""
from __future__ import annotations
import hashlib, json, math, os, re, tempfile, threading
from pathlib import Path
from urllib.parse import urlsplit

MAX_BYTES=2*1024*1024

def _unique(pairs):
 out={}
 for key,value in pairs:
  if key in out: raise ValueError('duplicate key')
  out[key]=value
 return out

def validate_review(text):
 if not isinstance(text,str): raise ValueError('invalid input')
 raw=text.encode('utf-8')
 if len(raw)>MAX_BYTES or not raw: raise ValueError('invalid size')
 obj=json.loads(text, object_pairs_hook=_unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('non-finite')))
 if not isinstance(obj,dict) or set(obj)!={'schema','media','origin','verification','association','persistence','marks','local_content_fingerprint'}: raise ValueError('invalid structure')
 if (obj['schema'],obj['origin'],obj['verification'],obj['association'],obj['persistence'])!=('ptti.manual-review/2','MANUAL_USER_RECORDED','NOT_INDEPENDENTLY_VERIFIED','NO_MATCH_ASSOCIATION','SESSION_ONLY'): raise ValueError('invalid version or provenance')
 media=obj['media'];fp=obj['local_content_fingerprint']
 if not isinstance(media,dict) or set(media)!={'identity','duration_seconds'}: raise ValueError('invalid media')
 ident=media['identity'];duration=media['duration_seconds']
 if not isinstance(ident,dict) or set(ident)!={'kind','value'} or ident['kind'] not in ('SHA256','SESSION') or not isinstance(ident['value'],str): raise ValueError('invalid identity')
 if not re.fullmatch(r'[a-f0-9]{64}' if ident['kind']=='SHA256' else r'[A-Za-z0-9_-]{16,128}',ident['value']): raise ValueError('invalid identity')
 if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<=0: raise ValueError('invalid duration')
 if not isinstance(fp,dict) or set(fp)!={'algorithm','digest'} or fp['algorithm']!='ptti-local-video-chunks-sha256-v1' or not isinstance(fp['digest'],str) or not re.fullmatch(r'[a-f0-9]{64}',fp['digest']): raise ValueError('invalid fingerprint')
 marks=obj['marks'];ids=set()
 if not isinstance(marks,list) or len(marks)>10000: raise ValueError('invalid marks')
 for m in marks:
  if not isinstance(m,dict) or set(m)!={'id','seconds','tag','note'}: raise ValueError('invalid mark')
  ident=m['id'];seconds=m['seconds']
  if not isinstance(ident,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',ident) or ident in ids: raise ValueError('invalid id')
  if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or not 0<=seconds<=duration or m['tag'] not in ('serve','receive','rally','other') or not isinstance(m['note'],str) or len(m['note'])>2000: raise ValueError('invalid mark')
  ids.add(ident)
 return raw

class ProLabSaveBridge:
 def __init__(self,port,save_dialog): self._port=port;self._dialog=save_dialog;self._window=None;self._lock=threading.Lock()
 def _bind_window(self,window): self._window=window
 def _trusted(self):
  try:
   u=urlsplit(self._window.get_current_url())
   return u.scheme=='http' and u.hostname=='127.0.0.1' and u.port==self._port and not u.username and not u.password and u.path=='/' and u.query=='ptti_native=1' and not u.fragment
  except Exception:return False
 def save_prolab_json(self,text):
  if not self._lock.acquire(blocking=False): return {'status':'error','message':'保存正在进行'}
  temp=None
  try:
   if not self._trusted(): return {'status':'error','message':'页面身份未通过检查'}
   raw=validate_review(text)
   choice=self._dialog(self._window)
   if not choice:return {'status':'cancelled'}
   if isinstance(choice,(tuple,list)):choice=choice[0] if choice else None
   if not isinstance(choice,str) or not choice:return {'status':'error','message':'保存位置无效'}
   path=Path(choice)
   if not path.is_absolute() or path.suffix.lower()!='.json' or not self._trusted():return {'status':'error','message':'保存位置或页面身份无效'}
   fd,temp=tempfile.mkstemp(prefix='.ptti-save-',suffix='.tmp',dir=path.parent)
   with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
   if hashlib.sha256(Path(temp).read_bytes()).digest()!=hashlib.sha256(raw).digest() or not self._trusted():raise OSError('verification failed')
   os.replace(temp,path);temp=None
   return {'status':'saved'}
  except Exception:return {'status':'error','message':'保存失败，请检查文件和位置后重试'}
  finally:
   if temp is not None:
    try:os.unlink(temp)
    except OSError:pass
   self._lock.release()
