import os
import sys
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response, FileResponse
from typing import Literal
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from core.engine import ingest, analyze, SCHEMA_VERSION, ANALYTICS_VERSION
from backend.repository import Repository
from core.importing import import_csv

ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
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
    repo=Repository(db_path or os.environ.get('PTTI_DB',str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'PTTI'/'matches.db')))
    def get(id):
        m=repo.get(id)
        if not m: raise HTTPException(404,'Match not found')
        return m
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
