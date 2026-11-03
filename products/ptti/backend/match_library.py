"""Video-first catalogue and opt-in, bounded local indexing. No model or GT reads."""
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.video_evidence import VideoInput, digest_file, utc_now
from vision.quality import video_metadata

VIDEO_STATES = {"LOCAL_READY", "AUTHORIZED_REMOTE_PLAYABLE", "OFFICIAL_EMBED_ALLOWED",
                "SOURCE_LINK_ONLY", "RIGHTS_REQUIRED", "UNAVAILABLE"}


class VideoSourceProvider:
    """An official page is a reference, never a licensed media stream."""
    @staticmethod
    def describe(match, videos):
        playable = [v for v in videos if v.get("match_id") == match["match_id"]
                    and v.get("availability_status") == "AVAILABLE"]
        url = match.get("external_reference_url")
        if url and (urlsplit(url).scheme != "https" or not urlsplit(url).netloc):
            url = None
        return {"status": "LOCAL_READY" if playable else "SOURCE_LINK_ONLY" if url else "RIGHTS_REQUIRED",
                "video_ids": [v["video_id"] for v in playable], "official_url": url,
                "reason": "已关联获准使用的本机录像" if playable else
                "比赛资料已收录，完整视频尚未获得可播放权限。",
                "embedding_verified": False, "frame_access": bool(playable)}


class FolderInput(BaseModel):
    path: str = Field(min_length=1, max_length=4000)
    rights_status: str = Field(pattern="^(USER_OWNED|LICENSED|RESEARCH_NONCOMMERCIAL)$")
    rights_confirmed: bool
    source_note: str = Field(min_length=1, max_length=2000)


class ConfirmInput(BaseModel):
    candidate_id: str
    match_id: str | None = None


class MappingInput(BaseModel):
    match_id: str
    user_confirmed: bool


class LocalMediaIndexer:
    def __init__(self, store):
        self.store = store
        self.stop = threading.Event()
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="media-index")
        self.lock = threading.Lock()
        self.confirm_lock = threading.Lock()
        with store.repo.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS media_scan_jobs (scan_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS media_recent_views (video_id TEXT PRIMARY KEY, viewed_at TEXT NOT NULL)")
            for identity, raw in db.execute("SELECT scan_id,payload FROM media_scan_jobs").fetchall():
                row = json.loads(raw)
                if row["status"] in {"QUEUED", "RUNNING"}:
                    row.update(status="INTERRUPTED", message="索引已中断；重新扫描会复用已登记录像")
                    db.execute("UPDATE media_scan_jobs SET payload=? WHERE scan_id=?", (json.dumps(row), identity))

    def save(self, row):
        # Progress is a recoverable checkpoint, not a human review action. Avoid
        # duplicating an ever-growing inventory in the append-only review audit.
        with self.store.repo.connect() as db:
            db.execute("INSERT INTO media_scan_jobs VALUES (?,?) ON CONFLICT(scan_id) DO UPDATE SET payload=excluded.payload",
                       (row["scan_id"], json.dumps(row, ensure_ascii=False)))

    def close(self):
        self.stop.set()
        self.worker.shutdown(wait=True, cancel_futures=True)

    def start(self, value):
        if not value.rights_confirmed or not value.source_note.strip():
            raise ValueError("请确认文件夹内视频的使用权限并填写来源")
        if value.path.startswith("\\\\"):
            raise ValueError("只支持本机视频文件夹")
        root = Path(value.path).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError("请选择存在的视频文件夹")
        with self.lock:
            if any(r["status"] in {"QUEUED", "RUNNING"} for r in self.store.list("media_scan_jobs")):
                raise ValueError("已有文件夹正在索引，请等待完成")
            row = {"scan_id": str(uuid.uuid4()), "path": str(root), "status": "QUEUED",
                   "rights_status": value.rights_status, "source_note": value.source_note,
                   "created_at": utc_now(), "candidates": [], "errors": [], "message": "等待后台索引"}
            self.save(row)
            self.worker.submit(self.scan, row)
        return row

    def scan(self, row):
        row.update(status="RUNNING", message="后台读取视频信息；原文件不会复制")
        self.save(row)
        try:
            existing = self.store.list("evidence_videos")
            # Deliberately non-recursive: user chooses the exact folder. No huge tree walks.
            for path in Path(row["path"]).iterdir():
                if self.stop.is_set():
                    row.update(status="INTERRUPTED", message="索引安全停止；可以重新扫描")
                    break
                if path.is_symlink() or not path.is_file() or path.suffix.lower() not in {".mp4", ".mov", ".mkv", ".avi"}:
                    continue
                if "extendedopenttgames" in str(path).lower() and (path.stem.lower() == "game_5" or path.stem.lower().startswith("test")):
                    continue  # Research holdout/test remain inaccessible in this sprint.
                if len(row["candidates"]) >= 500:
                    row["errors"].append("本次最多索引 500 个视频，请分文件夹处理")
                    break
                try:
                    resolved = path.resolve(strict=True)
                    stat = resolved.stat()
                    same = next((v for v in existing if Path(v["original_path"]) == resolved and
                                 v["file_size"] == stat.st_size and v["mtime_ns"] == stat.st_mtime_ns), None)
                    media = video_metadata(resolved)
                    sha = same.get("source_sha256") if same else None
                    if not sha:
                        sha = digest_file(resolved, self.stop)
                    after = resolved.stat()
                    if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise ValueError("视频在索引中改变，请稍后重试")
                    known = next((v for v in existing if v.get("source_sha256") == sha), same)
                    matches = self.store.repo.professional_matches()
                    suggestions = []
                    filename = resolved.stem.casefold()
                    for m in matches:
                        people = [self.store.repo.get_athlete(m[key]) for key in ("player_a_id", "player_b_id")]
                        if all(any(str(p.get(k) or "__missing__").casefold() in filename for k in
                                   ("canonical_name_zh", "canonical_name_en")) for p in people):
                            suggestions.append(m["match_id"])
                    row["candidates"].append({"candidate_id": str(uuid.uuid4()), "path": str(resolved),
                        "filename": resolved.name, "sha256": sha, "size": stat.st_size,
                        "mtime_ns": stat.st_mtime_ns, "media": media,
                        "existing_video_id": known["video_id"] if known else None,
                        "suggested_match_ids": suggestions, "status": "REVIEW_REQUIRED"})
                except InterruptedError:
                    row.update(status="INTERRUPTED", message="索引安全停止")
                    break
                except Exception as exc:
                    if len(row["errors"]) < 50:
                        row["errors"].append(f"{path.name}：读取失败（{type(exc).__name__}）")
                self.save(row)
            else:
                row.update(status="COMPLETED", message="索引完成；请确认关联，不会根据文件名自动绑定")
            if row["status"] == "RUNNING":
                row.update(status="COMPLETED", message="索引完成，请检查提示")
        except Exception as exc:
            row.update(status="FAILED", message=f"无法读取文件夹（{type(exc).__name__}）")
        self.save(row)

    def confirm(self, scan_id, value):
        with self.confirm_lock:
            job = self.store.get("media_scan_jobs", "scan_id", scan_id)
            if job["status"] not in {"COMPLETED", "INTERRUPTED"}:
                raise ValueError("请等待索引完成后确认")
            item = next((c for c in job["candidates"] if c["candidate_id"] == value.candidate_id), None)
            if not item:
                raise ValueError("视频候选不存在")
            match = self.store.repo.get_professional_match(value.match_id) if value.match_id else None
            if value.match_id and not match:
                raise ValueError("比赛不存在，不能关联")
            path = Path(item["path"])
            if not path.is_file() or digest_file(path, self.stop) != item["sha256"]:
                raise ValueError("视频已移动或改变，请重新扫描")
            video = next((v for v in self.store.list("evidence_videos") if v.get("source_sha256") == item["sha256"] or
                          (Path(v["original_path"]) == path and v["file_size"] == path.stat().st_size
                           and v["mtime_ns"] == path.stat().st_mtime_ns)), None)
            if video:
                if self.store.availability(video)["availability_status"] != "AVAILABLE":
                    video = self.store.relink(video["video_id"], str(path))
                if video.get("match_id") != value.match_id:
                    if video.get("match_id"):
                        raise ValueError("此录像已有比赛关联；本轮不静默覆盖，请核对原关联")
                    video = {**video, "match_id": value.match_id,
                             "athlete_ids": [match["player_a_id"], match["player_b_id"]] if match else [],
                             "mapping_source": "USER_CONFIRMED"}
                    self.store.save("evidence_videos", "video_id", video, "USER_CONFIRMED_MATCH_MAPPING")
            else:
                video = self.store.register(VideoInput(path=str(path), title=path.stem, match_id=value.match_id,
                    rights_status=job["rights_status"], rights_confirmed=True, source_note=job["source_note"]))
                # Already hashed during indexing; keep the ordinary registrar's background check too.
            return video


def library_router(store):
    indexer = LocalMediaIndexer(store)

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            indexer.close()

    router = APIRouter(prefix="/library", lifespan=lifespan)

    @router.get("")
    def catalog():
        videos = [store.availability(v) for v in store.list("evidence_videos")]
        with store.repo.connect() as db:
            recent = dict(db.execute("SELECT video_id,viewed_at FROM media_recent_views"))
        videos = [{**v, "last_opened_at": recent.get(v["video_id"])} for v in videos]
        matches = []
        for m in store.repo.professional_matches():
            matches.append({**m, "players": {"player_a": store.repo.get_athlete(m["player_a_id"]),
                "player_b": store.repo.get_athlete(m["player_b_id"])},
                "sources": store.repo.get_sources(m.get("source_ids", [])),
                "video_source": VideoSourceProvider.describe(m, videos)})
        editions = {m["event_name"]: {"edition_id": m.get("event_id") or m["event_name"],
                    "name": m["event_name"], "competition": m.get("competition_level"),
                    "date": m.get("event_date"), "source_ids": m.get("source_ids", [])} for m in matches}
        return {"matches": matches, "videos": videos, "athletes": store.repo.list_athletes(),
                "tournament_editions": list(editions.values()),
                "collections": store.list("evidence_collections"),
                "summary": {"matches": len(matches), "playable_professional": sum(m["video_source"]["status"] == "LOCAL_READY" for m in matches),
                    "local_playable": sum(v["availability_status"] == "AVAILABLE" for v in videos)},
                "remote_policy": "SOURCE_LINK_ONLY_UNTIL_PERMISSION_VERIFIED"}

    @router.get("/folders")
    def folders():
        return store.list("media_scan_jobs")

    @router.post("/videos/{video_id}/opened")
    def opened(video_id: str):
        video = store.get("evidence_videos", "video_id", video_id)
        if store.availability(video)["availability_status"] != "AVAILABLE":
            raise HTTPException(400, "录像暂时离线，不记录为最近观看")
        stamp = utc_now()
        with store.repo.connect() as db:
            db.execute("INSERT INTO media_recent_views VALUES (?,?) ON CONFLICT(video_id) DO UPDATE SET viewed_at=excluded.viewed_at",
                       (video_id, stamp))
        return {"video_id": video_id, "last_opened_at": stamp}

    @router.post("/folders")
    def start(value: FolderInput):
        try:
            return indexer.start(value)
        except (ValueError, OSError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("/folders/{scan_id}/confirm")
    def confirm(scan_id: str, value: ConfirmInput):
        try:
            return indexer.confirm(scan_id, value)
        except (ValueError, OSError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.put("/videos/{video_id}/match")
    def map_video(video_id: str, value: MappingInput):
        with indexer.confirm_lock:
            match = store.repo.get_professional_match(value.match_id)
            if not value.user_confirmed or not match:
                raise HTTPException(400, "必须确认真实比赛关联")
            old = store.get("evidence_videos", "video_id", video_id)
            if old.get("match_id") == value.match_id:
                return old
            if old.get("match_id"):
                raise HTTPException(400, "此录像已有比赛关联，不会覆盖")
            row = {**old, "match_id": value.match_id,
                   "athlete_ids": [match["player_a_id"], match["player_b_id"]],
                   "mapping_source": "USER_CONFIRMED"}
            store.save("evidence_videos", "video_id", row, "USER_CONFIRMED_MATCH_MAPPING")
            return row

    return router
