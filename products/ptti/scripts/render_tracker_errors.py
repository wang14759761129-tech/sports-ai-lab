"""Render retained official error frames; does not tune or alter evaluation files."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np

def render(report_path):
    report=json.loads(report_path.read_text(encoding='utf-8'))
    home=report_path.parent
    folder=home/'worst_cases'/report_path.stem/'images';folder.mkdir(parents=True,exist_ok=True)
    pages=[]
    for clip in report['clips']:
        _,match,rally=clip['source_id'].split('/')
        errors={e['frame']:e for e in clip['failures']}
        for frame,error in errors.items():
            path=home/'observations'/match/rally/'frames'/f'{frame:06d}.jpg'
            image=cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_COLOR)
            if image is None:raise RuntimeError(str(path))
            record=clip['evidence'][frame]
            for name,color in [('raw_prediction',(0,255,255)),('tti_prediction',(0,120,255))]:
                p=record[name]
                if p['visible']:
                    xy=(round(p['pixel_x']),round(p['pixel_y']))
                    cv2.circle(image,xy,12,color,2)
                    cv2.putText(image,'RAW' if name.startswith('raw') else 'TTI',(xy[0]+14,xy[1]),cv2.FONT_HERSHEY_SIMPLEX,.6,color,2)
            gt=error['gt']
            if gt['visible']:
                xy=(round(gt['x']),round(gt['y']));cv2.circle(image,xy,10,(0,255,0),2)
                cv2.putText(image,'GT',(xy[0]+14,xy[1]),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,0),2)
            scale=min(1,960/image.shape[1]);image=cv2.resize(image,None,fx=scale,fy=scale)
            cv2.putText(image,f'{match}/{rally} frame {frame}: {record["decision"]}',(12,25),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),2)
            target=folder/f'{match}_{rally}_{frame:06d}.jpg'
            ok,encoded=cv2.imencode('.jpg',image)
            if not ok:raise RuntimeError('Image encoding failed')
            encoded.tofile(target);pages.append(target)
    html='<!doctype html><meta charset="utf-8"><title>Tracker error evidence</title><h1>RAW / TTI / GT</h1><p>Yellow RAW; orange TTI; green visible GT. UNKNOWN taxonomy until human-reviewed. Predictions omitted when invisible.</p>'
    html+=''.join(f'<figure><img style="max-width:100%" src="images/{p.name}"><figcaption>{p.name}</figcaption></figure>' for p in pages)
    (folder.parent/'index.html').write_text(html,encoding='utf-8')
    print(f'{len(pages)} unique error-frame images rendered: {folder}')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('report',type=Path);args=p.parse_args();render(args.report)
