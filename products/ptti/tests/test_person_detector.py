import hashlib
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.person_detector import (R18_MODEL,R18_REVISION,R18_FILES,FROZEN_MANIFEST_SHA,
    RTDetrPredictionAdapter,RTDetrPersonDetector,GroundingDinoPersonDetector,verify_r18,
    evaluate_people,deduplicate_people,TablePersonRoleResolver,person_frame_review,select_person_detector)
from backend.person_scene import scene_snapshot,record_review,scene_asset


def test_rtdetr_person_filter_and_source_pixel_clipping():
    rows=RTDetrPredictionAdapter().adapt([
        {'label':'person','score':.8,'bbox':[-3,4,250,120]},
        {'label':'sports ball','score':.9,'bbox':[1,2,5,6]},
        {'label':'person','score':.1,'bbox':[1,2,5,6]}],
        image_size=(200,100),frame=10,timestamp_ms=1000,threshold=.4)
    assert len(rows)==1 and rows[0]['bbox']==[0,4,200,100]
    assert rows[0]['model_version']==R18_REVISION and rows[0]['status']=='SUGGESTED'


def test_generic_contract_accepts_both_detectors_without_framework_imports():
    class Frame:size=(200,100)
    infer=lambda image:[{'label':'person','score':.8,'bbox':[10,10,40,70]}]
    assert len(RTDetrPersonDetector(infer).detect(Frame(),frame=1,timestamp_ms=0))==1
    assert len(GroundingDinoPersonDetector(infer).detect(Frame(),frame=1,timestamp_ms=0))==1


def test_model_artifact_tamper_is_rejected(tmp_path,monkeypatch):
    import backend.person_detector as module
    contents={'config.json':json.dumps({'model_type':'rt_detr','id2label':{'0':'person'},'architectures':['RTDetrForObjectDetection']}),
              'preprocessor_config.json':'{}','model.safetensors':'test fixture'}
    for name,value in contents.items():(tmp_path/name).write_text(value)
    monkeypatch.setattr(module,'R18_FILES',{name:hashlib.sha256((tmp_path/name).read_bytes()).hexdigest() for name in contents})
    assert verify_r18(tmp_path)['revision']==R18_REVISION
    (tmp_path/'model.safetensors').write_text('changed')
    with pytest.raises(ValueError,match='SHA_MISMATCH'):verify_r18(tmp_path)


def test_one_large_prediction_cannot_match_two_players():
    gt={'players':[{'bbox':[0,0,10,10]},{'bbox':[10,0,20,10]}]}
    result=evaluate_people([{'bbox':[0,0,20,10]}],gt)
    assert result['matched_players']==1 and not result['both_matched']


def test_absent_players_are_not_counted_as_missed_and_referees_are_distinct():
    result=evaluate_people([{'bbox':[0,0,10,10]}],{'players':[],'referees':[[0,0,10,10]]})
    assert result['gt_players']==0 and not result['both_visible']
    assert result['referee_detections']==1


def test_duplicate_projection_does_not_mutate_raw():
    raw=[{'bbox':[0,0,10,10],'detector_score':.9},{'bbox':[0,0,10,10],'detector_score':.8}]
    assert len(deduplicate_people(raw))==1 and len(raw)==2


def test_table_resolver_keeps_central_referee_as_other_not_player():
    rows=TablePersonRoleResolver().resolve([100,100,300,220],[
        {'bbox':[5,10,75,150],'detector_score':.9},
        {'bbox':[330,80,390,270],'detector_score':.9},
        {'bbox':[180,10,220,80],'detector_score':.8}],image_size=(400,300))
    assert [r['role_candidate'] for r in rows]==['FAR_PLAYER','NEAR_PLAYER','OTHER']
    assert all(r['role']=='UNKNOWN' for r in rows)


def test_crowd_competition_and_front_on_center_remain_unknown():
    rows=TablePersonRoleResolver().resolve([100,100,300,220],[
        {'bbox':[5,10,75,150],'detector_score':.9},
        {'bbox':[5,12,80,151],'detector_score':.88},
        {'bbox':[330,80,390,270],'detector_score':.9}],image_size=(400,300))
    assert all(r['role_candidate']=='UNKNOWN' for r in rows)
    assert person_frame_review(rows)['priority']=='HIGH'


def test_dependency_failure_falls_back_truthfully():
    assert select_person_detector(None)=='GROUNDING_DINO_PLAYER_BASELINE'
    assert select_person_detector({'status':'FAILED'})=='GROUNDING_DINO_PLAYER_BASELINE'
    assert select_person_detector({'status':'REAL_DEV_EVALUATED','model':R18_MODEL})==R18_MODEL


def seed_scene(root):
    root.mkdir(parents=True)
    config={'model':R18_MODEL,'revision':R18_REVISION,'artifact_sha256':R18_FILES}
    config_path=root/'person_detector_config.json';config_path.write_text(json.dumps(config))
    report={'model':R18_MODEL,'config_sha256':hashlib.sha256(config_path.read_bytes()).hexdigest(),
        'manifest_sha256':FROZEN_MANIFEST_SHA,'runtime':{},'provenance':{},
        'frames':[{'game':'game_1','slot':1,'width':400,'height':300,'frame_sha256':'frame hash',
                  'table_bbox':[100,100,300,220],'timestamp_ms':0,'frame':0,
                  'detections':[{'candidate_id':'p1','bbox':[5,10,75,150],'label':'person',
                                 'detector_score':.9,'role_candidate':'UNKNOWN','role':'UNKNOWN'}]}]}
    (root/'person_detector_evaluation.json').write_text(json.dumps(report))
    return report


def test_frame_accept_and_later_edit_invalidates_verification_without_mutating_raw(tmp_path):
    root=tmp_path/'scene';raw=seed_scene(root)
    record_review(root,frame_id='dev-game_1-s1',action='ACCEPT_FRAME')
    assert scene_snapshot(root)['frames'][0]['review']['status']=='USER_VERIFIED'
    record_review(root,frame_id='dev-game_1-s1',candidate_id='p1',action='SET_ROLE',role='FAR_PLAYER')
    frame=scene_snapshot(root)['frames'][0]
    assert frame['review']['status']!='USER_VERIFIED'
    assert frame['detections'][0]['effective_role']=='FAR_PLAYER'
    assert json.loads((root/'person_detector_evaluation.json').read_text())==raw
    assert len(json.loads((root/'person_detector_reviews.json').read_text()))==2


def test_stale_reviews_are_not_applied_to_new_config_or_source(tmp_path):
    root=tmp_path/'scene';seed_scene(root)
    record_review(root,frame_id='dev-game_1-s1',action='ACCEPT_FRAME')
    report=json.loads((root/'person_detector_evaluation.json').read_text());report['frames'][0]['frame_sha256']='new hash'
    (root/'person_detector_evaluation.json').write_text(json.dumps(report))
    assert scene_snapshot(root)['frames'][0]['review']['status']!='USER_VERIFIED'


def test_result_config_mismatch_fails_closed(tmp_path):
    root=tmp_path/'scene';seed_scene(root)
    (root/'person_detector_config.json').write_text('{}')
    with pytest.raises(ValueError,match='IDENTITY_MISMATCH'):scene_snapshot(root)


def test_review_and_asset_requests_reject_unknown_inputs(tmp_path):
    root=tmp_path/'scene';seed_scene(root)
    with pytest.raises(KeyError):record_review(root,frame_id='missing',action='ACCEPT_FRAME')
    with pytest.raises(ValueError):record_review(root,frame_id='dev-game_1-s1',action='SET_ROLE',role='CHAMPION')
    with pytest.raises(ValueError):scene_asset(root,'../matches.db')
    assert scene_asset(root,'val-match20-s01.jpg')==root/'person-validation/match20-s01.jpg'


def test_desktop_person_scene_api_and_review_persistence(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path))
    root=tmp_path/'PTTI-Dev/vision-v2/scene-bootstrap';seed_scene(root)
    app=create_app(tmp_path/'qa/matches.db')
    with TestClient(app) as client:
        response=client.get('/api/vision/v2/person-detection')
        assert response.status_code==200 and response.json()['person_gate']=='PERSON_DETECTOR_PARTIAL'
        assert client.post('/api/vision/v2/person-detection/reviews',json={'frame_id':'dev-game_1-s1','action':'ACCEPT_FRAME'}).status_code==200
        assert client.get('/api/vision/v2/person-detection').json()['user_verified']==1
        assert client.post('/api/vision/v2/person-detection/reviews',json={'frame_id':'dev-game_1-s1','action':'SET_ROLE','candidate_id':'p1','role':'INVALID'}).status_code==422
        assert client.get('/api/vision/v2/person-detection/assets/dev-game_1-s01.jpg').status_code==404


def test_missing_artifacts_do_not_claim_inference(tmp_path):
    assert scene_snapshot(tmp_path)['status']=='NOT_RUN'


def test_qa_review_is_separate_from_research_reviews(tmp_path):
    root=tmp_path/'scene';seed_scene(root)
    qa=tmp_path/'isolated-qa/reviews.json'
    record_review(root,frame_id='dev-game_1-s1',action='ACCEPT_FRAME',reviews_path=qa,source='QA_UI')
    assert scene_snapshot(root,reviews_path=qa)['user_verified']==1
    assert scene_snapshot(root)['user_verified']==0
    assert not (root/'person_detector_reviews.json').exists()
    assert json.loads(qa.read_text())[0]['source']=='QA_UI'
