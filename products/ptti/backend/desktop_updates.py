"""Local preview deployment: immutable packages, verified manifests, atomic pointer.

Remote releases are discovery only until an authenticated signing policy is configured.
No database or media is migrated by this module.
"""
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from urllib.request import Request, urlopen
import time

FORBIDDEN = {'.db', '.sqlite', '.sqlite3', '.mp4', '.mkv', '.mov', '.pt', '.pth', '.env'}
_release_cache = {}


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.pending-', suffix='.json')
    try:
        with os.fdopen(fd, 'w', encoding='utf8') as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def manifest(folder):
    folder = Path(folder).resolve()
    info = json.loads((folder / 'build-info.json').read_text(encoding='utf8'))
    if info.get('source_tree_dirty') or info.get('environment') != 'DEVELOPMENT':
        raise ValueError('Only clean development Preview packages are supported')
    exes = list(folder.glob('*.exe'))
    if len(exes) != 1 or not (folder / '_internal/frontend/dist/index.html').is_file():
        raise ValueError('Incomplete package')
    files = {}
    for path in folder.rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlinks are forbidden')
        if path.is_file():
            if path.suffix.lower() in FORBIDDEN or path.name.lower() in {'.env', 'auth.json', 'cookies.txt'}:
                raise ValueError('Database, media, weights or credentials cannot be deployed')
            files[path.relative_to(folder).as_posix()] = digest(path)
    return {'schema': 1, 'channel': 'preview', 'commit': info['commit'],
            'version': info['version'], 'exe': exes[0].name, 'files': files}


def verify(folder, value):
    folder = Path(folder).resolve()
    if value.get('channel') != 'preview' or not value.get('files'):
        raise ValueError('Invalid manifest/channel')
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()
              and p != folder / 'manifest.json'}
    if actual != set(value['files']):
        raise ValueError('Unexpected or missing package files')
    for relative, expected in value['files'].items():
        path = (folder / relative).resolve()
        if not path.is_relative_to(folder) or not path.is_file() or digest(path) != expected:
            raise ValueError('Package integrity mismatch: ' + relative)
    if value['exe'] not in value['files'] or '_internal/frontend/dist/index.html' not in value['files']:
        raise ValueError('Incomplete manifest')
    info = json.loads((folder / 'build-info.json').read_text(encoding='utf8'))
    if info['commit'] != value['commit']:
        raise ValueError('Build identity mismatch')
    return folder / value['exe']


def _install(root, folder, health_check):
    """Copy/verify/health-check before activation. A failed step never changes pointer."""
    root = Path(root).resolve()
    value = manifest(folder)
    versions = root / 'versions'
    versions.mkdir(parents=True, exist_ok=True)
    target = versions / (value['commit'][:12] + '-' + uuid.uuid4().hex[:8])
    shutil.copytree(folder, target)
    verify(target, value)
    health_check(target / value['exe'], value)
    atomic_json(target / 'manifest.json', value)
    pointer = root / 'current-preview.json'
    if pointer.exists():
        previous = json.loads(pointer.read_text(encoding='utf8'))
        verify(root / previous['folder'], previous['manifest'])
        atomic_json(root / 'previous-preview.json', previous)
    active = {'folder': target.relative_to(root).as_posix(), 'manifest': value}
    atomic_json(pointer, active)
    return active


def install(root, folder, health_check):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock = root / '.deploy.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode())
        return _install(root, folder, health_check)
    finally:
        os.close(fd)
        lock.unlink()


def active(root, previous=False):
    root = Path(root).resolve()
    pointer = root / ('previous-preview.json' if previous else 'current-preview.json')
    value = json.loads(pointer.read_text(encoding='utf8'))
    folder = (root / value['folder']).resolve()
    if not folder.is_relative_to(root / 'versions'):
        raise ValueError('Version path escaped deployment root')
    return verify(folder, value['manifest'])


def status(root, running_commit=None):
    try:
        active(root)
        value = json.loads((Path(root) / 'current-preview.json').read_text(encoding='utf8'))['manifest']
        return {'channel': 'preview', 'deployed_commit': value['commit'],
                'restart_pending': bool(running_commit and running_commit != value['commit']),
                'integrity': 'VERIFIED', 'remote_install': 'CONFIRMATION_AND_TRUST_POLICY_REQUIRED'}
    except (OSError, ValueError, KeyError):
        return {'channel': 'preview', 'integrity': 'NOT_DEPLOYED_OR_INVALID', 'restart_pending': False}


def check_release(channel):
    if channel not in {'preview', 'stable'}:
        raise ValueError('Unknown channel')
    cached = _release_cache.get(channel)
    if cached and time.monotonic() - cached[0] < 1800:
        return cached[1]
    req = Request('https://api.github.com/repos/wang14759761129-tech/sports-ai-lab/releases?per_page=20',
                  headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'PTTI-Update-Check'})
    try:
        with urlopen(req, timeout=8) as response:
            rows = json.loads(response.read(1024 * 1024))
        rows = [r for r in rows if not r['draft'] and r['prerelease'] == (channel == 'preview')
                and r['tag_name'].startswith('ptti-')]
        result = {'channel': channel, 'release': rows[0]['html_url'] if rows else None,
                'status': 'RELEASE_DISCOVERED_NOT_INSTALL_APPROVED' if rows else 'NO_INSTALLABLE_RELEASE',
                'automatic_install': False}
    except (OSError, ValueError, KeyError):
        result = {'channel': channel, 'status': 'OFFLINE_OR_UNAVAILABLE', 'automatic_install': False}
    _release_cache[channel] = (time.monotonic(), result)
    return result
