"""Raw-preserving development/holdout evaluation. Does not open a match database."""
import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from html import escape
import json
import math
from pathlib import Path
import statistics
import subprocess

from .benchmark import compare, read_ground_truth, percentile
from .config import VisionConfig, DATA_REVISION
from .postprocess import TTIBallTrackPostProcessor, PostProcessorConfig
from .runner import run_analysis, sha256

TAXONOMY=('REFEREE_CLOTHING','PLAYER_CLOTHING','WHITE_TABLE_LINE','NET','BACKGROUND_LIGHT',
          'MOTION_BLUR','OCCLUSION','CAMERA_MOTION','BALL_NEAR_BODY','BALL_NEAR_TABLE','UNKNOWN')


def collect_errors(source,video,points,gt,width,height):
    by_frame={p['frame']:i for i,p in enumerate(points)};errors=[]
    threshold=math.hypot(width,height)*.01
    for frame,g in sorted(gt.items()):
        index=by_frame.get(frame);p=points[index] if index is not None else None
        pv=bool(p and p['visible']);distance=None;failure=None
        if g['visible'] and not pv: failure='MISSED_GT'
        elif not g['visible'] and pv: failure='FALSE_POSITIVE_ON_ANNOTATED_NEGATIVE'
        elif g['visible'] and pv:
            distance=math.hypot(p['pixel_x']-g['x'],p['pixel_y']-g['y'])
            if distance>threshold: failure='HIGH_POSITION_ERROR'
        if failure:
            errors.append({'clip_id':source,'video':str(video),'frame':frame,
                           'gt':[g['x'],g['y']] if g['visible'] else None,
                           'prediction':[p['pixel_x'],p['pixel_y']] if pv else None,
                           'error_px':distance,'failure':failure,'classification':'UNKNOWN',
                           'previous_prediction':points[index-1] if index is not None and index>0 else None,
                           'next_prediction':points[index+1] if index is not None and index+1<len(points) else None,
                           'model_output':p,'triage_threshold_px':threshold})
    return errors


def combine_metrics(clips,key):
    visible=sum(c[key]['visible_gt_frames'] for c in clips)
    detected=sum(c[key]['detected_visible_frames'] for c in clips)
    errors=[x for c in clips for x in c[key+'_errors']]
    return {'visible_gt_frames':visible,'detected_visible_frames':detected,'missed_frames':visible-detected,
            'recall':detected/visible if visible else None,
            'negative_gt_frames':sum(c[key]['annotated_negative_frames'] for c in clips),
            'false_positives':sum(c[key]['false_detections'] or 0 for c in clips),
            'co_visible_samples':len(errors),'mean_error_px':statistics.mean(errors) if errors else None,
            'median_error_px':statistics.median(errors) if errors else None,'p95_error_px':percentile(errors,.95)}


def position_errors(points,gt):
    by_frame={p['frame']:p for p in points}
    return [math.hypot(by_frame[f]['pixel_x']-g['x'],by_frame[f]['pixel_y']-g['y'])
            for f,g in gt.items() if g['visible'] and f in by_frame and by_frame[f]['visible']]


def evaluate(baseline_path,split_path,parameter_path,destination,split='development',config=None):
    config=config or VisionConfig.load();destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=False)
    baseline=json.loads(Path(baseline_path).read_text(encoding='utf-8'))
    manifest=json.loads(Path(split_path).read_text(encoding='utf-8'))
    if manifest['dataset_revision']!=DATA_REVISION or set(manifest['development']) & set(manifest['holdout']):
        raise ValueError('Invalid or overlapping frozen split')
    settings=json.loads(Path(parameter_path).read_text(encoding='utf-8'))
    params=PostProcessorConfig(**settings['experimental_rejection'])
    config_hash=sha256(parameter_path);split_hash=sha256(split_path)
    lock={'parameter_sha256':config_hash,'split_sha256':split_hash,'postprocessor':asdict(params)}
    lock_path=destination.parent/'postprocessor-lock-v1.json'
    if split=='development':
        if lock_path.exists() and json.loads(lock_path.read_text())!=lock: raise ValueError('Frozen parameter lock differs')
        lock_path.write_text(json.dumps(lock,indent=2),encoding='utf-8')
    elif not lock_path.is_file() or json.loads(lock_path.read_text())!=lock:
        raise ValueError('Holdout requires unchanged parameter and split lock')
    processor=TTIBallTrackPostProcessor(params);clips=[];error_rows=[]
    prior_review=Path(baseline_path).parent/'worst_cases/review.json'
    verified={(r['clip_id'],r['frame']):r for r in json.loads(prior_review.read_text(encoding='utf-8'))} if prior_review.exists() else {}
    for source_id in manifest[split]:
        _,match,rally=source_id.split('/')
        video=config.dataset_root/'tabletennis/videos'/f'{match}_{rally}.mp4'
        gt_path=config.dataset_root/'tabletennis/all'/match/'csv'/f'{rally}_ball.csv'
        if split=='development':
            clip=next(c for c in baseline['clips'] if c['source_id']==source_id)
            analysis_root=config.output_root/clip['analysis_id']
            analysis=json.loads((analysis_root/'analysis.json').read_text(encoding='utf-8'))
            if sha256(video)!=clip['video_sha256'] or sha256(gt_path)!=clip['gt_sha256']: raise ValueError('Baseline inputs changed')
        else:
            print('HOLDOUT '+source_id,flush=True)
            analysis=run_analysis(video,{'type':'racketvision','provider':'linfeng302/RacketVision','source_id':source_id,'rights':'research'},
                                  gt_path,config,'cuda',force_recompute=True)
            analysis_root=config.output_root/analysis['analysis_id']
        points=json.loads((analysis_root/'ball_track.json').read_text(encoding='utf-8'))
        meta=analysis['video'];gt=read_ground_truth(gt_path)
        records=processor.process(points,meta['width'],meta['height'],meta['fps'])
        filtered=[r['filtered_prediction'] for r in records]
        stem=source_id.replace('/','_')
        (destination/f'{stem}_raw-filtered.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
        raw_metrics=compare(points,gt,meta['width'],meta['height']);filtered_metrics=compare(filtered,gt,meta['width'],meta['height'])
        clips.append({'source_id':source_id,'analysis_id':analysis['analysis_id'],'video_sha256':sha256(video),
                      'gt_sha256':sha256(gt_path),'raw_prediction_sha256':sha256(analysis_root/'ball_track.json'),
                      'raw':raw_metrics,'filtered':filtered_metrics,'raw_errors':position_errors(points,gt),
                      'filtered_errors':position_errors(filtered,gt),'filter_counts':dict(Counter(r['filter_reason'] for r in records if r['filter_reason'])),
                      'provenance':analysis['provenance']})
        rows=collect_errors(source_id,video,points,gt,meta['width'],meta['height'])
        for row in rows:
            reviewed=verified.get((source_id,row['frame']),{})
            if reviewed.get('classification')=='background_person_clothing_confusion':
                row['classification']='REFEREE_CLOTHING';row['classification_evidence']='Prior full-frame manual review, retained without extrapolating to unreviewed frames'
            row['filtered_prediction']=records[by_frame_index(points,row['frame'])]['filtered_prediction'] if row['frame'] in {p['frame'] for p in points} else None
        error_rows.extend(rows)
    error_root=destination/'benchmark_errors';error_root.mkdir()
    input_path=error_root/'errors.json';input_path.write_text(json.dumps(error_rows,ensure_ascii=False,indent=2),encoding='utf-8')
    subprocess.run([str(config.worker_python),str(Path(__file__).resolve().parents[1]/'vision_worker/error_images.py'),
                    '--manifest',str(input_path),'--output',str(error_root/'images')],check=True)
    taxonomy={k:sum(r['classification']==k for r in error_rows) for k in TAXONOMY}
    summary={'status':'BASELINE_ONLY','split':split,'selection':manifest,'parameter_lock':lock,
             'recorded_at':datetime.now(timezone.utc).isoformat(),'raw':combine_metrics(clips,'raw'),
             'filtered':combine_metrics(clips,'filtered'),'default_annotation_only':'RAW metrics unchanged; rejection is experimental and not enabled in product',
             'taxonomy':taxonomy,'error_count':len(error_rows),'clips':clips,
             'scene_constraints':'No validated table detector; no ROI clipping or guessed ball location applied',
             'source_tree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
             'tti_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()}
    (destination/'raw-vs-filtered.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    figures=''.join(f'<article><h3>{escape(r["clip_id"])} · frame {r["frame"]} · {r["classification"]}</h3><img width="700" src="benchmark_errors/images/{i:03d}.jpg"><details><summary>原始证据</summary><pre>{escape(json.dumps(r,ensure_ascii=False,indent=2))}</pre></details></article>' for i,r in enumerate(error_rows))
    html='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>BallTrack 失败分析</title><style>body{font-family:Microsoft YaHei,sans-serif;max-width:1100px;margin:auto}img{max-width:100%}pre{white-space:pre-wrap}article{margin:30px 0}</style><h1>BallTrack 失败分析 · '+split+'</h1><p>绿色=GT；红色=原始预测。未知原因保持 UNKNOWN。拒绝模式仅为实验，默认不改变模型观测。</p><pre>'+escape(json.dumps({k:summary[k] for k in ('raw','filtered','taxonomy','parameter_lock')},indent=2))+'</pre>'+figures+'</html>'
    (destination/'failure_analysis.html').write_text(html,encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('raw','filtered','taxonomy','error_count')},indent=2),flush=True)
    return summary


def by_frame_index(points,frame):
    return next(i for i,p in enumerate(points) if p['frame']==frame)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--split-manifest',type=Path,required=True);parser.add_argument('--parameters',type=Path,default=Path('configs/balltrack-postprocess-v1.json'))
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--split',choices=['development','holdout'],required=True)
    args=parser.parse_args();evaluate(args.baseline,args.split_manifest,args.parameters,args.output,args.split)
