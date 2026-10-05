"""Fail-closed database protection and auditable startup selection."""
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

GUARD = 'PRODUCTION_DATABASE_WRITE_GUARD'


def package_identity():
    if os.name != 'nt':
        return 'UNPACKAGED'
    size=ctypes.c_uint32(2048);name=ctypes.create_unicode_buffer(size.value)
    code=ctypes.windll.kernel32.GetCurrentPackageFullName(ctypes.byref(size),name)
    return name.value if code==0 else ('UNPACKAGED' if code==15700 else f'UNKNOWN:{code}')


class ProductionDatabaseGuard:
    def __init__(self,mode,environ=None):
        self.mode=mode.lower()
        if self.mode not in ('production','development','test'):
            raise RuntimeError(f'{GUARD}: FATAL invalid database environment')
        self.environment=dict(os.environ if environ is None else environ)
        self.local=Path(self.environment.get('LOCALAPPDATA',Path.home())).resolve(strict=False)

    def validate(self,path):
        path=Path(path).resolve(strict=False)
        production=self.local/'PTTI'/'matches.db'
        aliases=[production]
        packages=self.local/'Packages'
        if packages.exists():
            aliases.extend(packages.glob('*/LocalCache/Local/PTTI/matches.db'))
        protected=False
        for alias in aliases:
            if os.path.normcase(str(path))==os.path.normcase(str(alias.resolve(strict=False))): protected=True
            try:
                if path.exists() and alias.exists() and os.path.samefile(path,alias): protected=True
            except OSError: pass
        # Protect even a not-yet-created MSIX copy under known local data roots.
        try:
            relative=path.relative_to(self.local)
            if relative.name.casefold()=='matches.db' and relative.parent.name.casefold()=='ptti': protected=True
        except ValueError: pass
        if self.mode in ('test','development') and protected:
            raise RuntimeError(f'{GUARD}: FATAL {self.mode} cannot open a production database or MSIX alias: {path}')
        if self.mode=='test':
            try: path.relative_to(Path(tempfile.gettempdir()).resolve())
            except ValueError as exc:
                raise RuntimeError(f'{GUARD}: FATAL test database must be under OS temp') from exc
        if self.mode=='production':
            if 'pytest' in sys.modules:
                raise RuntimeError(f'{GUARD}: FATAL tests cannot enable production mode')
            if path!=production.resolve(strict=False):
                raise RuntimeError(f'{GUARD}: FATAL production requires the canonical production path')
            identity=package_identity()
            if identity!='UNPACKAGED':
                raise RuntimeError(f'{GUARD}: FATAL production launched under a packaged host ({identity}); exit and launch PTTI from Windows desktop')
        return path


def database_banner(path,mode):
    path=Path(path).resolve(strict=False)
    result={'recorded_at':datetime.now(timezone.utc).isoformat(),'pid':os.getpid(),
            'environment':mode.upper(),'database':str(path),'database_mode':'READ_WRITE',
            'python':sys.executable,'package_identity':package_identity(),
            'file_id':hex(path.stat().st_ino),'physical_path':'UNKNOWN'}
    build=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))/'build-info.json'
    if build.is_file(): result['build']=json.loads(build.read_text(encoding='utf-8'))
    else:
        query=subprocess.run(['git','-C',str(Path(__file__).resolve().parents[1]),'rev-parse','HEAD'],capture_output=True,text=True,
                             **({'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}))
        result['build']={'version':'0.2.0-dev','commit':query.stdout.strip() if query.returncode==0 else 'UNKNOWN'}
    if os.name=='nt':
        query=subprocess.run(['fsutil','file','queryfilenamebyid',path.anchor,result['file_id']],capture_output=True,text=True,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        if query.returncode==0 and '\\\\?\\' in query.stdout:
            result['physical_path']=query.stdout.split('\\\\?\\',1)[1].strip()
    else: result['physical_path']=str(path)
    print(f'PTTI Environment: {mode.upper()}\nDatabase:\n{path}\nDatabase mode:\nREAD_WRITE',flush=True)
    # Persist beside the selected isolated DB so windowed EXEs retain evidence.
    with (path.parent/'startup-database.jsonl').open('a',encoding='utf-8') as log:
        log.write(json.dumps(result,ensure_ascii=False)+'\n')
    return result
