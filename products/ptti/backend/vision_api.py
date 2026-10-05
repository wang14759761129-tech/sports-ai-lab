import json
import uuid
import subprocess
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from vision.service import VisionService, DatasetManager
from vision.schema import Source
from vision.doctor import doctor

class BenchmarkRequest(BaseModel):
    device: str = 'cuda'

def router():
    api = APIRouter(prefix='/api/vision')
    service = VisionService()

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
        destination = service.config.dataset_root / 'user' / (str(uuid.uuid4()) + suffix)
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

    @api.post('/reference')
    def reference(source: Source):
        if source.type != 'external_reference': raise HTTPException(422, '请选择外部参考来源')
        folder = service.config.dataset_root / 'references'; folder.mkdir(parents=True, exist_ok=True)
        identifier = str(uuid.uuid4())
        (folder / (identifier + '.json')).write_text(source.model_dump_json(indent=2), encoding='utf-8')
        return dict(id=identifier, saved=True, downloaded=False)

    @api.get('/jobs/{id}')
    def job(id: str):
        with service.lock:
            if id not in service.jobs: raise HTTPException(404, '任务不存在；重启后请查看已完成分析')
            return service.jobs[id].copy()

    @api.get('/analyses/{id}/{asset}')
    def output(id: str, asset: str):
        try: path = service.asset(id, asset)
        except ValueError as exc: raise HTTPException(404, str(exc))
        return FileResponse(path, filename=asset if asset != 'ball_overlay.mp4' else None)

    return api
