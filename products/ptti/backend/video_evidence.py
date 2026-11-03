"""Local, reference-only evidence library. No vision runtime or research GT access."""

import hashlib
import csv
import html
import io
import json
import math
import mimetypes
import re
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from vision.quality import video_metadata


FROZEN_HIT_CONFIG_SHA = "7b3715807699180b1559d28df5a456046c870035c3d3e9e728e6981185f8ef98"
FROZEN_HIT_CONFIG_FILE_SHA = "fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3"
TRAIN_VIDEO_SHA = {
    "1": "1297b3db91f2e3e160337643695dff07eabf9785ea2d88c2f7b59687ba511148",
    "2": "330ac07730bae6d899dbbbd00ad43500c583e6af6ea6dd261565bc77811eba66",
    "3": "e0f6a1ddbb838ac6acc67fb50f763728b589ec8f8cb7ababd9fa95f13c853e49",
}
TRAIN_RESULT_SHA = {
    "1": "9b92c4a6d4f33bcca4016d7667276feda8db7dafe09cd51498e9a9cb1974df77",
    "2": "fbb96373b194ce505bf353890c012d1ee5a7fc61af3864e4f49ea44481ee4ec7",
    "3": "23ae3797b75da751283536cc53c217cfdfc280dc8ddf0b447c380e8220e9475e",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def _review_flags(row):
    """Expose explicit source evidence gaps without turning a rule into truth."""
    raw = row.get("raw_candidate") or {}
    flags = []
    if row.get("disposition") == "REVIEW" or raw.get("sequence_review_required") is True:
        flags.append("SEQUENCE_REVIEW")
    if row.get("suggested_side", raw.get("candidate_player")) not in {"NEAR", "FAR"}:
        flags.append("UNKNOWN_PLAYER_SIDE")
    if raw.get("ball_quality") == "JUMP_SUSPECT":
        flags.append("BALLTRACK_JUMP_SUSPECT")
    elif not raw.get("ball_quality"):
        flags.append("BALL_EVIDENCE_UNAVAILABLE")
    if raw.get("identity_status") not in {None, "CONFIDENT"}:
        flags.append("PLAYER_IDENTITY_UNCERTAIN")
    return flags


def _timestamp_basis(row):
    mapping = (row.get("ai_provenance") or {}).get("timestamp_mapping") or {}
    declared = mapping.get("timestamp_source") or mapping.get("timestamp_basis")
    if declared == "SOURCE_PTS":
        return "SOURCE_PTS"
    if declared in {"SOURCE_FRAME_RATE_ESTIMATE", "ESTIMATED_FROM_SOURCE_FRAME_AND_FPS"}:
        return "SOURCE_FRAME_RATE_ESTIMATE"
    if mapping.get("kind") == "CANONICAL_SOURCE_TIMESTAMP_MS":
        return "SOURCE_FRAME_RATE_ESTIMATE"
    if row.get("source") == "AI_SUGGESTION":
        return "UNKNOWN"
    return "USER_MARKED_VIDEO_TIME"


def _status_label(row):
    if row.get("review_status") == "FILTERED":
        return "算法已过滤"
    if row.get("review_status") == "CONFIRMED":
        return "人工已确认"
    if row.get("review_status") == "REJECTED":
        return "已否决"
    if row.get("source") == "AI_SUGGESTION":
        return "AI 候选 · 待复核"
    return "人工记录"


def digest_file(path, cancel=None):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            if cancel is not None and cancel.is_set():
                raise InterruptedError("Hash deferred until next app launch")
            digest.update(block)
    return digest.hexdigest()


class VideoInput(BaseModel):
    path: str = Field(min_length=1, max_length=4000)
    title: str = Field(default="", max_length=200)
    match_id: str | None = None
    rights_status: Literal["USER_OWNED", "LICENSED", "RESEARCH_NONCOMMERCIAL"]
    rights_confirmed: Literal[True]
    source_note: str = Field(min_length=1, max_length=2000)


class RelinkInput(BaseModel):
    path: str = Field(min_length=1, max_length=4000)


class EvidenceInput(BaseModel):
    video_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    representative_ms: int | None = Field(default=None, ge=0)
    point_id: str | None = None
    event_type: str = Field(default="KEY_CLIP", min_length=1, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=30)
    notes: str = Field(default="", max_length=10000)
    review_status: Literal["CONFIRMED", "REJECTED", "REVIEW_REQUIRED", "UNVERIFIED", "FILTERED"] = "CONFIRMED"


class CollectionInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    evidence_ids: list[str] = Field(default_factory=list, max_length=10000)


class AIImportInput(BaseModel):
    video_id: str
    path: str = Field(min_length=1, max_length=4000)


class AIReviewInput(BaseModel):
    decision: Literal["CONFIRMED", "REJECTED"]
    representative_ms: int | None = Field(default=None, ge=0)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, gt=0)
    reviewer_side: Literal["NEAR", "FAR", "UNKNOWN"] | None = None
    tags: list[str] | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=10000)


class PointInput(BaseModel):
    video_id: str
    game_number: int | None = Field(default=None, ge=1, le=20)
    score_a: int | None = Field(default=None, ge=0, le=30)
    score_b: int | None = Field(default=None, ge=0, le=30)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    tags: list[str] = Field(default_factory=list, max_length=30)
    evidence_ids: list[str] = Field(default_factory=list, max_length=1000)
    notes: str = Field(default="", max_length=10000)


class EvidenceStore:
    """Additive SQLite tables using the app's existing guarded connection."""

    def __init__(self, repo):
        if repo.guard.mode not in {"development", "test"}:
            raise RuntimeError(
                "Video Evidence Preview requires an isolated development/test database"
            )
        self.repo = repo
        self.hasher = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="evidence-sha"
        )
        self.importer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="evidence-import")
        self.import_cancellations = {}
        self.pending = set()
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        with repo.connect() as db:
            for name, key in (
                ("evidence_videos", "video_id"),
                ("video_evidence", "evidence_id"),
                ("evidence_collections", "collection_id"),
            ):
                db.execute(
                    f"CREATE TABLE IF NOT EXISTS {name} ({key} TEXT PRIMARY KEY, payload TEXT NOT NULL)"
                )
            db.execute(
                "CREATE TABLE IF NOT EXISTS evidence_audit (audit_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, action TEXT NOT NULL, recorded_at TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            db.execute("CREATE TABLE IF NOT EXISTS ai_import_batches (batch_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS ai_import_keys (import_key TEXT PRIMARY KEY, evidence_id TEXT NOT NULL, batch_id TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS evidence_points (point_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            for row in db.execute("SELECT batch_id,payload FROM ai_import_batches").fetchall():
                payload = json.loads(row[1])
                if payload.get("status") == "RUNNING":
                    payload.update(status="PAUSED", message="应用已关闭；可安全恢复导入")
                    db.execute("UPDATE ai_import_batches SET payload=? WHERE batch_id=?", (json.dumps(payload, ensure_ascii=False), row[0]))
        for row in self.list("evidence_videos"):
            if row.get("hash_status") == "PENDING":
                self.queue_hash(row["video_id"])

    def list(self, table):
        with self.repo.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    f"SELECT payload FROM {table} ORDER BY rowid DESC"
                )
            ]

    def get(self, table, key, identity):
        with self.repo.connect() as db:
            row = db.execute(
                f"SELECT payload FROM {table} WHERE {key}=?", (identity,)
            ).fetchone()
        if not row:
            raise HTTPException(404, "记录不存在")
        return json.loads(row[0])

    def save(self, table, key, row, action):
        with self.repo.connect() as db:
            db.execute(
                f"INSERT INTO {table} VALUES (?,?) ON CONFLICT({key}) DO UPDATE SET payload=excluded.payload",
                (row[key], json.dumps(row, ensure_ascii=False)),
            )
            db.execute(
                "INSERT INTO evidence_audit VALUES (?,?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    row[key],
                    action,
                    utc_now(),
                    json.dumps(row, ensure_ascii=False),
                ),
            )
        return row

    def availability(self, row):
        path = Path(row["original_path"])
        try:
            stat = path.stat()
        except OSError:
            return {**row, "availability_status": "MISSING_FILE"}
        changed = (
            stat.st_size != row["file_size"]
            or stat.st_mtime_ns != row["mtime_ns"]
            or stat.st_ino != row["file_id"]
        )
        return {
            **row,
            "availability_status": "SOURCE_CHANGED" if changed else "AVAILABLE",
        }

    def register(self, value):
        if not value.source_note.strip():
            raise ValueError("请填写视频来源说明")
        if value.path.startswith("\\\\"):
            raise ValueError("请选择本机磁盘上的视频，不支持网络共享路径")
        path = Path(value.path).expanduser().resolve(strict=True)
        if not path.is_file() or path.suffix.lower() not in {
            ".mp4",
            ".mov",
            ".mkv",
            ".avi",
        }:
            raise ValueError("请选择完整的 MP4 / MOV / MKV / AVI 视频文件")
        stat = path.stat()
        media = video_metadata(path)
        if not math.isfinite(media["duration"]) or media["duration"] <= 0:
            raise ValueError("无法读取有效视频时长")
        match = None
        if value.match_id:
            match = self.repo.get_professional_match(value.match_id) or self.repo.get(
                value.match_id
            )
            if not match:
                raise ValueError("关联比赛不存在")
        row = {
            "video_id": str(uuid.uuid4()),
            "match_id": value.match_id,
            "title": value.title.strip() or path.stem,
            "original_path": str(path),
            "file_size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "file_id": stat.st_ino,
            "duration_ms": round(media["duration"] * 1000),
            "fps": media["fps"],
            "width": media["width"],
            "height": media["height"],
            "codec": media["codec"],
            "source_sha256": None,
            "hash_status": "PENDING",
            "rights_status": value.rights_status,
            "source_note": value.source_note,
            "imported_at": utc_now(),
            "availability_status": "AVAILABLE",
            "athlete_ids": (
                [match["player_a_id"], match["player_b_id"]]
                if match and "player_a_id" in match
                else []
            ),
        }
        self.save("evidence_videos", "video_id", row, "REGISTER_SOURCE_REFERENCE")
        self.queue_hash(row["video_id"])
        return row

    def queue_hash(self, video_id):
        with self.lock:
            if video_id in self.pending:
                return
            self.pending.add(video_id)
        self.hasher.submit(self._hash, video_id)

    def _hash(self, video_id):
        try:
            row = self.get("evidence_videos", "video_id", video_id)
            if self.availability(row)["availability_status"] != "AVAILABLE":
                return
            digest = digest_file(row["original_path"], self.stopping)
            current = self.get("evidence_videos", "video_id", video_id)
            if (
                current["original_path"] == row["original_path"]
                and self.availability(row)["availability_status"] == "AVAILABLE"
            ):
                self.save(
                    "evidence_videos",
                    "video_id",
                    {**current, "source_sha256": digest, "hash_status": "VERIFIED"},
                    "SOURCE_HASH_VERIFIED",
                )
        except (OSError, HTTPException):
            pass
        finally:
            with self.lock:
                self.pending.discard(video_id)

    def close(self):
        self.stopping.set()
        self.hasher.shutdown(wait=False, cancel_futures=True)
        for cancel in self.import_cancellations.values():
            cancel.set()
        self.importer.shutdown(wait=False, cancel_futures=True)

    def relink(self, video_id, path):
        row = self.get("evidence_videos", "video_id", video_id)
        if not row.get("source_sha256"):
            raise ValueError(
                "原视频身份尚未校验，不能安全重新关联。请先恢复原文件并完成校验"
            )
        path = Path(path).expanduser().resolve(strict=True)
        stat = path.stat()
        if (
            stat.st_size != row["file_size"]
            or digest_file(path) != row["source_sha256"]
        ):
            raise ValueError("文件身份不一致：不能用同名或不同内容的视频替换证据源")
        if (
            path.stat().st_mtime_ns != stat.st_mtime_ns
            or path.stat().st_size != stat.st_size
        ):
            raise ValueError("重新关联期间文件发生变化")
        return self.save(
            "evidence_videos",
            "video_id",
            {
                **row,
                "original_path": str(path),
                "mtime_ns": stat.st_mtime_ns,
                "file_id": stat.st_ino,
                "availability_status": "AVAILABLE",
            },
            "RELINK_SOURCE_IDENTITY_VERIFIED",
        )

    def evidence(self, value, evidence_id=None):
        video = self.get("evidence_videos", "video_id", value.video_id)
        representative = (
            value.representative_ms
            if value.representative_ms is not None
            else value.start_ms
        )
        if (
            not 0
            <= value.start_ms
            <= representative
            < value.end_ms
            <= video["duration_ms"]
        ):
            raise ValueError("片段范围必须满足：0 ≤ 起点 ≤ 代表时刻 < 终点 ≤ 视频时长")
        tags = list(dict.fromkeys(tag.strip() for tag in value.tags if tag.strip()))
        if any(len(tag) > 100 for tag in tags):
            raise ValueError("标签最长 100 字")
        old = (
            self.get("video_evidence", "evidence_id", evidence_id)
            if evidence_id
            else None
        )
        if old and old["video_id"] != value.video_id:
            raise ValueError("已有证据不能改绑另一视频")
        source = old["source"] if old else "MANUAL_CONFIRMED"
        if source in {"AI_SUGGESTED", "AI_REVIEWED"}:
            source = (
                "AI_REVIEWED" if value.review_status != "REVIEW_REQUIRED" else source
            )
        row = {
            **(old or {}),
            **value.model_dump(),
            "evidence_id": evidence_id or str(uuid.uuid4()),
            "match_id": video["match_id"],
            "representative_ms": representative,
            "tags": tags,
            "source": source,
            "created_at": old["created_at"] if old else utc_now(),
            "updated_at": utc_now(),
        }
        return self.save(
            "video_evidence",
            "evidence_id",
            row,
            "HUMAN_EDIT" if old else "MANUAL_CREATE",
        )

    def import_ai_candidate(self, video_id, candidate):
        """Adapter contract only: source identity + raw candidate are mandatory."""
        video = self.get("evidence_videos", "video_id", video_id)
        if (
            not video.get("source_sha256")
            or candidate.get("video_sha256") != video["source_sha256"]
        ):
            raise ValueError("AI candidate source does not match registered video")
        stamp = candidate["timestamp_ms"]
        if not 0 <= stamp < video["duration_ms"] or not candidate.get("event_id"):
            raise ValueError("Invalid AI candidate")
        row = {
            "evidence_id": str(uuid.uuid4()),
            "video_id": video_id,
            "match_id": video["match_id"],
            "point_id": None,
            "start_ms": max(0, round(stamp) - 500),
            "end_ms": min(video["duration_ms"], round(stamp) + 501),
            "representative_ms": round(stamp),
            "event_type": "HIT_CANDIDATE",
            "tags": ["待复核"],
            "notes": "",
            "source": "AI_SUGGESTED",
            "review_status": "REVIEW_REQUIRED",
            "raw_candidate": candidate,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        return self.save("video_evidence", "evidence_id", row, "IMPORT_AI_SUGGESTION")

    def _verified_package(self, video_id, package_path):
        video = self.get("evidence_videos", "video_id", video_id)
        video = self.availability(video)
        if video.get("availability_status") != "AVAILABLE" or video.get("hash_status") != "VERIFIED":
            raise ValueError("请先恢复原视频并完成 SHA256 校验")
        if str(package_path).startswith(("\\\\", "//")):
            raise ValueError("请选择本机上的冻结结果包 JSONL")
        path = Path(package_path).expanduser().resolve(strict=True)
        if path.suffix.lower() != ".jsonl" or not path.is_file() or str(path).startswith("\\\\"):
            raise ValueError("请选择本机上的冻结结果包 JSONL")
        if path.stat().st_size > 2 * 1024 * 1024 * 1024:
            raise ValueError("结果包超过 2 GB 安全上限")
        package_sha = digest_file(path)
        with path.open("r", encoding="utf-8-sig") as stream:
            first = stream.readline()
        try:
            header = json.loads(first)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("结果包首行不是有效 JSON manifest") from exc
        manifest = header.get("manifest") if isinstance(header, dict) else None
        if not isinstance(header, dict) or header.get("kind") != "manifest" or not isinstance(manifest, dict):
            raise ValueError("结果包缺少 manifest")
        if manifest.get("schema") != "ptti-ai-evidence-package-v1":
            raise ValueError("不支持的 AI 证据包版本")
        if manifest.get("dataset") != "Extended OpenTTGames" or manifest.get("split") != "train":
            raise ValueError("此 Preview 仅接受 Extended OpenTTGames TRAIN 开发素材")
        match_ref = str(manifest.get("match_reference", "")).casefold()
        game_refs = re.findall(r"\bgame_([1-5])\b", match_ref)
        if len(game_refs) != 1 or game_refs[0] not in {"1", "2", "3"}:
            raise ValueError("GAME_4、GAME_5 与官方 TEST 素材在此导入中保持锁定")
        if manifest.get("commercial_use") is not False or manifest.get("dataset_license") != "CC BY-NC-SA 4.0":
            raise ValueError("结果包缺少正确的研究许可和非商业用途标记")
        game_number = game_refs[0]
        if manifest.get("source_video_sha256") != video.get("source_sha256") or video.get("source_sha256") != TRAIN_VIDEO_SHA[game_number]:
            raise ValueError("原视频 SHA256 不匹配，候选不能绑定到这场录像")
        if manifest.get("result_sha256") != TRAIN_RESULT_SHA[game_number]:
            raise ValueError("冻结研究结果 SHA256 与已登记的 D 结果不一致")
        if manifest.get("hit_event_version") != "v0.3" or manifest.get("variant") != "D" or manifest.get("frozen_config_sha256") != FROZEN_HIT_CONFIG_SHA:
            raise ValueError("结果包不是冻结的 Hit Event v0.3 D 配置")
        if manifest.get("frozen_config_file_sha256") != FROZEN_HIT_CONFIG_FILE_SHA:
            raise ValueError("冻结配置文件 SHA256 与登记值不一致")
        mapping = manifest.get("timestamp_mapping") or {}
        if mapping.get("kind") != "CANONICAL_SOURCE_TIMESTAMP_MS" or mapping.get("frame_field") != "source_frame" or mapping.get("timestamp_field") != "timestamp_ms":
            raise ValueError("结果包时间轴映射缺失或不受支持")
        source_fps = mapping.get("source_fps")
        if not isinstance(source_fps, (int, float)) or not math.isfinite(source_fps) or source_fps <= 0:
            raise ValueError("结果包源帧率无效")
        if abs(float(source_fps) - float(video["fps"])) > max(0.05, float(video["fps"]) * 0.001):
            raise ValueError("结果包帧率与登记的原视频不一致")
        return video, path, package_sha, manifest

    def start_ai_import(self, video_id, package_path):
        video, path, package_sha, manifest = self._verified_package(video_id, package_path)
        for existing in self.list("ai_import_batches"):
            if existing.get("video_id") == video_id and existing.get("package_sha256") == package_sha:
                if existing.get("status") in {"COMPLETED", "RUNNING", "PAUSED"}:
                    return existing
        batch = {
            "batch_id": str(uuid.uuid4()), "video_id": video_id, "package_path": str(path),
            "package_sha256": package_sha, "source_video_sha256": video["source_sha256"],
            "manifest": manifest, "status": "RUNNING", "processed_count": 0,
            "imported_count": 0, "duplicate_count": 0, "filtered_count": 0,
            "error_count": 0, "created_at": utc_now(), "updated_at": utc_now(), "message": "正在验证并导入候选",
        }
        self.save("ai_import_batches", "batch_id", batch, "AI_IMPORT_STARTED")
        cancel = threading.Event()
        self.import_cancellations[batch["batch_id"]] = cancel
        self.importer.submit(self._run_ai_import, batch["batch_id"], cancel)
        return batch

    def import_batch(self, batch_id):
        return self.get("ai_import_batches", "batch_id", batch_id)

    def _update_batch(self, batch_id, **changes):
        try:
            old = self.get("ai_import_batches", "batch_id", batch_id)
        except HTTPException:
            return None
        row = {**old, **changes, "updated_at": utc_now()}
        return self.save("ai_import_batches", "batch_id", row, "AI_IMPORT_PROGRESS")

    def cancel_ai_import(self, batch_id):
        batch = self.import_batch(batch_id)
        if batch.get("status") == "RUNNING":
            cancel = self.import_cancellations.get(batch_id)
            if cancel:
                cancel.set()
        return batch

    def resume_ai_import(self, batch_id):
        batch = self.import_batch(batch_id)
        if batch.get("status") not in {"PAUSED", "FAILED"}:
            raise ValueError("只有暂停或失败的导入可以恢复")
        video, path, package_sha, manifest = self._verified_package(batch["video_id"], batch["package_path"])
        if package_sha != batch["package_sha256"] or video["source_sha256"] != batch["source_video_sha256"]:
            raise ValueError("结果包或原视频已变化，拒绝继续旧导入")
        self._update_batch(batch_id, status="RUNNING", message="正在恢复导入")
        cancel = threading.Event()
        self.import_cancellations[batch_id] = cancel
        self.importer.submit(self._run_ai_import, batch_id, cancel)
        return self.import_batch(batch_id)

    def _run_ai_import(self, batch_id, cancel):
        batch = self.import_batch(batch_id)
        counts = {"processed_count": 0, "imported_count": 0, "duplicate_count": 0, "filtered_count": 0}
        disposition_counts = {"ACCEPTED": 0, "REVIEW": 0, "FILTERED": 0}
        try:
            video, path, package_sha, manifest = self._verified_package(batch["video_id"], batch["package_path"])
            if package_sha != batch["package_sha256"] or video["source_sha256"] != batch["source_video_sha256"]:
                raise ValueError("原视频或结果包身份改变")
            with path.open("r", encoding="utf-8-sig") as stream:
                header = json.loads(stream.readline())
                if header.get("kind") != "manifest" or header.get("manifest") != manifest:
                    raise ValueError("结果包 manifest 已改变")
                seen = {}
                for line_number, line in enumerate(stream, 2):
                    if cancel.is_set():
                        self._update_batch(batch_id, status="PAUSED", **counts, message="已暂停；可以安全恢复")
                        return
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    if item.get("kind") != "candidate" or item.get("disposition") not in {"ACCEPTED", "REVIEW", "FILTERED"}:
                        raise ValueError(f"第 {line_number} 行候选结构无效")
                    candidate = item.get("candidate")
                    self._validate_package_candidate(candidate, manifest, video)
                    event_id = candidate["event_id"]
                    disposition = item["disposition"]
                    disposition_counts[disposition] += 1
                    if event_id in seen:
                        previous = seen[event_id]
                        identity = {
                            key: value
                            for key, value in candidate.items()
                            if key not in {"status", "decision", "review_reason"}
                        }
                        exact_duplicate = (
                            disposition == previous["disposition"]
                            and candidate == previous["candidate"]
                        )
                        review_shadow = (
                            identity == previous["identity"]
                            and {disposition, previous["disposition"]} == {"REVIEW", "FILTERED"}
                            and candidate.get("status")
                            == ("RAW_CANDIDATE" if disposition == "FILTERED" else "REQUIRES_REVIEW")
                            and previous["candidate"].get("status")
                            == ("RAW_CANDIDATE" if previous["disposition"] == "FILTERED" else "REQUIRES_REVIEW")
                        )
                        if not exact_duplicate and not review_shadow:
                            raise ValueError(f"结果包内 event_id 内容冲突：{event_id}")
                        counts["duplicate_count"] += 1
                        counts["processed_count"] += 1
                        if counts["processed_count"] % 25 == 0:
                            self._update_batch(batch_id, **counts, message="正在导入；重复候选会自动跳过")
                        continue
                    identity = {
                        key: value
                        for key, value in candidate.items()
                        if key not in {"status", "decision", "review_reason"}
                    }
                    seen[event_id] = {
                        "identity": identity,
                        "disposition": disposition,
                        "candidate": candidate,
                    }
                    if disposition == "FILTERED":
                        counts["filtered_count"] += 1
                    key = f"{video['source_sha256']}:{event_id}:{manifest['frozen_config_sha256']}"
                    imported = self._store_ai_candidate(batch, candidate, disposition, key)
                    if imported and disposition != "FILTERED":
                        counts["imported_count"] += 1
                    elif not imported:
                        counts["duplicate_count"] += 1
                    counts["processed_count"] += 1
                    if counts["processed_count"] % 25 == 0:
                        self._update_batch(batch_id, **counts, message="正在导入；重复候选会自动跳过")
            expected = int(manifest.get("counts", {}).get("total", -1))
            if expected != counts["processed_count"]:
                raise ValueError(f"候选行数与 manifest 不符：{counts['processed_count']} / {expected}")
            if digest_file(path) != batch["package_sha256"]:
                raise ValueError("结果包在导入过程中发生变化")
            for key, value in (("accepted", "ACCEPTED"), ("review", "REVIEW"), ("filtered", "FILTERED")):
                if key in manifest.get("counts", {}) and int(manifest["counts"][key]) != disposition_counts[value]:
                    raise ValueError(f"候选类型计数与 manifest 不符：{key}")
            self._update_batch(batch_id, status="COMPLETED", **counts, message="导入完成；AI 建议仍需人工复核")
        except Exception as exc:
            self._update_batch(batch_id, status="FAILED", error_count=1, **counts, message=str(exc))
        finally:
            self.import_cancellations.pop(batch_id, None)

    @staticmethod
    def _validate_package_candidate(candidate, manifest, video):
        if not isinstance(candidate, dict) or candidate.get("event_type") != "HIT_CANDIDATE" or candidate.get("ablation") != "D":
            raise ValueError("结果包包含非 D 方案击球候选")
        event_id = candidate.get("event_id")
        stamp, frame = candidate.get("timestamp_ms"), candidate.get("source_frame")
        if not isinstance(event_id, str) or not event_id or not isinstance(stamp, (int, float)) or not math.isfinite(stamp):
            raise ValueError("候选 ID 或时间戳无效")
        if not isinstance(frame, int) or frame < 0 or not 0 <= stamp < video["duration_ms"]:
            raise ValueError("候选源帧或时间戳超出视频范围")
        fps = float(manifest["timestamp_mapping"]["source_fps"])
        if abs(stamp - frame * 1000 / fps) > (1000 / fps) + 0.02:
            raise ValueError("源帧与 canonical timestamp 不一致")
        side = candidate.get("candidate_player") or "UNKNOWN"
        if side not in {"NEAR", "FAR", "UNKNOWN"}:
            raise ValueError("候选击球方不是受支持的 Near/Far/Unknown 值")

    def _store_ai_candidate(self, batch, candidate, disposition, import_key):
        video = self.get("evidence_videos", "video_id", batch["video_id"])
        if video.get("source_sha256") != batch["source_video_sha256"] or self.availability(video).get("availability_status") != "AVAILABLE":
            raise ValueError("原视频身份在导入过程中发生变化")
        stamp = round(candidate["timestamp_ms"])
        filtered = disposition == "FILTERED"
        evidence_id = str(uuid.uuid4())
        raw_candidate = {**candidate, "source_video_sha256": batch["source_video_sha256"], "source_match_reference": batch["manifest"]["match_reference"], "model_version": batch["manifest"]["model_version"], "frozen_config_sha256": batch["manifest"]["frozen_config_sha256"], "import_batch_id": batch["batch_id"]}
        row = {
            "evidence_id": evidence_id, "video_id": batch["video_id"], "match_id": video.get("match_id"),
            "point_id": None, "start_ms": max(0, stamp - 700), "end_ms": min(video["duration_ms"], stamp + 701),
            "representative_ms": stamp, "event_type": "HIT_CANDIDATE", "tags": ["AI待复核"] if not filtered else ["算法已过滤"],
            "notes": "", "source": "AI_SUGGESTION", "review_status": "FILTERED" if filtered else "UNVERIFIED",
            "suggested_side": candidate.get("candidate_player", "UNKNOWN"), "disposition": disposition,
            "ai_provenance": {"source_video_sha256": batch["source_video_sha256"], "source_match_reference": batch["manifest"]["match_reference"], "dataset": batch["manifest"]["dataset"], "dataset_license": batch["manifest"]["dataset_license"], "commercial_use": False, "model_version": batch["manifest"]["model_version"], "frozen_config_sha256": batch["manifest"]["frozen_config_sha256"], "frozen_config_file_sha256": batch["manifest"].get("frozen_config_file_sha256"), "timestamp_mapping": batch["manifest"].get("timestamp_mapping"), "import_batch_id": batch["batch_id"], "package_sha256": batch["package_sha256"]},
            "raw_candidate": raw_candidate, "reviewer_decision": None, "reviewed_at": None, "reviewer_side": None,
            "review_history": [], "created_at": utc_now(), "updated_at": utc_now(),
        }
        with self.repo.connect() as db:
            if db.execute("SELECT 1 FROM ai_import_keys WHERE import_key=?", (import_key,)).fetchone():
                return False
            db.execute("INSERT INTO video_evidence VALUES (?,?)", (evidence_id, json.dumps(row, ensure_ascii=False)))
            db.execute("INSERT INTO ai_import_keys VALUES (?,?,?)", (import_key, evidence_id, batch["batch_id"]))
            db.execute("INSERT INTO evidence_audit VALUES (?,?,?,?,?)", (str(uuid.uuid4()), evidence_id, "IMPORT_AI_SUGGESTION", utc_now(), json.dumps(row, ensure_ascii=False)))
        return True

    def ai_suggestions(self, video_id, status, offset, limit, attention=None):
        rows = [row for row in self.list("video_evidence") if row.get("source") == "AI_SUGGESTION" and (not video_id or row.get("video_id") == video_id)]
        counts = {key: sum(row.get("review_status") == key for row in rows) for key in ("UNVERIFIED", "FILTERED", "CONFIRMED", "REJECTED")}
        attention_counts = {
            "NEEDS_REVIEW": sum(bool(_review_flags(row)) for row in rows if row.get("review_status") == "UNVERIFIED"),
            "EVIDENCE_GAP": sum(any(flag != "SEQUENCE_REVIEW" for flag in _review_flags(row))
                                 for row in rows if row.get("review_status") == "UNVERIFIED"),
        }
        selected = [row for row in rows if not status or row.get("review_status") == status]
        if attention == "NEEDS_REVIEW":
            selected = [row for row in selected if row.get("review_status") == "UNVERIFIED" and _review_flags(row)]
        elif attention == "EVIDENCE_GAP":
            selected = [row for row in selected if row.get("review_status") == "UNVERIFIED" and
                        any(flag != "SEQUENCE_REVIEW" for flag in _review_flags(row))]
        selected = [{**row, "review_flags": _review_flags(row)} for row in selected]
        selected.sort(key=lambda row: (row.get("representative_ms", 0), row["evidence_id"]))
        return {"counts": counts, "attention_counts": attention_counts, "attention": attention,
                "total": len(selected), "offset": offset, "limit": limit,
                "items": selected[offset:offset + limit]}

    def export_payload(self, video_id):
        video = self.availability(self.get("evidence_videos", "video_id", video_id))
        events = [row for row in self.list("video_evidence") if row.get("video_id") == video_id]
        events.sort(key=lambda row: (float(row.get("representative_ms", 0)), row["evidence_id"]))
        points = self.points(video_id)
        identities = {row["evidence_id"] for row in events} | {row["point_id"] for row in points}
        with self.repo.connect() as db:
            audit_rows = [
                {"audit_id": row[0], "entity_id": row[1], "action": row[2],
                 "recorded_at": row[3], "payload": json.loads(row[4])}
                for row in db.execute(
                    "SELECT audit_id,entity_id,action,recorded_at,payload FROM evidence_audit ORDER BY rowid"
                ).fetchall() if row[1] in identities
            ]
        for row in events:
            raw = row.get("raw_candidate") or {}
            row["timestamp_basis"] = _timestamp_basis(row)
            row["raw_timestamp_ms"] = raw.get("timestamp_ms")
            row["reviewed_timestamp_ms"] = row.get("representative_ms")
            row["status_label"] = _status_label(row)
            row["review_flags"] = _review_flags(row)
        counts = {key: sum(row.get("review_status") == key for row in events if row.get("source") == "AI_SUGGESTION")
                  for key in ("UNVERIFIED", "CONFIRMED", "REJECTED", "FILTERED")}
        return {
            "schema": "ptti-video-evidence-review-v1",
            "notice": "AI 击球候选是待复核提示，不代表已验证的真实击球。算法已过滤记录单独保留，不等同人工确认。",
            "video": {key: video.get(key) for key in (
                "video_id", "title", "duration_ms", "fps", "width", "height", "codec",
                "source_sha256", "hash_status", "availability_status", "rights_status")},
            "counts": counts,
            "events": events,
            "points": points,
            "audit": audit_rows,
            "policy": {"production_database": "NOT_ACCESSED", "raw_candidates_preserved": True,
                       "filtered_records_are_not_confirmed": True},
        }

    def review_ai(self, evidence_id, value):
        old = self.get("video_evidence", "evidence_id", evidence_id)
        if old.get("source") != "AI_SUGGESTION":
            raise ValueError("只有 AI 建议可以使用此复核操作")
        video = self.get("evidence_videos", "video_id", old["video_id"])
        representative = value.representative_ms if value.representative_ms is not None else old["representative_ms"]
        start = value.start_ms if value.start_ms is not None else old["start_ms"]
        end = value.end_ms if value.end_ms is not None else old["end_ms"]
        if not 0 <= start <= representative < end <= video["duration_ms"]:
            raise ValueError("复核后的范围必须满足 0 ≤ 起点 ≤ 代表时刻 < 终点 ≤ 视频时长")
        if value.tags is not None:
            tags = list(dict.fromkeys(tag.strip() for tag in value.tags if tag.strip()))
        else:
            tags = list(old["tags"])
        decision = value.decision
        change = {"reviewer_decision": decision, "reviewed_at": utc_now(), "reviewer_side": value.reviewer_side or old.get("reviewer_side") or old.get("suggested_side", "UNKNOWN"), "review_status": decision, "representative_ms": representative, "start_ms": start, "end_ms": end, "tags": tags, "notes": value.notes if value.notes is not None else old.get("notes", "")}
        history = list(old.get("review_history", []))
        history.append({"at": utc_now(), "decision": decision, "before": {"representative_ms": old["representative_ms"], "start_ms": old["start_ms"], "end_ms": old["end_ms"], "reviewer_side": old.get("reviewer_side")}, "after": {"representative_ms": representative, "start_ms": start, "end_ms": end, "reviewer_side": change["reviewer_side"]}})
        row = {**old, **change, "review_history": history, "updated_at": utc_now()}
        return self.save("video_evidence", "evidence_id", row, "AI_HUMAN_REVIEW")

    def points(self, video_id=None):
        rows = self.list("evidence_points")
        if video_id:
            rows = [row for row in rows if row.get("video_id") == video_id]
        return sorted(rows, key=lambda row: (row.get("game_number") or 999, row["start_ms"]))

    def save_point(self, value, point_id=None):
        video = self.get("evidence_videos", "video_id", value.video_id)
        if not 0 <= value.start_ms < value.end_ms <= video["duration_ms"]:
            raise ValueError("逐分范围必须位于比赛视频时长内")
        evidence_ids = list(dict.fromkeys(value.evidence_ids))
        for evidence_id in evidence_ids:
            evidence = self.get("video_evidence", "evidence_id", evidence_id)
            if evidence["video_id"] != value.video_id:
                raise ValueError("逐分证据必须来自同一场比赛录像")
        old = self.get("evidence_points", "point_id", point_id) if point_id else None
        row = {**(old or {}), **value.model_dump(), "point_id": point_id or str(uuid.uuid4()), "evidence_ids": evidence_ids, "source": "MANUAL_CONFIRMED", "created_at": old.get("created_at") if old else utc_now(), "updated_at": utc_now()}
        return self.save("evidence_points", "point_id", row, "MANUAL_POINT_SAVE")


def _review_export_csv(payload):
    output = io.StringIO(newline="")
    fields = ["event_id", "video_time_ms", "raw_ai_time_ms", "timestamp_basis", "player_side",
              "review_status", "status_label", "source", "rule_evidence_score",
              "review_flags", "evidence_sources", "raw_candidate_json", "review_history_json"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in payload["events"]:
        raw = row.get("raw_candidate") or {}
        writer.writerow({
            "event_id": row["evidence_id"], "video_time_ms": row.get("reviewed_timestamp_ms"),
            "raw_ai_time_ms": row.get("raw_timestamp_ms"), "timestamp_basis": row.get("timestamp_basis"),
            "player_side": row.get("reviewer_side") or row.get("suggested_side") or "UNKNOWN",
            "review_status": row.get("review_status"), "status_label": row.get("status_label"),
            "source": row.get("source"), "rule_evidence_score": raw.get("evidence_score"),
            "review_flags": ";".join(row.get("review_flags", [])),
            "evidence_sources": ";".join(raw.get("source_modules", [])),
            "raw_candidate_json": json.dumps(raw, ensure_ascii=False, separators=(",", ":")),
            "review_history_json": json.dumps(row.get("review_history", []), ensure_ascii=False,
                                               separators=(",", ":")),
        })
    return "\ufeff" + output.getvalue()


def _review_export_html(payload):
    video = payload["video"]
    esc = lambda value: html.escape("" if value is None else str(value))
    rows = []
    for row in payload["events"]:
        raw = row.get("raw_candidate") or {}
        side = row.get("reviewer_side") or row.get("suggested_side") or "UNKNOWN"
        rows.append(
            "<tr><td>{time}</td><td>{side}</td><td>{status}</td><td>{basis}</td>"
            "<td>{score}</td><td>{sources}</td><td><details><summary>查看原始证据与修正</summary>"
            "<pre>{raw}</pre><pre>{history}</pre></details></td></tr>".format(
                time=esc(row.get("reviewed_timestamp_ms")), side=esc(side),
                status=esc(row.get("status_label")), basis=esc(row.get("timestamp_basis")),
                score=esc(raw.get("evidence_score")),
                sources=esc(", ".join(raw.get("source_modules", []))),
                raw=esc(json.dumps(raw, ensure_ascii=False, indent=2)),
                history=esc(json.dumps(row.get("review_history", []), ensure_ascii=False, indent=2)),
            )
        )
    counts = " · ".join(f"{esc(key)} {esc(value)}" for key, value in payload["counts"].items())
    return (
        "<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
        "<title>PTTI 视频证据复核报告</title><style>body{font-family:'Microsoft YaHei UI','Microsoft YaHei',sans-serif;"
        "max-width:1200px;margin:32px auto;padding:0 18px;color:#16252a}table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #d8e0df;padding:8px;text-align:left;vertical-align:top}pre{white-space:pre-wrap;"
        "max-width:600px;overflow:auto;background:#f4f7f6;padding:10px}code{word-break:break-all}.notice{background:#fff6df;"
        "padding:12px}</style><h1>比赛视频复核时间线</h1><p class='notice'>" + esc(payload["notice"]) + "</p>"
        "<h2>" + esc(video.get("title")) + "</h2><p>视频 SHA-256：<code>" + esc(video.get("source_sha256")) +
        "</code></p><p>时长：" + esc(video.get("duration_ms")) + " ms · " + esc(video.get("width")) + "×" +
        esc(video.get("height")) + " · " + esc(video.get("fps")) + " FPS</p><p>" + counts + "</p>"
        "<p>“规则证据评分”不是校准概率；算法过滤记录保持独立状态，不代表已确认事件。</p>"
        "<table><thead><tr><th>视频时间 ms</th><th>击球方</th><th>状态</th><th>时间来源</th>"
        "<th>规则评分</th><th>证据来源</th><th>原始候选 / 人工修改</th></tr></thead><tbody>" +
        "".join(rows) + "</tbody></table></html>"
    )


def evidence_router(repo, mode):
    def local_only(request: Request):
        host = request.url.hostname
        origin = request.headers.get("origin")
        if host not in {"127.0.0.1", "localhost", "testserver"}:
            raise HTTPException(403, "仅允许本机访问")
        if (
            mode != "test"
            and request.client
            and request.client.host not in {"127.0.0.1", "::1"}
        ):
            raise HTTPException(403, "仅允许本机访问")
        if origin and (urlsplit(origin).scheme, urlsplit(origin).netloc) != (
            request.url.scheme,
            request.url.netloc,
        ):
            raise HTTPException(403, "不允许跨站访问本机文件")
        if mode == "production":
            raise HTTPException(503, "证据播放器仅在隔离 Preview 中开放")

    store = EvidenceStore(repo) if mode != "production" else None

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            if store:
                store.close()

    router = APIRouter(
        prefix="/api/video-evidence",
        dependencies=[Depends(local_only)],
        lifespan=lifespan,
    )

    @router.get("/videos")
    def videos():
        rows = [store.availability(row) for row in store.list("evidence_videos")]
        for row in rows:
            if (
                row["hash_status"] == "PENDING"
                and row["availability_status"] == "AVAILABLE"
            ):
                store.queue_hash(row["video_id"])
        return rows

    @router.get("/videos/{video_id}/export")
    def export_review(video_id: str, format: str = "json"):
        try:
            payload = store.export_payload(video_id)
        except HTTPException:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(409, "复核报告无法生成，请检查本机记录。") from exc
        filename = f"ptti-video-review-{video_id}"
        if format == "json":
            content = json.dumps(payload, ensure_ascii=False, indent=2)
            return Response(content, media_type="application/json; charset=utf-8",
                            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'})
        if format == "csv":
            return Response(_review_export_csv(payload), media_type="text/csv; charset=utf-8",
                            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'})
        if format == "html":
            return Response(_review_export_html(payload), media_type="text/html; charset=utf-8",
                            headers={"Content-Disposition": f'attachment; filename="{filename}.html"'})
        raise HTTPException(422, "支持的复核报告格式为 JSON、CSV 或 HTML。")

    @router.post("/videos")
    def register(value: VideoInput):
        try:
            return store.register(value)
        except (ValueError, OSError) as exc:
            raise HTTPException(400, str(exc)) from exc
        except subprocess.SubprocessError as exc:
            raise HTTPException(
                400, "无法读取视频信息，请检查文件是否完整、编码是否受支持"
            ) from exc

    @router.post("/videos/{video_id}/relink")
    def relink(video_id: str, value: RelinkInput):
        try:
            return store.relink(video_id, value.path)
        except (ValueError, OSError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.api_route("/videos/{video_id}/media", methods=["GET", "HEAD"])
    def media(video_id: str, request: Request):
        row = store.availability(store.get("evidence_videos", "video_id", video_id))
        if row["availability_status"] != "AVAILABLE":
            raise HTTPException(
                409,
                {
                    "status": row["availability_status"],
                    "message": "视频暂时离线或内容改变，请重新关联原文件",
                },
            )
        size = row["file_size"]
        start, end, status = 0, size - 1, 200
        requested = request.headers.get("range")
        if requested:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested.strip())
            if not match or not any(match.groups()):
                return Response(
                    status_code=416, headers={"Content-Range": f"bytes */{size}"}
                )
            left, right = match.groups()
            if left:
                start = int(left)
                end = min(int(right), size - 1) if right else size - 1
            else:
                start = max(0, size - int(right))
            if (
                start >= size
                or start > end
                or not size
                or (not left and int(right) == 0)
            ):
                return Response(
                    status_code=416, headers={"Content-Range": f"bytes */{size}"}
                )
            status = 206
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
            "Cache-Control": "private, no-store",
            "Content-Disposition": "inline",
        }
        if status == 206:
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        if row.get("source_sha256"):
            headers["ETag"] = '"' + row["source_sha256"] + '"'
        content_type = (
            mimetypes.guess_type(row["original_path"])[0] or "application/octet-stream"
        )
        if request.method == "HEAD":
            return Response(
                status_code=status, headers=headers, media_type=content_type
            )

        async def stream():
            async with await anyio.open_file(row["original_path"], "rb") as source:
                await source.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    if await request.is_disconnected():
                        break
                    block = await source.read(min(64 * 1024, remaining))
                    if not block:
                        break
                    remaining -= len(block)
                    yield block

        return StreamingResponse(
            stream(), status_code=status, headers=headers, media_type=content_type
        )

    @router.get("/evidence")
    def list_evidence():
        # Raw low-score/suppressed research rows stay in the explicit AI filter
        # endpoint and never flood the athlete's ordinary clip library.
        return [row for row in store.list("video_evidence") if row.get("source") != "AI_SUGGESTION" or row.get("review_status") == "CONFIRMED"]

    @router.get("/ai-suggestions")
    def ai_suggestions(video_id: str | None = None, status: str | None = None, offset: int = 0,
                       limit: int = 50, attention: str | None = None):
        if status not in {None, "UNVERIFIED", "FILTERED", "CONFIRMED", "REJECTED"}:
            raise HTTPException(400, "未知的 AI 建议筛选状态")
        if attention not in {None, "NEEDS_REVIEW", "EVIDENCE_GAP"}:
            raise HTTPException(400, "未知的复核优先级筛选")
        if offset < 0 or not 1 <= limit <= 100:
            raise HTTPException(400, "分页参数无效")
        return store.ai_suggestions(video_id, status, offset, limit, attention)

    @router.post("/imports")
    def start_import(value: AIImportInput):
        try:
            return store.start_ai_import(value.video_id, value.path)
        except (ValueError, OSError, HTTPException) as exc:
            if isinstance(exc, HTTPException):
                raise exc
            raise HTTPException(400, str(exc)) from exc

    @router.get("/imports")
    def list_imports(video_id: str | None = None):
        rows = store.list("ai_import_batches")
        return [row for row in rows if not video_id or row.get("video_id") == video_id]

    @router.get("/imports/{batch_id}")
    def get_import(batch_id: str):
        return store.import_batch(batch_id)

    @router.post("/imports/{batch_id}/cancel")
    def cancel_import(batch_id: str):
        return store.cancel_ai_import(batch_id)

    @router.post("/imports/{batch_id}/resume")
    def resume_import(batch_id: str):
        try:
            return store.resume_ai_import(batch_id)
        except (ValueError, OSError, HTTPException) as exc:
            if isinstance(exc, HTTPException):
                raise exc
            raise HTTPException(400, str(exc)) from exc

    @router.post("/evidence")
    def create_evidence(value: EvidenceInput):
        try:
            return store.evidence(value)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.put("/evidence/{evidence_id}")
    def edit_evidence(evidence_id: str, value: EvidenceInput):
        try:
            return store.evidence(value, evidence_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("/evidence/{evidence_id}/review")
    def review_ai(evidence_id: str, value: AIReviewInput):
        try:
            return store.review_ai(evidence_id, value)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.delete("/evidence/{evidence_id}")
    def delete_evidence(evidence_id: str):
        row = store.get("video_evidence", "evidence_id", evidence_id)
        with repo.connect() as db:
            db.execute("DELETE FROM video_evidence WHERE evidence_id=?", (evidence_id,))
            db.execute(
                "INSERT INTO evidence_audit VALUES (?,?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    evidence_id,
                    "DELETE_EVIDENCE",
                    utc_now(),
                    json.dumps(row, ensure_ascii=False),
                ),
            )
        return {"deleted": True}

    @router.get("/collections")
    def collections():
        return store.list("evidence_collections")

    @router.get("/points")
    def points(video_id: str | None = None):
        return store.points(video_id)

    @router.post("/points")
    def create_point(value: PointInput):
        try:
            return store.save_point(value)
        except (ValueError, HTTPException) as exc:
            if isinstance(exc, HTTPException):
                raise exc
            raise HTTPException(400, str(exc)) from exc

    @router.put("/points/{point_id}")
    def edit_point(point_id: str, value: PointInput):
        try:
            return store.save_point(value, point_id)
        except (ValueError, HTTPException) as exc:
            if isinstance(exc, HTTPException):
                raise exc
            raise HTTPException(400, str(exc)) from exc

    @router.post("/collections")
    @router.put("/collections/{collection_id}")
    def save_collection(value: CollectionInput, collection_id: str | None = None):
        if not value.name.strip():
            raise HTTPException(400, "请填写收藏夹名称")
        if collection_id:
            store.get("evidence_collections", "collection_id", collection_id)
        ids = list(dict.fromkeys(value.evidence_ids))
        for identity in ids:
            store.get("video_evidence", "evidence_id", identity)
        return store.save(
            "evidence_collections",
            "collection_id",
            {
                "collection_id": collection_id or str(uuid.uuid4()),
                "name": value.name.strip(),
                "evidence_ids": ids,
                "updated_at": utc_now(),
            },
            "SAVE_PLAYLIST",
        )

    return router
