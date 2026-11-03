import json
import sqlite3
import struct
import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.repository import Repository
NATIVE=Path('data/samples/synthetic.csv').read_bytes()
PROTOCOL=Path('data/samples/protocol-v0.3-example.csv').read_bytes()
META={'name':'中文比赛','player_a':'王','player_b':'凯','notes':'本地备注','synthetic':True}
def upload(c,raw,preview=False):return c.post('/api/matches/import',files={'file':('match.csv',raw)},data={'metadata':json.dumps(META),'preview':str(preview).lower()})
@pytest.mark.parametrize('theme',['system','light','dark'])
def test_settings_persist_restart(tmp_path,theme):
    db=tmp_path/'old.db'
    with TestClient(create_app(db)) as c:
        initial=c.get('/api/settings').json();assert initial=={'language':'zh-CN','theme':'system','start_page':'home','onboarding_complete':False}
        saved={**initial,'theme':theme,'start_page':'recent','onboarding_complete':True}
        assert c.put('/api/settings',json=saved).json()==saved
    with TestClient(create_app(db)) as c:assert c.get('/api/settings').json()==saved
@pytest.mark.parametrize('change',[{'language':'en'},{'theme':'neon'},{'start_page':'cloud'}])
def test_invalid_settings_do_not_replace(tmp_path,change):
    with TestClient(create_app(tmp_path/'db')) as c:
        before=c.get('/api/settings').json()
        assert c.put('/api/settings',json={**before,**change}).status_code==422
        assert c.get('/api/settings').json()==before
@pytest.mark.parametrize('raw',[NATIVE,PROTOCOL])
def test_preview_does_not_save_then_explicit_save(tmp_path,raw):
    with TestClient(create_app(tmp_path/'db')) as c:
        draft=upload(c,raw,True).json();assert draft['validation']['valid'] and draft['match']['id']==''
        assert c.get('/api/matches').json()==[]
        saved=upload(c,raw).json()['match'];assert saved['id'] and saved['metadata']['notes']=='本地备注'
        assert draft['match']['points']==saved['points'];assert draft['match']['analysis']==saved['analysis']
        assert len(c.get('/api/matches').json())==1
        assert c.get('/api/matches').json()[0]['source_schema']==saved['provenance']['source_schema']
def test_invalid_preview_and_save_never_persist(tmp_path):
    with TestClient(create_app(tmp_path/'db')) as c:
        for preview in [True,False]:
            result=upload(c,b'game,point\n2,1',preview).json()
            assert result['match'] is None and result['validation']['evidence_state']=='INVALID_DATA'
        assert c.get('/api/matches').json()==[]
def test_delete_only_selected_match_and_restart(tmp_path):
    db=tmp_path/'db'
    with TestClient(create_app(db)) as c:
        first=c.post('/api/matches/sample').json()['match'];second=c.post('/api/matches/sample').json()['match']
        assert c.delete('/api/matches/'+first['id']).json()=={'deleted':True}
        assert c.delete('/api/matches/'+first['id']).status_code==404
        assert c.get('/api/matches/'+second['id']).status_code==200
    with TestClient(create_app(db)) as c:assert [m['id'] for m in c.get('/api/matches').json()]==[second['id']]
def test_additive_settings_preserve_exact_legacy_payload(tmp_path):
    db=tmp_path/'matches.db';old={'id':'old-match','metadata':{'name':'旧版比赛'},'analysis':{'analytics_version':'0.1.0'},'points':[{'unknown':'raw'}]}
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE matches (id TEXT PRIMARY KEY,payload TEXT NOT NULL)');conn.execute('INSERT INTO matches VALUES (?,?)',('old-match',json.dumps(old)))
    repo=Repository(db);assert repo.get('old-match')==old
    repo.save_settings({'theme':'dark'});assert Repository(db).get('old-match')==old
@pytest.mark.parametrize('format,raw',[('native',NATIVE),('protocol',PROTOCOL)])
def test_download_templates_exact_and_whitelisted(tmp_path,format,raw):
    with TestClient(create_app(tmp_path/'db')) as c:
        result=c.get('/api/templates/'+format);assert result.status_code==200 and result.content==raw
        assert 'attachment' in result.headers['content-disposition']
        assert c.get('/api/templates/secrets').status_code==422
        assert c.get('/api/matches').json()==[]
def test_chinese_report_preserves_user_content_and_uncertainty(tmp_path):
    with TestClient(create_app(tmp_path/'db')) as c:
        meta={**META,'name':'Value <script>alert(1)</script>','player_a':'Metric Evidence'}
        saved=c.post('/api/matches/import',files={'file':('p.csv',PROTOCOL)},data={'metadata':json.dumps(meta)}).json()['match']
        report=c.get('/api/matches/'+saved['id']+'/report').text
        assert 'Value &lt;script&gt;' in report and 'Metric Evidence' in report
        assert '<script>alert' not in report
        assert '证据不足' in report and 'SYNTHETIC DEMONSTRATION' in report
        assert saved['analysis']['players']['A']['third_ball_win']['value'] is None
        assert c.get('/api/matches/'+saved['id']+'/export').json()['provenance']['original_points']==saved['provenance']['original_points']
def test_original_icon_has_multiple_valid_sizes():
    raw=Path('assets/ptti.ico').read_bytes();reserved,kind,count=struct.unpack_from('<HHH',raw)
    assert reserved==0 and kind==1 and count==6
    for i in range(count):
        *_,length,offset=struct.unpack_from('<BBBBHHII',raw,6+i*16)
        assert raw[offset:offset+8]==b'\x89PNG\r\n\x1a\n' and len(raw[offset:offset+length])==length
def test_release_powershell_scripts_parse():
    scripts=['scripts/INSTALL.ps1','scripts/UNINSTALL.ps1','scripts/package_release.ps1']
    for script in scripts:
        command="$e=$null;$t=$null;[System.Management.Automation.Language.Parser]::ParseFile('"+str(Path(script).resolve()).replace("'","''")+"',[ref]$t,[ref]$e) | Out-Null;if($e.Count){exit 1}"
        assert subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True).returncode==0
