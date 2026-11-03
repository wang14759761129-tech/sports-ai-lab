"""Build a separate Founder Preview package from a prepared frontend; never launch it."""
import argparse, hashlib, importlib.util, json, os, subprocess, sys, tempfile
from pathlib import Path
import psutil

ROOT=Path(__file__).resolve().parents[3]
PTTI=ROOT/'products'/'ptti'
spec=importlib.util.spec_from_file_location('guard', PTTI/'apps'/'founder_preview_guard.py')
guard=importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--prepared',required=True,type=Path); ap.add_argument('--output',required=True,type=Path); args=ap.parse_args()
    prepared=args.prepared.resolve(strict=True); output=args.output.resolve()
    if output.exists() or output.is_relative_to(ROOT.resolve()):raise RuntimeError('Output must be new and outside the source worktree.')
    if psutil.virtual_memory().available < int(2.5*1024**3):raise RuntimeError('Build requires 2.5 GiB available RAM.')
    if subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain'],text=True).strip():raise RuntimeError('Source worktree must be clean.')
    guard.verify_dist(prepared/'dist',prepared/'founder-build.json')
    head=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    env=os.environ.copy(); env['PTTI_FOUNDER_PREPARED']=str(prepared)
    with tempfile.TemporaryDirectory(prefix='ptti-founder-pyinstaller-') as tmp:
        tmp=Path(tmp)
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--distpath',str(tmp/'dist'),'--workpath',str(tmp/'work'),str(PTTI/'scripts'/'founder_preview.spec')],cwd=ROOT,env=env,check=True)
        package=tmp/'dist'/'PTTI-Founder-Preview'
        if not (package/'PTTI-Founder-Preview.exe').is_file():raise RuntimeError('EXE missing from build output.')
        import shutil
        output.mkdir(parents=True); shutil.copytree(package, output/'PTTI-Founder-Preview')
        files={p.relative_to(output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*')) if p.is_file()}
        (output/'package-manifest.json').write_text(json.dumps({'source_commit':guard.COMMIT,'host_commit':head,'unsigned':True,'files':files},indent=2)+'\n',encoding='utf-8')
        print('Unsigned package prepared without runtime validation:',output)
if __name__=='__main__':main()
