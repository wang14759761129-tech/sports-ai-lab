import hashlib, importlib.util, json, tempfile, unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'apps'/'founder_preview_guard.py'
spec=importlib.util.spec_from_file_location('guard',p); guard=importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
class Identity(unittest.TestCase):
 def test_manifest_checks_every_file_and_unified_mode(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t); dist=root/'dist'; dist.mkdir()
   for name in ('index.html','demo-synthetic.mp4'): (dist/name).write_bytes(name.encode())
   files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dist.iterdir()}
   manifest=root/'manifest.json'; info={'schema':'ptti.founder.dist/1','source_commit':guard.COMMIT,'unified_mode':True,'files':files}; manifest.write_text(json.dumps(info))
   guard.verify_dist(dist,manifest)
   (dist/'index.html').write_text('tampered')
   with self.assertRaises(RuntimeError):guard.verify_dist(dist,manifest)
   (dist/'index.html').write_bytes(b'index.html'); info['unified_mode']=False; manifest.write_text(json.dumps(info))
   with self.assertRaises(RuntimeError):guard.verify_dist(dist,manifest)
if __name__=='__main__':unittest.main()
