import os,unittest
from unittest.mock import patch
from backend import desktop_updates
class QAUpdates(unittest.TestCase):
 def test_qa_blocks_network_even_if_cached(self):
  with patch.dict(os.environ,{'PTTI_ISOLATED_QA':'1'}),patch.object(desktop_updates,'urlopen',side_effect=AssertionError('network used')):
   self.assertEqual(desktop_updates.check_release('preview')['status'],'DISABLED_IN_ISOLATED_QA')
 def test_qa_blocks_install_before_path_access(self):
  with patch.dict(os.environ,{'PTTI_ISOLATED_QA':'1'}):
   with self.assertRaisesRegex(RuntimeError,'disabled'):desktop_updates.install('untrusted','untrusted',None)

 def test_internal_install_and_status_do_not_access_external_paths(self):
  with patch.dict(os.environ,{'PTTI_ISOLATED_QA':'1'}),patch.object(desktop_updates.Path,'resolve',side_effect=AssertionError('path accessed')):
   with self.assertRaisesRegex(RuntimeError,'disabled'):desktop_updates._install('outside','outside',None)
   self.assertEqual(desktop_updates.status('outside')['integrity'],'DISABLED_IN_ISOLATED_QA')
   with self.assertRaisesRegex(RuntimeError,'disabled'):desktop_updates.active('outside')
