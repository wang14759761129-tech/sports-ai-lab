import socket
import threading
import time
import urllib.request
import uvicorn
import webview
from backend.main import app

def main():
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
    webview.create_window('PTTI · Match Intelligence',url,width=1440,height=900,min_size=(900,650))
    try: webview.start()
    finally: server.should_exit=True; thread.join(timeout=5)

if __name__=='__main__':
    try: main()
    except Exception:
        import traceback
        import os
        from pathlib import Path
        target=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'PTTI'
        target.mkdir(parents=True,exist_ok=True)
        (target/'startup-error.log').write_text(traceback.format_exc(),encoding='utf-8')
        raise
