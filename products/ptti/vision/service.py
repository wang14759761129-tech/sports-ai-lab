import json
import re
import threading
import traceback
import uuid
from pathlib import Path
from .runner import run_analysis, write_json
from .quality import video_metadata, classify
from .schema import Source
from .config import VisionConfig, DATA_REVISION

class DatasetManager:
    def __init__(self, config): self.config = config
    def benchmark(self):
        video = self.config.dataset_root / 'tabletennis/videos/match1_000.mp4'
        gt = self.config.dataset_root / 'tabletennis/all/match1/csv/000_ball.csv'
        if not video.is_file() or not gt.is_file(): raise ValueError('官方小样本尚未安装')
        return video, gt, Source(type='racketvision', rights='research', provider='linfeng302/RacketVision',
                                 source_id='tabletennis/match1/000', rights_notes='Dataset revision ' + DATA_REVISION)

class VisionService:
    def __init__(self, config=None):
        self.config = config or VisionConfig.load()
        self.jobs = {}; self.lock = threading.Lock(); self.active = None
        self.config.output_root.mkdir(parents=True, exist_ok=True)

    def inspect(self, video):
        metadata = video_metadata(video)
        return dict(video=metadata, quality=classify(metadata))

    def submit(self, video, source, gt=None, device='cuda', on_update=None):
        source = Source.model_validate(source).model_dump()
        if device not in ('cuda', 'cpu'): raise ValueError('Invalid processing device')
        with self.lock:
            if self.active: raise ValueError('已有视觉任务正在处理，请等待完成')
            job_id = str(uuid.uuid4()); self.active = job_id
            self.jobs[job_id] = dict(id=job_id, status='running', stage='等待读取视频', result=None, error=None)
            initial=self.jobs[job_id].copy()
        if on_update:
            try:on_update(initial)
            except Exception:
                with self.lock:
                    self.jobs.pop(job_id,None)
                    self.active=None
                raise
        def execute():
            try:
                def stage(value):
                    with self.lock: self.jobs[job_id]['stage'] = value
                result = run_analysis(video, source, gt, self.config, device, stage)
                with self.lock:
                    self.jobs[job_id].update(status='complete', stage='完成', result=result)
                    snapshot=self.jobs[job_id].copy()
                if on_update:on_update(snapshot)
            except Exception as exc:
                log = self.config.output_root / ('error-' + job_id + '.log')
                log.write_text(traceback.format_exc(), encoding='utf-8')
                with self.lock:
                    self.jobs[job_id].update(status='failed', stage='处理未完成', error=str(exc), technical_log=log.name)
                    snapshot=self.jobs[job_id].copy()
                if on_update:on_update(snapshot)
            finally:
                with self.lock: self.active = None
        threading.Thread(target=execute, daemon=True).start()
        return self.jobs[job_id].copy()

    def list_results(self):
        return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(self.config.output_root.glob('*/analysis.json'), reverse=True)]

    def asset(self, analysis_id, name):
        if not re.fullmatch(r'[0-9]{8}T[0-9]{6}_[a-f0-9]{12}', analysis_id): raise ValueError('Invalid analysis ID')
        if name not in {'ball_track.json', 'ball_track.csv', 'analysis.json', 'metrics.json', 'report.html',
                        'benchmark_report.html', 'ball_overlay.mp4'}: raise ValueError('Invalid asset')
        path = self.config.output_root / analysis_id / name
        if not path.is_file(): raise ValueError('Analysis asset unavailable')
        return path
