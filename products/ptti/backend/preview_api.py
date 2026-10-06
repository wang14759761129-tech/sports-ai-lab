"""Development-only product views over existing professional/vision capabilities."""
import json
import re
import subprocess
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.fullmatch import file_sha256
from backend.professional import ProfessionalMatchInput
from vision.quality import classify, video_metadata


class Registration(BaseModel):
    asset_id: str
    match_id: str | None = None
    metadata: dict = Field(default_factory=dict)
    rights_confirmed: bool = False
    source_note: str = Field(min_length=1, max_length=500)


def router(repo, data_root, mode):
    api = APIRouter(prefix="/api/preview")
    root = Path(data_root).resolve()
    staging = root / "preview-video-intake"

    def guard():
        if mode == "production":
            raise HTTPException(404, "Preview 仅在独立开发环境开放")

    def outputs(match_id):
        job = repo.get_full_match_job(match_id) or {}
        directory = Path(job.get("output_dir") or "")
        if not job.get("output_dir") or not directory.is_dir():
            return {"assets": [], "summary": None}
        try:
            directory.resolve().relative_to(root / "full_matches")
        except ValueError:
            return {"assets": [], "summary": None}
        allowed = ["full_match_report.html", "full_match_balltrack.csv", "full_match_balltrack.jsonl",
                   "full_match_summary.json", "match_structure.json", "match_structure.html"]
        assets = [{"name": name, "kind": "report" if name.endswith("html") else "data",
                   "url": f"/api/preview/matches/{match_id}/outputs/{name}"}
                  for name in allowed if (directory / name).is_file()]
        if (directory / 'full_match_balltrack.jsonl').is_file():
            assets.append({'name':'full_match_balltrack.json','kind':'data',
                'url':f'/api/preview/matches/{match_id}/outputs/full_match_balltrack.json'})
        for video in sorted((directory / "preview_overlays").glob("preview-*.mp4")):
            if re.fullmatch(r"preview-\d{2}\.mp4", video.name):
                assets.append({"name": video.name, "kind": "overlay",
                    "url": f"/api/preview/matches/{match_id}/outputs/{video.name}"})
        summary_path = directory / "full_match_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else None
        return {"assets": assets, "summary": summary, "output_directory": str(directory)}

    @api.get("/jobs")
    def jobs():
        guard()
        result = []
        for match in repo.professional_matches():
            job = repo.get_full_match_job(match["match_id"])
            if job:
                result.append({**job, "match_id": match["match_id"], "event_name": match["event_name"],
                    "player_a": repo.get_athlete(match["player_a_id"]),
                    "player_b": repo.get_athlete(match["player_b_id"]), "outputs": outputs(match["match_id"])})
        return sorted(result, key=lambda x: x.get("updated_at", x.get("created_at", "")), reverse=True)

    @api.get("/matches/{match_id}/outputs")
    def output_list(match_id: str):
        guard()
        if not repo.get_professional_match(match_id):
            raise HTTPException(404, "比赛不存在")
        return outputs(match_id)

    @api.get("/matches/{match_id}/outputs/{asset}")
    def output_asset(match_id: str, asset: str):
        guard()
        listing = outputs(match_id)
        if not any(item["name"] == asset for item in listing["assets"]):
            raise HTTPException(404, "分析文件尚未生成")
        directory = Path(listing["output_directory"])
        if asset=='full_match_balltrack.json':
            def rows():
                yield '['
                first=True
                with (directory/'full_match_balltrack.jsonl').open(encoding='utf-8') as stream:
                    for line in stream:
                        if not line.strip(): continue
                        value=json.dumps(json.loads(line),ensure_ascii=False)
                        yield ('' if first else ',')+value
                        first=False
                yield ']'
            return StreamingResponse(rows(),media_type='application/json',
                headers={'Content-Disposition':'attachment; filename="full_match_balltrack.json"'})
        candidate = directory / ("preview_overlays" if asset.endswith(".mp4") else "") / asset
        candidate = candidate.resolve()
        if not candidate.is_relative_to(directory.resolve()):
            raise HTTPException(403, "输出路径无效")
        return FileResponse(candidate, media_type="video/mp4" if asset.endswith(".mp4") else None,
                            filename=None if asset.endswith((".mp4", ".html")) else asset)

    @api.post("/videos/inspect")
    async def inspect(file: UploadFile = File(...)):
        guard()
        suffix = Path(file.filename or "").suffix.casefold()
        if suffix not in {".mp4", ".mov", ".mkv", ".avi"}:
            raise HTTPException(422, "请选择 MP4、MOV、MKV 或 AVI 视频")
        staging.mkdir(parents=True, exist_ok=True)
        asset_id = uuid.uuid4().hex
        path = staging / (asset_id + suffix)
        try:
            size = 0
            with path.open("xb") as stream:
                while block := await file.read(8 * 1024 * 1024):
                    size += len(block)
                    if size > 64 * 1024**3:
                        raise HTTPException(413, "当前支持不超过 64 GiB 的本机视频")
                    stream.write(block)
            media = video_metadata(path)
            result = {"asset_id": asset_id, "filename": Path(file.filename or "video").name,
                      "path": str(path), "size_bytes": size, "mtime_ns": path.stat().st_mtime_ns,
                      "sha256": file_sha256(path), "media": media, "quality": classify(media)}
            (staging / (asset_id + ".json")).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            return {k: v for k, v in result.items() if k != "path"}
        except HTTPException:
            path.unlink(missing_ok=True)
            raise
        except (OSError, ValueError, subprocess.SubprocessError):
            path.unlink(missing_ok=True)
            raise HTTPException(422, "视频无法读取，请确认文件完整后重新选择")
        finally:
            await file.close()

    @api.post("/videos/register", status_code=201)
    def register(value: Registration):
        guard()
        if not value.rights_confirmed or not value.source_note.strip():
            raise HTTPException(422, "请填写视频来源，并确认本机分析权限")
        if not re.fullmatch(r"[a-f0-9]{32}", value.asset_id):
            raise HTTPException(422, "视频登记标识无效")
        descriptor = staging / (value.asset_id + ".json")
        if not descriptor.is_file():
            raise HTTPException(404, "视频待登记记录不存在，请重新选择")
        staged = json.loads(descriptor.read_text(encoding="utf-8"))
        path = Path(staged["path"]).resolve()
        if path.parent != staging.resolve() or not path.is_file():
            raise HTTPException(422, "本机视频已移动，请重新选择")
        if path.stat().st_size != staged["size_bytes"] or file_sha256(path) != staged["sha256"]:
            raise HTTPException(409, "视频内容发生变化，请重新选择")
        if any(m.get("video_metadata", {}).get("sha256") == staged["sha256"] for m in repo.professional_matches()):
            raise HTTPException(409, "这段视频已经登记，请打开对应比赛")
        existing = repo.get_professional_match(value.match_id) if value.match_id else None
        if value.match_id and not existing:
            raise HTTPException(404, "选择的比赛不存在")
        if existing and existing.get("video_local_path"):
            raise HTTPException(409, "此比赛已关联视频，请新建比赛记录，保留原分析证据")
        fields = {key: existing.get(key) for key in ProfessionalMatchInput.model_fields} if existing else value.metadata.copy()
        fields.update(video_source_type="LOCAL_USER_VIDEO", rights_status="USER_AUTHORIZED", video_local_path=str(path), wtt_asset_id=None)
        try:
            record = ProfessionalMatchInput.model_validate(fields).to_record()
            record.update(analysis_status="VIDEO_READY", video_original_filename=staged["filename"],
                video_source_note=value.source_note.strip(),
                video_metadata={**staged["media"], "sha256": staged["sha256"], "size_bytes": staged["size_bytes"],
                    "mtime_ns": staged["mtime_ns"], "quality": staged["quality"]})
            if existing:
                record["match_id"] = existing["match_id"]
                with repo.connect() as db:
                    db.execute("UPDATE professional_matches SET payload=? WHERE match_id=?",
                               (json.dumps(record, ensure_ascii=False), record["match_id"]))
            else:
                repo.save_professional_match(record)
            return record
        except ValueError as exc:
            raise HTTPException(422, "比赛信息不完整，请核对双方运动员与赛事名称") from exc

    return api
