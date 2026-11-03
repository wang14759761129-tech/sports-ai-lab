import tempfile,unittest
from pathlib import Path
from apps.qa_isolation import configure,confined
class Isolation(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(prefix='PTTI-QA-');self.r=Path(self.t.name);self.e={'PTTI_QA_ROOT':str(self.r)}
  for k,v in {'PTTI_DB':'data/matches.db','PTTI_PREVIEW_QA_DB':'data/matches.db','LOCALAPPDATA':'local','WEBVIEW2_USER_DATA_FOLDER':'webview','PTTI_QA_MEDIA_ROOT':'media','PTTI_QA_LOG_ROOT':'logs','PTTI_QA_CONFIG_ROOT':'config'}.items():self.e[k]=str(self.r/v)
 def tearDown(self):self.t.cleanup()
 def test_valid(self):configure(self.e);self.assertFalse((self.r/'data/matches.db').exists())
 def test_missing(self):
  for key in self.e:
   e=dict(self.e);del e[key]
   with self.assertRaises(ValueError):configure(e)
 def test_external(self):
  for k in ['PTTI_DB','WEBVIEW2_USER_DATA_FOLDER']:
   e=dict(self.e);e[k]=str(self.r.parent/'user-data')
   with self.assertRaises(ValueError):configure(e)
 def test_vision(self):
  self.e['PTTI_VISION_HOME']='external'
  with self.assertRaises(ValueError):configure(self.e)
 def test_escape(self):
  with self.assertRaises(ValueError):confined(self.r/'..'/'escape',self.r)
if __name__=='__main__':unittest.main()
