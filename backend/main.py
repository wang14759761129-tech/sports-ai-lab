import os
import sys
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from core.engine import ingest, analyze, SCHEMA_VERSION, ANALYTICS_VERSION
from backend.repository import Repository

ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
class Metadata(BaseModel):
    name: str=Field(min_length=1,max_length=200)
    player_a: str=Field(min_length=1,max_length=100)
    player_b: str=Field(min_length=1,max_length=100)
    date: str=''
    event: str=''
    synthetic: bool=False
class Issue(BaseModel):
    level: str
    row: int | None
    field: str
    message: str
class Validation(BaseModel):
    valid: bool
    issues: list[Issue]
    row_count: int
class Match(BaseModel):
    id: str
    metadata: Metadata
    points: list[dict]
    validation: Validation
    analysis: dict
class ImportResult(BaseModel):
    validation: Validation
    match: Match | None=None

def create_app(db_path=None):
    app=FastAPI(title='PTTI',version='0.1.0')
    repo=Repository(db_path or os.environ.get('PTTI_DB',str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'PTTI'/'matches.db')))
    def get(id):
        m=repo.get(id)
        if not m: raise HTTPException(404,'Match not found')
        return m
    def import_data(raw,meta):
        rows,report=ingest(raw)
        if not report['valid']: return dict(validation=report,match=None)
        return dict(validation=report,match=repo.save(dict(metadata=meta.model_dump(),points=rows,validation=report,analysis=analyze(rows))))
    @app.get('/api/health')
    def health(): return dict(version='0.1.0',schema_version=SCHEMA_VERSION,analytics_version=ANALYTICS_VERSION)
    @app.post('/api/matches/import',response_model=ImportResult)
    async def upload(file:UploadFile=File(...),metadata:str=Form(...)):
        try: meta=Metadata.model_validate_json(metadata)
        except ValueError: raise HTTPException(422,'Invalid match metadata')
        raw=await file.read(10*1024*1024+1)
        if len(raw)>10*1024*1024: raise HTTPException(413,'CSV exceeds 10 MB')
        return import_data(raw,meta)
    @app.post('/api/matches/sample',response_model=ImportResult)
    def sample(): return import_data((ROOT/'data/samples/synthetic.csv').read_bytes(),Metadata(name='Training lab · synthetic demo',player_a='You',player_b='Kaikai',event='Synthetic demonstration',synthetic=True))
    @app.get('/api/matches')
    def library(): return [dict(id=m['id'],metadata=m['metadata'],point_count=len(m['points'])) for m in repo.list()]
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
        body=f'<h1>{escape(meta["name"])}</h1><p>{escape(meta["player_a"])} vs {escape(meta["player_b"])}</p><p>{escape(meta["event"])} · {escape(meta["date"])}</p>'
        if meta['synthetic']: body+='<p><strong>SYNTHETIC DEMONSTRATION — not real match evidence</strong></p>'
        for p in ['A','B']:
            body+=f'<h2>{escape(meta["player_a" if p=="A" else "player_b"])}</h2><table><tr><th>Metric</th><th>Value</th><th>Evidence</th></tr>'
            for key in ['points_won','serve_win','receive_win','third_ball_attack','third_ball_win','average_rally']:
                metric=analysis['players'][p][key]; value=metric['value']
                body+=f'<tr><td>{key.replace("_"," ")}</td><td>{"Insufficient data" if value is None else str(value)+( "" if key=="average_rally" else "%")}</td><td>{str(metric.get("numerator", ""))}/{metric["denominator"]} annotated points</td></tr>'
            body+='</table>'
        body+='<h2>Tactical evidence</h2>'
        for i in analysis['insights']: body+=f'<p><b>{escape(i["kind"])} · Player {i["player"]}</b>: {escape(i["statement"])}<br>{escape(i["evidence"])} · {escape(i["reliability"])}</p>'
        body+='<h2>Validation notices</h2>'
        for i in m['validation']['issues']: body+=f'<p>{escape(i["level"])} · CSV row {i["row"]} · {escape(i["field"])}: {escape(i["message"])}</p>'
        body+=f'<p>PTTI 0.1.0 · schema {SCHEMA_VERSION} · analytics {ANALYTICS_VERSION}. Descriptive recorded-point statistics. Third-ball conversion counts point wins following an attack annotation.</p>'
        html='<!doctype html><html><head><meta charset="utf-8"><title>PTTI match report</title><style>body{font-family:Segoe UI,Microsoft YaHei,sans-serif;max-width:900px;margin:40px auto;color:#183d3a}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}p{line-height:1.6}@media print{body{margin:0}}</style></head><body>'+body+'</body></html>'
        return Response(html,media_type='text/html',headers={'Content-Disposition':'attachment; filename="ptti-report.html"'})
    @app.delete('/api/matches/{id}')
    def delete(id:str):
        if not repo.delete(id): raise HTTPException(404,'Match not found')
        return {'deleted':True}
    static=ROOT/'frontend/dist'
    if static.exists(): app.mount('/',StaticFiles(directory=static,html=True),name='frontend')
    return app

app=create_app()
