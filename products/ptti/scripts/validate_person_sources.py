"""Locked-config, new-source scene check on five local official TRAIN clips.

No test split is read, no source video downloaded. No parameter changes are
permitted after this run. Output remains research evidence, not human GT.
"""
import gc
import json
import os
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEV=Path(os.environ['LOCALAPPDATA'])/'PTTI-Dev/vision-v2'
sys.path.insert(0,str(DEV/'venv/Lib/site-packages'));sys.path.insert(0,str(ROOT))
import cv2
import torch
from PIL import Image,ImageDraw
from transformers import (AutoModelForZeroShotObjectDetection,AutoProcessor,
                          RTDetrForObjectDetection,RTDetrImageProcessor)
from backend.person_detector import (file_sha,verify_r18,RTDetrPredictionAdapter,deduplicate_people,
    TablePersonRoleResolver,person_frame_review)
from backend.scene_bootstrap import MODEL_SHA256
from vision.config import DATA_REVISION


def main():
    scene=DEV/'scene-bootstrap';out=scene/'person-validation';out.mkdir(exist_ok=True)
    manifest_path=out/'person_detector_validation_manifest.json'
    if manifest_path.exists():raise RuntimeError('VALIDATION_MANIFEST_EXISTS_DO_NOT_RESELECT_OR_OVERWRITE')
    config_path=scene/'person_detector_config.json';cfg=json.loads(config_path.read_text())
    locked_sha=file_sha(config_path)
    train_file=ROOT/'datasets/racketvision/tabletennis/info/train.json'
    train=json.loads(train_file.read_text());chosen=[];seen=set()
    for match,clip in train:
        source=ROOT/f'datasets/racketvision/tabletennis/videos/{match}_{clip}.mp4'
        if match in seen or not source.is_file():continue
        chosen.append((match,clip,source));seen.add(match)
        if len(chosen)==5:break
    if len(chosen)!=5:raise RuntimeError('FIVE_LOCAL_OFFICIAL_TRAIN_MATCHES_UNAVAILABLE')
    records=[];sources=[]
    for match,clip,source in chosen:
        cap=cv2.VideoCapture(str(source));fps=cap.get(cv2.CAP_PROP_FPS);count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps<=0 or count<5:raise RuntimeError('VIDEO_PROBE_FAILED')
        media={"fps":fps,"frame_count":count,"duration_seconds":count/fps,
               "width":int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),"height":int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}
        source_hash=file_sha(source)
        sources.append({'match':match,'clip':clip,'source':str(source),'sha256':source_hash,
                        'bytes':source.stat().st_size,'media':media,'split':'train',
                        'dataset':'linfeng302/RacketVision','dataset_revision':DATA_REVISION,
                        'rights':'dataset card declares MIT; research only; no independent broadcast licence assertion'})
        for slot,fraction in enumerate((.2,.4,.6,.8),1):
            frame=round((count-1)*fraction);cap.set(cv2.CAP_PROP_POS_FRAMES,frame);ok,array=cap.read()
            if not ok:raise RuntimeError('SOURCE_FRAME_DECODE_FAILED')
            filename=f'{match}-s{slot:02d}.jpg';cv2.imwrite(str(out/filename),array)
            records.append({'game':match,'slot':slot,'frame':frame,'timestamp_ms':round(frame*1000/fps),
                            'timestamp_source':'CFR_FRAME_RATE_ESTIMATE','image':filename,
                            'frame_sha256':file_sha(out/filename),'width':media['width'],'height':media['height']})
        cap.release()
    manifest={'status':'LOCKED_BEFORE_INFERENCE','config_sha256':locked_sha,'train_index_sha256':file_sha(train_file),
              'dataset_revision':DATA_REVISION,'sources':sources,'frames':records,
              'selection':'first five distinct officially TRAIN matches with local video in train index order',
              'not_previously_in_person_development':True,'note':'these matches were exposed in prior BallTrack research; not universally untouched'}
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    gd=DEV/'models/grounding-dino-base'
    if file_sha(gd/'model.safetensors').lower()!=MODEL_SHA256.lower():raise RuntimeError('DINO_SHA_MISMATCH')
    proc=AutoProcessor.from_pretrained(gd,local_files_only=True)
    model=AutoModelForZeroShotObjectDetection.from_pretrained(gd,local_files_only=True).eval().to('cuda')
    for r in records:
        image=Image.open(out/r['image']).convert('RGB');inputs=proc(images=image,text='table tennis table.',return_tensors='pt').to('cuda')
        with torch.inference_mode():outputs=model(**inputs)
        det=proc.post_process_grounded_object_detection(outputs,inputs.input_ids,threshold=.25,text_threshold=.25,
            target_sizes=[(image.height,image.width)],text_labels=[['table tennis table']])[0]
        tables=[{'bbox':box.tolist(),'detector_score':float(score)} for box,score in zip(det['boxes'],det['scores'])
                if float(box[2]-box[0])>=image.width*.2 and float((box[2]-box[0])*(box[3]-box[1]))>=image.width*image.height*.03]
        r['raw_table_candidates']=tables;r['table_bbox']=max(tables,key=lambda d:d['detector_score'])['bbox'] if tables else None
        print('TABLE',r['game'],r['slot'],bool(r['table_bbox']),flush=True)
    del model,proc,outputs,inputs;gc.collect();torch.cuda.empty_cache()
    provenance=verify_r18(DEV/'models/rtdetr-r18vd')
    proc=RTDetrImageProcessor.from_pretrained(DEV/'models/rtdetr-r18vd',local_files_only=True)
    model=RTDetrForObjectDetection.from_pretrained(DEV/'models/rtdetr-r18vd',local_files_only=True).eval().to('cuda')
    latencies=[];torch.cuda.reset_peak_memory_stats()
    for r in records:
        image=Image.open(out/r['image']).convert('RGB');before=time.perf_counter()
        inputs=proc(images=image,return_tensors='pt').to('cuda')
        with torch.inference_mode():outputs=model(**inputs)
        det=proc.post_process_object_detection(outputs,target_sizes=torch.tensor([[image.height,image.width]],device='cuda'),threshold=.1)[0]
        torch.cuda.synchronize();latencies.append((time.perf_counter()-before)*1000)
        predictions=[{'label':model.config.id2label[int(label)],'score':float(score),'bbox':box.tolist()}
                     for score,label,box in zip(det['scores'],det['labels'],det['boxes'])]
        raw=RTDetrPredictionAdapter().adapt(predictions,image_size=image.size,frame=r['frame'],timestamp_ms=r['timestamp_ms'],threshold=.1)
        for i,p in enumerate(raw):p['candidate_id']=f"validation-{r['game']}-s{r['slot']:02d}-d{i}"
        r['raw_person_detections']=raw
        people=deduplicate_people([p for p in raw if p['detector_score']>=cfg['threshold']],cfg['duplicate_iou'])
        r['detections']=TablePersonRoleResolver().resolve(r['table_bbox'],people,image_size=image.size)
        r['review']=person_frame_review(r['detections'],table_present=bool(r['table_bbox']))
        r['both_candidates']={'NEAR_PLAYER','FAR_PLAYER'} <= {p['role_candidate'] for p in r['detections']}
        overlay=image.copy();draw=ImageDraw.Draw(overlay)
        if r['table_bbox']:draw.rectangle(r['table_bbox'],outline='#24e89c',width=3)
        for p in r['detections']:
            draw.rectangle(p['bbox'],outline='#ffab32' if p['role_candidate'] in {'OTHER','UNKNOWN'} else '#3388ff',width=3)
            draw.text((p['bbox'][0],max(0,p['bbox'][1]-12)),p['role_candidate'],fill='white')
        r['overlay']=r['image'].replace('.jpg','-overlay.jpg');overlay.save(out/r['overlay'])
        print('PERSON',r['game'],r['slot'],len(people),r['both_candidates'],flush=True)
    if file_sha(config_path)!=locked_sha:raise RuntimeError('LOCKED_CONFIG_CHANGED')
    summary=lambda items:{'frames':len(items),'table_found':sum(bool(r['table_bbox']) for r in items),
        'both_role_candidates':sum(r['both_candidates'] for r in items),
        'review_required':sum(r['review']['priority']=='HIGH' for r in items)}
    result={'status':'REAL_NEW_TRAIN_SOURCES_INFERRED','manifest_sha256':file_sha(manifest_path),
        'config_sha256':locked_sha,'provenance':provenance,'summary':summary(records),
        'per_match':{m:summary([r for r in records if r['game']==m]) for m in sorted(seen)},
        'runtime':{'mean_inference_ms':sum(latencies)/len(latencies),'peak_vram_bytes':torch.cuda.max_memory_allocated()},
        'independent_human_gt':False,'algorithm_accuracy':'NOT_MEASURED_WITH_INDEPENDENT_HUMAN_GT','frames':records}
    (out/'person_detector_validation_results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    html='<!doctype html><meta charset="utf-8"><title>Person validation — research</title><h1>Frozen RT-DETR R18: new TRAIN matches</h1><p>Candidate evidence, not independent human accuracy.</p>'
    for r in records:html+=f"<figure><img width='960' src='{r['overlay']}'><figcaption>{r['game']} {r['slot']} {r['review']}</figcaption></figure>"
    (out/'person_detector_validation.html').write_text(html,encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('summary','per_match','runtime')}),flush=True)


if __name__=='__main__':main()
