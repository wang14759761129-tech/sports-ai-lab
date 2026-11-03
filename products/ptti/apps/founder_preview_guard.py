"""Offline identity and single-instance protection for Founder Preview."""
from __future__ import annotations
import ctypes
import hashlib
import json
import os
from pathlib import Path

COMMIT = '5946c0c4d0517ade316b748933151816c6c504d3'
MUTEX = r'Local\PTTI.FounderPreview.Isolated'

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()

def verify_dist(dist: Path, manifest: Path) -> None:
    root = dist.resolve(strict=True)
    info = json.loads(manifest.read_text(encoding='utf-8'))
    if info.get('schema') != 'ptti.founder.dist/1' or info.get('source_commit') != COMMIT or info.get('unified_mode') is not True:
        raise RuntimeError('预览包身份不匹配。')
    expected = info.get('files')
    if not isinstance(expected, dict) or not expected or 'index.html' not in expected or 'demo-synthetic.mp4' not in expected:
        raise RuntimeError('预览文件清单无效。')
    actual = {}
    for p in root.rglob('*'):
        if p.is_symlink():
            raise RuntimeError('预览资源不允许符号链接。')
        if p.is_file():
            actual[p.relative_to(root).as_posix()] = digest(p)
    if actual != expected:
        raise RuntimeError('预览文件不完整或哈希不匹配。')

def acquire_mutex():
    if os.name != 'nt':
        raise RuntimeError('此预览仅支持 Windows。')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
    kernel.CreateMutexW.restype = ctypes.c_void_p
    ctypes.set_last_error(0)
    handle = kernel.CreateMutexW(None, False, MUTEX)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
        kernel.CloseHandle(handle)
        raise RuntimeError('PTTI Founder Preview 已在运行。')
    return handle

def release_mutex(handle):
    if handle:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
        kernel.CloseHandle(handle)

