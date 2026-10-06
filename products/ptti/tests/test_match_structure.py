import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.match_structure import (MatchStructureEngine, SceneBoundaryDetector,
    calibration_status, normalize_table_point, review_queue, review_rally, table_homography)
from backend.fullmatch import file_sha256


def rows_with_two_gaps(cross_chunk=False):
    rows=[]
    for frame,ms in enumerate(range(0,7001,100)):
        missing=(1200<=ms<=2200) or (3500<=ms<=4500)
        if cross_chunk and 5800<=ms<=6600:missing=True
        rows.append({'global_frame':frame,'timestamp_ms':ms,'visible':not missing,
                     'x':100+frame if not missing else None,'y':80 if not missing else None,
                     'raw_model_score':0.4 if not missing else None,
                     'chunk_index':int(ms//60000) if not cross_chunk else (0 if ms<6000 else 1)})
    return rows


def test_engine_suggests_only_interval_bracketed_by_two_evidence_windows():
    result=MatchStructureEngine(minimum_gap_ms=700,context_window_ms=1200).suggest(
        rows_with_two_gaps(),match_id='m',video_sha256='hash')
    assert len(result['events'])==4
    assert [e['event_type'] for e in result['events']]==[
        'RALLY_END_CANDIDATE','RALLY_START_CANDIDATE',
        'RALLY_END_CANDIDATE','RALLY_START_CANDIDATE']
    assert len(result['rallies'])==1
    rally=result['rallies'][0]
    assert (rally['start_ms'],rally['end_ms'])==(2300,3400)
    assert rally['status']=='SUGGESTED' and rally['confidence'] is None
    assert all(event['status']=='SUGGESTED' for event in result['events'])
    assert result['points']==[] and result['games']==[]


def test_cross_chunk_gap_stays_on_unified_timeline_and_manual_rally_is_only_flagged():
    timeline={'games':[{'points':[{'rallies':[{'rally_id':'manual-1','start_ms':4600,'end_ms':5700}]}]}]}
    result=MatchStructureEngine(minimum_gap_ms=700,context_window_ms=1200).suggest(
        rows_with_two_gaps(True),match_id='m',video_sha256='hash',manual_timeline=timeline)
    crossing=[e for e in result['events'] if e['evidence'][0]['first_missing_frame'] is not None]
    assert any(e['evidence'][2]['chunk_boundary_crossed'] for e in crossing)
    assert len(result['conflicts'])==1
    assert result['rallies'][0]['status']=='SUGGESTED'
    assert timeline['games'][0]['points'][0]['rallies'][0]['rally_id']=='manual-1'


def test_accepted_replay_scene_is_not_spanned_by_a_candidate_rally():
    timeline={'scene_segments':[{'scene_id':'replay','start_ms':2500,'end_ms':3000,
                                 'scene_type':'REPLAY','review_status':'ACCEPTED'}]}
    result=MatchStructureEngine().suggest(rows_with_two_gaps(),match_id='m',video_sha256='hash',
                                           manual_timeline=timeline)
    assert result['rallies']==[]


def test_single_missing_ball_gap_does_not_create_a_rally_segment_or_point_claim():
    rows=rows_with_two_gaps()[:]
    rows=[r for r in rows if r['timestamp_ms']<3500]
    result=MatchStructureEngine().suggest(rows,match_id='m',video_sha256='hash')
    assert result['rallies']==[]
    assert result['points']==[]
    assert result['games']==[]


def test_stationary_visible_candidates_are_not_mislabeled_as_active_motion():
    signal=MatchStructureEngine.activity({'timestamp_ms':10,'visible':True,'x':4,'y':7},
                                          {'timestamp_ms':0,'visible':True,'x':4,'y':7})
    assert signal.state=='LOW_ACTIVITY'
    rows=rows_with_two_gaps()
    for row in rows:
        if row['visible']:
            row['x']=10;row['y']=10
    result=MatchStructureEngine().suggest(rows,match_id='m',video_sha256='hash')
    assert result['events']==[]


def test_review_accept_reject_adjust_split_merge_and_audit_preserve_evidence():
    structure={'events':[],'confirmed_events':[],'conflicts':[],'rallies':[
        {'segment_id':'a','start_ms':1000,'end_ms':3000,'status':'SUGGESTED','evidence':[{'type':'raw'}]},
        {'segment_id':'b','start_ms':3000,'end_ms':5000,'status':'SUGGESTED','evidence':[{'type':'raw'}]},
        {'segment_id':'c','start_ms':7000,'end_ms':9000,'status':'SUGGESTED','evidence':[{'type':'raw'}]},
    ]}
    assert len(review_queue(structure))==3
    accepted=review_rally(structure,'a','accept')
    assert accepted['rallies'][0]['status']=='CONFIRMED'
    assert accepted['rallies'][0]['evidence']==[{'type':'raw'}]
    assert len(accepted['audit_trail'])==1
    rejected=review_rally(structure,'a','reject')
    assert rejected['rallies'][0]['status']=='REJECTED'
    adjusted=review_rally(structure,'a','adjust',start_ms=1200,end_ms=2800)
    assert (adjusted['rallies'][0]['start_ms'],adjusted['rallies'][0]['end_ms'])==(1200,2800)
    split=review_rally(structure,'a','split',split_at_ms=2000)
    assert len([r for r in split['rallies'] if r['status']=='CONFIRMED'])==2
    merged=review_rally(structure,'a','merge',target_segment_id='b')
    assert (merged['rallies'][0]['start_ms'],merged['rallies'][0]['end_ms'])==(1000,5000)
    assert merged['rallies'][1]['status']=='REJECTED'
    assert len(merged['rallies'][0]['evidence'])==2
    assert merged['audit_trail'][0]['related_entity_id']=='b'


def test_table_homography_maps_four_ordered_corners_and_stales_on_hash_or_scene_change():
    homography=table_homography([[10,20],[210,20],[200,120],[20,120]])
    points=[normalize_table_point(homography,*p) for p in [[10,20],[210,20],[200,120],[20,120]]]
    assert [(round(p['x']),round(p['y'])) for p in points]==[(0,0),(1,0),(1,1),(0,1)]
    calibration={'video_sha256':'abc','camera_segment_id':'scene-1'}
    assert calibration_status(calibration,'abc','scene-1')=='VALID'
    assert calibration_status(calibration,'changed','scene-1')=='STALE'
    assert calibration_status(calibration,'abc','scene-2')=='STALE'
    with pytest.raises(ValueError,match='non-zero'):
        table_homography([[1,1],[1,1],[1,1],[1,1]])


def test_scene_change_histogram_is_suggested_and_scoreboard_is_disabled():
    result=SceneBoundaryDetector.compare_histograms([100,0],[0,100])
    assert result['status']=='SUGGESTED' and result['event_type']=='SCENE_CHANGE'
    assert result['confidence'] is None


def _video(path: Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=size=320x240:rate=10:duration=1',
                    '-c:v','libx264','-y',str(path)],check=True)


def test_api_generates_persisted_review_suggestions_without_editing_manual_timeline(tmp_path):
    source=tmp_path/'authorized.mp4';_video(source)
    app=create_app(tmp_path/'db'/'matches.db')
    with TestClient(app) as client:
        repo=app.state.repository
        record={'match_id':'structure-match','event_name':'Engineering QA','player_a_id':'athlete:121558',
                'player_b_id':'athlete:135996','video_source_type':'LOCAL_USER_VIDEO',
                'rights_status':'USER_AUTHORIZED','video_local_path':str(source),
                'video_metadata':{'sha256':file_sha256(source),'width':320,'height':240}}
        repo.save_professional_match(record)
        output=app.state.data_root/'qa-output';output.mkdir()
        observations=rows_with_two_gaps()
        jsonl=output/'full_match_balltrack.jsonl'
        jsonl.write_text(''.join(json.dumps(row)+'\n' for row in observations),encoding='utf-8')
        repo.save_full_match_job(record['match_id'],{'status':'BALLTRACK_COMPLETE','jsonl_path':str(jsonl),
            'output_dir':str(output),'video_sha256':file_sha256(source),'cache_key':'qa-cache'})
        response=client.post('/api/professional-matches/structure-match/match-structure/suggest')
        assert response.status_code==200,response.text
        body=response.json();run_id=body['run_id']
        assert body['status']=='BASELINE_ENGINEERING_QA'
        assert (output/'match_structure.json').is_file() and (output/'match_structure.html').is_file()
        original=client.get('/api/professional-matches/structure-match/timeline').json()
        candidate=body['rallies'][0]
        reviewed=client.post(f"/api/professional-matches/structure-match/match-structure/{run_id}/rallies/{candidate['segment_id']}/review",
                             json={'action':'accept'})
        assert reviewed.status_code==200,reviewed.text
        assert reviewed.json()['rallies'][0]['status']=='CONFIRMED'
        assert client.get('/api/professional-matches/structure-match/timeline').json()==original
        report=(output/'match_structure.html').read_text(encoding='utf-8')
        assert '<h2>Confirmed</h2>' in report and '<h2>Suggested</h2>' in report and '<h2>Unknown</h2>' in report
        assert 'RALLY_START_CANDIDATE' in report
        asset=client.get('/api/professional-matches/structure-match/full-match/asset/match_structure.json')
        assert asset.status_code==200
        queue=client.get(f'/api/professional-matches/structure-match/match-structure/review-queue?run_id={run_id}').json()
        assert queue['items']==[]
        calibration=client.post('/api/professional-matches/structure-match/table-calibrations',json={
            'camera_segment_id':'scene-1','width':320,'height':240,
            'corners':[[10,20],[210,20],[200,120],[20,120]]})
        assert calibration.status_code==201,calibration.text
        listed=client.get('/api/professional-matches/structure-match/table-calibrations?camera_segment_id=scene-2').json()
        assert listed[0]['status']=='STALE'
