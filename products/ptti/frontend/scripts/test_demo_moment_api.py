import hashlib,http.client,json,shutil,socket,subprocess,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class RestartTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='ptti-sprint04-test-');self.root=Path(self.tmp.name);self.video=self.root/'synthetic.mp4';shutil.copyfile(ROOT/'public/demo-synthetic.mp4',self.video);self.sha=hashlib.sha256(self.video.read_bytes()).hexdigest();self.proc=None
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));self.port=sock.getsockname()[1]
  self.start()
 def start(self):
  self.proc=subprocess.Popen([sys.executable,str(ROOT/'scripts/demo_moment_api.py'),'--test-root',str(self.root),'--port',str(self.port),'--frontend-port','5230'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  deadline=time.monotonic()+10
  while time.monotonic()<deadline:
   if self.proc.poll() is not None:raise RuntimeError(self.proc.stderr.read().decode())
   try:
    with socket.create_connection(('127.0.0.1',self.port),timeout=.2):return
   except OSError:time.sleep(.05)
  raise RuntimeError('test API did not start')
 def stop(self):
  if self.proc and self.proc.poll() is None:self.proc.terminate();self.proc.wait(timeout=5)
  if self.proc:
   if self.proc.stdout:self.proc.stdout.close()
   if self.proc.stderr:self.proc.stderr.close()
  self.proc=None
 def tearDown(self):self.stop();self.tmp.cleanup()
 def request(self,method,path,data=None):
  conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=4)
  try:
   body=json.dumps(data).encode() if data is not None else None
   conn.request(method,path,body,{'Content-Type':'application/json'});response=conn.getresponse();return response.status,json.loads(response.read())
  finally:conn.close()
 def test_origin_is_explicit_and_fail_closed(self):
  for origin,expected in [('http://127.0.0.1:5230',200),('http://127.0.0.1:5220',403),('http://evil.example',403)]:
   conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=4)
   try:
    conn.request('GET','/moments?event=demo-1',headers={'Origin':origin});response=conn.getresponse();self.assertEqual(response.status,expected);response.read()
   finally:conn.close()
 def test_restart_and_event_isolation(self):
  body={'sha256':self.sha,'event_id':'demo-1','time':12.34,'note':'accurate note'}
  status,item=self.request('POST','/moments',body);self.assertEqual(status,201);self.stop();self.start()
  status,data=self.request('GET','/moments?event=demo-1');self.assertEqual(status,200);self.assertEqual(data['sha256'],self.sha);self.assertEqual(data['moments'],[{'id':item['id'],'time':12.34,'note':'accurate note'}])
  self.assertEqual(self.request('GET','/moments?event=demo-2')[1]['moments'],[])
  status,other=self.request('POST','/moments',{**body,'event_id':'demo-2','note':'second event'});self.assertEqual(status,201)
  self.assertEqual([m['id'] for m in self.request('GET','/moments?event=demo-1')[1]['moments']],[item['id']])
  self.assertEqual([m['id'] for m in self.request('GET','/moments?event=demo-2')[1]['moments']],[other['id']])
  status,earlier=self.request('POST','/moments',{**body,'time':1.0,'note':'earlier'});self.assertEqual(status,201)
  self.assertEqual([m['time'] for m in self.request('GET','/moments?event=demo-1')[1]['moments']],[1.0,12.34])
  self.assertEqual(self.request('PUT','/moments/'+item['id'],{**body,'event_id':'demo-2'})[0],404)
  self.assertEqual(self.request('POST','/moments',{**body,'sha256':'bad'})[0],400)
  for value in [-1,21,float('nan')]:self.assertEqual(self.request('POST','/moments',{**body,'time':value})[0],400)
  self.assertEqual(self.request('PUT','/moments/'+item['id'],{**body,'note':'edited'})[0],200)
  self.assertEqual(next(m for m in self.request('GET','/moments?event=demo-1')[1]['moments'] if m['id']==item['id'])['note'],'edited')
  self.assertEqual(self.request('DELETE','/moments/'+item['id'],body)[0],200);self.assertEqual([m['id'] for m in self.request('GET','/moments?event=demo-1')[1]['moments']],[earlier['id']])
  original=self.video.read_bytes();self.video.unlink();self.assertEqual(self.request('GET','/moments?event=demo-1')[0],503)
  self.video.write_bytes(original);self.assertEqual([m['id'] for m in self.request('GET','/moments?event=demo-1')[1]['moments']],[earlier['id']])
if __name__=='__main__':unittest.main()
