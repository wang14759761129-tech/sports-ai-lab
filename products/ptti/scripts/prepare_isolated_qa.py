"""Offline configuration/manifest preparation; never starts or packages an app."""
import argparse,hashlib,json,subprocess
from pathlib import Path
LAYOUT={'PTTI_DB':'data/matches.db','PTTI_PREVIEW_QA_DB':'data/matches.db','LOCALAPPDATA':'local','WEBVIEW2_USER_DATA_FOLDER':'webview','PTTI_QA_MEDIA_ROOT':'media','PTTI_QA_LOG_ROOT':'logs','PTTI_QA_CONFIG_ROOT':'config'}
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--qa-root',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 root=Path(args.qa_root)
 if not root.is_absolute():parser.error('QA root must be absolute')
 source=Path(__file__).resolve().parents[3]
 files=['products/ptti/apps/qa_isolation.py','products/ptti/apps/qa_desktop.py','products/ptti/apps/desktop.py','products/ptti/scripts/build_dual_source_v061_preview.py']
 result={'source_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip(),'dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=source,text=True).strip()),'template_only':True,'build_authorized':False,'native_storage':'NOT_TESTED','environment':{'PTTI_ISOLATED_QA':'1','PTTI_QA_ROOT':str(root),**{key:str(root/value) for key,value in LAYOUT.items()}},'inputs':{f:hashlib.sha256((source/f).read_bytes()).hexdigest() for f in files}}
 args.output.write_text(json.dumps(result,indent=2),encoding='utf8')
if __name__=='__main__':main()
