import json
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.desktop_updates import active, install, manifest, verify, status, check_release


def package(tmp_path, label):
    p = tmp_path / label
    (p / '_internal/frontend/dist').mkdir(parents=True)
    (p / 'app.exe').write_bytes(b'SIMULATED_PACKAGE_NOT_A_REAL_EXE:' + label.encode())
    (p / '_internal/frontend/dist/index.html').write_text(label)
    (p / 'build-info.json').write_text(json.dumps({'environment': 'DEVELOPMENT',
        'source_tree_dirty': False, 'commit': hashlib.sha256(label.encode()).hexdigest()[:40], 'version': label}))
    return p


def test_a_b_c_same_pointer_data_preserved_and_previous_available(tmp_path):
    root = tmp_path / 'install'
    db = tmp_path / 'user-data.db'
    db.write_bytes(b'QA_DATA_NO_PRODUCTION')
    calls = []
    for version in ['A', 'B', 'C']:
        install(root, package(tmp_path, version), lambda exe, m: calls.append(m['version']))
        assert json.loads((active(root).parent / 'build-info.json').read_text())['version'] == version
        assert db.read_bytes() == b'QA_DATA_NO_PRODUCTION'
    assert calls == ['A', 'B', 'C']
    assert json.loads((active(root, previous=True).parent / 'build-info.json').read_text())['version'] == 'B'
    assert status(root, 'old')['restart_pending']


def test_health_failure_preserves_pointer(tmp_path):
    root = tmp_path / 'install'
    install(root, package(tmp_path, 'A'), lambda *args: None)
    before = (root / 'current-preview.json').read_bytes()
    def fail(*args):
        raise RuntimeError('Simulated health failure')
    with pytest.raises(RuntimeError):
        install(root, package(tmp_path, 'B'), fail)
    assert (root / 'current-preview.json').read_bytes() == before
    assert active(root).is_file()


@pytest.mark.parametrize('damage', ['corrupt', 'missing', 'extra', 'escape'])
def test_integrity_failure_and_last_good_version(tmp_path, damage):
    root = tmp_path / 'install'
    install(root, package(tmp_path, 'A'), lambda *args: None)
    install(root, package(tmp_path, 'B'), lambda *args: None)
    exe = active(root)
    value = json.loads((root / 'current-preview.json').read_text())['manifest']
    if damage == 'corrupt':
        exe.write_bytes(b'corrupted')
    elif damage == 'missing':
        exe.unlink()
    elif damage == 'extra':
        (exe.parent / 'unexpected.dll').write_bytes(b'untrusted')
    else:
        value['files']['../escape.exe'] = '0' * 64
    with pytest.raises(ValueError):
        verify(exe.parent, value)
    assert active(root, previous=True).is_file()


def test_no_databases_or_media_and_deploy_lock(tmp_path):
    p = package(tmp_path, 'A')
    (p / 'private.db').write_bytes(b'private')
    with pytest.raises(ValueError):
        manifest(p)
    root = tmp_path / 'install'
    root.mkdir()
    (root / '.deploy.lock').write_text('another process')
    with pytest.raises(FileExistsError):
        install(root, p, lambda *args: None)


def test_remote_failure_never_stops_offline_launcher(monkeypatch):
    monkeypatch.setattr('backend.desktop_updates.urlopen', lambda *args, **kwargs: (_ for _ in ()).throw(OSError()))
    assert check_release('preview')['status'] == 'OFFLINE_OR_UNAVAILABLE'
    assert not check_release('stable')['automatic_install']


@pytest.mark.skipif(os.name != 'nt', reason='Windows PowerShell launcher test')
def test_actual_powershell_launcher_a_b_c_and_corruption_fallback(tmp_path):
    root = tmp_path / 'fixed-launcher'
    root.mkdir()
    shutil.copy2('scripts/desktop-launcher.ps1', root / 'launcher.ps1')
    ps = str(Path(os.environ['WINDIR']) / 'System32/WindowsPowerShell/v1.0/powershell.exe')
    command = [ps, '-NoProfile', '-File', str(root / 'launcher.ps1'), '-VerifyOnly']
    for label in ['A', 'B', 'C']:
        install(root, package(tmp_path, label), lambda *args: None)
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr
        assert str(active(root)) in result.stdout
    active(root).write_bytes(b'SIMULATED_CORRUPTION')
    result = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert str(active(root, previous=True)) in result.stdout
