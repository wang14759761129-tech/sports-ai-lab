"""Build-only CI companion to dev_sync. Never install or activate a version."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.desktop_updates import digest, manifest, verify  # noqa: E402
from scripts.build_dual_source_v061_preview import (  # noqa: E402
    MIN_START_RAM_BYTES, run_packager,
)
import psutil  # noqa: E402


def validate_source(expected):
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if actual != expected or subprocess.check_output(
        ['git', 'status', '--porcelain'], cwd=ROOT, text=True
    ).strip():
        raise RuntimeError('Clean exact target commit required')
    if digest(ROOT / 'configs/evidence-fusion/HIT_EVENT_V0_3_FROZEN_CONFIG.json') != (
        'fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3'
    ):
        raise RuntimeError('Frozen config mismatch')
    forbidden = {'.db', '.sqlite', '.sqlite3', '.mp4', '.mov', '.mkv', '.pt', '.pth', '.env'}
    tracked = subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines()
    if any(Path(p).suffix.lower() in forbidden for p in tracked):
        raise RuntimeError('Tracked sensitive/media file')
    return actual


def main():
    if sys.platform != 'win32' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('This build-only command requires an isolated Windows Actions runner')
    expected = os.environ['PTTI_EXPECTED_COMMIT']
    output = Path(os.environ['PTTI_CI_OUTPUT']).resolve()
    temp = Path(os.environ['RUNNER_TEMP']).resolve()
    if not output.is_relative_to(temp) or output == temp:
        raise RuntimeError('Output must be a dedicated runner temporary directory')
    output.mkdir(exist_ok=False)
    reports = output / 'reports'
    reports.mkdir()
    result = {'source_commit': expected, 'activation': 'NOT_ATTEMPTED',
              'native_gui': 'NOT_TESTED', 'status': 'FAILED'}
    try:
        validate_source(expected)
        if psutil.virtual_memory().available < MIN_START_RAM_BYTES:
            raise RuntimeError('2.5 GiB start resource guard')
        if shutil.disk_usage(output).free < 3 * 1024**3:
            raise RuntimeError('3 GiB free disk required')
        run_packager([sys.executable, '-m', 'pytest', '-q',
                      '--junitxml', str(reports / 'pytest.xml')], reports / 'pytest.log')
        run_packager([sys.executable, '-m', 'pip', 'check'], reports / 'pip-check.log')
        npm = shutil.which('npm.cmd')
        if not npm:
            raise RuntimeError('npm unavailable')
        for name in ['test:feed', 'test:studio', 'test:review', 'test:score', 'test:score-observation', 'build']:
            run_packager([npm, '--prefix', 'frontend', 'run', name],
                         reports / (name.replace(':', '-') + '.log'))
        run_packager([sys.executable, '-m', 'compileall', '-q', 'apps', 'backend', 'scripts'],
                     reports / 'compile.log')
        run_packager(['git', 'diff', '--check'], reports / 'diff-check.log')
        result['dependencies'] = subprocess.check_output(
            [sys.executable, '-m', 'pip', 'freeze'], text=True).splitlines()
        os.environ['PTTI_PREVIEW_PROFILE'] = 'video-first-r4'
        os.environ['PTTI_PREVIEW_BUILD_ROOT'] = str(output / 'build')
        run_packager([sys.executable, 'scripts/build_dual_source_v061_preview.py'],
                     reports / 'windows-build.log')
        folders = list((output / 'build').glob('*/dist/PTTI-Video-First-R4-Preview'))
        if len(folders) != 1:
            raise RuntimeError('Expected one candidate package')
        folder = folders[0]
        value = manifest(folder)
        exe = verify(folder, value)
        if value['commit'] != expected:
            raise RuntimeError('Package commit mismatch')
        for source in (ROOT / 'frontend/dist').rglob('*'):
            if source.is_file() and digest(source) != digest(
                folder / '_internal/frontend/dist' / source.relative_to(ROOT / 'frontend/dist')
            ):
                raise RuntimeError('Packaged frontend mismatch')
        with tempfile.TemporaryDirectory(prefix='ptti-ci-qa-') as qa:
            qa_db = Path(qa) / 'matches.db'
            os.environ['PTTI_PREVIEW_QA_DB'] = str(qa_db)
            run_packager([str(exe), '--deployment-health-check'], reports / 'health.log')
            health = json.loads(qa_db.with_suffix('.health.json').read_text(encoding='utf8'))
            if health['build_commit'] != expected:
                raise RuntimeError('Health identity mismatch')
            (reports / 'health.json').write_text(json.dumps(health, indent=2), encoding='utf8')
        validate_source(expected)
        result.update(status='BUILD_VERIFIED_NATIVE_ACCEPTANCE_PENDING',
                      exe_sha256=digest(exe), manifest=value,
                      icon_sha256=digest(ROOT / 'assets/ptti.ico'))
        (folder / 'manifest.json').write_text(json.dumps(value, indent=2), encoding='utf8')
        shutil.copytree(folder, output / 'package')
    except Exception as exc:
        result['error'] = str(exc)
        raise
    finally:
        (reports / 'candidate-report.json').write_text(
            json.dumps(result, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
