"""Loopback-only synthetic demo API; never opens user media or production DB."""
import argparse,hashlib,json,math,os,re,sqlite3,tempfile,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
VIDEO=Path(__file__).resolve().parents[1]/'public'/'demo-synthetic.mp4'
EXPECTED='23cd872e390f0393489f6ed3322764491c8ea3f76cfc1232852ed0da08b07da3'
DB=Path(tempfile.gettempdir())/'ptti-unified-demo'/'moments.sqlite3'
PORT=5221
FRONTEND_PORT=5220

def digest():
 if not VIDEO.is_file() or VIDEO.is_symlink():raise OSError('synthetic video missing')
 sha=hashlib.sha256(VIDEO.read_bytes()).hexdigest()
 if sha!=EXPECTED:raise OSError('synthetic video identity mismatch')
 return sha

def initialize():
 DB.parent.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(DB) as db:db.execute('CREATE TABLE IF NOT EXISTS moments(id TEXT PRIMARY KEY,sha256 TEXT NOT NULL,event_id TEXT NOT NULL,seconds REAL NOT NULL,note TEXT NOT NULL)')

def event_id(value):
 if not isinstance(value,str) or not re.fullmatch(r'demo-[1-8]',value):raise ValueError('invalid event identity')
 return value

class Handler(BaseHTTPRequestHandler):
 def respond(self,status,data):
  b=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def allowed(self):return self.headers.get('Host') in {f'127.0.0.1:{PORT}',f'localhost:{PORT}'} and self.headers.get('Origin') in (None,f'http://127.0.0.1:{FRONTEND_PORT}')
 def body(self):
  length=int(self.headers.get('Content-Length','0'))
  if not 0<length<=8192:raise ValueError('invalid input')
  return json.loads(self.rfile.read(length))
 def endpoint(self):return urlsplit(self.path).path
 def do_GET(self):
  if not self.allowed():return self.respond(403,{'error':'invalid origin'})
  if self.endpoint()!='/moments':return self.respond(404,{'error':'unknown endpoint'})
  try:
   event=event_id(parse_qs(urlsplit(self.path).query).get('event',[''])[0]);sha=digest()
   with sqlite3.connect(DB) as db:rows=db.execute('SELECT id,seconds,note FROM moments WHERE sha256=? AND event_id=? ORDER BY seconds,id',(sha,event)).fetchall()
   self.respond(200,{'sha256':sha,'event_id':event,'moments':[{'id':a,'time':b,'note':c} for a,b,c in rows]})
  except ValueError as e:self.respond(400,{'error':str(e)})
  except (OSError,sqlite3.Error):self.respond(503,{'error':'synthetic video or database unavailable'})
 def write(self,method):
  if not self.allowed():return self.respond(403,{'error':'invalid origin'})
  try:
   body=self.body();sha=digest();event=event_id(body.get('event_id'))
   if body.get('sha256')!=sha:raise ValueError('video identity mismatch')
   path=self.endpoint();ident=path.removeprefix('/moments/') if path.startswith('/moments/') else ''
   with sqlite3.connect(DB) as db:
    if method=='POST' and path=='/moments':
     seconds=float(body['time']);note=body['note']
     if not math.isfinite(seconds) or not 0<=seconds<=20 or not isinstance(note,str) or len(note)>2000:raise ValueError('invalid moment')
     ident=str(uuid.uuid4());db.execute('INSERT INTO moments VALUES (?,?,?,?,?)',(ident,sha,event,seconds,note));result={'id':ident,'time':seconds,'note':note}
    elif method in ('PUT','DELETE') and ident and re.fullmatch(r'[a-f0-9-]{36}',ident):
     if method=='PUT':
      note=body['note']
      if not isinstance(note,str) or len(note)>2000:raise ValueError('invalid note')
      cur=db.execute('UPDATE moments SET note=? WHERE id=? AND sha256=? AND event_id=?',(note,ident,sha,event));result={'id':ident,'note':note}
     else:cur=db.execute('DELETE FROM moments WHERE id=? AND sha256=? AND event_id=?',(ident,sha,event));result={'deleted':True}
     if cur.rowcount!=1:return self.respond(404,{'error':'moment not found for this event'})
    else:return self.respond(404,{'error':'unknown endpoint'})
   self.respond(201 if method=='POST' else 200,result)
  except (ValueError,TypeError,KeyError,json.JSONDecodeError):self.respond(400,{'error':'invalid moment or video/event identity'})
  except (OSError,sqlite3.Error):self.respond(503,{'error':'synthetic video or database unavailable'})
 def do_POST(self):self.write('POST')
 def do_PUT(self):self.write('PUT')
 def do_DELETE(self):self.write('DELETE')

def main():
 global DB,VIDEO,PORT,FRONTEND_PORT
 parser=argparse.ArgumentParser();parser.add_argument('--test-root',type=Path);parser.add_argument('--port',type=int,default=5221);parser.add_argument('--frontend-port',type=int,default=5220);args=parser.parse_args();PORT=args.port;FRONTEND_PORT=args.frontend_port
 if not 1<=PORT<=65535 or not 1<=FRONTEND_PORT<=65535:parser.error('invalid port')
 if args.test_root:
  root=args.test_root
  if not root.is_absolute() or root.is_symlink() or not root.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):parser.error('test root must be a non-symlink absolute temp directory')
  DB=root/'moments.sqlite3';VIDEO=root/'synthetic.mp4'
 initialize();print(f'DEMO API 127.0.0.1:{PORT} isolated SQLite: {DB}',flush=True)
 ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
if __name__=='__main__':main()
