import hashlib,importlib.util,tempfile,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'scripts'/'prepare_founder_prebuilt.py'
s=importlib.util.spec_from_file_location('prebuilt',p); m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class HandoffTest(unittest.TestCase):
 def test_exact_set_and_fail_closed(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);files={'index.html':b'html','demo-synthetic.mp4':b'synthetic',**{f'a/{i}.js':str(i).encode() for i in range(8)}}
   lines=[]
   for name,data in files.items():
    dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);lines.append(hashlib.sha256(data).hexdigest()+' '+name)
   manifest=('\n'.join(lines)+'\n').encode();pin=hashlib.sha256(manifest).hexdigest()
   self.assertEqual(len(m.verify_manifest(manifest,root,pin)),10)
   (root/'extra').write_text('x')
   with self.assertRaises(ValueError):m.verify_manifest(manifest,root,pin)
   (root/'extra').unlink();(root/'index.html').write_text('tampered')
   with self.assertRaises(ValueError):m.verify_manifest(manifest,root,pin)
   with self.assertRaises(ValueError):m.verify_manifest(manifest,root,'0'*64)
if __name__=='__main__':unittest.main()
