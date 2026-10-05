"""Error-frame JPEGs and paginated contact sheets; isolated CV dependencies."""
import argparse,json
from pathlib import Path
import cv2
import numpy as np

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    rows=json.loads(Path(args.manifest).read_text(encoding='utf-8'));out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    thumbnails=[]
    for i,row in enumerate(rows):
        cap=cv2.VideoCapture(row['video']);cap.set(cv2.CAP_PROP_POS_FRAMES,row['frame']);ok,image=cap.read();cap.release()
        if not ok: raise RuntimeError(f'Cannot decode {row["clip_id"]}:{row["frame"]}')
        if row['gt']:cv2.drawMarker(image,tuple(round(v) for v in row['gt']),(0,255,0),cv2.MARKER_CROSS,24,3)
        if row['prediction']:cv2.circle(image,tuple(round(v) for v in row['prediction']),12,(0,0,255),3)
        text=f'{i:03d} {row["clip_id"]} f{row["frame"]} {row["failure"]}'
        cv2.putText(image,text,(15,35),cv2.FONT_HERSHEY_SIMPLEX,.75,(255,255,255),3)
        cv2.putText(image,text,(15,35),cv2.FONT_HERSHEY_SIMPLEX,.75,(0,0,0),1)
        ok,data=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,92]);data.tofile(out/f'{i:03d}.jpg')
        thumb=cv2.resize(image,(480,270));thumbnails.append(thumb)
    for page in range((len(thumbnails)+19)//20):
        group=thumbnails[page*20:(page+1)*20];sheet=np.zeros((1350,1920,3),dtype=np.uint8)
        for i,thumb in enumerate(group):y=i//4*270;x=i%4*480;sheet[y:y+270,x:x+480]=thumb
        ok,data=cv2.imencode('.jpg',sheet,[cv2.IMWRITE_JPEG_QUALITY,90]);data.tofile(out/f'contact-{page:02d}.jpg')

if __name__=='__main__':main()
