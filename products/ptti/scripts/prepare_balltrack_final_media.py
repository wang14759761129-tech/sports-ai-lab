"""Build sparse frames and closest reproducible, match-level median inputs."""
import csv,json,math,sys
from collections import defaultdict
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from vision.config import VisionConfig
from vision.specialist import sha256,validate_split
from vision.benchmark import read_ground_truth

def main():
    home=ROOT/'outputs/vision/balltrack_final';manifest=json.loads((home/'split.json').read_text(encoding='utf-8'));validate_split(manifest)
    source=VisionConfig.load().dataset_root;out=home/'dataset/tabletennis';videos=defaultdict(list)
    for role in ['train','dev','known_evaluation']:
        for source_id in manifest[role]:
            _,m,r=source_id.split('/');videos[m].append((r,role))
    records=[];info={}
    for role in ['train','dev','known_evaluation']:
        entries=[]
        for sid in manifest[role]:
            _,m,r=sid.split('/');entries.append([m,r])
        info[role]=entries
    for m,items in sorted(videos.items()):
        items=sorted(set(items));metadata=[];total=0
        for r,role in items:
            vp=source/f'tabletennis/videos/{m}_{r}.mp4';gp=source/f'tabletennis/all/{m}/csv/{r}_ball.csv'
            if not vp.is_file() or not gp.is_file():raise FileNotFoundError(f'Pinned video/GT missing: {m}/{r}')
            cap=cv2.VideoCapture(str(vp));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT));cap.release()
            if count<=0 or w<=0 or h<=0:raise ValueError(f'Unreadable video metadata: {vp}')
            gt=read_ground_truth(gp)
            if any(not x['visible'] and (x['x']!=0 or x['y']!=0) for x in gt.values()):raise ValueError('Visibility sentinel mismatch')
            metadata.append(dict(rally=r,role=role,video=vp,gt_path=gp,count=count,width=w,height=h,gt=gt,offset=total));total+=count
        sample_global=set(np.linspace(0,total-1,min(total,100),dtype=int).tolist());background=[]
        for item in metadata:
            rally=item['rally'];target=out/'all'/m;frame_dir=target/'frame'/rally;csv_dir=target/'csv';frame_dir.mkdir(parents=True,exist_ok=True);csv_dir.mkdir(exist_ok=True)
            csv_target=csv_dir/f'{rally}_ball.csv'
            if not csv_target.exists():csv_target.write_bytes(item['gt_path'].read_bytes())
            needed={0}|{max(0,f-i) for f in item['gt'] for i in range(4)};cap=cv2.VideoCapture(str(item['video']));i=0
            while True:
                ok,image=cap.read()
                if not ok:break
                gidx=item['offset']+i
                if gidx in sample_global:background.append(image.copy())
                if i in needed:
                    dest=frame_dir/f'{i:04d}.jpg'
                    if not dest.exists():
                        ok,encoded=cv2.imencode('.jpg',image)
                        if not ok:raise IOError(f'Frame encode failed: {dest}')
                        encoded.tofile(dest)
                i+=1
            cap.release()
            if i!=item['count'] or max(needed)>=i:raise ValueError(f'Video frame count/GT bounds mismatch: {m}/{r}: metadata={item["count"]}, decoded={i}')
            records.append(dict(source_id=f'tabletennis/{m}/{r}',role=item['role'],frames=i,annotations=len(item['gt']),resolution=[item['width'],item['height']],video_sha256=sha256(item['video']),gt_sha256=sha256(item['gt_path'])))
        if len({(x['width'],x['height']) for x in metadata})!=1:raise ValueError(f'Changing resolution in match {m}; do not combine medians')
        # Faithful to create_median.py's np.linspace selection and uint8 pixel median,
        # restricted to downloaded annotated rallies rather than complete matches.
        median=np.median(np.stack(background),axis=0).astype(np.uint8);np.savez(out/'all'/m/'median.npz',median=median)
        ok,encoded=cv2.imencode('.png',median)
        if not ok:raise IOError('Median preview encode failed')
        encoded.tofile(out/'all'/m/'median.png')
        for record in records[-len(metadata):]:record['match_median_sha256']=sha256(out/'all'/m/'median.npz')
        print(f'{m}: {len(items)} rallies, {len(background)} globally sampled frames, {metadata[0]["width"]}x{metadata[0]["height"]}',flush=True)
    for role,entries in info.items():
        p=out/'info'/f'{role}.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(entries,indent=2)+'\n',encoding='utf-8')
    (home/'prepared_inputs.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
    print(f"Prepared {len(records)} clips across {len(videos)} matches; match medians cover selected annotated rallies only",flush=True)

if __name__=='__main__':main()
