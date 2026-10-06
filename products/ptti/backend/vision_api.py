import json
import hashlib
import uuid
import subprocess
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from vision.service import VisionService, DatasetManager
from vision.config import VisionConfig
from vision.schema import Source
from vision.doctor import doctor
from backend.full_match_pipeline import FullMatchService
from backend.fullmatch import quality_report, DEFAULT_CHUNK_SECONDS

class BenchmarkRequest(BaseModel):
    device: str = 'cuda'

def router(repo=None, data_root=None):
    api = APIRouter(prefix='/api/vision')
    config=VisionConfig.load()
    if data_root is not None:
        vision_root=Path(data_root)/'vision'
        config.cache_root=vision_root/'cache'
        config.output_root=vision_root/'outputs'
        (vision_root/'user_uploads').mkdir(parents=True,exist_ok=True)
    service = VisionService(config)
    linked_jobs={}
    full_match_service=FullMatchService(repo,data_root,config) if repo is not None and data_root is not None else None

    @api.get('/professional-matches/{match_id}/full-match')
    def full_match_status(match_id:str):
        if repo is None:raise HTTPException(503,'职业比赛服务不可用')
        if not repo.get_professional_match(match_id):raise HTTPException(404,'职业比赛记录不存在')
        return repo.get_full_match_job(match_id) or {'match_id':match_id,'status':'NOT_STARTED','stage':'等待开始'}

    @api.get('/professional-matches/{match_id}/full-match/quality')
    def full_match_quality(match_id:str,device:str='cuda'):
        if repo is None:raise HTTPException(503,'职业比赛服务不可用')
        record=repo.get_professional_match(match_id)
        if not record:raise HTTPException(404,'职业比赛记录不存在')
        if record.get('video_source_type') not in {'LICENSED_WTT_LOCAL','LOCAL_USER_VIDEO','RESEARCH_DATASET'} or record.get('rights_status') not in {'LICENSED_FOR_ANALYSIS','USER_AUTHORIZED','RESEARCH_DATASET_AUTHORIZED'}:
            raise HTTPException(403,'此比赛没有已授权的本机视频')
        metadata=record.get('video_metadata') or {}
        try:
            report=quality_report(metadata,int(metadata.get('size_bytes',0)),device,DEFAULT_CHUNK_SECONDS)
            report['input_file_present']=Path(record.get('video_local_path') or '').is_file()
            report['frozen_checkpoint_present']=bool(full_match_service and full_match_service.config.model_root.joinpath('balltrack_best.pth').is_file())
            return report
        except (KeyError,TypeError,ValueError) as exc:
            raise HTTPException(422,'视频媒体属性不完整，请重新登记本机视频') from exc

    @api.post('/professional-matches/{match_id}/full-match')
    def start_full_match(match_id:str,device:str='cuda',resume:bool=False):
        if full_match_service is None:raise HTTPException(503,'全场分析服务不可用')
        record=repo.get_professional_match(match_id)
        if not record:raise HTTPException(404,'职业比赛记录不存在')
        try:return full_match_service.start(match_id,device,resume)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc

    def persist_job(match_id, clip, note, job, clip_filename=None):
        if repo is None:return
        record=repo.get_professional_match(match_id)
        if not record:return
        previous=record.get('video_analysis') or {}
        state=job.get('status','running')
        value={**previous,'scope':'SHORT_CLIP','status':state,'job_id':job.get('id'),
               'clip_filename':clip_filename or clip.name,'source_note':note}
        if state=='complete':value['analysis_id']=(job.get('result') or {}).get('analysis_id')
        if state=='failed':value['error']=job.get('error')
        repo.update_professional_video_analysis(match_id,value)

    @api.get('/doctor')
    def environment(): return doctor(service.config)

    @api.get('/analyses')
    def library(): return service.list_results()

    @api.post('/benchmark')
    def benchmark(value: BenchmarkRequest):
        try:
            video, gt, source = DatasetManager(service.config).benchmark()
            return service.submit(video, source, gt, value.device)
        except ValueError as exc: raise HTTPException(422, str(exc))

    @api.post('/import')
    async def ingest(file: UploadFile = File(...), source: str = Form(...), device: str = Form('cuda')):
        try: metadata = Source.model_validate_json(source)
        except ValueError: raise HTTPException(422, '请填写有效来源与授权信息')
        suffix = __import__('pathlib').Path(file.filename or '').suffix.lower()
        if suffix not in {'.mp4', '.mov', '.mkv', '.avi'}: raise HTTPException(422, '请选择受支持的本地视频')
        destination = service.config.output_root.parent / 'user_uploads' / (str(uuid.uuid4()) + suffix)
        destination.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        with destination.open('xb') as output:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > 2 * 1024**3: raise HTTPException(413, '当前实验版限制视频为 2 GiB；未开始分析')
                output.write(chunk)
        try:
            quality = service.inspect(destination)
            return dict(job=service.submit(destination, metadata, device=device), **quality)
        except subprocess.CalledProcessError:
            raise HTTPException(422, '视频无法读取。请确认文件未损坏，并使用 MP4、MOV、MKV 或 AVI 视频。')
        except (ValueError, OSError) as exc: raise HTTPException(422, str(exc))

    @api.post('/professional-matches/{match_id}/balltrack-clip')
    async def analyze_professional_clip(match_id: str, file: UploadFile = File(...),
                                        rights_confirmed: bool = Form(False),
                                        source_note: str = Form(...), device: str = Form('cuda')):
        if repo is None or data_root is None:
            raise HTTPException(503,'职业比赛关联分析不可用')
        if not rights_confirmed:
            raise HTTPException(422,'请确认你有权分析这段比赛短片')
        note=source_note.strip()
        if not note or len(note)>500:
            raise HTTPException(422,'请填写不超过 500 字的短片来源与授权说明')
        record=repo.get_professional_match(match_id)
        if not record:raise HTTPException(404,'职业比赛记录不存在')
        if record.get('video_source_type') not in {'LOCAL_USER_VIDEO','LICENSED_WTT_LOCAL','RESEARCH_DATASET'} or record.get('rights_status') not in {'USER_AUTHORIZED','LICENSED_FOR_ANALYSIS','RESEARCH_DATASET_AUTHORIZED'}:
            raise HTTPException(403,'这场比赛没有已授权的本地视频记录')
        original=Path(record.get('video_local_path') or '')
        if not original.is_file():raise HTTPException(409,'已登记的本地视频文件当前不可用')
        suffix=Path(file.filename or '').suffix.lower()
        if suffix not in {'.mp4','.mov','.mkv','.avi'}:
            raise HTTPException(422,'请选择 MP4、MOV、MKV 或 AVI 短片')
        destination=Path(data_root)/'vision'/'user_uploads'/(str(uuid.uuid4())+suffix)
        destination.parent.mkdir(parents=True,exist_ok=True)
        digest=hashlib.sha256();total=0
        try:
            with destination.open('xb') as output:
                while chunk:=await file.read(1024*1024):
                    total+=len(chunk)
                    if total>2*1024**3:raise HTTPException(413,'短片超过 2 GiB；尚未开始分析')
                    digest.update(chunk);output.write(chunk)
            quality=service.inspect(destination)
            media=quality['video']
            frame_count=media.get('frame_count') or round(media['duration']*media['fps'])
            if media['duration']>60 or frame_count>1800:
                raise HTTPException(422,'当前只支持不超过 60 秒且不超过 1800 帧的短片；整场比赛分析尚未开放')
            source=Source(type='local',provider='用户授权的本地比赛视频',
                          rights='user_provided',source_id=match_id,
                          rights_notes=note,original_url=None,title=record['event_name'],
                          event=record['event_name'],players=f"{record['player_a_id']} vs {record['player_b_id']}",
                          round=record.get('round') or '')
            previous_analysis=record.get('video_analysis')
            repo.update_professional_video_analysis(match_id,{
                'scope':'SHORT_CLIP','status':'queued','clip_filename':Path(file.filename or '').name,
                'clip_path':str(destination),'clip_sha256':digest.hexdigest(),
                'clip_size_bytes':total,'source_note':note,'video':media,'quality':quality['quality']})
            original_filename=Path(file.filename or '').name
            def update(job):persist_job(match_id,destination,note,job,original_filename)
            try:
                job=service.submit(destination,source,device=device,on_update=update)
            except Exception:
                repo.update_professional_video_analysis(match_id,previous_analysis)
                raise
            linked_jobs[job['id']]={'match_id':match_id,'clip':destination,'note':note,'clip_filename':original_filename}
            return {'job':job,'scope':'SHORT_CLIP','video':media,'quality':quality['quality']}
        except HTTPException:
            destination.unlink(missing_ok=True)
            raise
        except subprocess.CalledProcessError as exc:
            destination.unlink(missing_ok=True)
            raise HTTPException(422,'短片无法读取，请确认文件完整') from exc
        except (ValueError,OSError) as exc:
            destination.unlink(missing_ok=True)
            raise HTTPException(422,str(exc)) from exc
        finally:
            await file.close()

    @api.post('/reference')
    def reference(source: Source):
        if source.type != 'external_reference': raise HTTPException(422, '请选择外部参考来源')
        folder = service.config.output_root.parent / 'references'; folder.mkdir(parents=True, exist_ok=True)
        identifier = str(uuid.uuid4())
        (folder / (identifier + '.json')).write_text(source.model_dump_json(indent=2), encoding='utf-8')
        return dict(id=identifier, saved=True, downloaded=False)

    @api.get('/jobs/{id}')
    def job(id: str):
        with service.lock:
            if id not in service.jobs: raise HTTPException(404, '任务不存在；重启后请查看已完成分析')
            result=service.jobs[id].copy()
        linked=linked_jobs.get(id)
        if linked and result.get('status') in {'complete','failed'}:
            persist_job(linked['match_id'],linked['clip'],linked['note'],result,linked['clip_filename'])
        return result

    @api.get('/analyses/{id}/{asset}')
    def output(id: str, asset: str):
        try: path = service.asset(id, asset)
        except ValueError as exc: raise HTTPException(404, str(exc))
        return FileResponse(path, filename=asset if asset != 'ball_overlay.mp4' else None)

    return api
