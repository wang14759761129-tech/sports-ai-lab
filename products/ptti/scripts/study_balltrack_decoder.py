"""DEV-only threshold/decoder/subpixel sweep; writes one immutable selected config."""
import itertools,json,math,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from vision.benchmark import read_ground_truth,compare,percentile
from vision.specialist import sha256

def decode(hm,threshold,kind,refinement):
    mask=hm>threshold
    if not mask.any():return None
    if kind=='contour_bbox':
        contours,_=cv2.findContours(mask.astype(np.uint8)*255,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        if not contours:return None
        c=max(contours,key=lambda z:cv2.boundingRect(z)[2]*cv2.boundingRect(z)[3]);x,y,w,h=cv2.boundingRect(c);px=x+w/2;py=y+h/2
    else:
        py,px=np.unravel_index(int(np.argmax(hm)),hm.shape);px=float(px);py=float(py)
    if refinement!='none':
        cx,cy=round(px),round(py);radius=2;patch=hm[max(0,cy-radius):cy+radius+1,max(0,cx-radius):cx+radius+1].astype(np.float64)
        if refinement=='weighted_centroid':weights=np.maximum(patch-float(patch.min()),0)
        else:weights=np.exp((patch-patch.max())/.05)
        if weights.sum()>0:
            yy,xx=np.mgrid[max(0,cy-radius):cy+radius+1,max(0,cx-radius):cx+radius+1];px=float((xx*weights).sum()/weights.sum());py=float((yy*weights).sum()/weights.sum())
    return px,py

def summarize(rows):
    visible=[r for r in rows if r['gt']['visible']];neg=[r for r in rows if not r['gt']['visible']];found=[r for r in visible if r['pred'] is not None];errors=[math.hypot(r['pred'][0]*r['width']/512-r['gt']['x'],r['pred'][1]*r['height']/288-r['gt']['y']) for r in found]
    return dict(visible=len(visible),detected=len(found),recall=len(found)/len(visible) if visible else None,fp=sum(r['pred'] is not None for r in neg),mean=float(np.mean(errors)) if errors else None,median=percentile(errors,.5),p95=percentile(errors,.95),catastrophic={str(t):sum(e>t for e in errors) for t in [20,50,100]})

def main():
    home=ROOT/'outputs/vision/balltrack_final';out=home/'decoder_study.json';lock=home/'decoder_config.json'
    if out.exists() or lock.exists():raise FileExistsError('Decoder study/config already frozen; use new experiment ID')
    manifest=json.loads((home/'split.json').read_text(encoding='utf-8'));prepared=json.loads((home/'prepared_inputs.json').read_text(encoding='utf-8'));dimensions={x['source_id']:x['resolution'] for x in prepared};base=[]
    for sid in manifest['dev']:
        _,m,r=sid.split('/');gt=read_ground_truth(home/f'dataset/tabletennis/all/{m}/csv/{r}_ball.csv');
        for frame,g in gt.items():
            p=home/'heatmaps/train_d/dev'/f'{m}_{r}_{frame:06d}.npz'
            if not p.exists():raise FileNotFoundError(f'Best-checkpoint DEV heatmap missing: {p}')
            hm=np.load(p)['heatmap'];w,h=dimensions[sid];base.append(dict(source_id=sid,frame=frame,gt=g,heatmap=hm,width=w,height=h))
    rows=[]
    for threshold,kind,refinement in itertools.product([.35,.40,.45,.50,.55],["contour_bbox","global_max"],["none","weighted_centroid","softargmax"]):
        predictions={}
        for sample in base:
            point=decode(sample['heatmap'],threshold,kind,refinement)
            predictions.setdefault(sample['source_id'],[]).append(dict(frame=sample['frame'],visible=point is not None,pixel_x=round(point[0]*sample['width']/512) if point else None,pixel_y=round(point[1]*sample['height']/288) if point else None))
        clips=[]
        for sid,ps in predictions.items():
            _,m,r=sid.split('/');gt=read_ground_truth(home/f'dataset/tabletennis/all/{m}/csv/{r}_ball.csv');w,h=dimensions[sid];clips.append(compare(ps,gt,w,h))
        metrics={k:sum(c[k] or 0 for c in clips) for k in ['visible_gt_frames','detected_visible_frames','annotated_negative_frames','false_detections']};errors=[]
        for sample in base:
            if sample['gt']['visible']:
                p=decode(sample['heatmap'],threshold,kind,refinement)
                if p:errors.append(math.hypot(p[0]*sample['width']/512-sample['gt']['x'],p[1]*sample['height']/288-sample['gt']['y']))
        metrics.update(recall=metrics['detected_visible_frames']/metrics['visible_gt_frames'],fp=metrics['false_detections'],mean=float(np.mean(errors)) if errors else None,median=percentile(errors,.5),p95=percentile(errors,.95),catastrophic={str(t):sum(e>t for e in errors) for t in [20,50,100]})
        rows.append(dict(threshold=threshold,decoder=kind,refinement=refinement,metrics=metrics))
    reference=next(x['metrics'] for x in rows if x['threshold']==.5 and x['decoder']=='contour_bbox' and x['refinement']=='none')
    viable=[x for x in rows if x['metrics']['recall']>=reference['recall'] and x['metrics']['fp']<=reference['fp'] and all(x['metrics']['catastrophic'][str(t)]<=reference['catastrophic'][str(t)] for t in [20,50,100])]
    winner=min(viable,key=lambda x:(x['metrics']['median'],x['metrics']['p95'],x['metrics']['mean'])) if viable else next(x for x in rows if x['threshold']==.5 and x['decoder']=='contour_bbox' and x['refinement']=='none')
    selected={'threshold':winner['threshold'],'decoder':'upstream_contour_bbox' if winner['decoder']=='contour_bbox' else 'global_max','refinement':winner['refinement'],'candidate_nms_radius':5,'selection':'DEV only: require recall >= default, FP and >20/50/100px errors no worse; among eligible minimize median then P95 then mean; otherwise keep upstream defaults','dev_metrics':winner['metrics'],'reference_dev_metrics':reference}
    out.write_text(json.dumps(dict(input_heatmap_dir='heatmaps/train_d/dev',input_files_sha256={str(p.relative_to(ROOT)):sha256(p) for p in sorted((home/'heatmaps/train_d/dev').glob('*.npz'))},trials=rows,selected=selected),indent=2)+'\n',encoding='utf-8')
    selected['study_sha256']=sha256(out);lock.write_text(json.dumps(selected,indent=2)+'\n',encoding='utf-8')
    checkpoint=ROOT/'models/tti_tabletennis/tti_balltrack_final_v1_D.pth';provenance_path=checkpoint.with_suffix('.provenance.json')
    provenance=json.loads(provenance_path.read_text(encoding='utf-8'));provenance['decoder_sha256']=sha256(lock);provenance['decoder_study_sha256']=sha256(out)
    provenance_path.write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    training_path=home/'D_training.json';training=json.loads(training_path.read_text(encoding='utf-8'));training['provenance']=provenance;training_path.write_text(json.dumps(training,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(selected,indent=2))

if __name__=='__main__':main()
