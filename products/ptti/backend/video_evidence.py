"""Local, reference-only evidence library. No vision runtime or research GT access."""

import hashlib
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


def utc_now():
    return datetime.now(timezone.utc).isoformat()


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
    review_status: Literal["CONFIRMED", "REJECTED", "REVIEW_REQUIRED"] = "CONFIRMED"


class CollectionInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    evidence_ids: list[str] = Field(default_factory=list, max_length=10000)


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
        return store.list("video_evidence")

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
