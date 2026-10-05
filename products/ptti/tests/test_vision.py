import json
import math
import subprocess
from pathlib import Path
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from backend.main import create_app
from vision.schema import Source, BallPoint
from vision.adapter import adapt_ball_rows
from vision.benchmark import read_ground_truth, compare
from vision.quality import classify, video_metadata
from vision.runner import cache_key, report_html
from vision.service import VisionService
from vision.config import VisionConfig

@pytest.mark.parametrize('height,fps,level',[(480,120,'LOW'),(720,30,'STANDARD'),(1080,30,'STANDARD'),(1080,60,'VISION'),(1080,120,'HIGH_SPEED')])
def test_quality_conditions_not_accuracy(height,fps,level):
    assert classify(dict(height=height,fps=fps))['level']==level

def test_coordinates_and_timestamps_preserve_missing():
    rows=[dict(Frame=0,Visibility=1,X=50,Y=25),dict(Frame=1,Visibility=0,X=0,Y=0)]
    a,b=adapt_ball_rows(rows,100,50,25)
    assert a['normalized_x']==a['normalized_y']==.5 and a['confidence'] is None
    assert b['timestamp_ms']==40 and b['pixel_x'] is None and b['normalized_y'] is None

@pytest.mark.parametrize('change',[{'normalized_x':2},{'confidence':1.2},{'frame':-1},{'visible':False,'pixel_x':10}])
def test_invalid_observations_rejected(change):
    point=dict(frame=1,timestamp_ms=40,visible=True,pixel_x=10,pixel_y=20,normalized_x=.1,normalized_y=.2)
    with pytest.raises(ValidationError):BallPoint(**{**point,**change})

def test_sparse_gt_unlabelled_frames_are_not_false_detections(tmp_path):
    gt=tmp_path/'gt.csv';gt.write_text('Frame,Visibility,X,Y\n2,1,10,10\n5,0,0,0\n8,1,30,30\n')
    points=adapt_ball_rows([dict(Frame=2,Visibility=1,X=13,Y=14),dict(Frame=3,Visibility=1,X=99,Y=99),dict(Frame=5,Visibility=1,X=10,Y=10)],100,100,25)
    result=compare(points,read_ground_truth(gt),100,100)
    assert result['visible_recall']==.5 and result['missed_frames']==1
    assert result['false_detections']==1 and result['unannotated_prediction_frames']==1
    assert result['mean_position_error_px']==result['p95_position_error_px']==5
    assert result['mean_normalized_position_error']==pytest.approx(.05)

def test_no_gt_evidence_does_not_become_zero():
    result=compare([], {1:dict(visible=False,x=0,y=0)},100,100)
    assert result['visible_recall'] is None and result['mean_position_error_px'] is None

@pytest.mark.parametrize('content',['Frame,Visibility,X,Y\n1,1,0,0\n1,1,2,2','Frame,Visibility,X,Y\n1,2,0,0','bad,header\n1,2'])
def test_gt_invalid_or_duplicate_rejected(tmp_path,content):
    p=tmp_path/'gt.csv';p.write_text(content)
    with pytest.raises(ValueError):read_ground_truth(p)

def test_wtt_rights_and_source_metadata():
    source=Source(type='wtt_licensed',rights='licensed',provider='WTT',source_id='123',licence_reference='local-reference')
    assert source.model_dump()['licence_reference']=='local-reference'
    with pytest.raises(ValidationError):Source(type='wtt_licensed',rights='user_provided')
    with pytest.raises(ValidationError):Source(type='external_reference',rights='research')

def test_cache_changes_on_model_video_or_configuration():
    base=cache_key('video','model',{'device':'cpu'})
    assert base==cache_key('video','model',{'device':'cpu'})
    assert len({base,cache_key('other','model',{'device':'cpu'}),cache_key('video','new',{'device':'cpu'}),cache_key('video','model',{'device':'cuda'})})==4

def test_report_escapes_source_and_no_false_pass():
    result=dict(source={'title':'<script>alert(1)</script>'},metrics={'status':'BASELINE_ONLY'},provenance={})
    report=report_html(result)
    assert '<script>' not in report and '&lt;script&gt;' in report and '尚无通过阈值' in report

def test_asset_whitelist_and_path_boundary(tmp_path):
    cfg=VisionConfig(tmp_path/'data',tmp_path/'models',tmp_path/'cache',tmp_path/'out',tmp_path/'runtime',tmp_path/'python')
    service=VisionService(cfg)
    with pytest.raises(ValueError):service.asset('../secret','analysis.json')
    with pytest.raises(ValueError):service.asset('20261005T123456_aaaaaaaaaaaa','../../secret')

def test_real_ffprobe_synthetic_fixture(tmp_path):
    path=tmp_path/'synthetic.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=size=320x240:rate=25:duration=1','-c:v','libx264','-n',str(path)],check=True)
    metadata=video_metadata(path)
    assert metadata['width']==320 and metadata['height']==240 and metadata['fps']==25 and metadata['frame_count']==25

def test_external_reference_saves_without_downloading(tmp_path,monkeypatch):
    monkeypatch.setenv('PTTI_VISION_HOME',str(tmp_path/'vision'))
    with TestClient(create_app(tmp_path/'matches.db')) as client:
        source=dict(type='external_reference',rights='research',original_url='https://example.org/match',title='参考比赛')
        result=client.post('/api/vision/reference',json=source)
        assert result.status_code==200 and not result.json()['downloaded']
        saved=list((tmp_path/'vision/datasets/racketvision/references').glob('*.json'))
        assert len(saved)==1 and json.loads(saved[0].read_text(encoding='utf-8'))['title']=='参考比赛'
        assert client.get('/api/matches').json()==[]

def test_absent_models_fail_gracefully_without_breaking_matches(tmp_path,monkeypatch):
    monkeypatch.setenv('PTTI_VISION_HOME',str(tmp_path/'vision'))
    with TestClient(create_app(tmp_path/'matches.db')) as client:
        assert client.post('/api/vision/benchmark',json={}).status_code==422
        assert client.post('/api/matches/sample').status_code==200
        assert client.get('/api/vision/analyses').json()==[]

def test_regression_requires_same_evidence():
    from vision.regression import compare_runs
    baseline={'provenance':{'video_sha256':'a'},'metrics':{'visible_recall':1.0,'mean_position_error_px':5,'p95_position_error_px':8}}
    candidate={'provenance':{'video_sha256':'b'},'metrics':baseline['metrics']}
    assert compare_runs(baseline,candidate)['status']=='NOT_COMPARABLE'

def test_regression_flags_real_measured_error_increase():
    from vision.regression import compare_runs
    baseline={'provenance':{},'metrics':{'visible_recall':1.0,'mean_position_error_px':5,'p95_position_error_px':8}}
    candidate={'provenance':{},'metrics':{'visible_recall':1.0,'mean_position_error_px':6,'p95_position_error_px':8}}
    assert compare_runs(baseline,candidate)['status']=='REGRESSION'
    assert compare_runs(baseline,baseline)['status']=='NO_MEASURED_REGRESSION'

def test_regression_rejects_different_pipeline():
    from vision.regression import compare_runs
    base={'provenance':{'pipeline':'0.2.a'},'metrics':{}}
    candidate={'provenance':{'pipeline':'0.2.b'},'metrics':{}}
    assert compare_runs(base,candidate)['status']=='NOT_COMPARABLE'
