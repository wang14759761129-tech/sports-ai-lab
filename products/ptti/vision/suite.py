"""Bounded, sparse-ground-truth evaluation across pinned official test clips."""
import json
import math
import math
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from html import escape

from .benchmark import percentile, read_ground_truth
from .config import DATA_REVISION, RV_COMMIT, VisionConfig
from .runner import run_analysis, sha256


def aggregate(clips, errors):
    analyzed=[c for c in clips if c.get('status')=='ANALYZED']
    visible=sum(c['visible_gt_frames'] for c in analyzed)
    detected=sum(c['detected_visible_frames'] for c in analyzed)
    annotated=sum(c['annotated_frames'] for c in analyzed)
    return {
        'clips_selected':len(clips),
        'clips_completed':len(analyzed),
        'clips_passed':None,
        'clip_pass_threshold':'not defined; results remain BASELINE_ONLY',
        'clips_with_failure_modes':sum(bool(c.get('failure_modes')) for c in analyzed),
        'annotated_frames':annotated,
        'visible_gt_frames':visible,
        'detected_visible_frames':detected,
        'overall_visible_recall':detected/visible if visible else None,
        'co_visible_position_errors':len(errors),
        'weighted_mean_position_error_px':statistics.mean(errors) if errors else None,
        'median_position_error_px':statistics.median(errors) if errors else None,
        'p95_position_error_px':percentile(errors,.95),
        'total_processing_seconds':sum(c.get('processing_seconds',0) for c in analyzed),
        'total_decoded_frames':sum(c.get('decoded_frames',0) for c in analyzed),
        'aggregate_processing_fps':(
            sum(c.get('decoded_frames',0) for c in analyzed)/
            sum(c.get('processing_seconds',0) for c in analyzed)
            if sum(c.get('processing_seconds',0) for c in analyzed)>0 else None),
        'per_phase_seconds':{
            key:sum(c.get('profile',{}).get(key,0) for c in analyzed)
            for key in ('frame_extraction_seconds','background_preprocessing_seconds','model_load_seconds',
                        'model_inference_seconds','prediction_serialization_seconds','normalization_seconds',
                        'postprocessing_seconds','overlay_encoding_seconds')
        },
        'false_detections_on_annotated_negatives':sum(c.get('false_detections',0) or 0 for c in analyzed),
        'annotated_negative_frames':sum(c.get('annotated_negative_frames',0) for c in analyzed),
        'definition':'Recall is computed only on visible annotated frames. Unannotated frames are not negatives. Position errors use co-visible GT/prediction pairs; clips_passed is null because no accuracy threshold was specified.'
    }


def _worst_observations(video, prediction, ground_truth, clip_id):
    pred={p['frame']:p for p in prediction}
    observations=[]
    for frame, gt in ground_truth.items():
        if not gt['visible']:
            p=pred.get(frame)
            if p and p['visible']:
                observations.append(dict(clip_id=clip_id,video=str(video),frame=frame,gt=None,
                                        prediction=[p['pixel_x'],p['pixel_y']],error_px=None,
                                        failure='false_detection_on_annotated_negative',classification='unknown'))
            continue
        p=pred.get(frame)
        if not p or not p.get('visible'):
            observations.append(dict(clip_id=clip_id,video=str(video),frame=frame,
                                    gt=[gt['x'],gt['y']],prediction=None,error_px=None,
                                    failure='missed_visible_annotation',classification='unknown'))
        else:
            error=math.hypot(p['pixel_x']-gt['x'],p['pixel_y']-gt['y'])
            observations.append(dict(clip_id=clip_id,video=str(video),frame=frame,
                                    gt=[gt['x'],gt['y']],prediction=[p['pixel_x'],p['pixel_y']],
                                    error_px=error,failure=None,classification='unknown'))
    observations.sort(key=lambda x:(x['error_px'] is None, x['error_px'] if x['error_px'] is not None else float('inf')), reverse=True)
    return observations


def select_worst_cases(observations, limit=20):
    """Keep failure examples and severe localization outliers in the same review set."""
    failures=[x for x in observations if x.get('failure')]
    misses=[x for x in failures if x.get('failure')=='missed_visible_annotation']
    false_positives=[x for x in failures if x.get('failure')!='missed_visible_annotation']
    prioritized=sorted(misses,key=lambda x:(x['clip_id'],x['frame']))
    prioritized+=sorted(false_positives,key=lambda x:(x['clip_id'],x['frame']))
    balanced=[];seen=set()
    for item in prioritized:
        if item['clip_id'] not in seen:
            balanced.append(item);seen.add(item['clip_id'])
    for item in prioritized:
        if len(balanced)>=limit//2: break
        if item not in balanced: balanced.append(item)
    numeric=sorted((x for x in observations if x.get('error_px') is not None),
                   key=lambda x:x['error_px'],reverse=True)
    selected=balanced[:limit//2]+numeric[:limit-len(balanced[:limit//2])]
    return selected


def _save_worst_frames(observations, destination, config):
    manifest=destination.parent/'worst-cases-input.json'
    manifest.write_text(json.dumps(observations,ensure_ascii=False,indent=2),encoding='utf-8')
    worker=Path(__file__).resolve().parents[1]/'vision_worker'/'worst_cases.py'
    subprocess.run([str(config.worker_python),str(worker),'--manifest',str(manifest),
                    '--output',str(destination)],check=True,timeout=600)
    manifest.unlink()
    return json.loads((destination/'review.json').read_text(encoding='utf-8'))


def _html_report(result):
    summary=result['aggregate']
    rows=[]
    for clip in result['clips']:
        metrics=clip.get('metrics') or {}
        rows.append('<tr>'+''.join(f'<td>{escape(str(value))}</td>' for value in (
            clip['source_id'],clip['status'],metrics.get('annotated_frames'),metrics.get('visible_gt_frames'),
            metrics.get('detected_visible_frames'),metrics.get('visible_recall'),metrics.get('mean_position_error_px'),
            metrics.get('median_position_error_px'),metrics.get('p95_position_error_px'),
            clip.get('processing_seconds'),clip.get('processing_fps')))+'<td>'+escape(', '.join(clip.get('failure_modes',[])))+'</td></tr>')
    profile=''.join(f'<tr><th>{escape(k)}</th><td>{escape(str(round(v,3)))} 秒</td></tr>' for k,v in summary['per_phase_seconds'].items())
    images=''.join(f'<a href="worst_cases/{escape(item["image"])}"><img width="240" src="worst_cases/{escape(item["image"])}"></a>'
                   for item in result.get('worst_cases',[]) if item.get('image'))
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>PTTI BallTrack 多片段基准</title>'
            '<style>body{font-family:Microsoft YaHei,Segoe UI,sans-serif;max-width:1200px;margin:32px auto;color:#183d3a}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}img{margin:4px}p{line-height:1.6}</style>'
            '<h1>RacketVision BallTrack 多片段基准</h1><p>稀疏标注；未标注帧不视为负例。没有设定准确率通过门槛，所有结果保持 BASELINE_ONLY。</p>'
            f'<p>数据 revision：{escape(result["dataset_revision"])} · 片段 {summary["clips_completed"]}/{summary["clips_selected"]} 完成</p>'
            '<h2>逐片段结果</h2><table><tr><th>来源 ID</th><th>运行</th><th>标注帧</th><th>可见 GT</th><th>检出</th><th>召回率</th><th>平均误差 px</th><th>中位数 px</th><th>P95 px</th><th>处理秒</th><th>处理 FPS</th><th>观察到的失败</th></tr>'
            +''.join(rows)+'</table><h2>汇总</h2><pre>'+escape(json.dumps(summary,ensure_ascii=False,indent=2))+'</pre>'
            '<h2>性能分段累计时间</h2><table>'+profile+'</table><h2>最差标注帧（绿色十字=GT，红色圆圈=预测；成因待人工确认）</h2>'+images+'</html>')


def run_suite(config=None,device='cuda',stage=print,force_recompute=False):
    config=config or VisionConfig.load()
    manifest_path=config.dataset_root/'benchmark-suite-manifest.json'
    if not manifest_path.is_file(): raise ValueError('请先运行 scripts/download_vision_sample.py --benchmark-suite')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('dataset_revision')!=DATA_REVISION:
        raise ValueError('Benchmark suite dataset revision does not match the pinned revision')
    source_ids=manifest.get('source_ids',[])
    if len(source_ids)<5: raise ValueError('Benchmark suite requires at least five official test clips')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    suite_root=config.output_root/f'benchmark_suite_{stamp}'
    suite_root.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter();clips=[];all_errors=[];worst=[]
    runtime_root=config.runtime_root
    try:
        racketvision_commit=__import__('subprocess').check_output(['git','-C',str(runtime_root),'rev-parse','HEAD'],text=True).strip()
    except Exception as exc:
        raise ValueError(f'Pinned RacketVision checkout unavailable: {exc}') from exc
    if racketvision_commit!=RV_COMMIT: raise ValueError('RacketVision checkout does not match pinned commit')
    for index,source_id in enumerate(source_ids,1):
        parts=source_id.split('/')
        if len(parts)!=3 or parts[0]!='tabletennis': raise ValueError(f'Invalid official test source id: {source_id}')
        _,match,rally=parts
        video=config.dataset_root/'tabletennis/videos'/f'{match}_{rally}.mp4'
        gt_path=config.dataset_root/'tabletennis/all'/match/'csv'/f'{rally}_ball.csv'
        clip=dict(source_id=source_id,status='FAILED',video_sha256=None,gt_sha256=None,metrics=None,error=None)
        clips.append(clip)
        if not video.is_file() or not gt_path.is_file():
            clip['error']='Pinned video or ground-truth file is missing'
            continue
        stage(f'基准片段 {index}/{len(source_ids)} · {source_id}')
        clip['video_sha256']=sha256(video);clip['gt_sha256']=sha256(gt_path)
        source=dict(type='racketvision',provider='linfeng302/RacketVision',source_id=source_id,
                    rights='research',rights_notes=f'Official test split; dataset revision {DATA_REVISION}')
        try:
            result=run_analysis(video,source,gt_path,config,device,stage=lambda _s:None,force_recompute=force_recompute)
            metrics=result['metrics'] or {}
            runtime=result['provenance']['runtime']
            clip.update(status='ANALYZED',analysis_id=result['analysis_id'],metrics=metrics,
                        decoded_frames=runtime.get('decoded_frames'),
                        processing_seconds=runtime.get('processing_seconds'),
                        processing_fps=runtime.get('processing_fps'),
                        inference_seconds=runtime.get('profile',{}).get('model_inference_seconds'),
                        cache_reused=result['provenance'].get('cache_reused',False),
                        profile=result['provenance'].get('profile',{}),
                        tti_commit=result['provenance'].get('tti_commit'),
                        source_tree_dirty=result['provenance'].get('source_tree_dirty'),
                        failure_modes=(['missed_visible_annotations'] if metrics.get('missed_frames',0) else [])+
                                      (['false_detection_on_annotated_negatives'] if (metrics.get('false_detections') or 0) else []))
            prediction=json.loads((config.output_root/result['analysis_id']/'ball_track.json').read_text(encoding='utf-8'))
            gt=read_ground_truth(gt_path)
            visible=sum(1 for item in gt.values() if item['visible'])
            pred={item['frame']:item for item in prediction}
            for frame,item in gt.items():
                if not item['visible']: continue
                point=pred.get(frame)
                if point and point.get('visible'):
                    all_errors.append(math.hypot(point['pixel_x']-item['x'],point['pixel_y']-item['y']))
            worst.extend(_worst_observations(video,prediction,gt,source_id))
            clip['visible_gt_frames']=visible
            clip['detected_visible_frames']=metrics.get('detected_visible_frames',0)
            clip['annotated_frames']=metrics.get('annotated_frames',0)
            clip['annotated_negative_frames']=metrics.get('annotated_negative_frames',0)
            clip['false_detections']=metrics.get('false_detections')
        except Exception as exc:
            clip['error']=f'{type(exc).__name__}: {exc}'
    selected_worst=select_worst_cases(worst,20)
    review=_save_worst_frames(selected_worst,suite_root/'worst_cases',config) if selected_worst else []
    tti_commit=__import__('subprocess').check_output(['git','-C',str(Path(__file__).resolve().parents[1]),'rev-parse','HEAD'],text=True).strip()
    source_tree_dirty=bool(__import__('subprocess').check_output(['git','-C',str(Path(__file__).resolve().parents[1]),'status','--porcelain'],text=True).strip())
    result={'suite_id':suite_root.name,'tti_commit':tti_commit,'source_tree_dirty':source_tree_dirty,
            'dataset_provider':manifest['provider'],'dataset_revision':DATA_REVISION,
            'split':manifest['split'],'racketvision_commit':racketvision_commit,'device':device,
            'checkpoint_sha256':sha256(config.model_root/'balltrack_best.pth'),
            'recorded_at':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.perf_counter()-start,
            'status':'BASELINE_ONLY','clips':clips,'aggregate':aggregate(clips,all_errors),'worst_cases':review}
    result['aggregate']['clips_passed']=None
    (suite_root/'benchmark_suite.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (suite_root/'benchmark_suite.html').write_text(_html_report(result),encoding='utf-8')
    return result
