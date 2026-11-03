import importlib.util,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
path=Path(__file__).resolve().parents[1]/'apps'/'prolab_save_bridge.py'
spec=importlib.util.spec_from_file_location('bridge',path);bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
class Window:
 def __init__(self,url='http://127.0.0.1:12345/?ptti_native=1'):self.url=url
 def get_current_url(self):return self.url
class SaveTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'review.json';self.window=Window()
  self.doc={'schema':'ptti.manual-review/2','media':{'identity':{'kind':'SESSION','value':'a'*32},'duration_seconds':20},'origin':'MANUAL_USER_RECORDED','verification':'NOT_INDEPENDENTLY_VERIFIED','association':'NO_MATCH_ASSOCIATION','persistence':'SESSION_ONLY','marks':[{'id':'a','seconds':1.5,'tag':'serve','note':'test'}],'local_content_fingerprint':{'algorithm':'ptti-local-video-chunks-sha256-v1','digest':'b'*64}}
  self.text=json.dumps(self.doc,ensure_ascii=False);self.api=bridge.ProLabSaveBridge(12345,lambda _:str(self.path));self.api._bind_window(self.window)
 def tearDown(self):self.tmp.cleanup()
 def test_save_and_cancel(self):
  self.assertEqual(self.api.save_prolab_json(self.text),{'status':'saved'});self.assertEqual(json.loads(self.path.read_text(encoding='utf8')),self.doc)
  self.api._dialog=lambda _:None;self.assertEqual(self.api.save_prolab_json(self.text),{'status':'cancelled'});self.assertEqual(json.loads(self.path.read_text(encoding='utf8')),self.doc)
 def test_invalid_and_untrusted(self):
  for url in ['https://example.com/','http://127.0.0.1:12345/','http://127.0.0.1:12345/?ptti_native=1#x','http://localhost:12345/?ptti_native=1']:
   self.window.url=url;self.assertEqual(self.api.save_prolab_json(self.text)['status'],'error')
  self.window.url='http://127.0.0.1:12345/?ptti_native=1'
  for invalid in ['{}','{"a":1,"a":2}',self.text+'x','x'*(bridge.MAX_BYTES+1)]:self.assertEqual(self.api.save_prolab_json(invalid)['status'],'error')
  self.assertFalse(self.path.exists())
 def test_failed_replace_preserves_existing(self):
  self.path.write_text('old',encoding='utf8')
  with patch.object(bridge.os,'replace',side_effect=PermissionError):self.assertEqual(self.api.save_prolab_json(self.text)['status'],'error')
  self.assertEqual(self.path.read_text(encoding='utf8'),'old');self.assertEqual(list(Path(self.tmp.name).iterdir()),[self.path])
 def test_navigation_change_and_single_flight(self):
  def dialog(_):self.window.url='https://example.com/';return str(self.path)
  self.api._dialog=dialog;self.assertEqual(self.api.save_prolab_json(self.text)['status'],'error');self.assertFalse(self.path.exists())
  self.api._lock.acquire()
  try:self.assertEqual(self.api.save_prolab_json(self.text)['status'],'error')
  finally:self.api._lock.release()
if __name__=='__main__':unittest.main()
