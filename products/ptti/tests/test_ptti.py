from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from core.engine import ingest, analyze, rate
from backend.main import create_app

RAW=Path('data/samples/synthetic.csv').read_bytes()
def test_sample():
    rows,report=ingest(RAW);assert report['valid'];assert not report['issues']
    a=analyze(rows);assert a['point_count']==len(rows)
    for p in ['A','B']:
        m=a['players'][p]
        assert m['points_won']['numerator']==sum(r['winner']==p for r in rows)
        assert m['serve_win']['denominator']==sum(r['server']==p for r in rows)
        assert m['receive_win']['denominator']==sum(r['server']!=p for r in rows)
        attacks=[r for r in rows if r['server']==p and r['third_ball_attack']=='yes']
        assert m['third_ball_attack']['numerator']==len(attacks)
        assert m['third_ball_attack']['denominator']==sum(r['server']==p and r.get('third_ball_attack') in {'yes','no'} for r in rows)
        assert m['third_ball_win']['numerator']==sum(r['winner']==p for r in attacks)
        assert sum(b['value'] for b in m['rally_bands'].values())==pytest.approx(100,abs=.02)
        assert m['average_rally']['value']==round(sum(int(r['rally_length']) for r in rows)/len(rows),2)
        for key,field in [('by_server','server'),('by_phase','point_phase')]:
            assert sum(v['denominator'] for v in m[key].values())==len(rows)
        for key in ['by_serve_placement','by_serve_type']:
            assert sum(v['denominator'] for v in m[key].values())==m['serve_win']['denominator']
        assert sum(v['denominator'] for v in m['by_receive_type'].values())==m['receive_win']['denominator']
        assert sum(m['outcomes'].values())==m['points_won']['numerator']
        for receiver in ['A','B']:
            received=[r for r in rows if r['server']!=receiver]
            assert m['by_receiver'][receiver]['numerator']==sum(r['winner']==p for r in received)
            assert m['by_receiver'][receiver]['denominator']==len(received)
    assert sum(r['length'] for r in a['runs'])==len(rows)
    assert len(a['progression'])==len(rows)
    assert [(s['a'],s['b']) for s in a['progression']]==[(int(r['score_a']),int(r['score_b'])) for r in rows]
    assert all(i['evidence'] for i in a['insights'])

@pytest.mark.parametrize('raw',[b'',b'x\n1',b'game,point,server,winner,score_a,score_b\n1,1,X,A,1,0',b'game,point,server,winner,score_a,score_b\n1,2,A,A,1,0',b'game,point,server,winner,score_a,score_b\n1,1,A,A,0,0',b'game,point,server,winner,score_a,score_b\n1,1,A,A,-1,0',b'game,point,server,winner,score_a,score_b\n1,1,A,,1,0',b'\xff',b'game,point,server,winner,score_a,score_b\n1,1,A,A,1'])
def test_invalid(raw): assert not ingest(raw)[1]['valid']

def test_missing_and_small():
    rows,v=ingest(b'game,point,server,winner,score_a,score_b\n1,1,A,A,1,0')
    assert v['valid'];assert v['issues'];m=analyze(rows)['players']
    assert m['A']['serve_win']['value']==100
    assert m['A']['receive_win']['value'] is None
    assert m['A']['third_ball_attack']['value'] is None
    assert m['A']['average_rally']['value'] is None
    assert m['A']['rally_bands']['short']['value'] is None
    assert rate([],lambda r:True)['value'] is None
    assert analyze([])['point_count']==0

def test_service_and_game_order():
    rows,v=ingest(RAW);rows[1]['server']='B' if rows[1]['server']=='A' else 'A'
    import csv,io
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    assert any(i['field']=='server' for i in ingest(s.getvalue().encode())[1]['issues'])

def csv_points(winners):
    lines=['game,point,server,winner,score_a,score_b'];a=b=0
    for p,w in enumerate(winners,1):
        t=a+b; flip=(t//2)%2 if t<20 else (t-20)%2
        server='B' if flip else 'A';a+=w=='A';b+=w=='B'
        lines.append(f'1,{p},{server},{w},{a},{b}')
    return '\n'.join(lines).encode()

def test_deuce_and_completed_game():
    rows,v=ingest(csv_points('AB'*10+'AA'));assert v['valid']
    assert rows[-1]['score_a']=='12';assert rows[-1]['server']=='B'
    assert not ingest(csv_points('AB'*10+'AAA'))[1]['valid']

def test_wrong_game_and_duplicate_header():
    assert not ingest(b'game,point,server,winner,score_a,score_b\n2,1,A,A,1,0')[1]['valid']
    assert not ingest(b'game,point,server,winner,score_a,score_b\n1,1,A,A,1,0\n2,1,B,B,0,1')[1]['valid']
    assert not ingest(b'game,point,server,winner,score_a,score_b,game\n1,1,A,A,1,0,1')[1]['valid']

def test_utf8_bom_and_unknown_optional():
    assert ingest(b'\xef\xbb\xbf'+RAW)[1]['valid']
    assert not ingest(RAW.replace(b'backspin',b'unknown'))[1]['valid']

def test_api_persistence(tmp_path):
    db=tmp_path/'matches.db'
    with TestClient(create_app(db)) as c:
        assert c.get('/api/health').status_code==200
        r=c.post('/api/matches/sample').json();assert r['validation']['valid'];id=r['match']['id']
        assert len(c.get('/api/matches').json())==1
        assert c.get(f'/api/matches/{id}/analysis').json()['point_count']>0
        assert c.get(f'/api/matches/{id}/points').json()
        assert c.get(f'/api/matches/{id}/export').json()['metadata']['synthetic']
        assert 'SYNTHETIC DEMONSTRATION' in c.get(f'/api/matches/{id}/report').text
        bad=c.post('/api/matches/import',files={'file':('bad.csv',b'bad')},data={'metadata':'{"name":"测试","player_a":"王","player_b":"凯"}'}).json()
        assert bad['match'] is None
        valid=c.post('/api/matches/import',files={'file':('match.csv',RAW)},data={'metadata':'{"name":"训练比赛","player_a":"王","player_b":"凯凯","event":"队内赛"}'}).json()
        assert valid['match']['metadata']['player_b']=='凯凯'
        assert valid['match']['points']==ingest(RAW)[0]
        assert c.post('/api/matches/import',files={'file':('ok.csv',RAW)},data={'metadata':'{}'}).status_code==422
    with TestClient(create_app(db)) as c:
        assert c.get(f'/api/matches/{id}').json()['id']==id
        assert c.delete(f'/api/matches/{id}').status_code==200
        assert c.get(f'/api/matches/{id}').status_code==404
        assert c.delete(f'/api/matches/{id}').status_code==404
