"""Blank WebView2 probe. No PTTI modules/data; explicit authorization required."""
import argparse,hashlib,json,os,tempfile,time,threading
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--authorized-disposable-environment',action='store_true');p.add_argument('--root',type=Path,required=True);a=p.parse_args()
 if not a.authorized_disposable_environment:p.error('Explicit authorized disposable environment required')
 root=a.root
 if not root.is_absolute() or root.exists() or not root.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):p.error('Use a NEW absolute OS-temp directory')
 for part in (root,*root.parents):
  if part.is_symlink() or (part.exists() and part.lstat().st_file_attributes & 0x400):p.error('Reparse path refused')
 import psutil
 samples=[]
 for _ in range(3):
  free=psutil.virtual_memory().available;samples.append(free)
  if free<3*1024**3:raise RuntimeError('RAM startup guard: below 3 GiB')
  time.sleep(1)
 root.mkdir();
 for name in ['local','roaming','temp','webview','logs']:(root/name).mkdir()
 os.environ.update(LOCALAPPDATA=str(root/'local'),APPDATA=str(root/'roaming'),TEMP=str(root/'temp'),TMP=str(root/'temp'),WEBVIEW2_USER_DATA_FOLDER=str(root/'webview'))
 import webview
 stop=threading.Event();observations=[]
 window=webview.create_window('Blank isolation probe',html='<!doctype html><title>Isolation probe</title><p>Blank local test. No PTTI data.</p>')
 def monitor():
  deadline=time.monotonic()+30
  while not stop.wait(1):
   processes=[]
   for process in [psutil.Process(),*psutil.Process().children(recursive=True)]:
    try:processes.append({'pid':process.pid,'exe':process.exe(),'command':process.cmdline()})
    except psutil.Error:pass
   free=psutil.virtual_memory().available;observations.append({'available':free,'processes':processes})
   if free<2.5*1024**3 or time.monotonic()>deadline:window.destroy();return
 threading.Thread(target=monitor,daemon=True).start()
 try:webview.start(gui='edgechromium',private_mode=False,storage_path=str(root/'webview'))
 finally:
  stop.set()
  files=[{'path':str(f.relative_to(root)),'bytes':f.stat().st_size} for f in root.rglob('*') if f.is_file()]
  (root/'logs/report.json').write_text(json.dumps({'ram_samples':samples,'observations':observations,'files':files,'physical_write_trace':'NOT_TESTED: requires approved OS file-write trace; inventory alone cannot prove absence of outside writes','acceptance':'NOT_TESTED'},indent=2),encoding='utf8')
if __name__=='__main__':main()
