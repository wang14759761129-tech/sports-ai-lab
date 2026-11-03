"""Build-only CI companion to dev_sync. Never install or activate a version."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.desktop_updates import digest, manifest, verify  # noqa: E402
from scripts.build_dual_source_v061_preview import (  # noqa: E402
    MIN_START_RAM_BYTES, PackagerTimeoutError, run_packager,
)
from backend.health_check import safe_error_type  # noqa: E402
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


def verify_health_check_result(report_path, qa_db, temp_root, expected_commit, returncode):
    """Require the child exit, health payload, source identity, and paths to agree."""
    root = Path(temp_root).resolve()
    report = Path(report_path).resolve()
    database = Path(qa_db).resolve()
    try:
        report.relative_to(root)
        database.relative_to(root)
    except ValueError as exc:
        raise RuntimeError('Health result or QA database outside runner temp') from exc
    if returncode != 0:
        raise RuntimeError('Health check did not exit normally')
    if database.suffix.casefold() not in {'.db', '.sqlite', '.sqlite3'} or not database.is_file():
        raise RuntimeError('Health check QA database is missing or invalid')
    try:
        value = json.loads(report.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise RuntimeError('Health result is missing or invalid') from exc
    if value.get('status') != 'success' or value.get('stage') != 'normal_exit' or value.get('exit_code') != 0:
        raise RuntimeError('Health result does not confirm normal exit')
    if value.get('database_location') != 'runner_temp':
        raise RuntimeError('Health result does not confirm isolated QA database')
    health = value.get('health')
    if not isinstance(health, dict) or health.get('build_commit') != expected_commit:
        raise RuntimeError('Health result source commit mismatch')
    return health


def record_health_timeout(report_path):
    """Turn the last safe stage snapshot into a bounded-timeout failure record."""
    report = Path(report_path)
    try:
        value = json.loads(report.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    if value.get('status') != 'running':
        return False
    value.update(status='failed', exit_code=124,
                 error_type='PackagerTimeoutError', exit_reason='health_check_timeout')
    report.write_text(json.dumps(value, sort_keys=True), encoding='utf-8')
    return True


def summarize_pytest_report(xml_path):
    """Return collection and failure counts without copying raw tracebacks into metadata."""
    path = Path(xml_path)
    if not path.is_file():
        return {'status': 'report_missing', 'collection': 'unknown', 'failure_reason': 'junit_report_missing'}
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return {'status': 'report_invalid', 'collection': 'unknown', 'failure_reason': 'junit_report_invalid'}

    suites = list(root.iter('testsuite'))
    tests = sum(int(suite.get('tests', 0)) for suite in suites)
    errors = sum(int(suite.get('errors', 0)) for suite in suites)
    failures = sum(int(suite.get('failures', 0)) for suite in suites)
    skipped = sum(int(suite.get('skipped', 0)) for suite in suites)
    collection_errors = [
        node for node in root.iter('error')
        if node.get('message', '').casefold() == 'collection failure'
    ]
    error_text = '\n'.join(node.text or '' for node in root.iter('error'))
    guard_rejected_temp = (
        'PRODUCTION_DATABASE_WRITE_GUARD' in error_text
        and any(marker in error_text.casefold() for marker in (
            'under the system temporary directory', 'under os temp',
        ))
    )
    if collection_errors and guard_rejected_temp:
        reason = 'database_path_guard_rejected_temp_root'
    elif collection_errors:
        reason = 'pytest_collection_error'
    elif failures:
        reason = 'pytest_test_failure'
    elif errors:
        reason = 'pytest_test_error'
    elif tests == 0:
        reason = 'pytest_collected_no_tests'
    else:
        reason = 'none'
    return {
        'status': 'passed' if tests and not (errors or failures) else 'failed',
        'collection': 'failed' if collection_errors else 'completed',
        'collected_cases': tests,
        'collection_errors': len(collection_errors),
        'test_errors': max(0, errors - len(collection_errors)),
        'test_failures': failures,
        'skipped': skipped,
        'failure_reason': reason,
    }


def pytest_failure_message(summary):
    reason = summary.get('failure_reason')
    allowed = {
        'database_path_guard_rejected_temp_root',
        'pytest_collection_error',
        'pytest_collected_no_tests',
        'pytest_test_failure',
        'pytest_test_error',
        'junit_report_missing',
        'junit_report_invalid',
    }
    if reason not in allowed:
        reason = 'pytest_process_failed'
    return f'pytest failed: {reason}'


def sanitize_pytest_artifacts(paths, roots):
    """Mask machine-specific roots in logs and JUnit while preserving relative evidence."""
    replacements = {}
    for label, root in roots:
        value = str(Path(root).resolve())
        replacements[value] = label
        replacements[value.replace('\\', '/')] = label
    for path in paths:
        path = Path(path)
        if not path.is_file():
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        for value, label in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
            text = re.sub(re.escape(value), f'[{label}]', text, flags=re.IGNORECASE)
        path.write_text(text, encoding='utf-8')


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
              'native_gui': 'NOT_TESTED', 'status': 'FAILED',
              'database_path_roots': {
                  'pytest_bootstrap': 'OS_TEMP',
                  'test_database_allowlist': ['OS_TEMP', 'RUNNER_TEMP'],
                  'deployment_health_check': 'RUNNER_TEMP only',
              },
              'pytest': {'status': 'not_started', 'collection': 'unknown'}}
    try:
        validate_source(expected)
        if psutil.virtual_memory().available < MIN_START_RAM_BYTES:
            raise RuntimeError('2.5 GiB start resource guard')
        if shutil.disk_usage(output).free < 3 * 1024**3:
            raise RuntimeError('3 GiB free disk required')
        node = shutil.which('node.exe') or shutil.which('node')
        npm = shutil.which('npm.cmd') or shutil.which('npm')
        if not node or not npm:
            raise RuntimeError('Pinned Node.js/npm unavailable')
        result['build_environment'] = {
            'python': sys.version.split()[0],
            'pip': subprocess.check_output([sys.executable, '-m', 'pip', '--version'], text=True).strip(),
            'node': subprocess.check_output([node, '--version'], text=True).strip(),
            'npm': subprocess.check_output([npm, '--version'], text=True).strip(),
            'frontend_lock_sha256': digest(ROOT / 'frontend/package-lock.json'),
            'ffmpeg_archive_sha256': os.environ.get('PTTI_FFMPEG_ARCHIVE_SHA256'),
            'workflow_run_id': os.environ.get('GITHUB_RUN_ID'),
            'workflow_ref': os.environ.get('GITHUB_WORKFLOW_REF'),
        }
        result['media_tools'] = {
            tool: subprocess.check_output([tool, '-version'], text=True).splitlines()[0]
            for tool in ('ffmpeg', 'ffprobe')
        }
        pytest_xml = reports / 'pytest.xml'
        pytest_log = reports / 'pytest.log'
        try:
            run_packager([sys.executable, '-m', 'pytest', '-q',
                          '--junitxml', str(pytest_xml)], pytest_log)
        except subprocess.CalledProcessError:
            result['pytest'] = summarize_pytest_report(pytest_xml)
            result['error_type'] = 'CalledProcessError'
            result['exit_reason'] = result['pytest']['failure_reason']
            raise SystemExit(pytest_failure_message(result['pytest'])) from None
        except Exception:
            result['pytest'] = summarize_pytest_report(pytest_xml)
            raise
        else:
            result['pytest'] = summarize_pytest_report(pytest_xml)
        finally:
            sanitize_pytest_artifacts(
                [pytest_log, pytest_xml],
                [('OS_TEMP', tempfile.gettempdir()), ('RUNNER_TEMP', temp),
                 ('WORKSPACE', ROOT), ('PYTHON_ROOT', sys.prefix)],
            )
        run_packager([sys.executable, '-m', 'pip', 'check'], reports / 'pip-check.log')
        for name in ['test:feed', 'test:studio', 'test:review', 'test:score', 'test:score-observation', 'build']:
            if name == 'build':
                for required_test in ['test:official-playback', 'test:vision-source-recovery', 'test:qa-proxy']:
                    run_packager([npm, '--prefix', 'frontend', 'run', required_test],
                                 reports / (required_test.replace(':', '-') + '.log'))
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
        with tempfile.TemporaryDirectory(prefix='ptti-ci-qa-', dir=temp) as qa:
            qa_root = Path(qa).resolve()
            if not qa_root.is_relative_to(temp):
                raise RuntimeError('QA database directory must remain inside RUNNER_TEMP')
            qa_db = Path(qa) / 'matches.db'
            health_report = reports / 'health-check.json'
            health_env = os.environ.copy()
            health_env.update({
                'PTTI_PREVIEW_QA_DB': str(qa_db),
                'PTTI_HEALTH_CHECK_MODE': '1',
                'PTTI_HEALTH_CHECK_RESULT': str(health_report),
                'PTTI_EXPECTED_COMMIT': expected,
            })
            health_returncode = run_packager(
                [str(exe), '--deployment-health-check'], reports / 'health.log',
                timeout_seconds=120, env=health_env,
            )
            health = verify_health_check_result(
                health_report, qa_db, temp, expected, health_returncode,
            )
            (reports / 'health.json').write_text(json.dumps(health, indent=2), encoding='utf8')
            result['qa_database'] = 'RUNNER_TEMP/ptti-ci-qa-*/matches.db (removed after health check)'
        validate_source(expected)
        result.update(status='BUILD_VERIFIED_NATIVE_ACCEPTANCE_PENDING',
                      exe_sha256=digest(exe), manifest=value,
                      icon_sha256=digest(ROOT / 'assets/ptti.ico'))
        (folder / 'manifest.json').write_text(json.dumps(value, indent=2), encoding='utf8')
        shutil.copytree(folder, output / 'package')
    except Exception as exc:
        result['error_type'] = safe_error_type(exc)
        result['exit_reason'] = getattr(exc, 'reason', 'candidate_validation_failed')
        health_report = reports / 'health-check.json'
        if isinstance(exc, PackagerTimeoutError):
            result['health_timeout_recorded'] = record_health_timeout(health_report)
        if health_report.is_file():
            try:
                health_value = json.loads(health_report.read_text(encoding='utf-8'))
                result['health_stage'] = health_value.get('stage')
                result['health_error_type'] = health_value.get('error_type')
                result['health_exit_reason'] = health_value.get('exit_reason')
            except (OSError, ValueError):
                result['health_report'] = 'invalid'
        raise
    finally:
        (reports / 'candidate-report.json').write_text(
            json.dumps(result, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
