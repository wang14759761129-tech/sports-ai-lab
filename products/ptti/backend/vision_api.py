import json
import hashlib
import os
import secrets
import uuid
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from vision.service import VisionService, DatasetManager
from vision.config import VisionConfig
from vision.schema import Source
from vision.doctor import doctor
from backend.full_match_pipeline import FullMatchService
from backend.vision_v2 import ModuleAvailability, VisionModuleManager
from backend.scene_bootstrap import (REVIEW_ROLES, apply_review, frame_review_priority,
                                     temporal_player_presence, assign_near_far_candidates)
from backend.hybrid_scene import SCOREBOARD_MODULE
from backend.person_scene import scene_snapshot, record_review, scene_asset
from backend.fullmatch import quality_report, DEFAULT_CHUNK_SECONDS
from backend.sam2_player_tracking import (player_tracking_frame_asset, player_tracking_root,
                                          player_tracking_snapshot, player_tracking_video_asset,
                                          record_player_tracking_review)
from backend.player_tracking_closed_loop import (
    append_manual_action, closed_loop_asset, closed_loop_root, create_closed_loop_job,
    job_root as closed_loop_job_root, list_closed_loop_samples, load_job_progress,
    player_tracking_conflict_asset, queue_reacquisition, save_job_progress,
    seed_detection_dir, seed_review_asset,
)
from backend.anchor_guided_tracker import validate_mask_conflict_review
from backend.player_motion import (TRACKING_JOB_ID, load_tracking_evidence, player_motion_job_root,
                                   player_motion_root, tracking_job_path)
from backend.tracking_validation_workbench import (list_tracking_window_reviews,
                                                   record_tracking_window_review)
from backend.player_motion_api import router as player_motion_api_router

_CLOSED_LOOP_PROCESS_LOCK = __import__('threading').RLock()
_CLOSED_LOOP_PROCESSES = {}
_PLAYER_MOTION_PROCESS_LOCK = __import__('threading').RLock()
_PLAYER_MOTION_PROCESSES = {}


def closed_loop_worker_paths():
    product_root = _worker_product_root()
    script = product_root/'vision_worker'/'player_tracking_closed_loop.py'
    local = Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))
    python = local/'PTTI-Dev'/'vision-v2-sam2'/'venv'/'Scripts'/'python.exe'
    if not script.is_file() or not python.is_file():
        raise HTTPException(503, '隔离追踪 worker 或 GPU 运行环境不可用。')
    return product_root, script, python


def launch_closed_loop_worker(*, python, script, job_id, product_root, env, stdout):
    return subprocess.Popen(
        [str(python), str(script), 'track', '--job-id', job_id],
        cwd=str(product_root), env=env, stdout=stdout, stderr=subprocess.STDOUT,
        **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))


def anchor_guided_worker_paths():
    product_root = _worker_product_root()
    script = product_root/'vision_worker'/'anchor_guided_player_tracker.py'
    local = Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))
    python = local/'PTTI-Dev'/'vision-v2-sam2'/'venv'/'Scripts'/'python.exe'
    if not script.is_file() or not python.is_file():
        raise HTTPException(503, '锚点追踪 worker 或隔离 GPU 运行环境不可用。')
    return product_root, script, python


def player_motion_worker_paths():
    product_root = _worker_product_root()
    script = product_root/'vision_worker'/'player_motion_rtmpose.py'
    runtime = player_motion_root()/'venv'/'Scripts'/'python.exe'
    model = player_motion_root()/'models'/'rtmpose-m-halpe26.onnx'
    if not script.is_file() or not runtime.is_file() or not model.is_file():
        raise HTTPException(503, '隔离姿态运行环境或模型权重尚未准备好。')
    return product_root, script, runtime


def _worker_product_root():
    """Resolve source files for the isolated worker, including in a frozen preview.

    PyInstaller stores the desktop server's Python modules inside its archive;
    an external GPU Python process cannot import those archived modules. A
    development preview therefore points PTTI_VISION_HOME at the matching
    local checkout through its build metadata. Source runs keep using this
    package's product directory.
    """
    configured = os.environ.get('PTTI_VISION_HOME')
    product_root = Path(configured).resolve() if configured else Path(__file__).resolve().parents[1]
    if not (product_root/'vision_worker').is_dir():
        raise HTTPException(503, '本机隔离追踪代码目录不可用。')
    return product_root


def launch_anchor_guided_worker(*, python, script, job_id, interval_seconds, product_root, env, stdout):
    return subprocess.Popen(
        [str(python), str(script), 'track', '--job-id', job_id,
         '--interval-seconds', str(interval_seconds)],
        cwd=str(product_root), env=env, stdout=stdout, stderr=subprocess.STDOUT,
        **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))


def launch_anchor_guided_review_worker(*, python, script, job_id, event_id, role,
                                       choice, action_id, bbox, product_root, env, stdout):
    command = [str(python), str(script), 'resolve-conflict', '--job-id', job_id,
               '--event-id', event_id, '--role', role, '--choice', choice,
               '--action-id', action_id]
    if bbox is not None:
        command += ['--bbox', *[str(value) for value in bbox]]
    return subprocess.Popen(command, cwd=str(product_root), env=env, stdout=stdout,
                            stderr=subprocess.STDOUT,
                            **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))

class BenchmarkRequest(BaseModel):
    device: str = 'cuda'

class SceneReviewRequest(BaseModel):
    candidate_id: str
    action: str
    role: str | None = None

class PersonSceneReviewRequest(BaseModel):
    frame_id: str
    action: str
    candidate_id: str | None = None
    role: str | None = None

class PlayerTrackingReviewRequest(BaseModel):
    action: str
    note: str = ''

class ClosedLoopSeedDetectionRequest(BaseModel):
    sample_id: str
    frame_index: int = Field(ge=0)

class ClosedLoopStartRequest(BaseModel):
    sample_id: str
    frame_index: int = Field(ge=0)
    detection_set_id: str
    near_candidate_id: str
    far_candidate_id: str
    user_confirmed: bool
    near_bbox: list[float] | None = None
    far_bbox: list[float] | None = None
    athlete_mapping: dict[str, str] | None = None
    candidate_review: dict[str, str] | None = None
    tracking_architecture: Literal['CLOSED_LOOP_SINGLE_SEED', 'DETECTION_ANCHORED_MASK_TRACKING'] = 'CLOSED_LOOP_SINGLE_SEED'
    anchor_interval_seconds: float = Field(default=1.0, gt=0, le=2.0)

class ClosedLoopReacquisitionRequest(BaseModel):
    role: str
    candidate_id: str

class PlayerTrackingConflictReviewRequest(BaseModel):
    event_id: str
    role: str
    choice: Literal['FORWARD', 'REVERSE', 'NEITHER', 'REBOX']
    bbox: list[float] | None = None

class PlayerTrackingOutOfFrameReviewRequest(BaseModel):
    event_id: str
    role: str
    confirm_out_of_frame: bool

class PlayerMotionReviewRequest(BaseModel):
    tracking_job_id: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    role: Literal['NEAR_PLAYER', 'FAR_PLAYER']
    visibility: Literal['VISIBLE', 'PARTIAL', 'OUT_OF_FRAME', 'UNKNOWN']
    identity: Literal['NEAR_PLAYER', 'FAR_PLAYER', 'UNCERTAIN']
    track_quality: Literal['GOOD', 'BAD', 'UNKNOWN']

def router(repo=None, data_root=None):
    api = APIRouter(prefix='/api/vision')
    api.include_router(player_motion_api_router())
    config=VisionConfig.load()
    if data_root is not None:
        vision_root=Path(data_root)/'vision'
        config.cache_root=vision_root/'cache'
        config.output_root=vision_root/'outputs'
        (vision_root/'user_uploads').mkdir(parents=True,exist_ok=True)
    service = VisionService(config)
    linked_jobs={}
    full_match_service=FullMatchService(repo,data_root,config) if repo is not None and data_root is not None else None

    def scene_bootstrap_root():
        # Research assets are deliberately independent from any selected DB root.
        # The standard preview/prod process can only view the explicit Dev QA area.
        import os
        local=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local')).resolve()
        return local/'PTTI-Dev'/'vision-v2'/'scene-bootstrap'

    def sam2_player_tracking_root():
        # Player-tracking research outputs are isolated from every SQLite root.
        return player_tracking_root(os.environ.get('LOCALAPPDATA'))

    def person_review_path():
        if os.environ.get('PTTI_ENV')=='test' and data_root is not None:
            import tempfile
            qa_root=Path(data_root).resolve()
            if not qa_root.is_relative_to(Path(tempfile.gettempdir()).resolve()):
                raise ValueError('PERSON_QA_REVIEW_OUTSIDE_OS_TEMP')
            return qa_root/'person_detector_reviews.json'
        return None

    @api.get('/v2/person-detection')
    def person_detection():
        try:return scene_snapshot(scene_bootstrap_root(),reviews_path=person_review_path())
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(409,'人物识别结果与当前配置不一致，需重新检查研究记录。') from exc

    @api.get('/v2/person-detection/assets/{asset_name}')
    def person_detection_asset(asset_name:str):
        try:path=scene_asset(scene_bootstrap_root(),asset_name)
        except ValueError as exc:raise HTTPException(404,'样本画面不存在') from exc
        if not path.is_file():raise HTTPException(404,'样本画面不存在')
        return FileResponse(path,media_type='image/jpeg')

    @api.post('/v2/person-detection/reviews')
    def person_detection_review(value:PersonSceneReviewRequest):
        try:return record_review(scene_bootstrap_root(),**value.model_dump(),reviews_path=person_review_path(),
                                 source='QA_UI' if os.environ.get('PTTI_ENV')=='test' else 'USER_UI')
        except KeyError as exc:raise HTTPException(404,'样本帧或检测框不存在') from exc
        except (OSError, ValueError, TypeError) as exc:raise HTTPException(422,'请选择有效操作，或检查研究结果配置。') from exc

    @api.get('/v2/player-tracking')
    def sam2_player_tracking():
        try:
            return player_tracking_snapshot(sam2_player_tracking_root())
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(409, '球员追踪结果无法通过来源与时间轴校验。') from exc

    @api.get('/v2/player-tracking/assets/{asset_name}')
    def sam2_player_tracking_asset(asset_name: str):
        try:
            path = player_tracking_video_asset(sam2_player_tracking_root(), asset_name)
        except ValueError as exc:
            raise HTTPException(404, '追踪预览不存在。') from exc
        if not path.is_file():
            raise HTTPException(404, '追踪预览不存在。')
        return FileResponse(path, media_type='video/mp4')

    @api.get('/v2/player-tracking/frames/{frame}/{view}')
    def sam2_player_tracking_frame(frame: int, view: str):
        try:
            path = player_tracking_frame_asset(sam2_player_tracking_root(), frame, view)
        except ValueError as exc:
            raise HTTPException(404, '追踪帧不存在。') from exc
        if not path.is_file():
            raise HTTPException(404, '追踪帧不存在。')
        return FileResponse(path, media_type='image/jpeg')

    @api.post('/v2/player-tracking/reviews')
    def sam2_player_tracking_review(value: PlayerTrackingReviewRequest):
        try:
            return record_player_tracking_review(sam2_player_tracking_root(), **value.model_dump())
        except ValueError as exc:
            raise HTTPException(422, '请选择有效复核操作。') from exc
        except (OSError, KeyError, TypeError) as exc:
            raise HTTPException(409, '追踪结果不可用，复核没有保存。') from exc

    def closed_loop_local_root():
        return Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))

    def closed_loop_worker():
        return closed_loop_worker_paths()

    @api.get('/v2/player-tracking/closed-loop/samples')
    def closed_loop_samples():
        try:
            samples = list_closed_loop_samples(closed_loop_local_root())
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(409, '研究视频未通过许可、来源或 SHA256 校验。') from exc
        return {'status': 'READY' if samples else 'NO_AUTHORIZED_SAMPLES',
                'samples': [{key: value for key, value in item.items() if key != 'video_path'}
                            for item in samples],
                'dataset': 'Extended OpenTTGames', 'rights': 'CC BY-NC-SA 4.0 research/non-commercial',
                'commercial_use': False, 'production_database': 'NOT_ACCESSED'}

    @api.post('/v2/player-tracking/closed-loop/seed-detections')
    def closed_loop_seed_detections(value: ClosedLoopSeedDetectionRequest):
        try:
            samples = list_closed_loop_samples(closed_loop_local_root())
            sample = next((item for item in samples if item['sample_id'] == value.sample_id), None)
            if sample is None or value.frame_index >= sample['frames']:
                raise ValueError('AUTHORIZED_TRAIN_SAMPLE_UNAVAILABLE_OR_FRAME_OUT_OF_RANGE')
            detection_set_id = secrets.token_hex(32)
            product_root, script, python = closed_loop_worker()
            env = dict(os.environ)
            env['PTTI_PRODUCT_ROOT'] = str(product_root)
            env['PYTHONUTF8'] = '1'
            process = subprocess.run(
                [str(python), str(script), 'detect-seed', '--sample-id', value.sample_id,
                 '--frame', str(value.frame_index), '--detection-set-id', detection_set_id],
                cwd=str(product_root), env=env, capture_output=True, text=True, timeout=180,
                **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))
            if process.returncode:
                raise RuntimeError(process.stderr[-1000:] or process.stdout[-1000:] or 'RTDETR_SEED_DETECTION_FAILED')
            folder = seed_detection_dir(value.sample_id, value.frame_index, detection_set_id, closed_loop_local_root())
            detections = json.loads((folder/'detections.json').read_text(encoding='utf-8'))
            if detections.get('clip_sha256') != sample['clip_sha256']:
                raise ValueError('SEED_SOURCE_SHA_MISMATCH')
            return {'status': 'DETECTIONS_READY', 'sample_id': value.sample_id,
                    'frame_index': value.frame_index, 'detection_set_id': detection_set_id,
                    'timestamp_ms': round((sample['start_seconds'] + value.frame_index/sample['sample_fps'])*1000),
                    'detections': detections['detections'], 'runtime': detections['runtime'],
                    'detector': detections['detector'], 'image_url':
                        f"/api/vision/v2/player-tracking/closed-loop/seed-assets/{value.sample_id}/{value.frame_index}/{detection_set_id}/overlay",
                    'source_image_url':
                        f"/api/vision/v2/player-tracking/closed-loop/seed-assets/{value.sample_id}/{value.frame_index}/{detection_set_id}/source",
                    'production_database': 'NOT_ACCESSED'}
        except HTTPException:
            raise
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(504, 'RT-DETR 初始化或检测超时；追踪尚未开始。') from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, '授权研究片段或检测结果不存在。') from exc
        except RuntimeError as exc:
            raise HTTPException(503, 'RT-DETR 种子检测失败；追踪尚未开始。') from exc
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422, '请选择有效片段和画面，并重新运行人物检测。') from exc

    @api.get('/v2/player-tracking/closed-loop/seed-assets/{sample_id}/{frame_index}/{detection_set_id}/{view}')
    def closed_loop_seed_asset(sample_id: str, frame_index: int, detection_set_id: str, view: str):
        try:
            path = seed_review_asset(sample_id, frame_index, detection_set_id, view, closed_loop_local_root())
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(404, '种子复核画面不存在。') from exc
        if not path.is_file():
            raise HTTPException(404, '种子复核画面不存在。')
        return FileResponse(path, media_type='image/jpeg')

    @api.post('/v2/player-tracking/closed-loop/jobs')
    def start_closed_loop(value: ClosedLoopStartRequest):
        try:
            job_id, root, seed = create_closed_loop_job(
                sample_id=value.sample_id, frame_index=value.frame_index,
                detection_set_id=value.detection_set_id,
                near_candidate_id=value.near_candidate_id,
                far_candidate_id=value.far_candidate_id,
                user_confirmed=value.user_confirmed, near_bbox=value.near_bbox,
                far_bbox=value.far_bbox, athlete_mapping=value.athlete_mapping,
                candidate_review=value.candidate_review,
                tracking_architecture=value.tracking_architecture,
                anchor_interval_seconds=value.anchor_interval_seconds,
                localappdata=closed_loop_local_root())
            with _CLOSED_LOOP_PROCESS_LOCK:
                for old_id, old in list(_CLOSED_LOOP_PROCESSES.items()):
                    if old.poll() is not None:
                        _CLOSED_LOOP_PROCESSES.pop(old_id, None)
                if _CLOSED_LOOP_PROCESSES:
                    (root/'progress.json').write_text(json.dumps({
                        'job_id': job_id, 'sample_id': value.sample_id, 'status': 'FAILED',
                        'stage': '已有隔离 GPU 追踪任务运行；本次尚未启动。',
                        'error': 'GPU_TRACKING_JOB_ALREADY_RUNNING', 'processed_frames': 0,
                        'events': [], 'production_database': 'NOT_ACCESSED'}, ensure_ascii=False), encoding='utf-8')
                    raise HTTPException(409, '另一个球员追踪任务仍在运行，请等待完成后再开始。')
                product_root, script, python = (anchor_guided_worker_paths()
                    if value.tracking_architecture == 'DETECTION_ANCHORED_MASK_TRACKING'
                    else closed_loop_worker())
                env = dict(os.environ)
                env['PTTI_PRODUCT_ROOT'] = str(product_root)
                env['PYTHONUTF8'] = '1'
                log = (root/'worker.log').open('ab')
                try:
                    if value.tracking_architecture == 'DETECTION_ANCHORED_MASK_TRACKING':
                        process = launch_anchor_guided_worker(
                            python=python, script=script, job_id=job_id,
                            interval_seconds=value.anchor_interval_seconds,
                            product_root=product_root, env=env, stdout=log)
                    else:
                        process = launch_closed_loop_worker(
                            python=python, script=script, job_id=job_id,
                            product_root=product_root, env=env, stdout=log)
                finally:
                    log.close()
                _CLOSED_LOOP_PROCESSES[job_id] = process
            return {'status': 'QUEUED', 'job_id': job_id,
                    'seed_frame': seed['seed_frame'],
                    'object_ids': {'NEAR_PLAYER': 1, 'FAR_PLAYER': 2},
                    'tracking_architecture': value.tracking_architecture,
                    'anchor_interval_seconds': value.anchor_interval_seconds,
                    'seed_source': 'USER_CONFIRMED_SEED',
                    'production_database': 'NOT_ACCESSED'}
        except HTTPException:
            raise
        except FileNotFoundError as exc:
            raise HTTPException(404, '种子检测已失效或样本不可用，请重新检测。') from exc
        except ValueError as exc:
            raise HTTPException(422, '追踪未启动：请确认两个不同人物框，并检查种子画面。') from exc
        except (OSError, RuntimeError) as exc:
            raise HTTPException(503, '隔离追踪任务无法启动；请检查研究版 GPU worker。') from exc

    @api.get('/v2/player-tracking/closed-loop/jobs/{job_id}')
    def closed_loop_job_status(job_id: str):
        try:
            progress = load_job_progress(job_id, closed_loop_local_root())
            if progress.get('status') == 'NEEDS_USER_CONFIRMATION':
                candidates_path = closed_loop_job_root(job_id, closed_loop_local_root())/'review_candidates.json'
                if candidates_path.is_file():
                    progress['review_candidates'] = json.loads(candidates_path.read_text(encoding='utf-8'))
            result_path = closed_loop_job_root(job_id, closed_loop_local_root())/'tracking.json'
            progress['result_available'] = result_path.is_file()
            return progress
        except FileNotFoundError as exc:
            raise HTTPException(404, '追踪任务不存在。') from exc
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(409, '追踪任务状态文件无法校验。') from exc

    @api.get('/v2/player-tracking/closed-loop/jobs/{job_id}/conflicts/{event_id}/{view}')
    def closed_loop_conflict_asset(job_id: str, event_id: str, view: str):
        try:
            path = player_tracking_conflict_asset(job_id, event_id, view, closed_loop_local_root())
        except ValueError as exc:
            raise HTTPException(404, '冲突复核画面不存在。') from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, '冲突复核画面尚未生成。') from exc
        if not path.is_file():
            raise HTTPException(404, '冲突复核画面尚未生成。')
        return FileResponse(path, media_type='image/jpeg')

    @api.post('/v2/player-tracking/closed-loop/jobs/{job_id}/conflicts')
    def closed_loop_mask_conflict_review(job_id: str, value: PlayerTrackingConflictReviewRequest):
        try:
            root = closed_loop_job_root(job_id, closed_loop_local_root())
            progress = load_job_progress(job_id, closed_loop_local_root())
            if progress.get('status') != 'COMPLETE':
                raise ValueError('TRACKING_JOB_NOT_READY_FOR_CONFLICT_REVIEW')
            manifest_path = root/'tracking.json'
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            if manifest.get('tracking_architecture') not in {None, 'DETECTION_ANCHORED_MASK_TRACKING'}:
                raise ValueError('MASK_CONFLICT_REVIEW_REQUIRES_ANCHOR_GUIDED_TRACKING')
            event = next((row for row in manifest.get('events', [])
                          if row.get('event_id') == value.event_id and row.get('type') == 'MASK_CONFLICT'), None)
            if event is None:
                raise ValueError('MASK_CONFLICT_NOT_FOUND')
            sample = next((row for row in list_closed_loop_samples(closed_loop_local_root())
                           if row['sample_id'] == manifest.get('sample_id')), None)
            if sample is None or sample['clip_sha256'] != manifest.get('source_sha256'):
                raise ValueError('MASK_CONFLICT_SOURCE_NOT_VERIFIED')
            selection = validate_mask_conflict_review(
                event=event, role=value.role, choice=value.choice, bbox=value.bbox,
                frame_size=(sample['width'], sample['height']))
            if value.choice == 'NEITHER':
                action = append_manual_action(
                    job_id=job_id, action='mask_choice',
                    details={**selection, 'status': 'NEEDS_REBOX'},
                    source='QA_UI' if os.environ.get('PTTI_ENV') == 'test' else 'USER_UI',
                    localappdata=closed_loop_local_root())
                event['last_review_action'] = {**selection, 'action_id': action['action_id'],
                                              'status': 'NEEDS_REBOX', 'timestamp': action['timestamp']}
                from backend.player_tracking_closed_loop import atomic_json
                atomic_json(manifest_path, manifest)
                progress['events'] = manifest['events']
                action_log = json.loads((root/'manual-actions.json').read_text(encoding='utf-8'))
                from backend.anchor_guided_tracker import summarize_manual_actions
                progress['manual_actions'] = summarize_manual_actions(
                    action_log['actions'], float(manifest['duration_seconds']))
                save_job_progress(job_id, progress, closed_loop_local_root())
                return {'status': 'NEEDS_REBOX', 'event_id': value.event_id,
                        'action_id': action['action_id'], 'production_database': 'NOT_ACCESSED'}

            with _CLOSED_LOOP_PROCESS_LOCK:
                for old_id, old in list(_CLOSED_LOOP_PROCESSES.items()):
                    if old.poll() is not None:
                        _CLOSED_LOOP_PROCESSES.pop(old_id, None)
                if any(proc.poll() is None for proc in _CLOSED_LOOP_PROCESSES.values()):
                    raise ValueError('GPU_TRACKING_JOB_ALREADY_RUNNING')
                action_type = 'manual_rebox' if value.choice == 'REBOX' else 'mask_choice'
                action = append_manual_action(
                    job_id=job_id, action=action_type,
                    details={**selection, 'status': 'QUEUED'},
                    source='QA_UI' if os.environ.get('PTTI_ENV') == 'test' else 'USER_UI',
                    localappdata=closed_loop_local_root())
                product_root, script, python = anchor_guided_worker_paths()
                env = dict(os.environ)
                env['PTTI_PRODUCT_ROOT'] = str(product_root)
                env['PYTHONUTF8'] = '1'
                event['last_review_action'] = {**selection, 'action_id': action['action_id'],
                                               'status': 'RUNNING', 'timestamp': action['timestamp']}
                from backend.player_tracking_closed_loop import atomic_json
                atomic_json(manifest_path, manifest)
                progress.update({'status': 'RUNNING_REVIEW', 'stage': '正在局部重跑冲突区间',
                                 'review_event_id': value.event_id, 'review_action_id': action['action_id']})
                save_job_progress(job_id, progress, closed_loop_local_root())
                log = (root/'worker.log').open('ab')
                try:
                    process = launch_anchor_guided_review_worker(
                        python=python, script=script, job_id=job_id,
                        event_id=value.event_id, role=value.role, choice=value.choice,
                        action_id=action['action_id'], bbox=value.bbox,
                        product_root=product_root, env=env, stdout=log)
                finally:
                    log.close()
                _CLOSED_LOOP_PROCESSES[job_id] = process
            return {'status': 'QUEUED', 'event_id': value.event_id,
                    'action_id': action['action_id'], 'choice': value.choice,
                    'production_database': 'NOT_ACCESSED'}
        except HTTPException:
            raise
        except ValueError as exc:
            raise HTTPException(409, '当前冲突不能按此选择处理；请刷新复核项后重试。') from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, '追踪结果或授权训练片段不可用。') from exc
        except (OSError, RuntimeError, KeyError, TypeError) as exc:
            raise HTTPException(503, '冲突局部重跑无法启动；原始前后向证据仍保留。') from exc

    @api.post('/v2/player-tracking/closed-loop/jobs/{job_id}/out-of-frame-reviews')
    def closed_loop_out_of_frame_review(job_id: str, value: PlayerTrackingOutOfFrameReviewRequest):
        try:
            root = closed_loop_job_root(job_id, closed_loop_local_root())
            manifest_path = root/'tracking.json'
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            event = next((row for row in manifest.get('events', [])
                          if row.get('event_id') == value.event_id
                          and row.get('type') in {'OUT_OF_FRAME', 'IDENTITY_UNCERTAIN'}), None)
            if event is None or event.get('role') != value.role:
                raise ValueError('OUT_OF_FRAME_EVENT_NOT_FOUND')
            action = append_manual_action(
                job_id=job_id, action='out_of_frame_confirm',
                details={'event_id': value.event_id,
                         'decision': 'OUT_OF_FRAME' if value.confirm_out_of_frame else 'IDENTITY_UNCERTAIN'},
                source='QA_UI' if os.environ.get('PTTI_ENV') == 'test' else 'USER_UI',
                localappdata=closed_loop_local_root())
            if value.confirm_out_of_frame:
                event.update({'type': 'OUT_OF_FRAME', 'classification': 'OUT_OF_FRAME',
                              'confidence_level': 'HIGH', 'status': 'CONFIRMED',
                              'human_confirmation': {'source': action['source'],
                                                     'timestamp': action['timestamp']}})
            else:
                event.update({'type': 'IDENTITY_UNCERTAIN', 'classification': 'UNKNOWN',
                              'confidence_level': 'LOW', 'status': 'REVIEW_REQUIRED',
                              'human_confirmation': {'source': action['source'],
                                                     'timestamp': action['timestamp']}})
            from backend.player_tracking_closed_loop import atomic_json
            atomic_json(manifest_path, manifest)
            progress = load_job_progress(job_id, closed_loop_local_root())
            progress['events'] = manifest['events']
            action_log = json.loads((root/'manual-actions.json').read_text(encoding='utf-8'))
            from backend.anchor_guided_tracker import summarize_manual_actions
            progress['manual_actions'] = summarize_manual_actions(
                action_log['actions'], float(manifest['duration_seconds']))
            save_job_progress(job_id, progress, closed_loop_local_root())
            return {'status': event['status'], 'event_id': value.event_id,
                    'classification': event['classification'],
                    'production_database': 'NOT_ACCESSED'}
        except ValueError as exc:
            raise HTTPException(404, '画外复核事件不存在或身份不匹配。') from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, '追踪结果不存在。') from exc
        except (OSError, KeyError, TypeError) as exc:
            raise HTTPException(409, '画外复核没有保存。') from exc

    @api.post('/v2/player-tracking/closed-loop/jobs/{job_id}/reacquisitions')
    def closed_loop_reacquisition(job_id: str, value: ClosedLoopReacquisitionRequest):
        try:
            return queue_reacquisition(job_id=job_id, role=value.role,
                                       candidate_id=value.candidate_id,
                                       localappdata=closed_loop_local_root())
        except FileNotFoundError as exc:
            raise HTTPException(404, '追踪异常候选当前不可用。') from exc
        except ValueError as exc:
            raise HTTPException(409, '追踪未处于等待人工重新确认状态，未发送操作。') from exc

    @api.get('/v2/player-tracking/closed-loop/jobs/{job_id}/assets/{asset_name:path}')
    def closed_loop_job_asset(job_id: str, asset_name: str):
        try:
            path = closed_loop_asset(job_id, asset_name, closed_loop_local_root())
        except ValueError as exc:
            raise HTTPException(404, '追踪预览不存在。') from exc
        if not path.is_file():
            raise HTTPException(404, '追踪预览尚未生成。')
        media = 'video/mp4' if path.suffix.lower() == '.mp4' else ('image/png' if path.suffix.lower() == '.png' else 'image/jpeg')
        return FileResponse(path, media_type=media)

    @api.get('/v2/scene-bootstrap')
    def scene_bootstrap_results():
        root=scene_bootstrap_root()
        path=root/'scene_bootstrap.json'
        if not path.is_file():
            return {'status':'NOT_RUN','dataset':'Extended OpenTTGames','commercial_use':False,
                    'rights':'CC BY-NC-SA 4.0','keyframes':[],'detections':[],
                    'message':'真实场景识别尚未运行；BallTrack 与本研究样本相互独立。'}
        try:
            result=json.loads(path.read_text(encoding='utf-8'))
            comparison=root/'scene_bootstrap_prompt_comparison.json'
            if comparison.is_file():
                try:result['prompt_comparison']=json.loads(comparison.read_text(encoding='utf-8'))
                except (OSError,ValueError):result['prompt_comparison']={'status':'UNAVAILABLE'}
            review_path=root/'reviews.json'
            corrections=json.loads(review_path.read_text(encoding='utf-8')) if review_path.is_file() else []
            result['detections']=apply_review(result.get('detections',[]),corrections)
            by_frame={}
            for candidate in result['detections']:
                by_frame.setdefault(candidate['frame'],[]).append(candidate)
            for frame in result.get('keyframes',[]):
                frame['detections']=by_frame.get(frame['frame'],[])
                table = max((d for d in frame['detections'] if 'table' in d.get('label','').casefold()
                             and not d.get('visualization_suppressed')
                             and d['bbox'][2]-d['bbox'][0] >= frame.get('width',1)*0.2
                             and (d['bbox'][2]-d['bbox'][0])*(d['bbox'][3]-d['bbox'][1]) >= frame.get('width',1)*frame.get('height',1)*0.03),
                            key=lambda d: d.get('detector_score',0), default=None)
                if table:
                    frame['detections'] = assign_near_far_candidates(frame['detections'], table['bbox'])
                frame['review'] = frame_review_priority(
                    frame['detections'], image_size=(frame.get('width', 1), frame.get('height', 1)))
            result['keyframes'] = temporal_player_presence(result.get('keyframes', []))
            result['reviews_count']=len(corrections)
            evaluation=root/'scene_bootstrap_eval_manifest.json'
            detector_comparison={
                'grounding_dino':{'baseline_id':'GROUNDING_DINO_PLAYER_BASELINE','status':'BASELINE_FROZEN',
                                  'sampled_frames':0,'both_player_candidate_frames':0,
                                  'candidate_coverage_percent':None,'per_game':{},
                                  'metrics_note':'候选覆盖率不是人工标注的检测召回率。'},
                'rtmdet':{'status':'NOT_RUN_RUNTIME_NOT_INSTALLED','model':'rtmdet_tiny_8xb32-300e_coco',
                          'runtime':'vision-v2-openmmlab','result_frames':0},
            }
            detector_comparison['rtmdet']['experiment_status']='RTMDET_RUNTIME_BLOCKED'
            person_report=root/'person_detector_evaluation.json'
            if person_report.is_file():
                try:
                    person=scene_snapshot(root)
                    detector_comparison['rtdetr']={'status':person['status'],'model':person.get('model'),
                        'development':person.get('development'),'validation':person.get('validation'),
                        'person_gate':person.get('person_gate')}
                except (OSError,ValueError,KeyError,TypeError):
                    detector_comparison['rtdetr']={'status':'RESULT_UNAVAILABLE'}
            openmmlab_root=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'PTTI-Dev'/'vision-v2-openmmlab'
            rtmdet_python=openmmlab_root/'.venv'/'Scripts'/'python.exe'
            rtmdet_checkpoint=openmmlab_root/'models'/'rtmdet_tiny_8xb32-300e_coco_20220902_112414-78e30dcc.pth'
            rtmdet_config=openmmlab_root/'configs'/'rtmdet_tiny_8xb32-300e_coco.py'
            if rtmdet_python.is_file() and not rtmdet_checkpoint.is_file():
                detector_comparison['rtmdet']['status']='NOT_RUN_CHECKPOINT_MISSING'
            elif rtmdet_python.is_file() and rtmdet_checkpoint.is_file() and not rtmdet_config.is_file():
                detector_comparison['rtmdet']['status']='NOT_RUN_CONFIG_MISSING'
            elif rtmdet_python.is_file() and rtmdet_checkpoint.is_file() and rtmdet_config.is_file():
                detector_comparison['rtmdet']['status']='RUNTIME_READY_NOT_EVALUATED'
            if evaluation.is_file():
                try:
                    manifest=json.loads(evaluation.read_text(encoding='utf-8'))
                    eval_review_path=root/'scene_bootstrap_eval_reviews.json'
                    try:eval_reviews=json.loads(eval_review_path.read_text(encoding='utf-8')) if eval_review_path.is_file() else []
                    except (OSError,ValueError):eval_reviews=[]
                    eval_frames=[]
                    for item in manifest.get('frame_results',[]):
                        if item.get('prompt_id') != 'official_bootstrap_a':
                            continue
                        game=item.get('game');slot=int(item.get('slot',0))
                        if game not in {f'game_{i}' for i in range(1,6)} or not 1 <= slot <= 99:
                            continue
                        detections=apply_review(item.get('detections',[]),eval_reviews)
                        table=item.get('selected_table_bbox')
                        if table:
                            detections=assign_near_far_candidates(detections,table)
                        eval_frames.append({
                            'game':game,'slot':slot,'timestamp_ms':round(item.get('timestamp_seconds',0)*1000),
                            'image_asset':f'{game}-sample-{slot:02d}.jpg',
                            'overlay_asset':item.get('overlay_asset'),
                            'width':item.get('width'),'height':item.get('height'),
                            'table_found':item.get('table_found'),
                            'both_player_candidates':item.get('both_player_candidates'),
                            'review':frame_review_priority(detections,image_size=(item.get('width',1),item.get('height',1))),
                            'detections':detections,
                        })
                    result['multi_match_evaluation']={
                        'status':manifest.get('status'), 'dataset':manifest.get('dataset'),
                        'license':manifest.get('license'), 'official_split':manifest.get('official_split'),
                        'games':manifest.get('games',[]), 'prompt_summary':manifest.get('prompt_summary',{}),
                        'keyframes':eval_frames,'video_sha256_note':manifest.get('video_sha256_note'),
                    }
                    baseline=manifest.get('prompt_summary',{}).get('official_bootstrap_a',{})
                    detector_comparison['grounding_dino']={
                        'baseline_id':'GROUNDING_DINO_PLAYER_BASELINE',
                        'status':'BASELINE_FROZEN',
                        'sampled_frames':baseline.get('sampled_frames',0),
                        'both_player_candidate_frames':baseline.get('both_player_candidate_frames',0),
                        'candidate_coverage_percent':baseline.get('both_player_candidate_coverage_percent'),
                        'per_game':baseline.get('per_game',{}),
                        'manifest_sha256':hashlib.sha256(evaluation.read_bytes()).hexdigest(),
                        'metrics_note':'候选覆盖率不是人工标注的检测召回率。',
                    }
                except (OSError,ValueError):
                    result['multi_match_evaluation']={'status':'UNAVAILABLE'}
            result['hybrid_scene']={
                'name':'Hybrid Scene Engine',
                'table':{'detector':'Grounding DINO','status':'TABLE_BOOTSTRAP_READY_FOR_SEGMENTATION',
                         'candidate_coverage_frames':'20/20'},
                'person_detectors':detector_comparison,
                'scoreboard':{'status':SCOREBOARD_MODULE.status,'blocks_scene_gate':SCOREBOARD_MODULE.blocks_scene_gate,
                              'message':'记分牌功能尚未实现；不阻止球台/人物 Gate。'},
                'pose_adapter':{'status':'INPUT_SCHEMA_ONLY_NOT_INFERRED'},
                'player_gate':'PLAYER_DETECTION_PARTIAL',
                'scene_gate':'SCENE_BOOTSTRAP_PARTIAL',
            }
            return result
        except (OSError,ValueError,TypeError) as exc:
            raise HTTPException(500,'场景识别结果文件无法读取') from exc

    @api.get('/v2/scene-bootstrap/assets/{asset_name}')
    def scene_bootstrap_asset(asset_name:str):
        import re
        eval_match=re.fullmatch(r'(game_[1-5])-(overlay-)?sample-(\d{2})\.jpg',asset_name)
        if not re.fullmatch(r'(?:frame-\d{6}\.jpg|overlay-frame-\d{6}\.jpg)',asset_name) and not eval_match:
            raise HTTPException(404,'场景识别图像不存在')
        root=scene_bootstrap_root()
        if eval_match:
            game,overlay,slot=eval_match.groups()
            filename=('overlay-' if overlay else '')+f'sample-{slot}.jpg'
            path=root/'multi-match-frames'/game/filename
        elif asset_name.startswith('overlay-frame-'):
            path=root/'scene_bootstrap_overlay'/asset_name
        else:
            path=root/'frames'/asset_name
        if not path.is_file():raise HTTPException(404,'场景识别图像不存在')
        return FileResponse(path,media_type='image/jpeg')

    @api.post('/v2/scene-bootstrap/reviews')
    def scene_bootstrap_review(value:SceneReviewRequest):
        if value.action not in {'SET_ROLE','REJECT'} or (value.action=='SET_ROLE' and value.role not in REVIEW_ROLES):
            raise HTTPException(422,'请选择有效的人工修正操作')
        root=scene_bootstrap_root();result_file=root/'scene_bootstrap.json'
        if not result_file.is_file():raise HTTPException(409,'尚无可修正的场景识别结果')
        try:result=json.loads(result_file.read_text(encoding='utf-8'))
        except (OSError,ValueError) as exc:raise HTTPException(500,'场景识别结果文件无法读取') from exc
        is_eval_candidate=False
        evaluation=root/'scene_bootstrap_eval_manifest.json'
        if evaluation.is_file():
            try:
                manifest=json.loads(evaluation.read_text(encoding='utf-8'))
                is_eval_candidate=any(item.get('prompt_id')=='official_bootstrap_a' and
                                      any(candidate.get('candidate_id')==value.candidate_id for candidate in item.get('detections',[]))
                                      for item in manifest.get('frame_results',[]))
            except (OSError,ValueError):
                is_eval_candidate=False
        if not is_eval_candidate and not any(x.get('candidate_id')==value.candidate_id for x in result.get('detections',[])):
            raise HTTPException(404,'检测候选不存在')
        review_file=root/('scene_bootstrap_eval_reviews.json' if is_eval_candidate else 'reviews.json')
        try:reviews=json.loads(review_file.read_text(encoding='utf-8')) if review_file.is_file() else []
        except (OSError,ValueError) as exc:raise HTTPException(500,'人工修正记录无法读取') from exc
        reviews.append({'candidate_id':value.candidate_id,'action':value.action,'role':value.role,
                        'recorded_at':datetime.now(timezone.utc).isoformat()})
        temp=review_file.with_suffix('.json.tmp')
        temp.write_text(json.dumps(reviews,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(temp,review_file)
        return {'reviews_count':len(reviews),'raw_preserved':True}

    @api.get('/research-datasets/extended-openttgames')
    def extended_openttgames_status():
        """Show locally staged research-only assets; never fetch or expose test data."""
        if data_root is None:
            raise HTTPException(503, 'Research dataset storage is unavailable')
        research_root=Path(data_root)
        requested=__import__('os').environ.get('PTTI_RESEARCH_DATA_ROOT')
        if requested:
            candidate=Path(requested).resolve()
            allowed=(Path(__import__('os').environ.get('LOCALAPPDATA',Path.home()))/'PTTI-Dev').resolve()
            if candidate==allowed:
                research_root=candidate
        root=research_root/'research-datasets'/'ExtendedOpenTTGames'
        game_dir=root/'annotations'/'train'/'game_data'
        ball_dir=root/'annotations'/'train'/'ball_data'
        video_dir=root/'videos'/'train'
        expected_sizes={"game_1":5572649632,"game_2":10833064677,"game_3":4637044123,
                        "game_4":3947371986,"game_5":4493632417}
        videos=[]
        for index in range(1,6):
            identifier=f'game_{index}';path=video_dir/f'{identifier}.mp4'
            size=path.stat().st_size if path.is_file() else None
            expected=expected_sizes[identifier]
            status='MISSING' if size is None else ('READY' if size==expected else ('PARTIAL' if size<expected else 'SIZE_MISMATCH'))
            videos.append({'id':identifier,'split':'training','status':status,
                           'size_bytes':size,'expected_size_bytes':expected})
        annotations=[]
        for index in range(1,6):
            game=game_dir/f'game_{index}.json'; ball=ball_dir/f'train_{index}.json'
            annotations.append({'id':f'game_{index}','split':'training',
                                'game_events':'READY' if game.is_file() else 'MISSING',
                                'ball_ground_truth':'READY' if ball.is_file() else 'MISSING'})
        return {'dataset':'Extended OpenTTGames','repository':'https://github.com/moamal01/table_tennis_data',
                'revision':'36471a76b969a0340df59258a813bf8214e68e7c','license':'CC BY-NC-SA 4.0',
                'usage':'Research / Non-commercial','commercial_use':False,
                'annotations_status':'READY' if all(x['game_events']=='READY' and x['ball_ground_truth']=='READY' for x in annotations) else 'PARTIAL',
                'training':{'annotations':annotations,'videos':videos},
                'test_split':{'status':'LOCKED_NOT_ACCESSED','videos':7},
                'storage_path':str(root) if root.exists() else None}

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

    @api.get('/v2/modules')
    def vision_v2_modules():
        runtime=doctor(service.config)
        worker=runtime.get('worker') or {}
        installed=worker.get('modules') or {}
        balltrack_ready=bool(runtime.get('checkpoint') and runtime.get('racketvision_commit'))
        scene_root=scene_bootstrap_root()
        scene_result=scene_root/'scene_bootstrap.json'
        scene_runtime=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'PTTI-Dev'/'vision-v2'/'venv'/'Scripts'/'python.exe'
        scene_weights=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'PTTI-Dev'/'vision-v2'/'models'/'grounding-dino-base'/'model.safetensors'
        sam2_root=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'PTTI-Dev'/'vision-v2-sam2'
        sam2_runtime=sam2_root/'venv'/'Scripts'/'python.exe'
        sam2_checkpoint=sam2_root/'checkpoints'/'sam2.1_hiera_small.pt'
        sam2_result=sam2_player_tracking_root()/'tracking.json'
        pose_root=player_motion_root(os.environ.get('LOCALAPPDATA'))
        pose_runtime=pose_root/'venv'/'Scripts'/'python.exe'
        pose_model=pose_root/'models'/'rtmpose-m-halpe26.onnx'
        pose_runtime_info={}
        try: pose_runtime_info=json.loads((pose_root/'runtime.json').read_text(encoding='utf-8'))
        except (OSError,ValueError,TypeError): pass
        pose_sessions=pose_runtime_info.get('session_providers') or []
        pose_cuda_ready=bool(pose_runtime.is_file() and pose_runtime_info.get('cuda_provider_available')
                             and (pose_runtime_info.get('cuda_session_verified') or any(
                                 'CUDAExecutionProvider' in row for row in pose_sessions if isinstance(row,list))))
        pose_model_ready=bool(pose_model.is_file() and pose_model.stat().st_size==55685444
                              and pose_runtime_info.get('onnx_sha256')=='26f3a19e61304a600dfb82d1001d41d24343b89fc70a33ffc84657e0b0bf2ecf')
        scene_integrated=scene_result.is_file()
        scene_manifest=scene_root/'scene_bootstrap_eval_manifest.json'
        scene_dependencies=scene_runtime.is_file()
        scene_checkpoint=scene_weights.is_file() and scene_weights.stat().st_size==933400872
        availability={
            'balltrack':ModuleAvailability(bool(worker.get('torch')),balltrack_ready),
            'scene-detector':ModuleAvailability(installed.get('cv2',False),checkpoint=bool(scene_result.is_file()),integrated=bool(scene_result.is_file())),
            'grounding-dino':ModuleAvailability(scene_dependencies,scene_checkpoint,integrated=scene_integrated),
            'grounding-dino-person':ModuleAvailability(scene_manifest.is_file(),scene_manifest.is_file(),integrated=scene_manifest.is_file()),
            'rtdetr-person':ModuleAvailability(scene_dependencies,
                (scene_root.parent/'models'/'rtdetr-r18vd'/'model.safetensors').is_file(),
                integrated=(scene_root/'person_detector_evaluation.json').is_file()),
            'rtmdet-person':ModuleAvailability(
                (Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'PTTI-Dev'/'vision-v2-openmmlab'/'.venv'/'Scripts'/'python.exe').is_file(),
                ((Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'PTTI-Dev'/'vision-v2-openmmlab'/'models'/'rtmdet_tiny_8xb32-300e_coco_20220902_112414-78e30dcc.pth').is_file() and
                 (Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'PTTI-Dev'/'vision-v2-openmmlab'/'configs'/'rtmdet_tiny_8xb32-300e_coco.py').is_file()),
                integrated=False),
            'scoreboard-module':ModuleAvailability(False,False,integrated=False),
            'video-segmenter':ModuleAvailability(
                sam2_runtime.is_file(),
                sam2_checkpoint.is_file() and sam2_checkpoint.stat().st_size==184416285,
                integrated=sam2_result.is_file()),
            'player-pose':ModuleAvailability(pose_cuda_ready,pose_model_ready,integrated=True),
            'scoreboard-ocr':ModuleAvailability(installed.get('paddleocr',False) and installed.get('paddle',False),False),
            'scene-classifier':ModuleAvailability(installed.get('mmaction',False),False),
            'co-tracker':ModuleAvailability(installed.get('cotracker',False),False),
        }
        availability['scene-detector']=ModuleAvailability(
            installed.get('cv2',False) or scene_integrated,
            checkpoint=scene_integrated,
            integrated=scene_integrated,
        )
        modules=[item.__dict__ | {'state':item.state.value} for item in VisionModuleManager(availability).snapshot()]
        return {'modules':modules,'runtime':worker,'policy':{'inference':'STAGED','balltrack':'FROZEN_RAW','production_database':'NOT_ACCESSED'}}

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
