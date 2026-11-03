"""Read-only Windows process/database evidence. Run with the explicit product venv."""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys


def process_details(pid):
    result = {'pid': pid}
    if os.name != 'nt' or struct.calcsize('P') != 8:
        return result | {'inspection_error': 'Windows x64 required'}
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    handle = kernel.OpenProcess(0x410, False, pid)
    if not handle:
        return result | {'inspection_error': f'OpenProcess: {ctypes.get_last_error()}'}
    try:
        size = wintypes.DWORD(2048)
        name = ctypes.create_unicode_buffer(size.value)
        kernel.GetPackageFullName.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR]
        code = kernel.GetPackageFullName(handle, ctypes.byref(size), name)
        result['package_identity'] = name.value if code == 0 else ('UNPACKAGED' if code == 15700 else f'UNKNOWN:{code}')
        def read(address, length):
            buf = ctypes.create_string_buffer(length)
            count = ctypes.c_size_t()
            ok = kernel.ReadProcessMemory(handle, address, buf, length, ctypes.byref(count))
            if not ok and count.value == 0:
                raise OSError(ctypes.get_last_error(), 'ReadProcessMemory')
            return buf.raw[:count.value]
        info = ctypes.create_string_buffer(48)
        ntdll = ctypes.WinDLL('ntdll')
        ntdll.NtQueryInformationProcess.argtypes = [wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG, ctypes.c_void_p]
        status = ntdll.NtQueryInformationProcess(handle, 0, info, 48, None)
        if status:
            raise OSError(status, 'NtQueryInformationProcess')
        peb = struct.unpack_from('<Q', info.raw, 8)[0]
        parameters = struct.unpack('<Q', read(peb + 0x20, 8))[0]
        def unicode_at(offset):
            descriptor = read(parameters + offset, 16)
            length = struct.unpack_from('<H', descriptor)[0]
            address = struct.unpack_from('<Q', descriptor, 8)[0]
            return read(address, length).decode('utf-16-le') if length else ''
        result['working_directory'] = unicode_at(0x38)
        result['image_path'] = unicode_at(0x60)
        result['command_line'] = unicode_at(0x70)
        address = struct.unpack('<Q', read(parameters + 0x80, 8))[0]
        block = read(address, 65536).decode('utf-16-le', errors='replace').split('\0\0')[0]
        allowed = {'PTTI_DB', 'PTTI_ENV', 'PTTI_VISION_HOME', 'LOCALAPPDATA'}
        result['environment'] = {key: value for entry in block.split('\0') if '=' in entry
                                 for key, value in [entry.split('=', 1)] if key in allowed}
    except Exception as exc:
        result['inspection_error'] = str(exc)
    finally:
        kernel.CloseHandle(handle)
    return result


def inspect_database(path):
    path = Path(path)
    before = path.stat()
    row = {'path': str(path.absolute()), 'size': before.st_size,
           'mtime_utc': datetime.fromtimestamp(before.st_mtime, timezone.utc).isoformat(),
           'file_id': hex(before.st_ino), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    if os.name == 'nt':
        query = subprocess.run(['fsutil', 'file', 'queryfilenamebyid', path.anchor, hex(before.st_ino)], capture_output=True, text=True)
        row['physical_path_query'] = query.stdout.strip() if query.returncode == 0 else 'UNKNOWN: ' + query.stderr.strip()
    try:
        with sqlite3.connect(path.absolute().as_uri() + '?mode=ro', uri=True) as db:
            db.execute('PRAGMA query_only=ON')
            row['integrity'] = db.execute('PRAGMA integrity_check').fetchone()[0]
            row['schema_version'] = db.execute('PRAGMA schema_version').fetchone()[0]
            row['user_version'] = db.execute('PRAGMA user_version').fetchone()[0]
            row['tables'] = [x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            if 'matches' in row['tables']:
                matches = db.execute('SELECT id,payload FROM matches').fetchall()
                row['match_count'] = len(matches)
                row['synthetic_count'] = sum(json.loads(payload).get('metadata', {}).get('synthetic') is True for _, payload in matches)
                row['records'] = [{'id': mid, 'synthetic': json.loads(payload).get('metadata', {}).get('synthetic'),
                                   'created_at': json.loads(payload).get('created_at'), 'updated_at': json.loads(payload).get('updated_at')}
                                  for mid, payload in matches]
    except Exception as exc:
        row['sqlite_error'] = str(exc)
    row['unchanged_during_read'] = path.stat().st_mtime_ns == before.st_mtime_ns and hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pid', type=int, action='append', default=[])
    parser.add_argument('--root', type=Path, action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    suffixes = ('.db', '.sqlite', '.sqlite3', '.bak', '.backup', '.old', '.copy')
    files = sorted({p for root in args.root if root.exists() for p in root.rglob('*')
                    if p.is_file() and (p.suffix.lower() in suffixes or '.forensic-backup' in p.name)})
    result = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'reader': sys.executable,
              'processes': [process_details(pid) for pid in args.pid],
              'databases': [inspect_database(p) for p in files]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'processes': result['processes'],
                      'database_count': len(files)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
