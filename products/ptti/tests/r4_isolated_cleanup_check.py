import os, sys, tempfile
from pathlib import Path

def main():
 with tempfile.TemporaryDirectory(prefix='ptti-r4-qa-cleanup-') as tmp:
  db=(Path(tmp)/'qa.db').resolve(); os.environ['PTTI_ENV']='test'; os.environ['PTTI_DB']=str(db); print('isolated database:',db)
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
  from backend.repository import Repository
  from backend.video_evidence import EvidenceStore
  repo=Repository(db); store=EvidenceStore(repo)
  try:
   future=store.hasher.submit(lambda: store.list('evidence_videos')); assert future.result(timeout=10)==[]
  finally:
   store.close(wait=True)
  db.unlink(); assert not db.exists()
 print('Windows isolated SQLite worker completion and deletion PASS')
if __name__=='__main__':main()
