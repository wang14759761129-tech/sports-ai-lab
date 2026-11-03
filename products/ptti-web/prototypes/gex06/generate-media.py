"""PTTI-owned synthetic animation. No third-party footage, likeness, or match claims."""
from PIL import Image, ImageDraw
import math, subprocess, pathlib, hashlib, json
root=pathlib.Path(__file__).parent
(root/'media').mkdir(exist_ok=True)
proc=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','960x540','-r','24','-i','-','-an','-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart',str(root/'media/rally.mp4')],stdin=subprocess.PIPE)
for n in range(288):
 t=n/24; im=Image.new('RGB',(960,540),'#090d17');d=ImageDraw.Draw(im)
 for y in range(540):
  glow=max(0,1-abs(y-280)/300);d.line((0,y,960,y),fill=(int(9+glow*8),int(13+glow*12),int(23+glow*18)))
 for x in [100,300,660,860]:d.polygon([(x,0),(x-95,410),(x+95,410)],fill='#121d2a')
 d.ellipse((170,410,790,520),fill='#05080f')
 d.polygon([(310,210),(650,210),(820,430),(140,430)],fill='#133b4c',outline='#d4e4e4',width=3)
 d.line((480,210,480,430),fill='#809a9d',width=2);d.line((230,320,730,320),fill='#c9b888',width=3)
 for x in range(235,731,14):d.line((x,293,x,320),fill='#869da2')
 d.line((230,293,730,293),fill='#e6dcc5',width=2)
 for y in [455,180]:
  x=480+math.sin(t*1.7+(0 if y==455 else 2))*110
  d.ellipse((x-24,y-63,x+24,y-15),fill='#c7b8a2');d.rounded_rectangle((x-37,y-10,x+37,y+45),radius=20,fill='#ab353d' if y==455 else '#477d94')
  d.ellipse((x+42,y+5,x+72,y+43),fill='#db6b55')
 phase=(t*1.35)%2; f=phase if phase<1 else 2-phase
 bx=350+210*math.sin(t*1.2);by=225+190*f;z=math.sin(f*math.pi)*65
 d.ellipse((bx-8,by-3,bx+8,by+3),fill='#091820')
 for j in range(5):d.ellipse((bx-6-j*6,by-z-6+j*3,bx+6-j*6,by-z+6+j*3),fill=('#e8d4a4' if j==0 else '#7d8078'))
 d.text((34,24),'PTTI ORIGINAL / SYNTHETIC RALLY / NO REAL MATCH',fill='#e5d1a8')
 d.text((34,498),f'DEMONSTRATION   {t:04.1f}s   |   NOT ATHLETE FOOTAGE',fill='#b1bbc5')
 if n in [12,84,156,228]:im.save(root/f'media/frame-{n}.webp',quality=88)
 proc.stdin.write(im.tobytes())
proc.stdin.close()
if proc.wait()!=0:raise SystemExit('Media generation failed')
files={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (root/'media').iterdir()}
(root/'media-manifest.json').write_text(json.dumps({'schema':'ptti.gex06.original-media/1','rights':'PTTI_ORIGINAL_SYNTHETIC','duration_seconds':12,'fps':24,'audio':False,'public_match_id':None,'files':files},indent=2))
