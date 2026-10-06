# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('build/build-info.json', '.'), ('frontend/dist', 'frontend/dist'), ('data/samples', 'data/samples'), ('data/professional', 'data/professional'), ('vision_worker/balltrack.py', 'vision_worker'), ('vision_worker/background.py', 'vision_worker'), ('vision_worker/overlay.py', 'vision_worker'), ('vision_worker/candidates.py', 'vision_worker'), ('configs/vision/PLAYER_TRACKING_V1_CANDIDATE.json', 'configs/vision')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('webview')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['apps/desktop.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PTTI-Vision-Dev',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/ptti.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PTTI-Vision-Dev',
)
