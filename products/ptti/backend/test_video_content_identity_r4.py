import hashlib, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from video_content_identity import verify_registered_content
class ContentIdentity(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'test.mp4'; self.path.write_bytes(b'A'*2000000); stat=self.path.stat(); self.row={'original_path':str(self.path),'source_sha256':hashlib.sha256(b'A'*2000000).hexdigest(),'hash_status':'VERIFIED','file_size':stat.st_size,'mtime_ns':stat.st_mtime_ns,'file_id':stat.st_ino}
 def tearDown(self): self.tmp.cleanup()
 def test_exact_file(self): self.assertEqual(verify_registered_content(self.row),self.row['source_sha256'])
 def test_same_name_size_timestamp_content_changed(self):
  m=self.path.stat().st_mtime_ns; self.path.write_bytes(b'B'*2000000);os.utime(self.path,ns=(m,m))
  with self.assertRaises(ValueError):verify_registered_content(self.row)
 def test_replace_after_registration(self):
  p=self.path.with_name('replacement');p.write_bytes(b'A'*2000000);os.replace(p,self.path)
  with self.assertRaises(ValueError):verify_registered_content(self.row)
 def test_missing(self):
  self.path.unlink()
  with self.assertRaises(ValueError):verify_registered_content(self.row)
 def test_read_error(self):
  with patch.object(Path,'open',side_effect=PermissionError('denied')):
   with self.assertRaises(ValueError):verify_registered_content(self.row)
 def test_changes_while_checking(self):
  done=[]
  def mutate():
   if not done:
    done.append(True)
    with self.path.open('r+b') as stream:stream.seek(0);stream.write(b'Z')
  with self.assertRaises(ValueError):verify_registered_content(self.row,on_block=mutate)
if __name__=='__main__': unittest.main()
