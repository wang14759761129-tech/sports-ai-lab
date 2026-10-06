import json
from pathlib import Path
import subprocess

from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.preview_api import router
from unittest.mock import patch


def fixture_video(tmp_path):
    video=tmp_path/'authorized-qa.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=320x240:rate=25',
                    '-t','1','-c:v','libx264','-pix_fmt','yuv420p','-y',str(video)],check=True)
    return video


def test_preview_lands_on_real_registry_without_creating_demo(tmp_path):
    with TestClient(create_app(tmp_path/'matches.db')) as client:
        players=client.get('/api/players').json()
        assert len(players)==16
        assert {'王楚钦','松岛辉空','张本智和'} <= {p['athlete']['canonical_name_zh'] for p in players}
        assert len(client.get('/api/professional-matches').json())==6
        assert client.get('/api/matches').json()==[]
        assert client.get('/api/preview/jobs').json()==[]


def test_workspace_refresh_uses_one_guarded_connection_and_retains_rankings_and_sources(tmp_path):
    app=create_app(tmp_path/'matches.db')
    repo=app.state.repository
    expected=repo.professional_matches()
    with patch.object(repo,'connect',wraps=repo.connect) as connect:
        snapshot=repo.professional_workspace()
        assert connect.call_count==1
    assert len(snapshot['athletes'])==16 and len(snapshot['matches'])==6
    for record in expected:
        view=next(m for m in snapshot['matches'] if m['match_id']==record['match_id'])
        assert view['source_ids']==record['source_ids']
        assert view.get('final_score')==record.get('final_score')
        assert view['players']['player_a']['athlete_id']==record['player_a_id']
    with TestClient(app) as client:
        assert client.get('/api/preview/workspace').json()['jobs']==[]
        aid=next(a['athlete_id'] for a in snapshot['athletes'] if a['canonical_name_zh']=='王楚钦')
        profile=client.get('/api/preview/athletes/'+aid).json()
        assert len(profile['matches'])==2 and profile['rankings'][0]['source']['source_url']


def test_inspect_attach_existing_match_preserves_provenance_and_checks_rights(tmp_path):
    video=fixture_video(tmp_path)
    app=create_app(tmp_path/'matches.db')
    with TestClient(app) as client:
        original=client.get('/api/professional-matches').json()[0]
        staged=client.post('/api/preview/videos/inspect',files={'file':('own-video.mp4',video.read_bytes(),'video/mp4')})
        assert staged.status_code==200
        asset=staged.json()
        assert asset['media']['fps']==25 and len(asset['sha256'])==64
        body={'asset_id':asset['asset_id'],'match_id':original['match_id'],'source_note':'自有合法 QA 视频'}
        assert client.post('/api/preview/videos/register',json=body).status_code==422
        body['rights_confirmed']=True
        saved=client.post('/api/preview/videos/register',json=body)
        assert saved.status_code==201
        assert saved.json()['source_ids']==original['source_ids']
        assert saved.json()['final_score']==original['final_score']
        refreshed=client.get('/api/professional-matches').json()
        assert len(refreshed)==6
        assert next(m for m in refreshed if m['match_id']==original['match_id'])['video_local_path']
        assert client.post('/api/preview/videos/register',json=body).status_code==409


def test_changed_staged_source_is_refused(tmp_path):
    video=fixture_video(tmp_path)
    app=create_app(tmp_path/'matches.db')
    with TestClient(app) as client:
        staged=client.post('/api/preview/videos/inspect',files={'file':('own.mp4',video.read_bytes(),'video/mp4')}).json()
        descriptor=app.state.data_root/'preview-video-intake'/(staged['asset_id']+'.json')
        path=Path(json.loads(descriptor.read_text(encoding='utf-8'))['path'])
        path.write_bytes(b'changed')
        ids=[p['athlete']['athlete_id'] for p in client.get('/api/players').json()]
        response=client.post('/api/preview/videos/register',json={'asset_id':staged['asset_id'],'rights_confirmed':True,
            'source_note':'QA','metadata':{'event_name':'QA','player_a_id':ids[0],'player_b_id':ids[1]}})
        assert response.status_code==409


def test_output_center_serves_only_real_allowed_outputs_and_job_progress(tmp_path):
    app=create_app(tmp_path/'matches.db')
    with TestClient(app) as client:
        match=client.get('/api/professional-matches').json()[0]
        mid=match['match_id']
        repo=app.state.repository
        folder=app.state.data_root/'full_matches'/'qa-result'
        (folder/'preview_overlays').mkdir(parents=True)
        (folder/'full_match_summary.json').write_text(json.dumps({'balltrack_frames':10,'balltrack_visible_frames':8,'balltrack_coverage':.8}))
        (folder/'full_match_balltrack.jsonl').write_text('{"global_frame":0,"visible":false}\n{"global_frame":1,"visible":true}\n')
        (folder/'preview_overlays'/'preview-01.mp4').write_bytes(b'qa-video')
        (folder/'private.txt').write_text('secret')
        repo.save_full_match_job(mid,{'status':'RUNNING','completed_chunks':1,'total_chunks':3,'output_dir':str(folder)})
        jobs=client.get('/api/preview/jobs').json()
        assert jobs[0]['completed_chunks']==1
        listing=client.get(f'/api/preview/matches/{mid}/outputs').json()
        assert listing['summary']['balltrack_coverage']==.8
        assert {x['name'] for x in listing['assets']}=={'full_match_summary.json','preview-01.mp4','full_match_balltrack.jsonl','full_match_balltrack.json'}
        assert client.get(f'/api/preview/matches/{mid}/outputs/full_match_balltrack.json').json()==[
            {'global_frame':0,'visible':False},{'global_frame':1,'visible':True}]
        asset=next(x for x in listing['assets'] if x['kind']=='overlay')
        assert client.get(asset['url']).content==b'qa-video'
        assert client.get(f'/api/preview/matches/{mid}/outputs/private.txt').status_code==404


def test_preview_routes_are_disabled_in_production_without_opening_production_db(tmp_path):
    dev_app=create_app(tmp_path/'matches.db')
    app=FastAPI()
    app.include_router(router(dev_app.state.repository,tmp_path,'production'))
    with TestClient(app) as client:
        assert client.get('/api/preview/jobs').status_code==404


def test_broken_video_has_chinese_error_and_no_orphan_intake_file(tmp_path):
    app=create_app(tmp_path/'matches.db')
    with TestClient(app) as client:
        response=client.post('/api/preview/videos/inspect',files={'file':('broken.mp4',b'bad','video/mp4')})
        assert response.status_code==422 and '视频无法读取' in response.json()['detail']
        assert list((app.state.data_root/'preview-video-intake').iterdir())==[]
