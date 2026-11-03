import socket
import threading
import time
import urllib.request
import uvicorn
import webview
import os
from pathlib import Path
from apps.native_qa import (
    NativeQAError,
    bind_native_qa_port,
    configure_native_qa,
    health_matches_native_qa,
    mark_native_qa_database_ready,
    validate_native_qa_candidate,
)

def is_development_preview(executable_name):
    stem=Path(executable_name).stem.casefold()
    return stem in {'ptti-professional-preview-v0.2','ptti-scene-bootstrap-preview-v2',
                    'ptti-vision-lab-v2-scene-preview','ptti-vision-v2-hybrid-scene-preview',
                    'ptti-vision-v2-player-tracking-preview',
                    'ptti-vision-v2-player-motion-preview',
                    'ptti-evidence-fusion-preview', 'ptti-video-evidence-preview',
                    'ptti-video-evidence-ai-bridge-preview', 'ptti-video-evidence-v0.3-preview', 'ptti-match-library-v0.4-preview',
                    'ptti-score-navigation-v0.1-preview','ptti-video-first-v0.5-preview','ptti-video-first-v0.5.1-preview',
                    'ptti-dual-source-v0.6.1-preview','ptti-personal-match-library-r3-preview','ptti-video-first-r4-preview',
                    'ptti-dark-studio-v0.7-preview','ptti-cinema-v0.7.1-preview',
                    'ptti-next-preview',
                    'ptti-vision-v2-player-tracking-v1-preview',
                    'ptti-vision-v2-person-preview'}


def configure_dual_source_preview(local_app_data, environ=None, database_subdir="DualSource-v061-Preview"):
    """Pin the dual-source preview to its own development database and product mode."""
    local = Path(local_app_data)
    target = os.environ if environ is None else environ
    target.update({
        'PTTI_ENV': 'development',
        'PTTI_PREVIEW': '1',
        'PTTI_DB': str(local / 'PTTI-Dev' / database_subdir / 'matches.db'),
        'PTTI_MATCH_LIBRARY_PREVIEW': '1',
        'PTTI_VIDEO_FEED_PREVIEW': '1',
        'PTTI_DUAL_SOURCE_PREVIEW': '1',
        'PTTI_EVIDENCE_PREVIEW': '0',
        'PTTI_AI_EVIDENCE_BRIDGE': '0',
        'PTTI_SCORE_NAV_PREVIEW': '0',
    })


def bind_ephemeral_loopback_port():
    """Reserve a private loopback port until the embedded Uvicorn server owns it."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_socket.bind(('127.0.0.1', 0))
        server_socket.listen(socket.SOMAXCONN)
    except BaseException:
        server_socket.close()
        raise
    return server_socket

class DesktopAPI:
    def open_official_video(self, requested_url, expected_video_id=None):
        from apps.external_links import open_official_video_url
        return open_official_video_url(requested_url, expected_video_id=expected_video_id)

    def select_evidence_video(self):
        result=webview.windows[0].create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=False,
            file_types=('视频文件 (*.mp4;*.mov;*.mkv;*.avi)',))
        return str(result[0]) if result else None

    def select_video_folder(self):
        result=webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER)
        return str(result[0]) if result else None

    def select_evidence_package(self):
        result=webview.windows[0].create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=False,
            file_types=('PTTI 冻结证据包 (*.jsonl)',))
        return str(result[0]) if result else None

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
    native_qa = None
    native_qa_build_commit = None
    if os.environ.get('PTTI_NATIVE_QA') == '1':
        if not getattr(sys, 'frozen', False) or Path(sys.executable).stem.casefold() != 'ptti-video-first-r4-preview':
            raise RuntimeError('Native QA mode is only available in the isolated Video First R4 Preview executable')
        native_qa_build_commit = validate_native_qa_candidate(
            sys.executable,
            os.environ.get('LOCALAPPDATA', Path.home()),
            os.environ.get('PTTI_NATIVE_QA_CANDIDATE_ROOT'),
        )
    if getattr(sys, 'frozen', False):
        executable=Path(sys.executable).stem.casefold()
        if is_development_preview(sys.executable):
            # Preview is fail-closed development, even when launched with stale env vars.
            os.environ['PTTI_ENV']='development'
            os.environ['PTTI_PREVIEW']='1'
            local=Path(os.environ.get('LOCALAPPDATA',Path.home()))
            os.environ['PTTI_DB']=str(local/'PTTI-Dev'/'ProfessionalPreview'/'matches.db')
            if executable in {'ptti-dual-source-v0.6.1-preview','ptti-personal-match-library-r3-preview','ptti-video-first-r4-preview','ptti-dark-studio-v0.7-preview','ptti-cinema-v0.7.1-preview','ptti-next-preview'}:
                configure_dual_source_preview(local, database_subdir={
                    'ptti-personal-match-library-r3-preview':'PersonalMatchLibrary-R3-Preview',
                    'ptti-video-first-r4-preview':'VideoFirst-R4-Preview',
                    'ptti-dark-studio-v0.7-preview':'DarkStudio-v07-Preview',
                    'ptti-cinema-v0.7.1-preview':'Cinema-v071-Preview',
                    'ptti-next-preview':'Next-D2-Preview',
                }.get(executable,'DualSource-v061-Preview'))
                if executable == 'ptti-next-preview':
                    os.environ['PTTI_DESKTOP_DEPLOY_ROOT']=str(Path(sys.executable).resolve().parent)
            if executable in {'ptti-video-evidence-preview','ptti-video-evidence-ai-bridge-preview','ptti-video-evidence-v0.3-preview','ptti-match-library-v0.4-preview','ptti-score-navigation-v0.1-preview','ptti-video-first-v0.5-preview','ptti-video-first-v0.5.1-preview'}:
                os.environ['PTTI_DB']=str(local/'PTTI-Dev'/'VideoEvidencePreview'/'matches.db')
            if executable in {'ptti-video-evidence-v0.3-preview','ptti-match-library-v0.4-preview','ptti-score-navigation-v0.1-preview','ptti-video-first-v0.5-preview','ptti-video-first-v0.5.1-preview'}:
                os.environ['PTTI_DB']=str(local/'PTTI-Dev'/'VideoEvidence-v03-Preview'/'matches.db')
            if executable in {'ptti-score-navigation-v0.1-preview','ptti-video-first-v0.5-preview','ptti-video-first-v0.5.1-preview'}:
                os.environ['PTTI_DB']=str(local/'PTTI-Dev'/'ScoreNavigation-v01-Preview'/'matches.db')
                os.environ['PTTI_MATCH_LIBRARY_PREVIEW']='1'
                os.environ['PTTI_SCORE_NAV_PREVIEW']='1'
                if executable in {'ptti-video-first-v0.5-preview','ptti-video-first-v0.5.1-preview'}:
                    os.environ['PTTI_DB']=str(local/'PTTI-Dev'/'VideoFirst-v05-Preview'/'matches.db')
                    os.environ['PTTI_VIDEO_FIRST_V05']='1'
                    if executable=='ptti-video-first-v0.5.1-preview':
                        os.environ['PTTI_VIDEO_FEED_PREVIEW']='1'
                        os.environ['PTTI_DB']=str(local/'PTTI-Dev'/'VideoFirst-v051-Preview'/'matches.db')
            if executable=='ptti-match-library-v0.4-preview':
                os.environ['PTTI_DB']=str(local/'PTTI-Dev'/'MatchLibrary-v04-Preview'/'matches.db')
                os.environ['PTTI_MATCH_LIBRARY_PREVIEW']='1'
            os.environ['PTTI_EVIDENCE_PREVIEW']='1' if executable in {'ptti-video-evidence-preview','ptti-video-evidence-ai-bridge-preview','ptti-video-evidence-v0.3-preview','ptti-match-library-v0.4-preview','ptti-score-navigation-v0.1-preview','ptti-video-first-v0.5-preview','ptti-video-first-v0.5.1-preview'} else '0'
            os.environ['PTTI_AI_EVIDENCE_BRIDGE']='1' if executable in {'ptti-video-evidence-ai-bridge-preview','ptti-video-evidence-v0.3-preview','ptti-match-library-v0.4-preview','ptti-score-navigation-v0.1-preview','ptti-video-first-v0.5-preview','ptti-video-first-v0.5.1-preview'} else '0'
            qa_database=os.environ.get('PTTI_PREVIEW_QA_DB')
            if qa_database:
                import tempfile
                candidate=Path(qa_database).resolve()
                native_qa_enabled=os.environ.get('PTTI_NATIVE_QA')=='1'
                if not native_qa_enabled and not candidate.is_relative_to(Path(tempfile.gettempdir()).resolve()):
                    raise RuntimeError('Preview QA database must be inside OS temp')
                os.environ['PTTI_DB']=str(candidate)
                os.environ['PTTI_ENV']='test'
            os.environ['PTTI_RESEARCH_DATA_ROOT']=str(local/'PTTI-Dev')
            internal=Path(getattr(sys,'_MEIPASS',Path(sys.executable).parent))
            os.environ['PATH']=str(internal)+os.pathsep+os.environ.get('PATH','')
            build=Path(getattr(sys,'_MEIPASS',Path(sys.executable).parent))/'build-info.json'
            if build.is_file():
                import json
                build_info=json.loads(build.read_text(encoding='utf-8'))
                if executable in {'ptti-video-evidence-v0.3-preview','ptti-match-library-v0.4-preview','ptti-score-navigation-v0.1-preview','ptti-video-first-v0.5-preview','ptti-video-first-v0.5.1-preview','ptti-dual-source-v0.6.1-preview','ptti-personal-match-library-r3-preview','ptti-video-first-r4-preview','ptti-dark-studio-v0.7-preview','ptti-cinema-v0.7.1-preview','ptti-next-preview'}:
                    os.environ['PTTI_PREVIEW_VERSION']=build_info['version']
                    os.environ['PTTI_PREVIEW_COMMIT']=build_info['commit']
                    os.environ['PTTI_PREVIEW_BUILT_AT']=build_info.get('built_at','')
                    if executable in {'ptti-score-navigation-v0.1-preview','ptti-video-first-v0.5-preview','ptti-video-first-v0.5.1-preview','ptti-dual-source-v0.6.1-preview','ptti-personal-match-library-r3-preview','ptti-video-first-r4-preview','ptti-dark-studio-v0.7-preview','ptti-cinema-v0.7.1-preview','ptti-next-preview'}:
                        os.environ['PTTI_PREVIEW_PRODUCT_NAME']=build_info.get('product_name','PTTI 比分导航')
                        os.environ['PTTI_PREVIEW_BUILD_ID']=build_info.get('build_id',build_info['commit'][:10])
                runtime_home=build_info.get('local_vision_runtime_home')
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
    if os.environ.get('PTTI_NATIVE_QA') == '1':
        if os.environ.get('PTTI_PREVIEW_COMMIT') != native_qa_build_commit:
            raise NativeQAError('Native QA candidate commit does not match its embedded build identity')
        native_qa = configure_native_qa(
            os.environ.get('LOCALAPPDATA', Path.home()),
            os.environ,
            native_qa_build_commit,
        )
        if native_qa is None:
            raise RuntimeError('Native QA configuration was not enabled')
    webview.settings['ALLOW_DOWNLOADS']=True
    next_preview = getattr(sys, 'frozen', False) and Path(sys.executable).stem.casefold() == 'ptti-next-preview'
    server_socket = (bind_native_qa_port(native_qa.port) if native_qa else
                    bind_ephemeral_loopback_port() if next_preview else None)
    try:
        from backend.main import app
    except BaseException:
        if server_socket:
            server_socket.close()
        raise
    if getattr(sys, 'frozen', False) and Path(sys.executable).stem.casefold() == 'ptti-next-preview':
        expected_db = (Path(os.environ['LOCALAPPDATA']) / 'PTTI-Dev' / 'Next-D2-Preview' / 'matches.db').resolve()
        if Path(app.state.database_path).resolve() != expected_db:
            if server_socket:
                server_socket.close()
            raise RuntimeError('PTTI Next refused an unexpected database location; existing databases were preserved')
    if server_socket is None:
        with socket.socket() as s:
            s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
    else:
        port = server_socket.getsockname()[1]
    try:
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_config=None))
        if server_socket:
            thread=threading.Thread(target=server.run,kwargs={'sockets':[server_socket]},daemon=True)
        else:
            thread=threading.Thread(target=server.run,daemon=True)
    except BaseException:
        if server_socket:
            server_socket.close()
        raise
    update_stop = threading.Event()
    url=f'http://127.0.0.1:{port}'
    thread_started = False
    try:
        thread.start()
        thread_started = True
        for _ in range(100):
            try:
                with urllib.request.urlopen(url+'/api/health',timeout=.2) as response:
                    import json
                    health = json.load(response)
            except Exception:
                time.sleep(.1)
                continue
            if native_qa and not health_matches_native_qa(
                    health, native_qa.build_commit, native_qa.instance_id, native_qa.origin,
                    str(native_qa.qa_data)):
                raise NativeQAError('Health endpoint does not match this isolated Native QA build, instance and origin')
            if Path(sys.executable).stem.casefold() == 'ptti-next-preview':
                expected_commit = os.environ.get('PTTI_PREVIEW_COMMIT')
                if (health.get('product_name') != 'PTTI Next'
                        or health.get('build_commit') != expected_commit
                        or health.get('video_feed') is not True):
                    raise RuntimeError('PTTI Next embedded service identity did not match the desktop package')
            if native_qa:
                mark_native_qa_database_ready(native_qa)
            break
        else:
            raise RuntimeError('Local PTTI server did not start')
    except BaseException:
        update_stop.set()
        server.should_exit=True
        if thread_started:
            thread.join(timeout=5)
        if server_socket:
            server_socket.close()
        raise
    def update_discovery():
        from backend.desktop_updates import check_release
        while not update_stop.is_set():
            check_release('preview')
            update_stop.wait(1800)
    if (os.environ.get('PTTI_DESKTOP_DEPLOY_ROOT') and '--deployment-health-check' not in sys.argv
            and Path(sys.executable).stem.casefold() != 'ptti-next-preview'):
        threading.Thread(target=update_discovery, daemon=True).start()
    if '--deployment-health-check' in sys.argv:
        import json
        try:
            with urllib.request.urlopen(url+'/api/health', timeout=5) as response:
                report = json.load(response)
            qa = Path(os.environ['PTTI_PREVIEW_QA_DB']).resolve()
            qa_root = (Path(os.environ['LOCALAPPDATA']) / 'PTTI-Dev' / 'NativeQA' / 'GEX03' /
                       os.environ['PTTI_PREVIEW_COMMIT'] / 'qa-data').resolve()
            if qa != (qa_root / 'matches.db').resolve():
                raise RuntimeError('Health check requires the exact persistent per-commit Native QA database')
            qa.with_suffix('.health.json').write_text(json.dumps(report), encoding='utf8')
        finally:
            server.should_exit=True
            thread.join(timeout=5)
            if server_socket:
                server_socket.close()
        return
    width,height=1366,768
    requested=os.environ.get('PTTI_WINDOW_SIZE','')
    if requested:
        try:
            width,height=map(int,requested.lower().split('x'));width=max(1024,width);height=max(640,height)
        except ValueError: pass
    print('PTTI Desktop URL: '+url,flush=True)
    stem=Path(sys.executable).stem.casefold()
    title=(f"{os.environ.get('PTTI_PREVIEW_PRODUCT_NAME','PTTI 比分导航')} v{os.environ.get('PTTI_PREVIEW_VERSION','0.1')} Preview · {os.environ.get('PTTI_PREVIEW_BUILD_ID',os.environ.get('PTTI_PREVIEW_COMMIT','UNKNOWN')[:10])}" if stem in {'ptti-score-navigation-v0.1-preview','ptti-video-first-v0.5-preview','ptti-video-first-v0.5.1-preview','ptti-dual-source-v0.6.1-preview','ptti-personal-match-library-r3-preview','ptti-video-first-r4-preview','ptti-dark-studio-v0.7-preview','ptti-cinema-v0.7.1-preview','ptti-next-preview'} else ('PTTI · 比赛录像库 v0.4 Preview · '+os.environ.get('PTTI_PREVIEW_COMMIT','UNKNOWN')[:10] if stem=='ptti-match-library-v0.4-preview' else ('PTTI · Video Evidence v0.3 Preview · '+os.environ.get('PTTI_PREVIEW_COMMIT','UNKNOWN')[:10]) if stem=='ptti-video-evidence-v0.3-preview' else
           'PTTI · AI 证据复盘 Preview' if 'video-evidence-ai-bridge-preview' in stem else
           'PTTI · 视频证据复盘 Preview' if 'video-evidence-preview' in stem else
           'PTTI · Vision v2 Person Preview' if 'vision-v2-person-preview' in stem else
           'PTTI · Vision v2 Player Tracking v1 Preview' if 'vision-v2-player-tracking-v1-preview' in stem else
           'PTTI · Vision v2 Player Motion Preview' if 'vision-v2-player-motion-preview' in stem else
           'PTTI · Evidence Fusion Preview' if 'evidence-fusion-preview' in stem else
           'PTTI · Vision v2 Player Tracking Preview' if 'vision-v2-player-tracking-preview' in stem else
           'PTTI · Vision v2 Hybrid Scene Preview' if 'hybrid-scene-preview' in stem else
           'PTTI · Vision Lab v2 Scene Bootstrap Preview' if 'scene-bootstrap-preview' in stem or 'vision-lab-v2-scene-preview' in stem else
           'PTTI · Professional Preview v0.2' if 'professional-preview' in stem else
           'PTTI · 个人乒乓球比赛分析'))
    try:
        webview.create_window(title,url,width=width,height=height,min_size=(1024,640),js_api=DesktopAPI())
        if native_qa:
            webview.start(**native_qa.webview_options)
        elif stem == 'ptti-next-preview':
            local=Path(os.environ.get('LOCALAPPDATA',Path.home()))
            storage=local/'PTTI-Dev'/'Next-D2-Preview'/'webview2-user-data'
            storage.mkdir(parents=True,exist_ok=True)
            webview.start(private_mode=False,storage_path=str(storage))
        else:
            webview.start()
    finally:
        update_stop.set(); server.should_exit=True; thread.join(timeout=5)
        if server_socket:
            server_socket.close()

if __name__=='__main__':
    try: main()
    except Exception:
        import traceback
        import os
        from pathlib import Path
        native_root=os.environ.get('PTTI_NATIVE_QA_ROOT') if os.environ.get('PTTI_NATIVE_QA')=='1' else None
        target=(Path(native_root) if native_root else Path(os.environ.get('LOCALAPPDATA',Path.home()))/'PTTI-Dev'/'NativeQA'/'GEX03') if os.environ.get('PTTI_NATIVE_QA')=='1' else Path(os.environ.get('LOCALAPPDATA',Path.home()))/('PTTI' if os.environ.get('PTTI_ENV')=='production' else 'PTTI-Dev')
        target.mkdir(parents=True,exist_ok=True)
        error_log=target/('startup-error-'+time.strftime('%Y%m%dT%H%M%S')+'.log' if os.environ.get('PTTI_NATIVE_QA')=='1' else 'startup-error.log')
        error_log.write_text(traceback.format_exc(),encoding='utf-8')
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,'PTTI 无法启动。请确认已完整解压，并已安装 Microsoft Edge WebView2 Runtime。\n\n已有比赛不会被重置。日志：\n'+str(error_log),'PTTI · 启动失败',0x10)
        except Exception: pass
        raise
