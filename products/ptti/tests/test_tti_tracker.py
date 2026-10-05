from vision.tracker import TTIBallTracker, TrackerConfig, SceneContext
from scripts.cross_match_tracker import development
import pytest

def inputs(xs):
    raw=[dict(frame=i,visible=x is not None,pixel_x=x,pixel_y=50 if x is not None else None,confidence=.8 if x is not None else None) for i,x in enumerate(xs)]
    obs=[dict(frame=i,heatmap_shape=[100,100],candidates=[] if x is None else [dict(model_x=x,model_y=50,model_response=.8)]) for i,x in enumerate(xs)]
    return raw,obs

def test_raw_preserved_and_evidence():
    raw,obs=inputs([10,20,30]);snapshot=[dict(p) for p in raw]
    result=TTIBallTracker().track(raw,obs,100,100,30)
    assert raw==snapshot
    assert all(r['raw_prediction']==p for r,p in zip(result,raw))
    assert all('model_response' in r['evidence'] for r in result)
    assert all(r['tti_prediction']['confidence'] is None for r in result)

def test_missing_not_invented():
    raw,obs=inputs([10,None,20]);result=TTIBallTracker().track(raw,obs,100,100,30)
    assert result[1]['decision']=='NO_RELIABLE_CANDIDATE'
    assert not result[1]['tti_prediction']['visible']

def test_interpolation_explicit():
    raw,obs=inputs([10,None,20]);result=TTIBallTracker(TrackerConfig(interpolation_frames=1)).track(raw,obs,100,100,30)
    middle=result[1]['tti_prediction']
    assert middle['source']=='interpolated' and middle['model_observation'] is False
    assert middle['pixel_x']==15

def test_bounce_not_absolute_rejection():
    raw,obs=inputs([10,20,10]);result=TTIBallTracker().track(raw,obs,100,100,30)
    assert all(r['tti_prediction']['visible'] for r in result)

def test_scene_soft_not_mask():
    raw,obs=inputs([10,20]);scene=SceneContext([dict(x0=0,y0=0,x1=1,y1=1,penalty=.01)])
    result=TTIBallTracker(scene=scene).track(raw,obs,100,100,30)
    assert all(r['tti_prediction']['visible'] for r in result)

def test_alignment_fail_closed():
    raw,obs=inputs([10]);obs[0]['frame']=2
    with pytest.raises(ValueError):TTIBallTracker().track(raw,obs,100,100,30)

def test_cross_match_ids_not_development():
    assert not {s.split('/')[1] for s in development()} & {f'match{i}' for i in range(14,20)}

def test_persistence_is_fraction_of_frames():
    raw,obs=inputs([10,10])
    for o in obs:o['candidates'].append(dict(model_x=11,model_y=50,model_response=.7))
    result=TTIBallTracker().track(raw,obs,100,100,30)
    assert all(r['evidence'].get('persistent_response_fraction',0)<=1 for r in result)

def test_invalid_costs_fail_closed():
    with pytest.raises(ValueError):TTIBallTracker(TrackerConfig(motion_weight=-1))
    with pytest.raises(ValueError):TTIBallTracker(TrackerConfig(missing_cost=float('nan')))

def test_holdout_lock_detects_configuration_change(tmp_path,monkeypatch):
    import scripts.cross_match_tracker as experiment
    monkeypatch.setattr(experiment,'HOME',tmp_path)
    paths={'config':tmp_path/'tracker_config.json','manifest':tmp_path/'dataset_manifest.json',
           'tracker':experiment.ROOT/'vision/tracker.py','candidates':experiment.ROOT/'vision_worker/candidates.py',
           'worker':experiment.ROOT/'vision_worker/balltrack.py','evaluator':experiment.ROOT/'scripts/cross_match_tracker.py'}
    experiment.write(paths['config'],{'top_k':16});experiment.write(paths['manifest'],{'split':'locked'})
    experiment.write(tmp_path/'tracker_lock.json',{k:experiment.sha(p) for k,p in paths.items()})
    assert experiment.verify_lock()
    experiment.write(paths['config'],{'top_k':64})
    with pytest.raises(ValueError):experiment.verify_lock()

def test_real_peak_extraction_worker_runtime():
    import subprocess
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    worker=root/'vision_worker/.venv/Scripts/python.exe'
    if not worker.exists():pytest.skip('Optional isolated vision runtime unavailable')
    script='''import numpy as np
from vision_worker.candidates import extract_peaks
h=np.zeros((20,30));h[5,5]=.65;h[5,6]=.4;h[15,20]=.037
p=extract_peaks(h,16,.01,2)
assert len(p)==2 and abs(p[1]['model_response']-.037)<1e-7
assert not any(c['model_x']==6 and c['model_y']==5 for c in p)
try:extract_peaks(np.array([[float('nan')]]),4,.01,2)
except ValueError:pass
else:raise AssertionError('Nonfinite evidence accepted')
'''
    subprocess.run([str(worker),'-c',script],cwd=root,check=True)
