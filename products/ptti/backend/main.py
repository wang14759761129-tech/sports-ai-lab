import json
import hashlib
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import uuid
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
from backend.fullmatch import (SUPPORTED_VIDEO_SUFFIXES, file_sha256, scan_wtt_inbox,
                               MatchTimeline, TimelineAction, apply_timeline_action)

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
    resolved_db=resolve_database_path(db_path)
    app.state.database_path=resolved_db
    mode='test' if 'pytest' in sys.modules or os.environ.get('PTTI_ENV')=='test' else os.environ.get('PTTI_ENV','development')
    repo=Repository(resolved_db,guard=ProductionDatabaseGuard(mode))
    app.state.repository=repo
    app.state.data_root=Path(resolved_db).parent
    wtt_inbox=app.state.data_root/'inbox'/'wtt'
    wtt_inbox.mkdir(parents=True,exist_ok=True)
    inbox_scan_cache={}
    from backend.vision_api import router as vision_router
    app.include_router(vision_router(repo=repo,data_root=Path(resolved_db).parent))
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
        full_job=repo.get_full_match_job(record['match_id'])
        if full_job and full_job.get('status')=='BALLTRACK_COMPLETE':
            record={**record,'analysis_status':'BALLTRACK_COMPLETE'}
        return {**record,'players':{'player_a':a,'player_b':b},'sources':repo.get_sources(record.get('source_ids',[])),
                'full_match_analysis':full_job}
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
        athletes=repo.list_athletes(group_code,search)
        sources=repo.get_sources([source for a in athletes for source in a.get('source_ids',[])])
        source_map={source['source_id']:source for source in sources}
        return [dict(athlete=a,sources=[source_map[s] for s in a.get('source_ids',[]) if s in source_map]) for a in athletes]
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
    @app.get('/api/professional-matches/inbox')
    def professional_video_inbox():
        registered={m.get('video_metadata',{}).get('sha256') for m in repo.professional_matches()}
        athletes=[repo.get_athlete(item['athlete_id']) for item in repo.list_athletes()]
        # Only this explicit application inbox is scanned. Downloads are available via
        # the file-picker upload below; no directory-wide scan is performed.
        items=[]
        for path in sorted(wtt_inbox.iterdir(),key=lambda item:item.name.casefold()):
            if not path.is_file() or path.suffix.casefold() not in SUPPORTED_VIDEO_SUFFIXES:continue
            stat=path.stat();signature=(stat.st_size,stat.st_mtime_ns)
            cached=inbox_scan_cache.get(str(path.resolve()))
            if cached and cached[0]==signature:
                item=dict(cached[1])
            else:
                inspected=scan_wtt_inbox(wtt_inbox,registered,athletes,only_file=path)
                item=inspected[0] if inspected else None
                if item is None:continue
                inbox_scan_cache[str(path.resolve())]=(signature,dict(item))
            item['duplicate']=bool(item.get('sha256') in registered)
            items.append(item)
        return {'inbox_directory':str(wtt_inbox),'items':items}

    @app.get('/api/professional-matches/{match_id}/video')
    def professional_match_video(match_id:str):
        record=repo.get_professional_match(match_id)
        if not record:raise HTTPException(404,'职业比赛记录不存在')
        if record.get('video_source_type') not in {'LICENSED_WTT_LOCAL','LOCAL_USER_VIDEO','RESEARCH_DATASET'} or record.get('rights_status') not in {'LICENSED_FOR_ANALYSIS','USER_AUTHORIZED','RESEARCH_DATASET_AUTHORIZED'}:
            raise HTTPException(403,'此比赛没有已授权的本机视频')
        path=Path(record.get('video_local_path') or '')
        if not path.is_file():raise HTTPException(404,'登记的视频文件当前不可用')
        return FileResponse(path,media_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream',filename=record.get('video_original_filename') or path.name)

    @app.get('/api/professional-matches/{match_id}/timeline')
    def professional_match_timeline(match_id:str):
        if not repo.get_professional_match(match_id):raise HTTPException(404,'职业比赛记录不存在')
        value=repo.get_match_timeline(match_id) or {'match_id':match_id,'revision':0,'games':[],'scene_segments':[]}
        return MatchTimeline.model_validate(value).model_dump(mode='json')

    @app.get('/api/professional-matches/{match_id}/scoreboard-recognizer')
    def scoreboard_recognizer_status(match_id:str):
        if not repo.get_professional_match(match_id):raise HTTPException(404,'职业比赛记录不存在')
        return {'status':'EXPERIMENTAL','enabled':False,'score':None,
                'fallback':'MANUAL_SCORE_ENTRY','message':'当前不依赖记分牌 OCR；请人工录入并核对比分。'}

    @app.put('/api/professional-matches/{match_id}/timeline')
    def replace_professional_match_timeline(match_id:str,value:MatchTimeline,expected_revision:int|None=None):
        if not repo.get_professional_match(match_id):raise HTTPException(404,'职业比赛记录不存在')
        if value.match_id!=match_id:raise HTTPException(422,'时间轴比赛标识不匹配')
        try:
            saved=repo.save_match_timeline(match_id,value.model_dump(mode='json',exclude={'revision'}),expected_revision)
            from backend.full_match_pipeline import refresh_timeline_summary
            refresh_timeline_summary(repo,match_id,saved)
            return saved
        except ValueError as exc:raise HTTPException(409,str(exc)) from exc

    @app.post('/api/professional-matches/{match_id}/timeline/actions')
    def professional_timeline_action(match_id:str,value:TimelineAction,expected_revision:int|None=None):
        if not repo.get_professional_match(match_id):raise HTTPException(404,'职业比赛记录不存在')
        for athlete_id in (value.scorer_id,value.server_id,value.receiver_id):
            if athlete_id is not None and not repo.get_athlete(athlete_id):
                raise HTTPException(422,'得分方、发球方或接发方必须使用运动员名录中的 ID')
        existing=repo.get_match_timeline(match_id) or {'match_id':match_id,'revision':0,'games':[],'scene_segments':[]}
        if expected_revision is not None and expected_revision!=existing['revision']:
            raise HTTPException(409,f"Timeline revision conflict: expected {expected_revision}, current {existing['revision']}")
        try:
            updated=apply_timeline_action(existing,value)
            saved=repo.save_match_timeline(match_id,updated,existing['revision'])
            from backend.full_match_pipeline import refresh_timeline_summary
            refresh_timeline_summary(repo,match_id,saved)
            return saved
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc

    @app.get('/api/professional-matches/{match_id}/full-match/asset/{asset}')
    def professional_full_match_asset(match_id:str,asset:str):
        if asset not in {'full_match_balltrack.csv','full_match_balltrack.jsonl','full_match_summary.json',
                         'full_match_report.html','full_match_validation.json','full_match_validation.html',
                         'manifest.json','match_timeline.json'}:
            raise HTTPException(404,'分析文件不存在')
        job=repo.get_full_match_job(match_id)
        if not job or not job.get('output_dir'):raise HTTPException(404,'全场分析文件尚未生成')
        path=Path(job['output_dir'])/asset
        if not path.is_file():raise HTTPException(404,'分析文件尚未生成')
        return FileResponse(path,filename=asset)

    @app.post('/api/professional-matches/inbox/import',status_code=201)
    async def import_wtt_video(metadata:str=Form(...),rights_confirmed:bool=Form(False),
                               video_source_note:str=Form(...),inbox_id:str|None=Form(None),
                               file:UploadFile|None=File(None)):
        if not rights_confirmed:raise HTTPException(422,'请确认已通过 WTT 官方流程取得本机分析授权')
        note=video_source_note.strip()
        if not note or len(note)>1000:raise HTTPException(422,'请填写不超过 1000 字的视频授权来源说明')
        try:
            values=json.loads(metadata)
            if not isinstance(values,dict):raise ValueError('比赛资料格式无效')
            values['video_source_type']='LICENSED_WTT_LOCAL'
            values['rights_status']='LICENSED_FOR_ANALYSIS'
            if not values.get('licence_reference'):raise ValueError('请填写 WTT 授权编号或许可记录')
            if not values.get('wtt_asset_id'):raise ValueError('请填写 WTT Asset / Record ID')
            if not values.get('external_reference_url'):raise ValueError('请填写 WTT 官方比赛或媒体来源链接')
            if file is not None:
                suffix=Path(file.filename or '').suffix.casefold()
                if suffix not in SUPPORTED_VIDEO_SUFFIXES:raise ValueError('请选择 MP4、MOV、MKV 或 AVI 视频')
                temp_path=wtt_inbox/(str(uuid.uuid4())+suffix)
                size=0
                try:
                    with temp_path.open('xb') as output:
                        while block:=await file.read(8*1024*1024):
                            size+=len(block)
                            if size>64*1024**3:raise HTTPException(413,'视频超过 64 GiB，未登记比赛')
                            output.write(block)
                except Exception:
                    temp_path.unlink(missing_ok=True)
                    raise
                digest=file_sha256(temp_path)
                destination=wtt_inbox/(digest+suffix)
                if destination.exists():temp_path.unlink()
                else:temp_path.replace(destination)
                video_path=destination
                original_name=Path(values.get('original_filename') or file.filename or '').name
            else:
                if not inbox_id or not re.fullmatch(r'[a-f0-9]{64}',inbox_id):
                    raise ValueError('请选择 WTT Inbox 中的视频文件')
                candidates=[p for p in wtt_inbox.iterdir() if p.is_file() and p.suffix.casefold() in SUPPORTED_VIDEO_SUFFIXES]
                video_path=next((p for p in candidates if file_sha256(p)==inbox_id),None)
                if video_path is None:raise HTTPException(404,'Inbox 视频已移动或发生变化，请重新扫描')
                if video_path.is_symlink() or video_path.resolve().parent!=wtt_inbox.resolve():
                    raise HTTPException(403,'Inbox 文件路径不安全')
                digest=inbox_id;size=video_path.stat().st_size;original_name=Path(values.get('original_filename') or video_path.name).name
            for previous in repo.professional_matches():
                if previous.get('video_metadata',{}).get('sha256')==digest:
                    raise HTTPException(409,'这段视频已登记，不能重复导入')
            from vision.quality import video_metadata,classify
            media=video_metadata(video_path)
            values.update(video_local_path=str(video_path),external_reference_url=values.get('external_reference_url'))
            record=ProfessionalMatchInput.model_validate(values).to_record()
            record.update(analysis_status='VIDEO_READY',video_source_note=note,
                          video_original_filename=original_name,
                          video_metadata={**media,'size_bytes':size,'mtime_ns':video_path.stat().st_mtime_ns,'sha256':digest,'quality':classify(media)})
            saved=repo.save_professional_match(record)
            return {**professional_match_view(saved),'quality':classify(media)}
        except HTTPException:raise
        except subprocess.CalledProcessError as exc:raise HTTPException(422,'视频无法读取，请确认本机文件完整') from exc
        except (ValueError,OSError) as exc:raise HTTPException(422,str(exc)) from exc
        finally:
            if file is not None:await file.close()

    @app.post('/api/professional-matches/inbox/stage')
    async def stage_wtt_video(file:UploadFile=File(...),rights_confirmed:bool=Form(False),
                              video_source_note:str=Form(...)):
        """Copy one explicitly selected, authorized local file into the review inbox."""
        if not rights_confirmed:raise HTTPException(422,'请先确认该文件允许本机分析')
        note=video_source_note.strip()
        if not note or len(note)>1000:raise HTTPException(422,'请填写授权与来源说明')
        suffix=Path(file.filename or '').suffix.casefold()
        if suffix not in SUPPORTED_VIDEO_SUFFIXES:raise HTTPException(422,'请选择 MP4、MOV、MKV 或 AVI 视频')
        temporary=wtt_inbox/(str(uuid.uuid4())+suffix)
        try:
            size=0
            with temporary.open('xb') as output:
                while block:=await file.read(8*1024*1024):
                    size+=len(block)
                    if size>64*1024**3:raise HTTPException(413,'视频超过 64 GiB')
                    output.write(block)
            digest=file_sha256(temporary)
            original=Path(file.filename or '').name
            safe_name=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',original)[:120] or ('video'+suffix)
            destination=wtt_inbox/(digest[:12]+'_'+safe_name)
            if destination.exists():temporary.unlink()
            else:temporary.replace(destination)
            item=next((value for value in scan_wtt_inbox(wtt_inbox,athletes=[repo.get_athlete(x['athlete_id']) for x in repo.list_athletes()],only_file=destination)),None)
            if not item:raise HTTPException(422,'所选文件无法读取')
            item['original_filename']=original
            return item
        except HTTPException:
            temporary.unlink(missing_ok=True)
            raise
        except (subprocess.CalledProcessError,ValueError,OSError) as exc:
            temporary.unlink(missing_ok=True)
            raise HTTPException(422,'视频无法读取，请确认本机文件完整') from exc
        finally:
            await file.close()
    @app.post('/api/professional-matches',status_code=201)
    def create_professional_match(value:ProfessionalMatchInput):
        try:record=repo.save_professional_match(value.to_record())
        except ValueError as exc:raise HTTPException(422,str(exc))
        return professional_match_view(record)
    @app.post('/api/professional-matches/local-video',status_code=201)
    async def create_professional_match_with_local_video(
        metadata:str=Form(...),
        video_source_note:str=Form(...),
        rights_confirmed:bool=Form(False),
        file:UploadFile=File(...),
    ):
        if not rights_confirmed:
            raise HTTPException(422,'请先确认你有权在本机分析此视频')
        try:
            values=json.loads(metadata)
            if not isinstance(values,dict):raise ValueError('比赛信息格式无效')
            source_note=video_source_note.strip()
            if not source_note or len(source_note)>500:
                raise ValueError('请填写不超过 500 字的视频来源与授权说明')
            suffix=Path(file.filename or '').suffix.casefold()
            if suffix not in {'.mp4','.mov','.mkv','.avi'}:
                raise ValueError('请选择 MP4、MOV、MKV 或 AVI 视频')
            video_dir=Path(resolved_db).parent/'professional-videos'
            video_dir.mkdir(parents=True,exist_ok=True)
            destination=video_dir/(str(uuid.uuid4())+suffix)
            total=0;digest=hashlib.sha256()
            try:
                with destination.open('xb') as output:
                    while chunk:=await file.read(1024*1024):
                        total+=len(chunk)
                        if total>2*1024**3:raise HTTPException(413,'视频超过 2 GiB，尚未保存比赛记录')
                        digest.update(chunk);output.write(chunk)
                from vision.quality import video_metadata, classify
                media=video_metadata(destination)
                quality=classify(media)
                values.update(video_source_type='LOCAL_USER_VIDEO',video_local_path=str(destination),rights_status='USER_AUTHORIZED')
                record=ProfessionalMatchInput.model_validate(values).to_record()
                record['analysis_status']='VIDEO_READY'
                record['video_source_note']=source_note
                record['video_original_filename']=Path(file.filename or '').name
                record['video_metadata']={**media,'size_bytes':total,'mtime_ns':destination.stat().st_mtime_ns,'sha256':digest.hexdigest(),'quality':quality}
                try:record=repo.save_professional_match(record)
                except ValueError as exc:raise HTTPException(422,str(exc)) from exc
                return {**professional_match_view(record),'quality':quality}
            except Exception:
                destination.unlink(missing_ok=True)
                raise
        except HTTPException:raise
        except subprocess.CalledProcessError as exc:
            raise HTTPException(422,'视频无法读取。请确认文件完整，并使用 MP4、MOV、MKV 或 AVI。') from exc
        except (ValueError,OSError) as exc:
            raise HTTPException(422,str(exc)) from exc
        finally:
            await file.close()
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
