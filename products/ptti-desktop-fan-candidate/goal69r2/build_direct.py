"""One bounded isolated rebuild of Host only; reuse verified frozen Web payload."""
import ast
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path
HERE=Path(__file__).resolve().parent
OLD=Path(r"<LOCAL_USER_ROOT>\PTTI\Candidates\GOAL65\0.1.11-grand-ab484d6")
OUT=Path(r"<LOCAL_USER_ROOT>\PTTI\Candidates\GOAL69R2")
VERSION='0.1.12-direct-ab484d6'
EXPECTED_RELEASE='94b1b04159fd1688f286b0d5e03751d790bfcf6b084b3158e99e3aa8a224e224'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if sha(OLD/'release.json')!=EXPECTED_RELEASE:raise RuntimeError('Original release identity changed')
    release=json.loads((OLD/'release.json').read_text(encoding='utf-8'))
    pins=ast.literal_eval((OLD/'source/goal23_identity.py').read_text(encoding='utf-8').split('=',1)[1])
    sys.modules['goal23_identity']=types.SimpleNamespace(PINS=pins)
    spec=importlib.util.spec_from_file_location('host',HERE/'desktop_host.py')
    host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
    host.verify_package(OLD)
    # Build/automation policy is unchanged. Never prompt to bypass it.
    host.check_start_policy(True)
    host.PINS['qa_port']=4213
    host.ensure_port_free(4213)
    if (OUT/VERSION).exists() or (OUT/'.build-direct').exists():raise RuntimeError('Output exists; no overwrite/retry')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE,text=True).strip()
    if subprocess.check_output(['git','status','--porcelain'],cwd=HERE,text=True).strip():raise RuntimeError('Commit source first')
    OUT.mkdir(parents=True,exist_ok=True)
    stage=OUT/'.build-direct';stage.mkdir()
    package=stage/'package';package.mkdir()
    shutil.copytree(OLD/'fan-universe',package/'fan-universe')
    shutil.copytree(OLD/'source',package/'source')
    shutil.copy2(HERE/'desktop_host.py',package/'source/desktop_host.py')
    pins.update(version=VERSION,host_version='0.1.12-goal69r2',qa_port=4213,host_commit=commit,
                candidate_title='PTTI CINEMA 3.1 · DIRECT START ALPHA',manual_start_policy='DIRECT_WITH_MEMORY_ADVISORY')
    (package/'source/goal23_identity.py').write_text('PINS = '+repr(pins)+'\n',encoding='utf-8')
    config=json.loads((package/'source/goal23-build.json').read_text(encoding='utf-8'))
    config.update({k:pins[k] for k in ('version','host_version','qa_port','candidate_title','manual_start_policy')})
    (package/'source/goal23-build.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed',
       '--name','PTTI-Desktop-Fan','--collect-all','webview','--paths',str(package/'source'),
       '--distpath',str(stage/'dist'),'--workpath',str(stage/'work'),'--specpath',str(stage),
       str(package/'source/desktop_host.py')],cwd=stage,check=True,timeout=240)
    shutil.copytree(stage/'dist/PTTI-Desktop-Fan',package/'host')
    release.update(pins)
    release.update(default_port=4213,parent_release_manifest_sha256=EXPECTED_RELEASE,
                   source_identity='verified-parent-web-payload-and-committed-direct-host',files=host.tree_manifest(package))
    (package/'release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    host.PINS=pins
    host.verify_package(package)
    subprocess.run([str(package/'host/PTTI-Desktop-Fan.exe'),'--verify-only'],check=True,timeout=40)
    final=OUT/VERSION;package.rename(final)
    receipt={'status':'BUILD_PASS','version':VERSION,'exe':str(final/'host/PTTI-Desktop-Fan.exe'),
       'exe_sha256':sha(final/'host/PTTI-Desktop-Fan.exe'),'release_sha256':sha(final/'release.json'),
       'web_sha256':host.tree_sha256(final/'fan-universe'),'host_commit':commit,'san_commit':pins['san_commit'],
       'gui':'NOT_TESTED','files':len(release['files']),'original_release_unchanged':sha(OLD/'release.json')==EXPECTED_RELEASE}
    (OUT/'direct-build-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
