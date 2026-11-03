"""Render worst annotated BallTrack frames inside the isolated CV runtime."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    observations=json.loads(Path(args.manifest).read_text(encoding='utf-8'))
    destination=Path(args.output);destination.mkdir(parents=True,exist_ok=False)
    review=[];thumbnails=[]
    for index,item in enumerate(observations,1):
        cap=cv2.VideoCapture(item['video'])
        cap.set(cv2.CAP_PROP_POS_FRAMES,item['frame'])
        ok,frame=cap.read();cap.release()
        if not ok:
            item['image_error']='frame decode failed';review.append(item);continue
        if item['gt']:
            cv2.drawMarker(frame,(round(item['gt'][0]),round(item['gt'][1])),(0,255,0),cv2.MARKER_CROSS,26,3)
        if item['prediction']:
            cv2.circle(frame,(round(item['prediction'][0]),round(item['prediction'][1])),13,(0,0,255),3)
        title=f"{item['clip_id']} frame {item['frame']} | {item['error_px'] if item['error_px'] is not None else item['failure']}"
        cv2.putText(frame,title,(22,38),cv2.FONT_HERSHEY_SIMPLEX,.75,(255,255,255),3,cv2.LINE_AA)
        cv2.putText(frame,title,(22,38),cv2.FONT_HERSHEY_SIMPLEX,.75,(10,10,10),1,cv2.LINE_AA)
        name=f"{index:02d}_{item['clip_id'].replace('/','_')}_f{item['frame']:06d}.png"
        ok,encoded=cv2.imencode('.png',frame)
        if not ok: raise RuntimeError(f'Could not encode worst-case image {name}')
        encoded.tofile(destination/name)
        item['image']=name
        thumb=cv2.resize(frame,(480,270))
        cv2.putText(thumb,f"{index:02d} {item['clip_id']} f{item['frame']}",(8,22),cv2.FONT_HERSHEY_SIMPLEX,.48,(255,255,255),2,cv2.LINE_AA)
        thumbnails.append(thumb);review.append(item)
    if thumbnails:
        cols=4;rows=(len(thumbnails)+cols-1)//cols
        sheet=np.zeros((rows*270,cols*480,3),dtype=np.uint8)
        for i,thumb in enumerate(thumbnails):
            y=(i//cols)*270;x=(i%cols)*480;sheet[y:y+270,x:x+480]=thumb
        ok,encoded=cv2.imencode('.jpg',sheet,[cv2.IMWRITE_JPEG_QUALITY,90])
        if not ok: raise RuntimeError('Could not encode worst-cases contact sheet')
        encoded.tofile(destination/'contact-sheet.jpg')
    (destination/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
