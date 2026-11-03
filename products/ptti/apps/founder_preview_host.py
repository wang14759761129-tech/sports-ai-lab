"""Isolated Founder Preview host; development only, not a release launcher."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SOURCE_COMMIT = '5946c0c4d0517ade316b748933151816c6c504d3'
MIN_RAM = int(2.5 * 1024**3)


def start_services(frontend: Path, qa_root: Path):
    """Create only loopback services; caller must shut down and close both servers."""
    frontend = frontend.resolve(strict=True)
    qa_root = qa_root.resolve(strict=True)
    if not (frontend / 'dist' / 'index.html').is_file():
        raise RuntimeError('缺少统一模式前端文件，请重新完整准备预览包。')
    spec = importlib.util.spec_from_file_location('founder_demo_api', frontend / 'scripts' / 'demo_moment_api.py')
    if spec is None or spec.loader is None:
        raise RuntimeError('缺少演示 API。')
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    synthetic = frontend / 'dist' / 'demo-synthetic.mp4'
    if not synthetic.is_file():
        raise RuntimeError('缺少合成测试视频。')
    api.DB = qa_root / 'moments.sqlite3'
    api.VIDEO = synthetic
    api.digest()  # fail closed before creating database
    api.initialize()
    api_server = ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
    api.PORT = api_server.server_port

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(frontend / 'dist'), **kwargs)
        def proxy(self):
            if not self.path.startswith('/demo-api/'):
                self.send_error(404)
                return
            length = int(self.headers.get('Content-Length', '0'))
            if length > 8192:
                self.send_error(413)
                return
            data = self.rfile.read(length) if self.command != 'GET' else None
            request = Request(f'http://127.0.0.1:{api.PORT}' + self.path[len('/demo-api'):], data=data,
                              headers={'Origin': f'http://127.0.0.1:{self.server.server_port}', 'Content-Type': 'application/json'}, method=self.command)
            try:
                with urlopen(request, timeout=5) as response:
                    status, body = response.status, response.read()
            except HTTPError as error:
                status, body = error.code, error.read()
            except URLError:
                status, body = 503, b'{"error":"demo API unavailable"}'
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def do_GET(self):
            if self.path.startswith('/demo-api/'):
                self.proxy()
            else:
                super().do_GET()
        def do_POST(self): self.proxy()
        def do_PUT(self): self.proxy()
        def do_DELETE(self): self.proxy()

    try:
        web = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    except Exception:
        api_server.server_close()
        raise
    api.FRONTEND_PORT = web.server_port
    for server in (api_server, web):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    return web, api_server


def main() -> int:
    if os.name != 'nt':
        raise RuntimeError('此预览仅支持 Windows。')
    import psutil
    if psutil.virtual_memory().available < MIN_RAM:
        raise RuntimeError('可用内存不足 2.5 GiB，预览未启动。')
    import webview
    bundle_root = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
    frontend = bundle_root / 'frontend'
    from apps.founder_preview_guard import verify_dist, acquire_mutex, release_mutex
    verify_dist(frontend / 'dist', frontend / 'founder-build.json')
    mutex = acquire_mutex()
    qa_root = None
    web = api = None
    try:
        qa_root = Path(tempfile.mkdtemp(prefix='ptti-founder-preview-'))
        web, api = start_services(frontend, qa_root)
        webview.create_window('PTTI Founder Preview', f'http://127.0.0.1:{web.server_port}/', width=1440, height=900)
        webview.start(gui='edgechromium', private_mode=False, storage_path=str(qa_root / 'webview2'))
        return 0
    finally:
        for server in (web, api):
            if server is not None:
                server.shutdown()
                server.server_close()
        if qa_root is not None:
            shutil.rmtree(qa_root, ignore_errors=True)
        release_mutex(mutex)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        # Do not fall back to a production launcher or database.
        if os.name == 'nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(error), 'PTTI Founder Preview 启动失败', 0x10)
        else:
            print(str(error), file=sys.stderr)
        sys.exit(1)



