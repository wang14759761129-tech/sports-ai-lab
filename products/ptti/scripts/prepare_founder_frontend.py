"""Prepare a verified frontend directory; no EXE packaging or program launch."""
import argparse, hashlib, json, os, subprocess, tempfile
from pathlib import Path
import psutil

BASE = '5946c0c4d0517ade316b748933151816c6c504d3'
ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / 'products' / 'ptti' / 'frontend'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    output = parser.parse_args().output.resolve()
    if output.exists():
        raise RuntimeError('Output already exists; refusing to overwrite.')
    if output.is_relative_to(ROOT.resolve()):
        raise RuntimeError('Output must be outside the source worktree.')
    if psutil.virtual_memory().available < int(2.5 * 1024**3):
        raise RuntimeError('Build requires 2.5 GiB available RAM.')
    head = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', BASE, head], check=True)
    if subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'], text=True).strip():
        raise RuntimeError('Source worktree is not clean.')
    if not (FRONTEND / 'node_modules' / '.bin' / 'vite.cmd').exists():
        raise RuntimeError('Locked frontend dependencies are missing.')
    with tempfile.TemporaryDirectory(prefix='ptti-founder-build-') as tmp:
        build = Path(tmp) / 'dist'
        env = os.environ.copy()
        env['VITE_UNIFIED_MODE'] = '1'
        subprocess.run(['npm.cmd', 'run', 'build', '--', '--mode', 'demo', '--outDir', str(build)], cwd=FRONTEND, env=env, check=True)
        files = {p.relative_to(build).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(build.rglob('*')) if p.is_file()}
        if 'index.html' not in files or 'demo-synthetic.mp4' not in files:
            raise RuntimeError('Required frontend assets are missing.')
        import shutil
        output.mkdir(parents=True)
        shutil.copytree(build, output / 'dist')
        (output / 'founder-build.json').write_text(json.dumps({'schema':'ptti.founder.dist/1','source_commit':BASE,'host_commit':head,'unified_mode':True,'files':files}, indent=2) + '\n', encoding='utf-8')
        print('Prepared frontend only:', output)
if __name__ == '__main__':
    main()
