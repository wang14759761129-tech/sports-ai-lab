"""Original PTTI mark, reproducible with Python's standard library only."""
from pathlib import Path
import math,struct,zlib
ROOT=Path(__file__).resolve().parents[1]
def png(size):
    rows=[]
    for y in range(size):
        row=bytearray([0])
        for x in range(size):
            u,v=x/size,y/size
            color=(13,73,66,255)
            # Ball, trajectory and three telemetry bars. Original geometric artwork.
            if (u-.35)**2+(v-.36)**2<.13**2: color=(246,249,245,255)
            if .18<u<.68 and abs(v-(.70-.9*(u-.18)**2))<.015: color=(91,220,171,255)
            for bx,top in [(.60,.35),(.71,.26),(.82,.17)]:
                if bx<u<bx+.055 and top<v<.64: color=(91,220,171,255)
            row.extend(color)
        rows.append(bytes(row))
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',size,size,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows),9))+chunk(b'IEND',b'')
def main():
    asset=ROOT/'assets';asset.mkdir(exist_ok=True)
    images=[png(s) for s in [16,32,48,64,128,256]]
    offset=6+16*len(images);entries=[]
    for size,data in zip([16,32,48,64,128,256],images):
        entries.append(struct.pack('<BBBBHHII',size%256,size%256,0,0,1,32,len(data),offset));offset+=len(data)
    (asset/'ptti.ico').write_bytes(struct.pack('<HHH',0,1,len(images))+b''.join(entries)+b''.join(images))
    svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="20" fill="#0d4942"/><circle cx="35" cy="36" r="13" fill="#f6f9f5"/><path d="M18 70 Q42 70 68 47" fill="none" stroke="#5bdcab" stroke-width="3"/><path d="M60 64V35 M71 64V26 M82 64V17" stroke="#5bdcab" stroke-width="5.5"/></svg>'
    (asset/'ptti.svg').write_text(svg,encoding='utf-8')
    public=ROOT/'frontend/public';public.mkdir(exist_ok=True)
    (public/'ptti.svg').write_text(svg,encoding='utf-8')
if __name__=='__main__':main()
