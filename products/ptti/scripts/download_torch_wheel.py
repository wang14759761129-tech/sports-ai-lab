"""Official CUDA wheel fallback; resumable HTTP ranges + published SHA256 verification.

Explicit setup action only. Downloads are never triggered by desktop startup.
"""
import concurrent.futures
import hashlib
import shutil
import subprocess
from pathlib import Path

URL = 'https://pytorch.s3.amazonaws.com/whl/cu128/torch-2.10.0%2Bcu128-cp312-cp312-win_amd64.whl'
SIZE = 2867409626
SHA = 'fbde8f6a9ec8c76979a0d14df21c10b9e5cab6f0d106a73ca73e2179bc597cae'
ROOT = Path(__file__).resolve().parents[1] / 'downloads'
WHEEL = ROOT / 'torch-2.10.0+cu128-cp312-cp312-win_amd64.whl'

def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as f:
        while chunk := f.read(1024 * 1024): sha.update(chunk)
    return sha.hexdigest()

def main():
    ROOT.mkdir(exist_ok=True)
    if WHEEL.exists() and WHEEL.stat().st_size == SIZE:
        if digest(WHEEL) != SHA: raise RuntimeError('Existing wheel SHA256 mismatch')
        print('Verified official wheel already exists'); return
    prefix = ROOT / 'torch-download-prefix.partial'
    if WHEEL.exists():
        if prefix.exists(): raise RuntimeError('Two partial downloads exist; preserve and inspect before resuming')
        WHEEL.rename(prefix)
    offset = prefix.stat().st_size if prefix.exists() else 0
    parts = ROOT / 'torch-parts'; parts.mkdir(exist_ok=True)
    segment = 64 * 1024 * 1024
    ranges = [(start, min(SIZE - 1, start + segment - 1)) for start in range(offset, SIZE, segment)]
    def fetch(pair):
        start, end = pair
        part = parts / f'{start}-{end}.part'
        if part.exists() and part.stat().st_size == end - start + 1: return part
        # Keep validated prefix bytes within each range across timeout/restart.
        existing = part.stat().st_size if part.exists() else 0
        if existing > end - start + 1: raise RuntimeError('Oversized partial range')
        fragment = parts / f'{start}-{end}.fragment'
        if fragment.exists() and fragment.stat().st_size:
            if fragment.stat().st_size > end - start + 1 - existing:
                raise RuntimeError('Oversized retained fragment')
            with part.open('ab') as output, fragment.open('rb') as incoming:
                shutil.copyfileobj(incoming, output)
            fragment.rename(parts / f'{start}-{end}.{existing}.retained')
            existing = part.stat().st_size
            if existing == end - start + 1: return part
        process = subprocess.run(['curl.exe', '--fail', '--silent', '--show-error',
                        '--connect-timeout', '20', '--max-time', '1200', '--range', f'{start + existing}-{end}',
                        '-o', str(fragment), URL])
        if fragment.stat().st_size != end - start + 1 - existing:
            raise RuntimeError('Server fragment range mismatch; original part retained')
        # Windows Schannel can report missing TLS close_notify after all bytes
        # arrived. Exact sizes + the published full-file SHA remain mandatory.
        if process.returncode not in (0, 56): raise RuntimeError('Official range transfer failed')
        with part.open('ab') as output, fragment.open('rb') as incoming:
            shutil.copyfileobj(incoming, output)
        if part.stat().st_size != end - start + 1: raise RuntimeError('Server range mismatch')
        print(f'Completed official range {start}-{end}', flush=True)
        return part
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        downloaded = list(executor.map(fetch, ranges))
    temporary = ROOT / 'torch-combined.partial'
    with temporary.open('wb') as output:
        for part in ([prefix] if prefix.exists() else []) + downloaded:
            with part.open('rb') as f: shutil.copyfileobj(f, output, length=1024 * 1024)
    if temporary.stat().st_size != SIZE or digest(temporary) != SHA:
        raise RuntimeError('Official wheel size / SHA256 mismatch. Parts retained.')
    temporary.rename(WHEEL)
    print('Official PyTorch CUDA wheel SHA256 verified:', SHA, flush=True)

if __name__ == '__main__': main()
