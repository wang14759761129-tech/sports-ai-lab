"""Database-free, immutable-run tracker experiment. No production imports."""
import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from vision.config import VisionConfig, DATA_REVISION
from vision.tracker import TTIBallTracker, TrackerConfig
from vision.adapter import adapt_ball_rows
from vision.benchmark import read_ground_truth, compare, percentile
from scripts.download_vision_sample import download

ROOT=Path(__file__).resolve().parents[1]
HOME=ROOT/'outputs/vision/tracker_v2'
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2),encoding='utf-8')
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def development():
    return [f'tabletennis/{m}/{r}' for r in ['000','001'] for m in ['match1','match10','match11','match12','match13']]
def metadata(video):
    a=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-of','json',str(video)]))['streams'][0]
    n,d=map(int,a['avg_frame_rate'].split('/'))
    return dict(width=a['width'],height=a['height'],fps=n/d,codec=a['codec_name'],camera_angle='unknown',lighting='unknown',visible_referee='unknown',background_complexity='unknown')
def prepare():
    cfg=VisionConfig.load()
    # Select first two validation rallies from five ordered matches, BEFORE reading GT or predictions.
    sources=[f'tabletennis/match{m}/{r}' for m in range(14,19) for r in ['000','001']]
    sources.remove('tabletennis/match18/001') # Official val contains one rally for match18.
    sources.append('tabletennis/match19/000')
    download('linfeng302/RacketVision','datasets',DATA_REVISION,'tabletennis/info/val.json',cfg.dataset_root/'tabletennis/info/val.json')
    official=json.loads((cfg.dataset_root/'tabletennis/info/val.json').read_text())
    if not set(sources)<=set('tabletennis/'+m+'/'+r for m,r in official): raise ValueError('Selection outside official val')
    manifest=dict(dataset_revision=DATA_REVISION,development=development(),internal_holdout=[s[:-3]+'002' for s in development()[:5]],
                  cross_match_holdout=sources,selection='first available val rallies in ordered matches14..19; no GT/prediction selection',
                  upstream_exposure='Official val is used for best-checkpoint selection; matches overlap upstream train. This is TTI-only holdout, NOT model-unseen evidence.')
    path=HOME/'dataset_manifest.json'
    if path.exists() and json.loads(path.read_text())!=manifest: raise ValueError('Manifest already frozen')
    write(path,manifest)
    for s in sources:
        _,m,r=s.split('/')
        for relative in [f'tabletennis/videos/{m}_{r}.mp4',f'tabletennis/all/{m}/csv/{r}_ball.csv']:
            download('linfeng302/RacketVision','datasets',DATA_REVISION,relative,cfg.dataset_root/relative)

def infer(split):
    cfg=VisionConfig.load();manifest=json.loads((HOME/'dataset_manifest.json').read_text())
    if split=='cross_match_holdout': verify_lock()
    for s in manifest[split]:
        _,m,r=s.split('/');out=HOME/'observations'/m/r
        if (out/'peak_candidates.json').exists():
            hashes=json.loads((out/'input_hashes.json').read_text())
            if hashes.get('candidate_code_sha256')!=sha(ROOT/'vision_worker/candidates.py') or hashes.get('capture_top_k')!=128: raise ValueError('Existing capture uses a different extractor; retain in separate directory')
            print('Already captured',s,flush=True);continue
        video=cfg.dataset_root/f'tabletennis/videos/{m}_{r}.mp4'
        print('GPU',s,flush=True)
        subprocess.run([str(cfg.worker_python),str(ROOT/'vision_worker/balltrack.py'),'--runtime',str(cfg.runtime_root),'--checkpoint',str(cfg.model_root/'balltrack_best.pth'),
                        '--video',str(video),'--output',str(out),'--top-k','128','--minimum-response','.005','--nms-radius','5'],check=True)
        write(out/'meta.json',metadata(video))
        write(out/'input_hashes.json',dict(video_sha256=sha(video),checkpoint_sha256=sha(cfg.model_root/'balltrack_best.pth'),dataset_revision=DATA_REVISION,candidate_code_sha256=sha(ROOT/'vision_worker/candidates.py'),worker_code_sha256=sha(ROOT/'vision_worker/balltrack.py'),capture_top_k=128))

def verify_lock():
    lock=json.loads((HOME/'tracker_lock.json').read_text())
    for key,path in [('config',HOME/'tracker_config.json'),('manifest',HOME/'dataset_manifest.json'),('tracker',ROOT/'vision/tracker.py'),('candidates',ROOT/'vision_worker/candidates.py'),('worker',ROOT/'vision_worker/balltrack.py'),('evaluator',Path(__file__))]:
        if lock[key]!=sha(path): raise ValueError('Frozen '+key+' changed')
    return lock
def evaluate(split,settings):
    cfg=VisionConfig.load();manifest=json.loads((HOME/'dataset_manifest.json').read_text());clips=[]
    for s in manifest[split]:
        _,m,r=s.split('/');out=HOME/'observations'/m/r
        meta=json.loads((out/'meta.json').read_text());w,h,fps=meta['width'],meta['height'],meta['fps']
        raw=adapt_ball_rows(json.loads((out/'raw_prediction.json').read_text()),w,h,fps)
        if split=='development':
            baseline=json.loads((cfg.output_root/'benchmark_suite_20261005T113747/benchmark_suite.json').read_text())
            original=next(c for c in baseline['clips'] if c['source_id']==s)
            saved=json.loads((cfg.output_root/original['analysis_id']/'ball_track.json').read_text())
            if isinstance(saved,dict):saved=saved.get('points',saved.get('ball_track',saved))
            if raw!=saved: raise ValueError('Fresh RAW differs from preserved baseline: '+s)
        observations=json.loads((out/'peak_candidates.json').read_text())
        for obs in observations:
            obs['candidates']=[c for c in obs['candidates'] if c['model_response']>=settings.minimum_response][:settings.top_k]
        start=time.perf_counter();rows=TTIBallTracker(settings).track(raw,observations,w,h,fps);seconds=time.perf_counter()-start
        tti=[dict(r['tti_prediction'],visible=r['tti_prediction']['visible'] and r['tti_prediction']['model_observation']) for r in rows]
        gtpath=cfg.dataset_root/f'tabletennis/all/{m}/csv/{r}_ball.csv';gt=read_ground_truth(gtpath)
        c=dict(source_id=s,metadata=meta,raw=compare(raw,gt,w,h),tti=compare(tti,gt,w,h),tracker_seconds=seconds,
               runtime=json.loads((out/'runtime.json').read_text()),gt_sha256=sha(gtpath),inputs=json.loads((out/'input_hashes.json').read_text()),
               raw_coverage=sum(p['visible'] for p in raw)/len(raw),usable_coverage=sum(r['tti_prediction']['visible'] for r in rows)/len(rows),frames=len(rows))
        for name,points in [('raw',raw),('tti',tti)]:
            errors=[]
            for p in points:
                g=gt.get(p['frame'])
                if g and g['visible'] and p['visible']:
                    err=math.hypot(p['pixel_x']-g['x'],p['pixel_y']-g['y']);errors.append(dict(frame=p['frame'],px=err,normalized=err/math.hypot(w,h)))
            c[name+'_errors']=errors
        c['failures']=[]
        for label,points in [('raw',raw),('tti',tti)]:
            for point in points:
                g=gt.get(point['frame'])
                if g is None:continue
                kind=None;error=None
                if g['visible'] and not point['visible']:kind='MISS'
                elif not g['visible'] and point['visible']:kind='FALSE_POSITIVE'
                elif g['visible'] and point['visible']:
                    error=math.hypot(point['pixel_x']-g['x'],point['pixel_y']-g['y'])
                    if error/math.hypot(w,h)>20/math.hypot(1920,1080):kind='LOCALIZATION_OUTLIER'
                if kind:c['failures'].append(dict(pipeline=label,frame=point['frame'],kind=kind,error_px=error,gt=g,classification='UNKNOWN'))
        c['evidence']=rows
        clips.append(c)
    def aggregate(cs,name):
        errors=[e for c in cs for e in c[name+'_errors']];px=[e['px'] for e in errors]
        visible=sum(c[name]['visible_gt_frames'] for c in cs);detected=sum(c[name]['detected_visible_frames'] for c in cs)
        return dict(visible=visible,detected=detected,recall=detected/visible if visible else None,negative=sum(c[name]['annotated_negative_frames'] for c in cs),
                    false_positives=sum(c[name]['false_detections'] or 0 for c in cs),mean=statistics.mean(px) if px else None,median=statistics.median(px) if px else None,p95=percentile(px,.95),
                    catastrophic={str(t):sum(e['normalized']>t/math.hypot(1920,1080) for e in errors) for t in [20,50,100]},
                    coverage=sum(c['raw_coverage' if name=='raw' else 'usable_coverage']*c['frames'] for c in cs)/sum(c['frames'] for c in cs))
    return dict(split=split,config=asdict(settings),raw=aggregate(clips,'raw'),tti=aggregate(clips,'tti'),
                by_match={m:{n:aggregate([c for c in clips if c['source_id'].split('/')[1]==m],n) for n in ['raw','tti']} for m in sorted(set(c['source_id'].split('/')[1] for c in clips))},clips=clips)

def save_report(report,name):
    report['git_commit']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    report['source_tree_dirty']=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip())
    # Do not overwrite first evaluation.
    path=HOME/(name+'.json')
    if path.exists(): raise ValueError('First evaluation must remain immutable')
    write(path,report)
    import html
    (HOME/(name+'.html')).write_text('<!doctype html><meta charset="utf-8"><title>TTI RAW vs Tracker</title><h1>'+html.escape(name)+'</h1><p>BASELINE_ONLY. Sparse GT; interpolation excluded from detection. Upstream model exposure: validation/training matches.</p><pre>'+html.escape(json.dumps({k:v for k,v in report.items() if k!='clips'},indent=2))+'</pre>',encoding='utf-8')
    for c in report['clips']:
        for e in c['failures']:
            write(HOME/'worst_cases'/name/(c['source_id'].replace('/','_')+'_'+str(e['frame'])+'_'+e['pipeline']+'.json'),dict(error=e,evidence=c['evidence'][e['frame']],classification='UNKNOWN'))

def tune():
    trials=[]
    # Deliberately small, declared development-only grid. No holdout metrics read.
    for k in [16,64,128]:
        for weight in [.1,.2]:
            settings=TrackerConfig(top_k=k,response_weight=weight,motion_weight=1.)
            report=evaluate('development',settings)
            trials.append((report,settings));print(asdict(settings),report['tti'],flush=True)
    # Development objective counts misses and false positives as well as catastrophes.
    def objective(pair):
        m=pair[0]['tti'];return (m['visible']-m['detected'])*2+m['false_positives']*2+m['catastrophic']['50']*4+m['catastrophic']['20']
    report,settings=min(trials,key=objective)
    write(HOME/'development_trials.json',[dict(config=asdict(s),raw=r['raw'],tti=r['tti'],objective=objective((r,s))) for r,s in trials])
    save_report(report,'development_benchmark')
    write(HOME/'tracker_config.json',asdict(settings))
    paths=dict(config=HOME/'tracker_config.json',manifest=HOME/'dataset_manifest.json',tracker=ROOT/'vision/tracker.py',candidates=ROOT/'vision_worker/candidates.py',worker=ROOT/'vision_worker/balltrack.py',evaluator=Path(__file__))
    write(HOME/'tracker_lock.json',{k:sha(p) for k,p in paths.items()})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','development','tune','cross_match_holdout','evaluate']);args=p.parse_args()
    if args.stage=='prepare':prepare()
    elif args.stage in ['development','cross_match_holdout']:infer(args.stage)
    elif args.stage=='tune':tune()
    else:
        lock=verify_lock();r=evaluate('cross_match_holdout',TrackerConfig(**json.loads((HOME/'tracker_config.json').read_text())))
        r['lock']=lock;save_report(r,'cross_match_benchmark')
