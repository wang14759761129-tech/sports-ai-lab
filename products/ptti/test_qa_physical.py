import os, sqlite3, subprocess, unittest
from pathlib import Path
import test_qa_isolation
from apps.qa_isolation import confined, check_database
from backend.database import ProductionDatabaseGuard

class Physical(test_qa_isolation.Isolation):
 def test_unc_relative_drive(self):
  for path in ['relative', '//server/share/test', 'Z:/outside']:
   with self.assertRaises(ValueError): confined(path,self.r)
 def test_junction(self):
  import tempfile
  with tempfile.TemporaryDirectory(prefix='PTTI-canary-') as outside:
   canary=Path(outside)/'canary';canary.write_bytes(b'unchanged')
   link=self.r/'link'
   subprocess.run(['powershell.exe','-NoProfile','-Command',f"New-Item -ItemType Junction -Path '{link}' -Target '{outside}' | Out-Null"],check=True,capture_output=True)
   try:
    with self.assertRaises(ValueError):confined(link/'canary',self.r)
    self.assertEqual(canary.read_bytes(),b'unchanged')
   finally:os.rmdir(link)
 def _make_symlink(self,link,target,directory=False):
  if os.environ.get("PTTI_AUTHORIZED_SYMLINK_TEST") != "1":
   self.skipTest("SKIP_ENVIRONMENT: physical symlink tests require an authorized disposable Windows environment")
  try:link.symlink_to(target,target_is_directory=directory)
  except OSError as exc:
   if getattr(exc,'winerror',None)==1314:self.skipTest('SKIP_PRIVILEGE: Windows symlink creation denied (1314)')
   raise
  self.assertTrue(link.is_symlink(),"fixture creation must succeed")
  print("SYMLINK_CREATED:",link,"->",os.readlink(link),flush=True)
 def test_symlink_outside(self):
  import tempfile
  with tempfile.TemporaryDirectory(prefix='PTTI-canary-') as outside:
   target=Path(outside)/'canary';target.write_bytes(b'unchanged')
   link=self.r/'symbolic';self._make_symlink(link,target)
   with self.assertRaises(ValueError):confined(link,self.r)
   self.assertEqual(target.read_bytes(),b'unchanged')
 def test_symlink_dangling(self):
  link=self.r/'dangling';self._make_symlink(link,self.r.parent/'PTTI-nonexistent-symlink-target')
  with self.assertRaises(ValueError):confined(link,self.r)
 def test_symlink_parent(self):
  target=self.r/'real';target.mkdir();(target/'canary').write_bytes(b'unchanged')
  link=self.r/'parent-link';self._make_symlink(link,target,True)
  with self.assertRaises(ValueError):confined(link/'canary',self.r)
 def test_reparse_metadata(self):
  from unittest.mock import patch
  from types import SimpleNamespace
  original=Path.lstat
  target=self.r/"unresolved-reparse"
  def attributes(path,*args,**kwargs):
   if path==target:return SimpleNamespace(st_mode=0,st_file_attributes=0x400)
   return original(path,*args,**kwargs)
  with patch.object(Path,"lstat",attributes):
   with self.assertRaises(ValueError):confined(target,self.r)
 def test_layout(self):
  from apps.qa_isolation import configure
  configure(self.e)
  for key in ["TEMP","TMP","APPDATA","LOCALAPPDATA","WEBVIEW2_USER_DATA_FOLDER","PTTI_QA_LOG_ROOT","PTTI_QA_CONFIG_ROOT"]:
   self.assertTrue(Path(self.e[key]).is_relative_to(self.r))
 def test_hardlink(self):
  original=self.r/'original';original.write_bytes(b'canary');link=self.r/'alias';os.link(original,link)
  with self.assertRaises(ValueError):confined(link,self.r)
  self.assertEqual(original.read_bytes(),b'canary')
 def test_sqlite(self):
  from apps.qa_isolation import configure
  configure(self.e);self.e['PTTI_ISOLATED_QA']='1'
  path=ProductionDatabaseGuard('test',self.e).validate(self.e['PTTI_DB'])
  db=sqlite3.connect(path)
  try:
   db.execute('create table qa(value text)');db.execute("insert into qa values('test-only')");db.commit()
   self.assertEqual(db.execute('select value from qa').fetchone()[0],'test-only')
   self.assertEqual(Path(db.execute('pragma database_list').fetchone()[2]).resolve(),self.r/'data/matches.db')
  finally:db.close()
 def test_mismatch(self):
  self.e['PTTI_ISOLATED_QA']='1';self.e['PTTI_PREVIEW_QA_DB']=str(self.r/'wrong.db')
  with self.assertRaises(ValueError):check_database(self.e['PTTI_DB'],self.e)
 def test_media(self):
  import json,hashlib
  from unittest.mock import patch
  from apps.qa_isolation import configure,check_media
  configure(self.e);self.e['PTTI_ISOLATED_QA']='1'
  media=self.r/'media/test.mp4';media.write_bytes(b'synthetic-fixture-not-decoded-video')
  (self.r/'config/media.json').write_text(json.dumps({media.name:hashlib.sha256(media.read_bytes()).hexdigest()}))
  with patch.dict(os.environ,self.e):
   self.assertEqual(check_media(media),media)
   media.write_bytes(b'replaced')
   with self.assertRaises(ValueError):check_media(media)
   with self.assertRaises(ValueError):check_media(self.r.parent/'private.mp4')
if __name__=='__main__':unittest.main()
