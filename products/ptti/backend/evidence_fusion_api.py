"""Local-only, TRAIN-research hit-event review API.

Evaluation artifacts and human corrections live under PTTI-Dev. This module
does not receive or resolve a database path and never writes over raw evidence.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.evidence_fusion import load_review_corrections, record_review_correction
from backend.player_motion import TRACKING_JOB_ID, load_tracking_evidence, player_motion_job_root


SAMPLE_ID = re.compile(r"game_[1-5]-t(?:30|60)\Z")


class HitEventReviewRequest(BaseModel):
    action: Literal["CONFIRM", "REJECT", "ADJUST", "ADD"]
    event_id: str | None = Field(default=None, max_length=80)
    timestamp_ms: float = Field(ge=0)
    player: Literal["NEAR_PLAYER", "FAR_PLAYER", "UNKNOWN"] = "UNKNOWN"


def _localappdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")).resolve()


def _safe_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(409, "击球候选证据无法读取。") from exc
    if not isinstance(value, dict):
        raise HTTPException(409, "击球候选证据格式无效。")
    return value


def _load_review_context(tracking_job_id: str, local: Path) -> tuple[dict, dict, list[dict], list[dict], Path, str, Path]:
    if not TRACKING_JOB_ID.fullmatch(tracking_job_id):
        raise HTTPException(422, "追踪任务编号无效。")
    try:
        tracking_manifest, _ = load_tracking_evidence(tracking_job_id, local)
    except FileNotFoundError as exc:
        raise HTTPException(404, "真实视频追踪证据不存在。") from exc
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(409, "追踪来源完整性检查失败。") from exc

    motion_path = player_motion_job_root(tracking_job_id, local) / "player_motion.json"
    motion = _safe_json(motion_path)
    sample_id = str(motion.get("sample_id") or "")
    if not SAMPLE_ID.fullmatch(sample_id) or motion.get("official_split") != "TRAIN":
        raise HTTPException(404, "目前只开放已核验的 TRAIN 研究片段。")
    digest = str(motion.get("source_sha256") or "").lower()
    if len(digest) != 64 or digest != str(tracking_manifest.get("source_sha256") or "").lower():
        raise HTTPException(409, "姿态与追踪视频来源不一致。")

    dev_root = local / "PTTI-Dev"
    # Windows packaged-app LocalAppData may redirect a child directory into
    # its package cache. Resolve the configured research folder first, then
    # constrain that resolved folder to LocalAppData and its own evaluation
    # subdirectory. Comparing only against the unresolved PTTI-Dev alias
    # rejects the legitimate package-cache path.
    vision_root = (dev_root / "vision-v2-evidence-fusion").resolve()
    evaluation_root = (vision_root / "evaluation").resolve()
    if not vision_root.is_relative_to(local) or not evaluation_root.is_relative_to(vision_root):
        raise HTTPException(409, "研究数据目录解析失败。")
    candidates = []
    for phase in ("dev", "validation"):
        phase_root = evaluation_root / phase
        if not phase_root.is_dir():
            continue
        for run_dir in phase_root.iterdir():
            sample_dir = run_dir / sample_id
            manifest_path = sample_dir / "clip_manifest.json"
            event_path = sample_dir / "hit_candidates.json"
            evidence_path = sample_dir / "frame_evidence.jsonl"
            if not (manifest_path.is_file() and event_path.is_file() and evidence_path.is_file()):
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if (manifest.get("official_split") == "TRAIN"
                        and manifest.get("video_sha256", "").lower() == digest
                        and manifest.get("tracking_job_id") == tracking_job_id):
                    candidates.append((manifest_path.stat().st_mtime_ns, phase, sample_dir,
                                       manifest, event_path, evidence_path, run_dir))
            except (OSError, ValueError, TypeError):
                continue
    if not candidates:
        raise HTTPException(404, "这段视频尚无与当前追踪结果匹配的 TRAIN 击球候选。")
    _, phase, sample_dir, manifest, event_path, evidence_path, run_dir = max(candidates, key=lambda row: row[0])
    try:
        raw_events = json.loads(event_path.read_text(encoding="utf-8"))
        if not isinstance(raw_events, list):
            raise ValueError("EVENTS_NOT_LIST")
        frame_evidence = [json.loads(line) for line in evidence_path.read_text(encoding="utf-8").splitlines()
                          if line.strip()]
        reviews_path = dev_root / "vision-v2-evidence-fusion" / "reviews" / f"{digest}.jsonl"
        reviews = [row for row in load_review_corrections(reviews_path)
                   if row.get("video_sha256", "").lower() == digest]
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(409, "击球候选或复核记录格式无效。") from exc

    return manifest, {"phase": phase, "sample_id": sample_id}, raw_events, frame_evidence, reviews_path, digest, run_dir


def router() -> APIRouter:
    api = APIRouter(prefix="/player-motion/jobs/{tracking_job_id}/hit-events")

    @api.get("")
    def get_hit_events(tracking_job_id: str):
        local = _localappdata()
        manifest, info, raw_events, frames, reviews_path, digest, run_dir = _load_review_context(tracking_job_id, local)
        try:
            all_reviews = load_review_corrections(reviews_path)
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(409, "人工复核记录无法读取。") from exc
        latest = {}
        for row in all_reviews:
            if row.get("video_sha256", "").lower() == digest:
                latest[row["event_id"]] = row
        events = []
        raw_ids = set()
        for raw in raw_events:
            event = {key: raw.get(key) for key in (
                "event_id", "event_type", "status", "frame", "source_frame", "processing_frame",
                "timestamp_ms", "candidate_player", "evidence_score", "confidence", "evidence_level",
                "evidence_components", "source_modules", "sequence_index", "interval_from_previous_ms",
                "sequence_review_required")}
            event["raw_status"] = raw.get("status", "SUGGESTED")
            event["review"] = latest.get(str(raw.get("event_id")))
            events.append(event)
            raw_ids.add(str(raw.get("event_id")))
        for row in latest.values():
            if row.get("action") == "ADD" and row["event_id"] not in raw_ids:
                events.append({"event_id": row["event_id"], "event_type": "HIT", "status": "USER_ADDED",
                               "raw_status": None, "timestamp_ms": row["timestamp_ms"],
                               "candidate_player": row["player"], "confidence": None,
                               "evidence_score": None, "evidence_components": {}, "source_modules": ["USER"],
                               "review": row})
        events.sort(key=lambda row: (float((row.get("review") or {}).get("timestamp_ms", row["timestamp_ms"])),
                                     str(row["event_id"])))
        clip_start = float(manifest["timeline_audit"]["first_timestamp_ms"])
        processing_fps = float(manifest["timeline_audit"]["processing_fps"])
        duration_ms = float(manifest["timeline_audit"]["processing_frames"]) * 1000.0 / processing_fps
        ball = [{"frame": row.get("processing_frame"), "timestamp_ms": row.get("timestamp_ms"),
                 "visible": (row.get("ball") or {}).get("visible"),
                 "x": (row.get("ball") or {}).get("x"), "y": (row.get("ball") or {}).get("y")}
                for row in frames]
        # Research metrics remain a separate, explicitly labeled payload.
        research = {}
        report = run_dir / "hit_event_evaluation.json"
        if report.is_file():
            try:
                research = json.loads(report.read_text(encoding="utf-8")).get("aggregate", {})
            except (OSError, ValueError, TypeError):
                research = {}
        return {"sample_id": info["sample_id"], "phase": info["phase"], "status": "RESEARCH_PREVIEW",
                "official_split": "TRAIN", "video_sha256": digest,
                "clip_start_timestamp_ms": clip_start, "clip_duration_ms": duration_ms,
                "processing_fps": processing_fps, "events": events, "ball_observations": ball,
                "research_metrics": research,
                "policy": {"official_test_split": "NOT_ACCESSED", "production_database": "NOT_ACCESSED",
                           "raw_candidates_preserved": True}}

    @api.post("/reviews")
    def review_hit_event(tracking_job_id: str, value: HitEventReviewRequest):
        local = _localappdata()
        manifest, _, raw_events, _, reviews_path, digest, _ = _load_review_context(tracking_job_id, local)
        raw_by_id = {str(row.get("event_id")): row for row in raw_events}
        try:
            existing_reviews = load_review_corrections(reviews_path)
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(409, "人工复核记录无法读取。") from exc
        known_adds = {str(row.get("event_id")) for row in existing_reviews if row.get("action") == "ADD"}
        event_id = value.event_id
        if value.action == "ADD":
            event_id = f"user-{uuid.uuid4().hex}"
        elif not event_id or (event_id not in raw_by_id and event_id not in known_adds):
            raise HTTPException(404, "没有找到要复核的原始候选。")
        clip_start = float(manifest["timeline_audit"]["first_timestamp_ms"])
        duration_ms = float(manifest["timeline_audit"]["processing_frames"]) * 1000.0 / float(
            manifest["timeline_audit"]["processing_fps"])
        if value.action in {"CONFIRM", "REJECT"}:
            timestamp = float(raw_by_id.get(event_id, {}).get("timestamp_ms", value.timestamp_ms))
        else:
            timestamp = float(value.timestamp_ms)
        if not clip_start <= timestamp <= clip_start + duration_ms:
            raise HTTPException(422, "复核时间超出当前视频片段。")
        try:
            saved = record_review_correction(reviews_path, video_sha256=digest, action=value.action,
                                             event_id=str(event_id), timestamp_ms=timestamp, player=value.player)
            return {**saved, "production_database": "NOT_ACCESSED", "raw_candidate_modified": False}
        except (OSError, ValueError) as exc:
            raise HTTPException(422, "复核记录没有保存。") from exc

    return api
