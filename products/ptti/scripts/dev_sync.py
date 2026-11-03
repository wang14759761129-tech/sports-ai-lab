"""One-command clean-source test/build/verify/QA/activate. No network code execution."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.desktop_updates import install, digest  # noqa: E402
from scripts.build_dual_source_v061_preview import run_packager  # noqa: E402


def main():
    deploy = Path(os.environ.get('PTTI_DESKTOP_DEPLOY_ROOT', Path(os.environ['LOCALAPPDATA']) / 'PTTI-Cinema'))
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
        raise RuntimeError('CODE_NOT_COMMITTED: preserve and commit source before sync')
    expected_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if digest(ROOT / 'configs/evidence-fusion/HIT_EVENT_V0_3_FROZEN_CONFIG.json') != 'fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3':
        raise RuntimeError('Frozen research configuration changed')
    if psutil.virtual_memory().available < 2.5 * 1024**3:
        raise RuntimeError('DESKTOP_UPDATE_PENDING: need 2.5 GiB start RAM; hard floor remains 2 GiB')
    deploy.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(deploy).free < 3 * 1024**3:
        raise RuntimeError('DESKTOP_UPDATE_PENDING: need 3 GiB free deployment disk')
    forbidden = {'.db', '.sqlite', '.sqlite3', '.mp4', '.mkv', '.mov', '.pt', '.pth', '.env'}
    files = subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines()
    if any(Path(p).suffix.lower() in forbidden for p in files):
        raise RuntimeError('Sensitive/media tracked-file audit failed')
    logdir = deploy / 'logs' / str(time.time_ns())
    logdir.mkdir(parents=True)
    npm = shutil.which('npm.cmd') or shutil.which('npm')
    if not npm:
        raise RuntimeError('npm unavailable')
    steps = [[sys.executable, '-m', 'pytest', '-q'], [sys.executable, '-m', 'pip', 'check']]
    for index, command in enumerate(steps):
        run_packager(command, logdir / f'backend-{index}.log')
    for name in ['test:feed', 'test:studio', 'test:review', 'test:score', 'test:score-observation', 'build']:
        with (logdir / f'{name.replace(":", "-")}.log').open('w') as out:
            process = subprocess.Popen([npm, 'run', name], cwd=ROOT / 'frontend', stdout=out, stderr=subprocess.STDOUT)
            while process.poll() is None:
                if psutil.virtual_memory().available < 2 * 1024**3:
                    from scripts.build_dual_source_v061_preview import stop_process_tree
                    stop_process_tree(process)
                    raise RuntimeError('DESKTOP_UPDATE_PENDING: frontend resource stop')
                time.sleep(1)
            if process.returncode:
                raise RuntimeError('Frontend check failed: ' + name)
    os.environ['PTTI_PREVIEW_PROFILE'] = 'video-first-r4'
    build_root = Path(os.environ.get('PTTI_DEV_BUILD_ROOT', 'C:/PTTI-Cinema-Builds'))
    os.environ['PTTI_PREVIEW_BUILD_ROOT'] = str(build_root)
    run_packager([sys.executable, 'scripts/build_dual_source_v061_preview.py'], logdir / 'build.log')
    folders = list(build_root.glob('*/dist/PTTI-Video-First-R4-Preview'))
    folder = max(folders, key=lambda p: p.stat().st_mtime_ns)
    if json.loads((folder / 'build-info.json').read_text())['commit'] != expected_commit:
        raise RuntimeError('Source HEAD changed during sync')
    for file in (ROOT / 'frontend/dist').rglob('*'):
        if file.is_file() and digest(file) != digest(folder / '_internal/frontend/dist' / file.relative_to(ROOT / 'frontend/dist')):
            raise RuntimeError('Frontend build/package mismatch')
    def health(exe, value):
        qa = Path(tempfile.mkdtemp(prefix='ptti-sync-qa-')) / 'matches.db'
        env = {**os.environ, 'PTTI_PREVIEW_QA_DB': str(qa)}
        proc = subprocess.Popen([str(exe), '--deployment-health-check'], env=env, cwd=exe.parent)
        try:
            deadline = time.monotonic() + 60
            while proc.poll() is None:
                if psutil.virtual_memory().available < 2 * 1024**3 or time.monotonic() > deadline:
                    raise RuntimeError('Health check resource/timeout stop')
                time.sleep(.5)
            result = proc.returncode
            if result != 0:
                raise RuntimeError('Isolated Preview health check failed')
            report = json.loads(qa.with_suffix('.health.json').read_text())
            if report['build_commit'] != value['commit']:
                raise RuntimeError('Health identity mismatch')
        finally:
            if proc.poll() is None:
                from scripts.build_dual_source_v061_preview import stop_process_tree
                stop_process_tree(proc)
    activated = install(deploy, folder, health)
    print(json.dumps({'status': 'DESKTOP_UPDATED', 'activation': activated['manifest']['commit'],
                      'running_instances': 'UNCHANGED; new target used on next launch'}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('DESKTOP_UPDATE_PENDING:', str(exc))
        sys.exit(1)
