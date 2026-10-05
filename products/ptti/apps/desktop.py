import socket
import threading
import time
import urllib.request
import uvicorn
import webview
import os
from pathlib import Path

class DesktopAPI:
    def open_data_folder(self):
        folder=Path(os.environ['PTTI_DB']).parent if os.environ.get('PTTI_DB') else Path(os.environ.get('LOCALAPPDATA',Path.home()))/'PTTI-Dev'
        folder.mkdir(parents=True,exist_ok=True)
        os.startfile(str(folder))
        return True

def main():
    import sys
    if getattr(sys, 'frozen', False):
        executable=Path(sys.executable).stem.casefold()
        if executable=='ptti-vision-dev':
            # Workspace-only experimental EXE always uses an isolated DB.
            product=next((p for p in Path(sys.executable).resolve().parents if (p/'vision_worker/balltrack.py').is_file()),
                         Path(os.environ.get('LOCALAPPDATA',Path.home()))/'PTTI-Dev'/'vision')
            os.environ['PTTI_ENV']='development'
            os.environ.setdefault('PTTI_VISION_HOME',str(product))
            local=Path(os.environ.get('LOCALAPPDATA',Path.home()))
            os.environ.setdefault('PTTI_DB',str(local/'PTTI-Dev'/'matches.db'))
        elif executable=='ptti':
            # Only the stable desktop executable is allowed to open user data.
            database=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'PTTI'/'matches.db'
            os.environ['PTTI_ENV']='production'
            os.environ['PTTI_DB']=str(database)
        else:
            raise RuntimeError(f'Unrecognized packaged PTTI executable: {sys.executable}')
    else:
        # Running from source is development; default to a separate user folder.
        os.environ['PTTI_ENV']='development'
        local=Path(os.environ.get('LOCALAPPDATA',Path.home()))
        os.environ.setdefault('PTTI_DB',str(local/'PTTI-Dev'/'matches.db'))
    from backend.main import app
    webview.settings['ALLOW_DOWNLOADS']=True
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_config=None))
    thread=threading.Thread(target=server.run,daemon=True); thread.start()
    url=f'http://127.0.0.1:{port}'
    for _ in range(100):
        try:
            urllib.request.urlopen(url+'/api/health',timeout=.2); break
        except Exception: time.sleep(.1)
    else: raise RuntimeError('Local PTTI server did not start')
    width,height=1366,768
    requested=os.environ.get('PTTI_WINDOW_SIZE','')
    if requested:
        try:
            width,height=map(int,requested.lower().split('x'));width=max(1024,width);height=max(640,height)
        except ValueError: pass
    webview.create_window('PTTI · 个人乒乓球比赛分析',url,width=width,height=height,min_size=(1024,640),js_api=DesktopAPI())
    try: webview.start()
    finally: server.should_exit=True; thread.join(timeout=5)

if __name__=='__main__':
    try: main()
    except Exception:
        import traceback
        import os
        from pathlib import Path
        target=Path(os.environ.get('LOCALAPPDATA',Path.home()))/('PTTI' if os.environ.get('PTTI_ENV')=='production' else 'PTTI-Dev')
        target.mkdir(parents=True,exist_ok=True)
        (target/'startup-error.log').write_text(traceback.format_exc(),encoding='utf-8')
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,'PTTI 无法启动。请确认已完整解压，并已安装 Microsoft Edge WebView2 Runtime。\n\n已有比赛不会被重置。日志：\n'+str(target/'startup-error.log'),'PTTI · 启动失败',0x10)
        except Exception: pass
        raise
