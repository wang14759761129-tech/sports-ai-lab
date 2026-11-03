"""Embed exact source provenance in local developer packages."""
import json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def git(*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
path=root/'build'/'build-info.json';path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps({'version':'0.2.0-dev','commit':git('rev-parse','HEAD'),'source_tree_dirty':bool(git('status','--porcelain'))},indent=2),encoding='utf-8')
