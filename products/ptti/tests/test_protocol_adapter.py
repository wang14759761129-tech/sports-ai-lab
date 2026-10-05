import csv
import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from core.importing import import_csv
from core.engine import analyze
from core.adapters.protocol_v0_3 import FIELDS
from backend.main import create_app

RESEARCH=Path('../../research-tracks/match-analytics/serve-third-ball-analytics')
PILOT=(RESEARCH/'data/raw/match_001_points.csv').read_bytes()

def encode(rows,fields=None):
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows);return s.getvalue().encode('utf-8')

def source_rows(): return list(csv.DictReader(io.StringIO(PILOT.decode())))

def test_real_pilot_provenance_and_score():
    rows,v,p=import_csv(PILOT)
    assert v['valid'];assert len(rows)==10;assert p['source_schema']=='protocol_v0_3'
    assert p['original_points']==source_rows();assert p['adapter_version']=='0.1.1'
    assert p['source_revision']=='1b30e8ea0f8a90a745fb6c30105599f0334fdf7c'
    assert rows[0]['server']=='B';assert rows[0]['winner']=='B'
    assert (rows[-1]['score_a'],rows[-1]['score_b'])==('5','5')
    assert rows[4]['score_a']=='4';assert rows[4]['score_b']=='1'
    assert all(r['source_'+f]==o[f] for r,o in zip(rows,source_rows()) for f in FIELDS)
    assert 'already underway' in rows[0]['source_notes'];assert rows[0]['source_video_timestamp']=='00:00:00'

def test_real_pilot_evidence():
    rows,v,p=import_csv(PILOT);a=analyze(rows)
    assert a['players']['A']['points_won']['value']==50
    for player in ['A','B']:
        m=a['players'][player]
        assert m['serve_win']['evidence_state']=='AVAILABLE'
        assert m['third_ball_attack']['value'] is None
        assert m['third_ball_win']['value'] is None
        assert m['third_ball_win']['denominator']==0
        assert m['average_rally']['value'] is None
        assert not m['by_serve_type'];assert not m['by_serve_placement']
    q=a['evidence']['source_third_ball_side']
    assert q['eligible_rows']==0;assert q['unresolved_eligibility']==10;assert q['uncertainty_rate'] is None
    assert q['row_label_counts']=={'unknown':1,'unclear':9}
    assert not any(i['metric']=='third_ball_win' for i in a['insights'])

@pytest.mark.parametrize('value',['unknown','unclear','not_applicable'])
def test_uncertainty_preserved(value):
    raw=source_rows()
    for r in raw:
        for f in ['serve_spin','receive_type','third_ball_attack','rally_length']:r[f]=value
    rows,v,p=import_csv(encode(raw));assert v['valid']
    assert all(r['serve_type']==value and r['source_serve_spin']==value for r in rows)
    a=analyze(rows);assert a['players']['A']['third_ball_attack']['value'] is None
    q=a['evidence']['third_ball_attack']
    if value=='not_applicable':assert q['eligible_rows']==0 and q['not_applicable']==10
    else:assert q[value]==10 and q['uncertainty_rate']==1

def test_lossy_and_conflicting_outcomes():
    raw=source_rows();raw[0]['receive_type']='chiquita';raw[0]['serve_length']='half_long';raw[0]['serve_location']='backhand'
    rows,v,p=import_csv(encode(raw));assert v['valid']
    assert rows[0]['receive_type']=='flick';assert rows[0]['source_receive_type']=='chiquita'
    assert not rows[0]['serve_placement'];assert rows[0]['outcome']==''
    assert any(i['field']=='receive_type' for i in p['conversion_warnings'])
    raw[0]['point_outcome']='win';assert not import_csv(encode(raw))[1]['valid']

@pytest.mark.parametrize('field,value',[('server','unknown'),('receiver','opponent'),('point_winner','unclear'),('server_score_before','unknown'),('server_score_before','4'),('game_number','2'),('third_ball_attack','maybe'),('rally_length','0')])
def test_invalid_historical_row(field,value):
    raw=source_rows();raw[0][field]=value
    rows,v,p=import_csv(encode(raw));assert not v['valid'];assert p['original_points'][0][field]==value

def test_missing_tactical_and_mixed_schema():
    raw=source_rows();fields=['match_id','game_number','point_number','server','receiver','server_score_before','receiver_score_before','point_winner']
    reduced=[{k:r[k] for k in fields} for r in raw]
    rows,v,p=import_csv(encode(reduced));assert v['valid'];assert any(i['field']=='rally_length' for i in v['issues'])
    assert analyze(rows)['players']['A']['average_rally']['evidence_state']=='NOT_AVAILABLE'
    for r in raw:r['game']='1'
    assert not import_csv(encode(raw))[1]['valid']
    for r in raw:r.pop('game');r['match_id']='other' if r['point_number']=='1' else 'match_001'
    assert not import_csv(encode(raw))[1]['valid']

def test_minimum_and_uncertainty_denominators():
    raw=source_rows()
    for r in raw:r['third_ball_attack']='yes';r['rally_length']='5'
    rows,v,p=import_csv(encode(raw));assert v['valid'];a=analyze(rows)
    # A serves four times: insufficient, B serves six: descriptive value available.
    assert a['players']['A']['third_ball_win']['denominator']==4
    assert a['players']['A']['third_ball_win']['evidence_state']=='INSUFFICIENT_EVIDENCE'
    assert a['players']['B']['third_ball_win']['evidence_state']=='AVAILABLE'
    raw[0]['third_ball_attack']='not_applicable';raw[1]['third_ball_attack']='unclear'
    rows,v,p=import_csv(encode(raw));m=analyze(rows)['players']['B']['third_ball_attack']
    assert m['denominator']==4;assert m['not_applicable']==1;assert m['unclear']==1;assert m['eligible_rows']==5
    for r in raw:r['rally_length']='unknown'
    raw[0]['rally_length']='5'
    assert analyze(import_csv(encode(raw))[0])['players']['A']['average_rally']['value'] is None

def test_historical_api_restart_export_and_mixed_import(tmp_path):
    db=tmp_path/'data.db';meta='{"name":"历史协议测试","player_a":"王楚钦","player_b":"樊振东"}'
    with TestClient(create_app(db)) as c:
        result=c.post('/api/matches/import',files={'file':('pilot.csv',PILOT)},data={'metadata':meta}).json()
        assert result['validation']['valid'];id=result['match']['id']
        assert result['match']['provenance']['original_points']==source_rows()
        assert c.post('/api/matches/sample').json()['match']['metadata']['synthetic']
        assert len(c.get('/api/matches').json())==2
    with TestClient(create_app(db)) as c:
        export=c.get(f'/api/matches/{id}/export').json()
        assert export['provenance']['original_points']==source_rows()
        assert export['analysis']['players']['A']['third_ball_win']['value'] is None
        assert 'protocol_v0_3' in c.get(f'/api/matches/{id}/report').text
        raw=source_rows();raw[0]['point_winner']='unknown'
        invalid=c.post('/api/matches/import',files={'file':('bad.csv',encode(raw))},data={'metadata':meta}).json()
        assert invalid['validation']['evidence_state']=='INVALID_DATA';assert invalid['match'] is None

def test_delivered_protocol_example_and_true_zero():
    raw=Path('data/samples/protocol-v0.3-example.csv').read_bytes()
    rows,v,p=import_csv(raw);assert v['valid'];assert len(rows)==10
    assert all('SYNTHETIC ONLY' in r['source_notes'] for r in rows)
    assert analyze(rows)['players']['A']['third_ball_attack']['value'] is None
    from core.engine import ingest
    native,_=ingest(Path('data/samples/synthetic.csv').read_bytes())
    # Valid known winning identities allow a genuine zero; uncertainty must not create one.
    for r in native:r['winner']='B'
    a=analyze(native)
    assert a['players']['A']['points_won']['value']==0
    assert a['players']['A']['points_won']['evidence_state']=='AVAILABLE'
