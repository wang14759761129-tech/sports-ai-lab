import unittest
from unittest.mock import patch
from pathlib import Path
from test_qa_isolation import Isolation as Base
from apps.qa_isolation import configure,webview_options
class Configuration(Base):
 def test_storage_mapping(self):
  configure(self.e);self.assertEqual(webview_options(self.r),{'gui':'edgechromium','private_mode':False,'storage_path':str(self.r/'webview')})
 def test_cache_config_log_external(self):
  for name in ['cache','config','logs']:
   if (self.r/name).is_dir():(self.r/name).rmdir()
   (self.r/name).write_bytes(b'not-a-directory')
   with self.assertRaises(OSError):configure(dict(self.e))
   (self.r/name).unlink()
 def test_disabled_vision_and_updates(self):
  self.e['PTTI_DESKTOP_DEPLOY_ROOT']='external';self.e['PTTI_VISION_LAB_DEV_ONLY']='1'
  configure(self.e)
  self.assertNotIn('PTTI_DESKTOP_DEPLOY_ROOT',self.e)
  self.assertNotIn('PTTI_VISION_LAB_DEV_ONLY',self.e)
  self.assertEqual(self.e['PTTI_VISION_HOME'],str(self.r/'vision-disabled'))
if __name__=='__main__':unittest.main()
