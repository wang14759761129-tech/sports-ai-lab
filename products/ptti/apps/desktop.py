import os
from pathlib import Path

def desktop_window_title(executable_name, legacy_title, build_commit=None):
    if Path(executable_name).stem.casefold() == 'ptti-video-first-r4-preview':
        build = str(build_commit or '').strip()[:10]
        return 'PTTI Cinema · ' + (build or 'Preview')
    return legacy_title

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

class DesktopAPI:
    def record_playback_diagnostic(self, payload):
        from backend.playback_diagnostics import record_ui_state
        return record_ui_state(payload)

    def open_official_video(self, requested_url):
        from apps.external_links import open_official_video_url
        return open_official_video_url(requested_url)

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


def report_health_startup_failure(exc, reporter):
    """Persist a sanitized failure and return the non-zero unattended exit code."""
    reporter.fail(exc, exit_code=2)
    return 2

def main():
    import sys
    from backend.health_check import (
        HealthCheckError, HealthCheckReporter, fetch_health_json,
        is_health_check_mode, set_active_reporter, set_health_stage,
        validate_qa_database_path,
    )
    health_mode = is_health_check_mode()
    reporter = HealthCheckReporter.from_environment() if health_mode else None
    if reporter is not None:
        set_active_reporter(reporter)
        os.environ['PTTI_HEALTH_CHECK_MODE'] = '1'
        set_health_stage('startup')
    set_health_stage('importing_runtime') if health_mode else None
    import socket
    import threading
    import time
    import urllib.request
    import uvicorn
    if not health_mode:
        import webview
        globals()['webview'] = webview
    if getattr(sys, 'frozen', False):
        executable=Path(sys.executable).stem.casefold()
        if is_development_preview(sys.executable):
            # Preview is fail-closed development, even when launched with stale env vars.
            os.environ['PTTI_ENV']='development'
            os.environ['PTTI_PREVIEW']='1'
            local=Path(os.environ.get('LOCALAPPDATA',Path.home()))
            os.environ['PTTI_DB']=str(local/'PTTI-Dev'/'ProfessionalPreview'/'matches.db')
            if executable in {'ptti-dual-source-v0.6.1-preview','ptti-personal-match-library-r3-preview','ptti-video-first-r4-preview','ptti-dark-studio-v0.7-preview','ptti-cinema-v0.7.1-preview'}:
                configure_dual_source_preview(local, database_subdir={
                    'ptti-personal-match-library-r3-preview':'PersonalMatchLibrary-R3-Preview',
                    'ptti-video-first-r4-preview':'VideoFirst-R4-Preview',
                    'ptti-dark-studio-v0.7-preview':'DarkStudio-v07-Preview',
                    'ptti-cinema-v0.7.1-preview':'Cinema-v071-Preview',
                }.get(executable,'DualSource-v061-Preview'))
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
            if health_mode:
                set_health_stage('qa_database_validation')
                if not qa_database:
                    raise HealthCheckError('qa_database_outside_temp')
            if qa_database:
                from backend.temp_paths import resolve_temp_root
                try:
                    candidate=validate_qa_database_path(qa_database, resolve_temp_root())
                except HealthCheckError:
                    from backend.playback_diagnostics import record_qa_database_rejected
                    record_qa_database_rejected()
                    raise
                os.environ['PTTI_DB']=str(candidate)
                os.environ['PTTI_ENV']='test'
            os.environ['PTTI_RESEARCH_DATA_ROOT']=str(local/'PTTI-Dev')
            internal=Path(getattr(sys,'_MEIPASS',Path(sys.executable).parent))
            os.environ['PATH']=str(internal)+os.pathsep+os.environ.get('PATH','')
            build=Path(getattr(sys,'_MEIPASS',Path(sys.executable).parent))/'build-info.json'
            if build.is_file():
                import json
                build_info=json.loads(build.read_text(encoding='utf-8'))
                if executable in {'ptti-video-evidence-v0.3-preview','ptti-match-library-v0.4-preview','ptti-score-navigation-v0.1-preview','ptti-video-first-v0.5-preview','ptti-video-first-v0.5.1-preview','ptti-dual-source-v0.6.1-preview','ptti-personal-match-library-r3-preview','ptti-video-first-r4-preview','ptti-dark-studio-v0.7-preview','ptti-cinema-v0.7.1-preview'}:
                    os.environ['PTTI_PREVIEW_VERSION']=build_info['version']
                    os.environ['PTTI_PREVIEW_COMMIT']=build_info['commit']
                    os.environ['PTTI_PREVIEW_BUILT_AT']=build_info.get('built_at','')
                    if executable in {'ptti-score-navigation-v0.1-preview','ptti-video-first-v0.5-preview','ptti-video-first-v0.5.1-preview','ptti-dual-source-v0.6.1-preview','ptti-personal-match-library-r3-preview','ptti-video-first-r4-preview','ptti-dark-studio-v0.7-preview','ptti-cinema-v0.7.1-preview'}:
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
    if health_mode:
        set_health_stage('importing_backend')
    from backend.main import app
    if not health_mode:
        webview.settings['ALLOW_DOWNLOADS']=True
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
    if health_mode:
        set_health_stage('service_starting')
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_config=None))
    thread=threading.Thread(target=server.run,daemon=True); thread.start()
    url=f'http://127.0.0.1:{port}'
    for _ in range(100):
        try:
            urllib.request.urlopen(url+'/api/health',timeout=.2); break
        except Exception: time.sleep(.1)
    else: raise RuntimeError('Local PTTI server did not start')
    if health_mode:
        set_health_stage('service_ready')
    from backend.playback_diagnostics import record_server_started
    database_location = 'os_temp_qa' if os.environ.get('PTTI_PREVIEW_QA_DB') else 'ptti_dev'
    record_server_started(port, database_location)
    update_stop = threading.Event()
    def update_discovery():
        from backend.desktop_updates import check_release
        while not update_stop.is_set():
            check_release('preview')
            update_stop.wait(1800)
    if os.environ.get('PTTI_DESKTOP_DEPLOY_ROOT') and '--deployment-health-check' not in sys.argv:
        threading.Thread(target=update_discovery, daemon=True).start()
    if health_mode:
        try:
            set_health_stage('http_check')
            health = fetch_health_json(url+'/api/health', timeout=5)
            expected_commit = os.environ.get('PTTI_EXPECTED_COMMIT')
            if expected_commit and health.get('build_commit') != expected_commit:
                raise HealthCheckError('health_commit_mismatch')
        finally:
            server.should_exit=True
            thread.join(timeout=5)
        if thread.is_alive():
            raise HealthCheckError('service_shutdown_timeout')
        set_health_stage('result_write')
        reporter.succeed(health, exit_code=0)
        return
    width,height=1366,768
    requested=os.environ.get('PTTI_WINDOW_SIZE','')
    if requested:
        try:
            width,height=map(int,requested.lower().split('x'));width=max(1024,width);height=max(640,height)
        except ValueError: pass
    print('PTTI Desktop URL: '+url,flush=True)
    stem=Path(sys.executable).stem.casefold()
    title=(f"{os.environ.get('PTTI_PREVIEW_PRODUCT_NAME','PTTI 比分导航')} v{os.environ.get('PTTI_PREVIEW_VERSION','0.1')} Preview · {os.environ.get('PTTI_PREVIEW_BUILD_ID',os.environ.get('PTTI_PREVIEW_COMMIT','UNKNOWN')[:10])}" if stem in {'ptti-score-navigation-v0.1-preview','ptti-video-first-v0.5-preview','ptti-video-first-v0.5.1-preview','ptti-dual-source-v0.6.1-preview','ptti-personal-match-library-r3-preview','ptti-video-first-r4-preview','ptti-dark-studio-v0.7-preview','ptti-cinema-v0.7.1-preview'} else ('PTTI · 比赛录像库 v0.4 Preview · '+os.environ.get('PTTI_PREVIEW_COMMIT','UNKNOWN')[:10] if stem=='ptti-match-library-v0.4-preview' else ('PTTI · Video Evidence v0.3 Preview · '+os.environ.get('PTTI_PREVIEW_COMMIT','UNKNOWN')[:10]) if stem=='ptti-video-evidence-v0.3-preview' else
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
    title=desktop_window_title(sys.executable,title,os.environ.get('PTTI_PREVIEW_COMMIT'))
    webview.create_window(title,url,width=width,height=height,min_size=(1024,640),js_api=DesktopAPI())
    try: webview.start()
    finally: update_stop.set(); server.should_exit=True; thread.join(timeout=5)

if __name__=='__main__':
    try: main()
    except Exception as exc:
        import sys
        from backend.health_check import (
            HealthCheckReporter, get_active_reporter, is_health_check_mode,
        )
        if is_health_check_mode():
            reporter = get_active_reporter()
            try:
                reporter = reporter or HealthCheckReporter.from_environment()
                exit_code = report_health_startup_failure(exc, reporter)
            except Exception:
                # Never fall through to a GUI prompt in unattended health-check mode.
                exit_code = 2
            raise SystemExit(exit_code) from None
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
