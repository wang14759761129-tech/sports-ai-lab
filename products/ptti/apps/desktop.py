import socket
import threading
import time
import urllib.request
import uvicorn
import webview
import os
from pathlib import Path

def is_development_preview(executable_name):
    stem=Path(executable_name).stem.casefold()
    return stem in {'ptti-professional-preview-v0.2','ptti-scene-bootstrap-preview-v2',
                    'ptti-vision-lab-v2-scene-preview','ptti-vision-v2-hybrid-scene-preview'}

class DesktopAPI:
    def open_output_folder(self, requested):
        folder=Path(requested).resolve()
        root=(Path(os.environ['PTTI_DB']).parent/'full_matches').resolve()
        if not folder.is_dir() or not folder.is_relative_to(root):
            raise ValueError('Only this Preview application output directory may be opened')
        os.startfile(str(folder))
        return True

    def open_data_folder(self):
        folder=Path(os.environ['PTTI_DB']).parent if os.environ.get('PTTI_DB') else Path(os.environ.get('LOCALAPPDATA',Path.home()))/'PTTI-Dev'
        folder.mkdir(parents=True,exist_ok=True)
        os.startfile(str(folder))
        return True

def main():
    import sys
    if getattr(sys, 'frozen', False):
        executable=Path(sys.executable).stem.casefold()
        if is_development_preview(sys.executable):
            # Preview is fail-closed development, even when launched with stale env vars.
            os.environ['PTTI_ENV']='development'
            os.environ['PTTI_PREVIEW']='1'
            local=Path(os.environ.get('LOCALAPPDATA',Path.home()))
            os.environ['PTTI_DB']=str(local/'PTTI-Dev'/'ProfessionalPreview'/'matches.db')
            qa_database=os.environ.get('PTTI_PREVIEW_QA_DB')
            if qa_database:
                import tempfile
                candidate=Path(qa_database).resolve()
                if not candidate.is_relative_to(Path(tempfile.gettempdir()).resolve()):
                    raise RuntimeError('Preview QA database must be inside OS temp')
                os.environ['PTTI_DB']=str(candidate)
                os.environ['PTTI_ENV']='test'
            os.environ['PTTI_RESEARCH_DATA_ROOT']=str(local/'PTTI-Dev')
            internal=Path(getattr(sys,'_MEIPASS',Path(sys.executable).parent))
            os.environ['PATH']=str(internal)+os.pathsep+os.environ.get('PATH','')
            build=Path(getattr(sys,'_MEIPASS',Path(sys.executable).parent))/'build-info.json'
            if build.is_file():
                import json
                runtime_home=json.loads(build.read_text(encoding='utf-8')).get('local_vision_runtime_home')
                if runtime_home and (Path(runtime_home)/'vision_worker/balltrack.py').is_file():
                    os.environ['PTTI_VISION_HOME']=runtime_home
        elif executable=='ptti-vision-dev':
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
    print('PTTI Desktop URL: '+url,flush=True)
    stem=Path(sys.executable).stem.casefold()
    title=('PTTI · Vision v2 Hybrid Scene Preview' if 'hybrid-scene-preview' in stem else
           'PTTI · Vision Lab v2 Scene Bootstrap Preview' if 'scene-bootstrap-preview' in stem or 'vision-lab-v2-scene-preview' in stem else
           'PTTI · Professional Preview v0.2' if 'professional-preview' in stem else
           'PTTI · 个人乒乓球比赛分析')
    webview.create_window(title,url,width=width,height=height,min_size=(1024,640),js_api=DesktopAPI())
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
