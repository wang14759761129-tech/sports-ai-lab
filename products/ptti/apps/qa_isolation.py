"""Fail-closed local QA policy; no database is opened by validation."""
import hashlib,json,os,stat,tempfile
from pathlib import Path

def confined(path,root):
 p=Path(path)
 if str(p).startswith(('\\\\', '//')):raise ValueError('UNC/device paths forbidden')
 if not p.is_absolute():raise ValueError('QA paths must be absolute')
 for part in (p,*p.parents):
  try:
   info=part.lstat()
  except FileNotFoundError:
   continue
  if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
   raise ValueError('QA reparse/junction path rejected')
 if p.exists() and p.is_file() and p.stat().st_nlink != 1:raise ValueError('Hard-linked QA file rejected')
 p=p.resolve();r=Path(root).resolve()
 if not p.is_relative_to(r):raise ValueError('QA path escapes root')
 return p

def configure(env):
 raw=env.get('PTTI_QA_ROOT')
 if not raw:raise ValueError('Explicit QA root required')
 root=confined(raw,Path(tempfile.gettempdir()).resolve())
 if root.name[:8]!='PTTI-QA-' or not root.is_dir():raise ValueError('Dedicated existing QA temp root required')
 if env.get('PTTI_VISION_HOME'):raise ValueError('External Vision disabled in QA')
 layout={'PTTI_DB':'data/matches.db','PTTI_PREVIEW_QA_DB':'data/matches.db','LOCALAPPDATA':'local','WEBVIEW2_USER_DATA_FOLDER':'webview','PTTI_QA_MEDIA_ROOT':'media','PTTI_QA_LOG_ROOT':'logs','PTTI_QA_CONFIG_ROOT':'config'}
 for key,relative in layout.items():
  expected=root/relative
  if key not in env or confined(env[key],root)!=expected:raise ValueError('Missing or incorrect QA path: '+key)
 for relative in ['data','local','webview','media','logs','config','cache','vision-disabled']:confined(root/relative,root).mkdir(exist_ok=True)
 env.update(PTTI_ENV='test',PTTI_RESEARCH_DATA_ROOT=str(root/'vision-disabled'),PTTI_VISION_HOME=str(root/'vision-disabled'),TEMP=str(root/'cache'),TMP=str(root/'cache'))
 env['APPDATA']=str(root/'config')
 env['XDG_CACHE_HOME']=str(root/'cache')
 env.pop('PTTI_DESKTOP_DEPLOY_ROOT',None)
 env.pop('PTTI_VISION_LAB_DEV_ONLY',None)
 return root

def check_media(path):
 if os.environ.get('PTTI_ISOLATED_QA')!='1':return Path(path)
 root=Path(os.environ['PTTI_QA_ROOT']);p=confined(path,root/'media')
 manifest_path=confined(root/'config/media.json',root)
 manifest=json.loads(manifest_path.read_text(encoding='utf8'))
 expected=manifest.get(p.name)
 if not expected:raise ValueError("Media absent from synthetic manifest")
 digest=hashlib.sha256()
 with p.open('rb') as source:
  for block in iter(lambda:source.read(1024*1024),b''):digest.update(block)
 if not expected or digest.hexdigest()!=expected:raise ValueError('Only manifest-approved synthetic QA media is allowed')
 return p


def check_database(path, env=None):
 env=os.environ if env is None else env
 if env.get('PTTI_ISOLATED_QA')!='1':return Path(path)
 root=Path(env['PTTI_QA_ROOT'])
 expected=confined(root/'data/matches.db',root)
 for value in (path,env.get('PTTI_DB',''),env.get('PTTI_PREVIEW_QA_DB','')):
  if confined(value,root)!=expected:raise ValueError('QA database identity mismatch')
 return expected

# Only reviewed local-library operations are available in the isolated QA profile.
# New routes are denied by default, rather than inheriting broad research access.
def api_allowed(method, path):
 import re
 rules={
  'GET':[r'/api/(health|settings|diagnostics/database)',r'/api/video-evidence/(videos|evidence|points|collections)',r'/api/video-evidence/videos/[^/]+/media',r'/api/video-evidence/library',r'/api/video-evidence/library/videos/[^/]+/thumbnail'],
  'HEAD':[r'/api/video-evidence/videos/[^/]+/media'],
  'POST':[r'/api/video-evidence/(videos|evidence|points|collections)',r'/api/video-evidence/videos/[^/]+/relink',r'/api/video-evidence/library/videos/[^/]+/opened'],
  'PUT':[r'/api/video-evidence/(evidence|points|collections)/[^/]+',r'/api/video-evidence/library/feed/favorite'],
  'DELETE':[r'/api/video-evidence/evidence/[^/]+'],
 }
 return any(re.fullmatch(pattern,path) for pattern in rules.get(method,[]))

def install_api_guard(app):
 from starlette.responses import JSONResponse
 @app.middleware('http')
 async def qa_boundary(request,call_next):
  try:
   root=Path(os.environ['PTTI_QA_ROOT'])
   check_database(os.environ['PTTI_DB'])
   for item in ['data','local','webview','cache','logs','config','media','vision-disabled']:
    confined(root/item,root)
   if request.url.path.startswith('/api/') and not api_allowed(request.method,request.url.path):
    return JSONResponse({'detail':'QA_ROUTE_DISABLED: not approved for isolated synthetic-media QA'},status_code=403)
  except (KeyError,ValueError,OSError):
   return JSONResponse({'detail':'QA_ISOLATION_INVALID: request refused'},status_code=503)
  response=await call_next(request)
  # Isolated QA never fetches third-party pictures, embeds, or network media.
  response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-src 'none'; object-src 'none'"
  return response


def webview_options(root):
 root=Path(root)
 storage=confined(root/'webview',root)
 return {'gui':'edgechromium','private_mode':False,'storage_path':str(storage)}
