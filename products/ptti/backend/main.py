import os
import sys
import tempfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response, FileResponse
from typing import Literal
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from core.engine import ingest, analyze, SCHEMA_VERSION, ANALYTICS_VERSION
from backend.repository import Repository
from backend.database import ProductionDatabaseGuard, database_banner
from core.importing import import_csv
from backend.professional import GroupMembershipUpdate, ProfessionalMatchInput

ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))

PRODUCTION_DATABASE_WRITE_GUARD = 'PRODUCTION_DATABASE_WRITE_GUARD'

def _same_path(left, right):
    left=Path(left).expanduser().resolve(strict=False)
    right=Path(right).expanduser().resolve(strict=False)
    if os.path.normcase(str(left))==os.path.normcase(str(right)):
        return True
    try:
        return left.exists() and right.exists() and os.path.samefile(left,right)
    except OSError:
        return False

def resolve_database_path(db_path=None, environ=None, testing=None):
    """Resolve a DB path while preventing test/development writes to user data."""
    env=os.environ if environ is None else environ
    local=Path(env.get('LOCALAPPDATA',Path.home()))
    production=(local/'PTTI'/'matches.db').resolve(strict=False)
    mode=env.get('PTTI_ENV','').strip().lower()
    if testing is None:
        testing=('pytest' in sys.modules) if environ is None else mode=='test'
    if testing:
        mode='test'
    elif not mode:
        mode='development'

    configured=db_path if db_path is not None else env.get('PTTI_DB')
    if mode=='test':
        if configured is None:
            raise RuntimeError(f'{PRODUCTION_DATABASE_WRITE_GUARD}: tests require an explicit temporary PTTI_DB')
        chosen=Path(configured).expanduser().resolve(strict=False)
        if _same_path(chosen,production):
            raise RuntimeError(f'{PRODUCTION_DATABASE_WRITE_GUARD}: tests cannot open the production database')
        temporary=Path(tempfile.gettempdir()).resolve(strict=False)
        try:
            chosen.relative_to(temporary)
        except ValueError as exc:
            raise RuntimeError(f'{PRODUCTION_DATABASE_WRITE_GUARD}: test databases must be under the system temporary directory') from exc
    elif mode=='development':
        chosen=Path(configured).expanduser().resolve(strict=False) if configured is not None else (local/'PTTI-Dev'/'matches.db').resolve(strict=False)
        if _same_path(chosen,production):
            raise RuntimeError(f'{PRODUCTION_DATABASE_WRITE_GUARD}: development cannot open the production database')
    elif mode=='production':
        chosen=Path(configured).expanduser().resolve(strict=False) if configured is not None else production
        if not _same_path(chosen,production):
            raise RuntimeError(f'{PRODUCTION_DATABASE_WRITE_GUARD}: production database path must be {production}')
    else:
        raise RuntimeError(f'Unsupported PTTI_ENV: {mode}')
    return ProductionDatabaseGuard(mode,env).validate(chosen)

class Metadata(BaseModel):
    name: str=Field(min_length=1,max_length=200)
    player_a: str=Field(min_length=1,max_length=100)
    player_b: str=Field(min_length=1,max_length=100)
    date: str=''
    event: str=''
    synthetic: bool=False
    notes: str=Field(default='',max_length=2000)
class Settings(BaseModel):
    language: Literal['zh-CN']='zh-CN'
    theme: Literal['system','light','dark']='system'
    start_page: Literal['home','recent']='home'
    onboarding_complete: bool=False
class Issue(BaseModel):
    level: str
    row: int | None
    field: str
    message: str
class Validation(BaseModel):
    valid: bool
    issues: list[Issue]
    row_count: int
    evidence_state: str='AVAILABLE'
class Match(BaseModel):
    id: str
    metadata: Metadata
    points: list[dict]
    validation: Validation
    analysis: dict
    provenance: dict = Field(default_factory=dict)
class ImportResult(BaseModel):
    validation: Validation
    match: Match | None=None
    provenance: dict = Field(default_factory=dict)

def create_app(db_path=None):
    app=FastAPI(title='PTTI',version='0.2.0-dev')
    from backend.vision_api import router as vision_router
    app.include_router(vision_router())
    resolved_db=resolve_database_path(db_path)
    app.state.database_path=resolved_db
    mode='test' if 'pytest' in sys.modules or os.environ.get('PTTI_ENV')=='test' else os.environ.get('PTTI_ENV','development')
    repo=Repository(resolved_db,guard=ProductionDatabaseGuard(mode))
    professional_manifest=ROOT/'data'/'professional'/'registry.json'
    repo.seed_professional(__import__('json').loads(professional_manifest.read_text(encoding='utf-8')))
    app.state.database_diagnostics=database_banner(resolved_db,mode)
    @app.get('/api/diagnostics/database',include_in_schema=False)
    def database_diagnostics():
        if mode=='production': raise HTTPException(404,'Not available')
        return app.state.database_diagnostics
    def get(id):
        m=repo.get(id)
        if not m: raise HTTPException(404,'Match not found')
        return m
    def professional_match_view(record):
        if not record:return None
        a=repo.get_athlete(record['player_a_id']);b=repo.get_athlete(record['player_b_id'])
        return {**record,'players':{'player_a':a,'player_b':b},'sources':repo.get_sources(record.get('source_ids',[]))}
    def import_data(raw,meta,save=True):
        rows,report,provenance=import_csv(raw)
        report['evidence_state']='AVAILABLE' if report['valid'] else 'INVALID_DATA'
        if not report['valid']: return dict(validation=report,match=None,provenance=provenance)
        payload=dict(id='',metadata=meta.model_dump(),points=rows,validation=report,analysis=analyze(rows),provenance=provenance)
        return dict(validation=report,match=repo.save(payload) if save else payload,provenance=provenance)
    @app.get('/api/health')
    def health(): return dict(version='0.2.0-dev',schema_version=SCHEMA_VERSION,analytics_version=ANALYTICS_VERSION,adapter_version='0.1.1')
    @app.get('/api/settings')
    def settings(): return Settings.model_validate(repo.settings()).model_dump()
    @app.put('/api/settings')
    def save_settings(value:Settings):
        repo.save_settings(value.model_dump());return value
    @app.get('/api/players')
    def players(group_code:str|None=None,search:str|None=None):
        if group_code and not repo.get_group(group_code):raise HTTPException(404,'Player group not found')
        return [dict(athlete=a,sources=repo.get_sources(a.get('source_ids',[]))) for a in repo.list_athletes(group_code,search)]
    @app.get('/api/players/{athlete_id}/rankings')
    def player_rankings(athlete_id:str):
        if not repo.get_athlete(athlete_id):raise HTTPException(404,'Athlete not found')
        rows=repo.get_rankings(athlete_id)
        for row in rows:row['source']=repo.get_sources([row['source_id']])[0]
        return rows
    @app.get('/api/players/{athlete_id}/matches')
    def player_matches(athlete_id:str):
        if not repo.get_athlete(athlete_id):raise HTTPException(404,'Athlete not found')
        return [professional_match_view(m) for m in repo.professional_matches(athlete_id)]
    @app.get('/api/players/{athlete_id}')
    def player_detail(athlete_id:str):
        athlete=repo.get_athlete(athlete_id)
        if not athlete:raise HTTPException(404,'Athlete not found')
        return dict(athlete=athlete,rankings=player_rankings(athlete_id),matches=player_matches(athlete_id),
            sources=repo.get_sources(athlete.get('source_ids',[])))
    @app.get('/api/player-groups')
    def player_groups():return repo.list_groups()
    @app.put('/api/player-groups/{group_code}/members')
    def update_player_group(group_code:str,value:GroupMembershipUpdate):
        try:result=repo.set_group_members(group_code,value.athlete_ids)
        except ValueError as exc:raise HTTPException(422,str(exc))
        if result is None:raise HTTPException(404,'Player group not found')
        return result
    @app.get('/api/professional-matches')
    def professional_matches(athlete_id:str|None=None):
        if athlete_id and not repo.get_athlete(athlete_id):raise HTTPException(404,'Athlete not found')
        return [professional_match_view(m) for m in repo.professional_matches(athlete_id)]
    @app.post('/api/professional-matches',status_code=201)
    def create_professional_match(value:ProfessionalMatchInput):
        try:record=repo.save_professional_match(value.to_record())
        except ValueError as exc:raise HTTPException(422,str(exc))
        return professional_match_view(record)
    @app.get('/api/templates/{format}')
    def template(format:Literal['native','protocol']):
        filename='synthetic.csv' if format=='native' else 'protocol-v0.3-example.csv'
        return FileResponse(ROOT/'data/samples'/filename,media_type='text/csv; charset=utf-8',filename=filename)
    @app.post('/api/matches/import',response_model=ImportResult)
    async def upload(file:UploadFile=File(...),metadata:str=Form(...),preview:bool=Form(False)):
        try: meta=Metadata.model_validate_json(metadata)
        except ValueError: raise HTTPException(422,'Invalid match metadata')
        raw=await file.read(10*1024*1024+1)
        if len(raw)>10*1024*1024: raise HTTPException(413,'CSV exceeds 10 MB')
        return import_data(raw,meta,save=not preview)
    @app.post('/api/matches/sample',response_model=ImportResult)
    def sample(): return import_data((ROOT/'data/samples/synthetic.csv').read_bytes(),Metadata(name='训练示例 · 合成比赛',player_a='你',player_b='凯凯',event='合成示例',synthetic=True))
    @app.get('/api/matches')
    def library(): return [dict(id=m['id'],metadata=m['metadata'],point_count=len(m['points']),source_schema=m.get('provenance',{}).get('source_schema','legacy'),warning_count=sum(i['level']=='warning' for i in m['validation']['issues'])) for m in repo.list()]
    @app.get('/api/matches/{id}',response_model=Match)
    def match(id:str): return get(id)
    @app.get('/api/matches/{id}/analysis')
    def analysis(id:str): return get(id)['analysis']
    @app.get('/api/matches/{id}/points')
    def points(id:str): return get(id)['points']
    @app.get('/api/matches/{id}/export')
    def export(id:str):
        import json
        return Response(json.dumps(get(id),ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename="ptti-match.json"'})
    @app.get('/api/matches/{id}/report')
    def report(id:str):
        from html import escape
        m=get(id); meta=m['metadata']; analysis=m['analysis']
        labels={'points_won':'得分率','serve_win':'发球得分率','receive_win':'接发得分率','third_ball_attack':'第三板抢攻率','third_ball_win':'抢攻后该分得分率','average_rally':'平均回合长度'}
        states={'AVAILABLE':'数据充足','INSUFFICIENT_EVIDENCE':'证据不足','NOT_AVAILABLE':'暂无该字段'}
        body=f'<h1>{escape(meta["name"])}</h1><p>{escape(meta["player_a"])} vs {escape(meta["player_b"])}</p><p>{escape(meta["event"])} · {escape(meta["date"])}</p>'
        if meta['synthetic']: body+='<p><strong>合成示例，不是真实比赛证据</strong><small> · SYNTHETIC DEMONSTRATION</small></p>'
        for player in ['A','B']:
            body+=f'<h2>{escape(meta["player_a" if player=="A" else "player_b"])}</h2><table><tr><th>指标</th><th>数值</th><th>有效样本</th><th>证据状态</th></tr>'
            for key,label in labels.items():
                metric=analysis['players'][player][key]; value=metric['value']; state=metric.get('evidence_state','legacy')
                shown='—' if value is None else str(value)+(' 次' if key=='average_rally' else '%')
                numerator=str(metric['numerator'])+' / ' if 'numerator' in metric else ''
                body+=f'<tr><td>{label}</td><td>{shown}</td><td>{numerator}{metric["denominator"]}</td><td>{states.get(state,"旧版结果")}<small> · {state}</small></td></tr>'
            body+='</table>'
        schema=m.get('provenance',{}).get('source_schema','legacy')
        body+=f'<h2>数据来源与可信度</h2><p>数据格式：{escape(schema)}。未知不等于零；证据不足时不显示猜测比例。</p>'
        body+='<p>第三板抢攻得分率表示已标注抢攻后赢下该分，不是第三板直接得分。仅描述已记录样本，不等于科学研究结论。</p><h2>数据检查</h2>'
        for issue in m['validation']['issues']:
            severity='错误' if issue['level']=='error' else '警告'
            row='整场数据' if issue['row'] is None else '第 '+str(issue['row'])+' 行'
            body+=f'<p>{severity} · {row} · {escape(issue["field"])}：{escape(issue["message"])}</p>'
        body+=f'<p>PTTI 0.1.2 · 数据格式 {SCHEMA_VERSION} · 分析版本 {escape(analysis.get("analytics_version","0.1.0"))}。</p>'
        html='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>PTTI 比赛分析报告</title><style>body{font-family:Microsoft YaHei UI,Microsoft YaHei,Segoe UI,sans-serif;max-width:900px;margin:40px auto;color:#183d3a}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}p{line-height:1.6}small{color:#637879}@media print{body{margin:0}}</style></head><body>'+body+'</body></html>'
        return Response(html,media_type='text/html',headers={'Content-Disposition':'attachment; filename="ptti-report.html"'})
    @app.delete('/api/matches/{id}')
    def delete(id:str):
        if not repo.delete(id): raise HTTPException(404,'Match not found')
        return {'deleted':True}
    static=ROOT/'frontend/dist'
    if static.exists(): app.mount('/',StaticFiles(directory=static,html=True),name='frontend')
    return app

app=create_app()
