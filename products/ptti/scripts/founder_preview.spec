# Founder Preview onedir spec. Inputs must be separately prepared and reviewed.
# Running this spec produces a candidate only in an explicitly approved environment.
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

spec_root = Path(SPECPATH).resolve()
ptti_root = spec_root.parent
prepared = Path(os.environ['PTTI_FOUNDER_PREPARED']).resolve(strict=True)
if not (prepared / 'dist' / 'index.html').is_file() or not (prepared / 'founder-build.json').is_file():
    raise RuntimeError('Prepared unified frontend and manifest are required')
api = ptti_root / 'frontend' / 'scripts' / 'demo_moment_api.py'
if not api.is_file():
    raise RuntimeError('Isolated demo API is missing')

a = Analysis([str(ptti_root / 'apps' / 'founder_preview_host.py')],
             pathex=[str(ptti_root)],
             binaries=[],
             datas=[(str(prepared / 'dist'), 'frontend/dist'),
                    (str(prepared / 'founder-build.json'), 'frontend'),
                    (str(api), 'frontend/scripts')],
             # The isolated Demo API is bundled as a data file and loaded with
             # importlib at runtime. PyInstaller cannot discover its sqlite3
             # imports from Analysis of the host entry point alone.
             hiddenimports=['apps.founder_preview_guard', 'webview.platforms.edgechromium',
                            'sqlite3', 'sqlite3.dbapi2', '_sqlite3'] + collect_submodules('webview'),
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['torch','onnxruntime','tensorflow'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='PTTI-Founder-Preview', console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='PTTI-Founder-Preview')
