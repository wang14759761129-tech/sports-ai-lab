"""Local-only API for quality-gated pose runs and tracking-truth review."""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.player_motion import (TRACKING_JOB_ID, load_tracking_evidence,
                                   list_motion_exclusions, motion_metrics,
                                   player_motion_job_root, player_motion_root,
                                   record_motion_exclusion,
                                   supports_pose_tracking_manifest)
from backend.tracking_validation_workbench import (list_tracking_window_reviews,
                                                   record_tracking_window_review)


_PROCESS_LOCK = threading.RLock()
_PROCESSES = {}
_EXPECTED_ONNX_SHA256 = "26f3a19e61304a600dfb82d1001d41d24343b89fc70a33ffc84657e0b0bf2ecf"


class PlayerMotionReviewRequest(BaseModel):
    tracking_job_id: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    role: Literal["NEAR_PLAYER", "FAR_PLAYER"]
    visibility: Literal["VISIBLE", "PARTIAL", "OUT_OF_FRAME", "UNKNOWN"]
    identity: Literal["NEAR_PLAYER", "FAR_PLAYER", "UNCERTAIN"]
    track_quality: Literal["GOOD", "BAD", "UNKNOWN"]


class MotionExclusionRequest(BaseModel):
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    role: Literal["NEAR_PLAYER", "FAR_PLAYER"]


def _local() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")).resolve()


def _worker_paths():
    configured = os.environ.get("PTTI_VISION_HOME")
    product_root = Path(configured).resolve() if configured else Path(__file__).resolve().parents[1]
    runtime_root = player_motion_root(_local())
    python = runtime_root / "venv" / "Scripts" / "python.exe"
    script = product_root / "vision_worker" / "player_motion_rtmpose.py"
    model = runtime_root / "models" / "rtmpose-m-halpe26.onnx"
    if not python.is_file() or not script.is_file() or not model.is_file():
        raise HTTPException(503, "隔离姿态运行环境或模型权重尚未准备好。")
    return product_root, script, python


def _tracking_jobs():
    base = _local() / "PTTI-Dev" / "vision-v2-sam2" / "runs" / "closed-loop" / "jobs"
    latest = {}
    if base.is_dir():
        for folder in base.iterdir():
            if not folder.is_dir() or not TRACKING_JOB_ID.fullmatch(folder.name):
                continue
            path = folder / "tracking.json"
            if not path.is_file():
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if value.get("job_id") != folder.name or not supports_pose_tracking_manifest(value):
                    continue
                row = {"tracking_job_id": folder.name, "sample_id": value.get("sample_id"),
                       "match_id": value.get("match_id"), "duration_seconds": value.get("duration_seconds"),
                       "frames": value.get("frames"), "source_sha256": value.get("source_sha256"),
                       "rights": value.get("rights"), "updated_at": folder.stat().st_mtime}
                old = latest.get(row["sample_id"])
                if old is None or row["updated_at"] > old["updated_at"]:
                    latest[row["sample_id"]] = row
            except (OSError, ValueError, TypeError):
                continue
    jobs = []
    for row in latest.values():
        root = player_motion_job_root(row["tracking_job_id"], _local())
        progress_path, result_path = root / "progress.json", root / "player_motion.json"
        state, summary = "NOT_RUN", None
        if result_path.is_file():
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
                state, summary = result.get("status", "COMPLETE"), result.get("summary")
            except (OSError, ValueError, TypeError):
                state = "CORRUPT_RESULT"
        elif progress_path.is_file():
            try:
                progress = json.loads(progress_path.read_text(encoding="utf-8"))
                state, summary = progress.get("status", "UNKNOWN"), progress.get("summary")
            except (OSError, ValueError, TypeError):
                state = "CORRUPT_STATUS"
        jobs.append({**row, "status": state, "summary": summary,
                     "result_available": result_path.is_file()})
    return sorted(jobs, key=lambda row: (row["match_id"] or "", row["sample_id"] or ""))


def router() -> APIRouter:
    api = APIRouter(prefix="/v2")

    @api.get("/player-motion")
    def snapshot():
        runtime_path = player_motion_root(_local()) / "runtime.json"
        runtime = {}
        if runtime_path.is_file():
            try:
                runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                runtime = {"status": "INVALID_RUNTIME_RECORD"}
        session_providers = runtime.get("session_providers") or []
        cuda_session = runtime.get("cuda_session_verified") or any(
            "CUDAExecutionProvider" in row for row in session_providers if isinstance(row, list))
        return {"status": "READY" if runtime.get("cuda_provider_available")
                and cuda_session and runtime.get("onnx_sha256") == _EXPECTED_ONNX_SHA256 else "RUNTIME_NOT_READY",
                "runtime": runtime, "jobs": _tracking_jobs(),
                "validation_reviews": len(list_tracking_window_reviews(_local())),
                "policy": {"tracking_gate": "PLAYER_TRACKING_V1_PARTIAL",
                           "pose_gate": "QUALITY_GATED",
                           "production_database": "NOT_ACCESSED",
                           "official_test_split": "NOT_ACCESSED"}}

    @api.post("/player-motion/jobs/{tracking_job_id}")
    def start(tracking_job_id: str):
        if not TRACKING_JOB_ID.fullmatch(tracking_job_id):
            raise HTTPException(422, "追踪任务编号无效。")
        try:
            manifest, _ = load_tracking_evidence(tracking_job_id, _local())
        except FileNotFoundError as exc:
            raise HTTPException(404, "没有找到通过完整性检查的真实追踪片段。") from exc
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(409, "追踪证据未通过姿态分析前置检查。") from exc
        root = player_motion_job_root(tracking_job_id, _local())
        result_path = root / "player_motion.json"
        if result_path.is_file():
            return {"status": "COMPLETE", "tracking_job_id": tracking_job_id,
                    "result_available": True, "production_database": "NOT_ACCESSED"}
        with _PROCESS_LOCK:
            for old_id, old in list(_PROCESSES.items()):
                if old.poll() is not None:
                    _PROCESSES.pop(old_id, None)
            if any(process.poll() is None for process in _PROCESSES.values()):
                raise HTTPException(409, "另一个姿态任务正在运行，请等待它完成。")
            try:
                from backend import vision_api
                if any(process.poll() is None for process in vision_api._CLOSED_LOOP_PROCESSES.values()):
                    raise HTTPException(409, "追踪 GPU worker 仍在运行；姿态任务会在其结束后开始。")
            except ImportError:
                pass
            product_root, script, python = _worker_paths()
            root.mkdir(parents=True, exist_ok=True)
            env = dict(os.environ)
            env["PTTI_PRODUCT_ROOT"] = str(product_root)
            env["PYTHONUTF8"] = "1"
            log = (root / "worker.log").open("ab")
            try:
                process = subprocess.Popen(
                    [str(python), str(script), "--tracking-job-id", tracking_job_id],
                    cwd=str(product_root), env=env, stdout=log, stderr=subprocess.STDOUT,
                    **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
            except OSError as exc:
                raise HTTPException(503, "隔离姿态 worker 无法启动。") from exc
            finally:
                log.close()
            _PROCESSES[tracking_job_id] = process
        return {"status": "RUNNING", "stage": "姿态任务已启动",
                "tracking_job_id": tracking_job_id, "sample_id": manifest.get("sample_id"),
                "production_database": "NOT_ACCESSED"}

    @api.get("/player-motion/jobs/{tracking_job_id}")
    def status(tracking_job_id: str):
        if not TRACKING_JOB_ID.fullmatch(tracking_job_id):
            raise HTTPException(422, "姿态任务编号无效。")
        root = player_motion_job_root(tracking_job_id, _local())
        result_path, progress_path = root / "player_motion.json", root / "progress.json"
        if result_path.is_file():
            result = json.loads(result_path.read_text(encoding="utf-8"))
            return {"status": result.get("status"), "tracking_job_id": tracking_job_id,
                    "sample_id": result.get("sample_id"), "summary": result.get("summary"),
                    "result_available": True, "sampled_frames": result.get("sampled_frames", [])}
        if progress_path.is_file():
            return json.loads(progress_path.read_text(encoding="utf-8"))
        raise HTTPException(404, "尚未找到这段视频的人体动作分析记录。")

    @api.get("/player-motion/jobs/{tracking_job_id}/result")
    def result(tracking_job_id: str):
        if not TRACKING_JOB_ID.fullmatch(tracking_job_id):
            raise HTTPException(422, "姿态任务编号无效。")
        path = player_motion_job_root(tracking_job_id, _local()) / "player_motion.json"
        if not path.is_file():
            raise HTTPException(404, "人体姿态结果尚未生成。")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            exclusions = list_motion_exclusions(tracking_job_id, _local())
            retained = [row for row in value.get("records", [])
                        if row.get("player_role") in {"NEAR_PLAYER", "FAR_PLAYER"}
                        and not any(exclusion["role"] == row.get("player_role")
                                    and exclusion["start_frame"] <= int(row.get("frame", -1))
                                    < exclusion["end_frame"] for exclusion in exclusions)]
            effective_metrics = {
                role: motion_metrics([row for row in retained
                                      if row.get("player_role") == role])
                for role in ("NEAR_PLAYER", "FAR_PLAYER")
            }
            return {**value, "user_exclusions": exclusions,
                    "effective_metrics_after_user_exclusions": effective_metrics}
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(409, "人体姿态结果无法读取。") from exc

    @api.post("/player-motion/jobs/{tracking_job_id}/exclusions")
    def exclude_motion_segment(tracking_job_id: str, value: MotionExclusionRequest):
        if not TRACKING_JOB_ID.fullmatch(tracking_job_id):
            raise HTTPException(422, "姿态任务编号无效。")
        try:
            result_path = player_motion_job_root(tracking_job_id, _local()) / "player_motion.json"
            if not result_path.is_file():
                raise FileNotFoundError("PLAYER_MOTION_RESULT_UNAVAILABLE")
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if value.end_frame > int(result.get("video", {}).get("frame_count", 0)):
                raise ValueError("MOTION_EXCLUSION_OUT_OF_RANGE")
            row = record_motion_exclusion(
                job_id=tracking_job_id, source_sha256=str(result["source_sha256"]),
                start_frame=value.start_frame, end_frame=value.end_frame,
                role=value.role, localappdata=_local())
            return {**row, "production_database": "NOT_ACCESSED"}
        except FileNotFoundError as exc:
            raise HTTPException(404, "人体姿态结果不存在。") from exc
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422, "排除的区间或来源信息无效。") from exc

    @api.get("/player-motion/jobs/{tracking_job_id}/source")
    def source(tracking_job_id: str):
        if not TRACKING_JOB_ID.fullmatch(tracking_job_id):
            raise HTTPException(422, "追踪任务编号无效。")
        try:
            _, path = load_tracking_evidence(tracking_job_id, _local())
        except FileNotFoundError as exc:
            raise HTTPException(404, "来源视频不可用。") from exc
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(409, "来源视频完整性检查失败。") from exc
        browser_preview = player_motion_job_root(tracking_job_id, _local()) / "player_motion_source_preview.mp4"
        return FileResponse(browser_preview if browser_preview.is_file() else path,
                            media_type="video/mp4")

    @api.get("/player-motion/jobs/{tracking_job_id}/assets/{asset_name}")
    def asset(tracking_job_id: str, asset_name: str):
        if not TRACKING_JOB_ID.fullmatch(tracking_job_id):
            raise HTTPException(422, "姿态任务编号无效。")
        if asset_name != "player_motion_overlay.mp4" and not re.fullmatch(r"pose-frame-\d{5}\.jpg", asset_name):
            raise HTTPException(404, "人体动作预览不存在。")
        root = player_motion_job_root(tracking_job_id, _local()).resolve()
        path = (root / asset_name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise HTTPException(404, "人体动作预览不存在。")
        media_type = "video/mp4" if path.suffix.lower() == ".mp4" else "image/jpeg"
        return FileResponse(path, media_type=media_type)

    @api.get("/tracking-validation-workbench")
    def validation_workbench():
        return {"reviews": list_tracking_window_reviews(_local()),
                "storage": "%LOCALAPPDATA%/PTTI-Dev/vision-v2-sam2/validation-workbench",
                "production_database": "NOT_ACCESSED"}

    @api.post("/tracking-validation-workbench/reviews")
    def review(value: PlayerMotionReviewRequest):
        try:
            manifest, _ = load_tracking_evidence(value.tracking_job_id, _local())
            if value.end_frame > int(manifest.get("frames", 0)):
                raise ValueError("TRACKING_REVIEW_WINDOW_OUT_OF_RANGE")
            row = record_tracking_window_review(
                job_id=value.tracking_job_id, sample_id=str(manifest["sample_id"]),
                source_sha256=str(manifest["source_sha256"]), start_frame=value.start_frame,
                end_frame=value.end_frame, role=value.role, visibility=value.visibility,
                identity=value.identity, track_quality=value.track_quality, localappdata=_local())
            return {**row, "production_database": "NOT_ACCESSED"}
        except FileNotFoundError as exc:
            raise HTTPException(404, "追踪结果不存在。") from exc
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422, "追踪复核标签或时间范围无效。") from exc

    return api
