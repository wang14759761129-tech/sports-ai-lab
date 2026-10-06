"""Persistent, resumable whole-match BallTrack orchestration.

The official RacketVision model remains frozen and unmodified. Input videos are
read-only; every normalized segment, checkpoint, raw prediction, and report is
stored under the active isolated database's data directory.
"""
import csv
import hashlib
import html
import json
import os
import tempfile
from pathlib import Path
import subprocess
import threading
from datetime import datetime, timezone

from backend.fullmatch import (DEFAULT_CHUNK_SECONDS, PROCESSING_VERSION, build_chunks,
                               cache_key, file_sha256, map_chunk_observation,
                               extract_source_frame_timestamps, quality_report,
                               run_resumable_chunks, save_manifest)
from vision.config import VisionConfig, RV_COMMIT
from vision.quality import video_metadata, classify


def _json_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class FullMatchService:
    def __init__(self, repo, data_root, config=None, chunk_seconds=DEFAULT_CHUNK_SECONDS):
        self.repo = repo
        self.data_root = Path(data_root).resolve()
        self.config = config or VisionConfig.load()
        self.chunk_seconds = int(chunk_seconds)
        if not 30 <= self.chunk_seconds <= 120:
            raise ValueError("Chunk duration must be between 30 and 120 seconds")
        self.root = self.data_root / "full_matches"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.active = set()

    def prepare(self, record, device="cuda"):
        if device not in ("cuda", "cpu"):
            raise ValueError("Processing device must be cuda or cpu")
        if record.get("video_source_type") not in {"LICENSED_WTT_LOCAL", "LOCAL_USER_VIDEO", "RESEARCH_DATASET"}:
            raise ValueError("Full-match processing requires authorized local video")
        if record.get("rights_status") not in {"LICENSED_FOR_ANALYSIS", "USER_AUTHORIZED", "RESEARCH_DATASET_AUTHORIZED"}:
            raise ValueError("Video rights are not approved for local analysis")
        video = Path(record.get("video_local_path") or "").resolve()
        if not video.is_file():
            raise ValueError("Registered local video is unavailable")
        checkpoint = self.config.model_root / "balltrack_best.pth"
        if not checkpoint.is_file() or not self.config.worker_python.is_file():
            raise ValueError("Frozen BallTrack runtime/checkpoint is not installed")
        meta = video_metadata(video)
        video_hash = file_sha256(video)
        checkpoint_hash = file_sha256(checkpoint)
        options = {"device": device, "chunk_seconds": self.chunk_seconds, "fps": meta["fps"],
                   "batchsize": 2, "rv_commit": RV_COMMIT, "normalization": "CFR per chunk",
                   "background": "whole-match median from up to 100 deterministic samples"}
        config_hash = _json_sha(options)
        key = cache_key(video_hash, checkpoint_hash, config_hash)
        match_folder = self.root / hashlib.sha256(record["match_id"].encode()).hexdigest()[:20]
        run_folder = match_folder / key
        manifest_path = run_folder / "manifest.json"
        return {"video": video, "checkpoint": checkpoint, "metadata": meta,
                "video_sha256": video_hash, "checkpoint_sha256": checkpoint_hash,
                "config": options, "config_sha256": config_hash, "cache_key": key,
                "run_folder": run_folder, "manifest_path": manifest_path}

    def start(self, match_id, device="cuda", resume=False):
        record = self.repo.get_professional_match(match_id)
        if not record:
            raise ValueError("Professional match not found")
        prepared = self.prepare(record, device)
        with self.lock:
            if match_id in self.active:
                raise ValueError("A full-match job is already active for this match")
            self.active.add(match_id)
        try:
            existing = self.repo.get_full_match_job(match_id) or {}
            if resume:
                manifest_path = Path(existing.get("manifest_path") or "")
                if not manifest_path.is_file():
                    raise ValueError("No resumable full-match manifest exists")
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest.get("cache_key") != prepared["cache_key"]:
                    raise ValueError("Video/checkpoint/config changed; refusing to resume a different analysis")
                if manifest.get("status") == "BALLTRACK_COMPLETE":
                    return existing
            else:
                prepared["run_folder"].mkdir(parents=True, exist_ok=True)
                media = prepared["metadata"]
                frames = media.get("frame_count") or round(media["duration"] * media["fps"])
                if prepared["manifest_path"].is_file():
                    raise ValueError("A matching cached analysis exists; use resume instead of replacing its evidence")
                timestamps_path=None
                frame_timestamps=None
                if media.get("rate_variable"):
                    frame_timestamps=extract_source_frame_timestamps(prepared["video"],media.get("frame_count"))
                    frames=len(frame_timestamps)
                    timestamps_path=prepared["run_folder"]/'source_frame_timestamps_ms.json'
                    timestamps_path.write_text(json.dumps(frame_timestamps,separators=(",",":")),encoding="utf-8")
                chunks = build_chunks(frames, media["fps"], self.chunk_seconds,frame_timestamps)
                manifest = {
                "manifest_version": 1, "processing_version": PROCESSING_VERSION,
                "cache_key": prepared["cache_key"], "video_sha256": prepared["video_sha256"],
                "checkpoint_sha256": prepared["checkpoint_sha256"], "config_sha256": prepared["config_sha256"],
                "config": prepared["config"], "match_id": match_id,
                "input_path": str(prepared["video"]), "media": media,
                "frame_timeline_basis": "global_frame is full-run CFR processing ordinal; timestamp_ms is mapped to source presentation time; source_frame records nearest source frame for VFR",
                "source_frame_timestamps_path": str(timestamps_path) if timestamps_path else None,
                "chunk_seconds": self.chunk_seconds, "chunks": chunks,
                "scene_segments": [{"scene_id": "scene-0001", "start_ms": 0,
                    "end_ms": round(media["duration"] * 1000), "scene_type": "UNKNOWN",
                    "review_status": "CANDIDATE", "evidence": {"source": "UNCLASSIFIED",
                    "note": "Camera-cut classification is not yet validated; review before interpreting view type."}}],
                "status": "QUEUED", "created_at": datetime.now(timezone.utc).isoformat(),
                }
                save_manifest(prepared["manifest_path"], manifest)
            job = {"match_id": match_id, "status": "QUEUED", "stage": "等待处理",
               "cache_key": prepared["cache_key"], "manifest_path": str(prepared["manifest_path"]),
               "completed_chunks": sum(c["status"] == "COMPLETE" for c in manifest["chunks"]),
               "total_chunks": len(manifest["chunks"]), "device": device,
               "quality_report": quality_report(prepared["metadata"],
                   record.get("video_metadata",{}).get("size_bytes",0),device,self.chunk_seconds)}
            self.repo.save_full_match_job(match_id, job)
            thread = threading.Thread(target=self._run, args=(record, prepared, manifest, device), daemon=True)
            thread.start()
            return job
        except Exception:
            with self.lock:
                self.active.discard(match_id)
            raise

    def _run(self, record, prepared, manifest, device):
        match_id = record["match_id"]
        path = prepared["manifest_path"]
        worker = Path(__file__).resolve().parents[1] / "vision_worker" / "balltrack.py"
        logs = prepared["run_folder"] / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        timestamps_path=manifest.get("source_frame_timestamps_path")
        source_frame_times=(json.loads(Path(timestamps_path).read_text(encoding="utf-8"))
                            if timestamps_path and Path(timestamps_path).is_file() else None)

        def persist(current):
            job = {"match_id": match_id, "status": current["status"], "stage": current["status"],
                   "cache_key": current["cache_key"], "manifest_path": str(path),
                   "completed_chunks": sum(c["status"] == "COMPLETE" for c in current["chunks"]),
                   "total_chunks": len(current["chunks"]), "device": device,
                   "last_error": current.get("last_error"),
                   "current_chunk": next((c["chunk_index"] for c in current["chunks"] if c["status"] == "RUNNING"), None)}
            self.repo.save_full_match_job(match_id, job)

        def execute(chunk):
            chunk_root = prepared["run_folder"] / "chunks" / f"{chunk['chunk_index'] + 1:06d}"
            chunk_root.mkdir(parents=True, exist_ok=True)
            chunk_video = chunk_root / "input.mp4"
            expected_frames = chunk.get("expected_processed_frames",chunk["end_frame_exclusive"] - chunk["start_frame_inclusive"])
            start_seconds = chunk["source_timestamp_start_ms"] / 1000.0
            duration_seconds = (chunk["source_timestamp_end_ms"]-chunk["source_timestamp_start_ms"])/1000.0
            command = ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{start_seconds:.9f}",
                       "-i", str(prepared["video"]), "-t", f"{duration_seconds:.9f}",
                       "-map", "0:v:0", "-an", "-vf", f"fps={prepared['metadata']['fps']}",
                       "-frames:v", str(expected_frames), "-c:v", "libx264", "-preset", "ultrafast",
                       "-crf", "18", "-y", str(chunk_video)]
            subprocess.run(command, check=True, timeout=3600, capture_output=True, text=True)
            output = chunk_root / "balltrack"
            output.mkdir(exist_ok=True)
            log_path = logs / f"chunk-{chunk['chunk_index'] + 1:06d}.log"
            worker_command = [str(self.config.worker_python), str(worker),
                              "--runtime", str(self.config.runtime_root), "--checkpoint", str(prepared["checkpoint"]),
                              "--video", str(chunk_video), "--output", str(output), "--device", device,
                              "--batchsize", "2", "--median-input",
                              str(prepared["run_folder"] / "global_median.npz")]
            with log_path.open("w", encoding="utf-8") as log:
                subprocess.run(worker_command, stdout=log, stderr=subprocess.STDOUT,
                               check=True, timeout=3600, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            raw_path = output / "raw_prediction.json"
            runtime_path = output / "runtime.json"
            if not raw_path.is_file() or not runtime_path.is_file():
                raise RuntimeError("BallTrack worker finished without prediction/runtime evidence")
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
            if len(raw) != expected_frames:
                raise RuntimeError(f"Chunk frame count mismatch: expected {expected_frames}, got {len(raw)}")
            mapped = []
            for row in raw:
                frame = map_chunk_observation(chunk, int(row["Frame"]), prepared["metadata"]["fps"],source_frame_times)
                mapped.append({"global_frame": frame["global_frame"], "source_frame":frame["source_frame"],
                               "timestamp_ms": round(frame["timestamp_ms"], 3),
                               "local_frame": int(row["Frame"]), "chunk_index": chunk["chunk_index"],
                               "visible": bool(row["Visibility"]), "x": row["X"] if row["Visibility"] else None,
                               "y": row["Y"] if row["Visibility"] else None,
                               "raw_model_score": row.get("Confidence"),
                               "raw_score_semantics": "Upstream threshold-component mean; not calibrated probability"})
            mapped_path = output / "global_observations.json"
            mapped_path.write_text(json.dumps(mapped, ensure_ascii=False), encoding="utf-8")
            runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
            return {"raw_prediction_path": str(raw_path), "observations_path": str(mapped_path),
                    "runtime_path": str(runtime_path), "log_path": str(log_path),
                    "decoded_frames": len(raw), "runtime": runtime,
                    "completed_at": datetime.now(timezone.utc).isoformat()}

        try:
            background_path = prepared["run_folder"] / "global_median.npz"
            if not background_path.is_file():
                background_script = Path(__file__).resolve().parents[1] / "vision_worker" / "background.py"
                subprocess.run([str(self.config.worker_python), str(background_script),
                                "--runtime", str(self.config.runtime_root), "--video", str(prepared["video"]),
                                "--output", str(background_path)], check=True, timeout=3600,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            manifest = json.loads(path.read_text(encoding="utf-8"))
            background_info = background_path.with_suffix(".json")
            manifest["background"] = {"path": str(background_path), "metadata_path": str(background_info),
                                      "sha256": file_sha256(background_path),
                                      "sampling": json.loads(background_info.read_text(encoding="utf-8"))}
            save_manifest(path, manifest)
            manifest = run_resumable_chunks(path, execute, persist)
            merged_csv = prepared["run_folder"] / "full_match_balltrack.csv"
            columns = ["global_frame", "source_frame", "timestamp_ms", "local_frame", "chunk_index", "visible", "x", "y",
                       "raw_model_score", "raw_score_semantics"]
            frame_count = visible = 0
            previous_global_frame = -1
            with merged_csv.open("w", encoding="utf-8", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=columns)
                writer.writeheader()
                for chunk in sorted(manifest["chunks"],key=lambda item:item["chunk_index"]):
                    observations=json.loads(Path(chunk["observations_path"]).read_text(encoding="utf-8"))
                    for item in observations:
                        if item["global_frame"]<=previous_global_frame:
                            raise ValueError("Chunk outputs are duplicated or out of global timeline order")
                        previous_global_frame=item["global_frame"]
                        writer.writerow(item);frame_count+=1;visible+=bool(item["visible"])
            timeline = self.repo.get_match_timeline(match_id) or {
                "match_id": match_id, "revision": 0, "games": [], "scene_segments": manifest["scene_segments"]}
            timeline_path = prepared["run_folder"] / "match_timeline.json"
            timeline_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
            media = manifest["media"]
            points = [point for game in timeline.get("games", []) for point in game.get("points", [])]
            rallies = [rally for point in points for rally in point.get("rallies", [])]
            summary = {"match_id": match_id, "event": record["event_name"], "round": record.get("round"),
                       "player_a_id": record["player_a_id"], "player_b_id": record["player_b_id"],
                       "duration_seconds": media["duration"], "games": len(timeline.get("games", [])),
                       "points": len(points), "rallies": len(rallies),
                       "average_rally_duration_ms": (sum(r["end_ms"] - r["start_ms"] for r in rallies) / len(rallies) if rallies else None),
                       "balltrack_frames": frame_count, "balltrack_visible_frames": visible,
                       "balltrack_coverage": visible / frame_count if frame_count else None,
                       "video_quality": quality_report_for_summary(media, record),
                       "analysis_completeness": {"video_validated": True, "full_match_balltrack": True,
                           "game_point_segmentation": bool(points), "manual_review_complete": all(p.get("review_status") in {"ACCEPTED", "ADJUSTED"} for p in points) if points else False},
                       "manual_corrections": sum(p.get("segmentation_source") == "MANUAL" for p in points),
                       "player_model_hooks": [{"athlete_id": athlete_id, "match_id": match_id,
                           "status": "STRUCTURE_READY_ONLY", "metrics_emitted": []}
                           for athlete_id in (record["player_a_id"],record["player_b_id"])],
                       "scoreboard_recognizer": {"status": "EXPERIMENTAL", "used": False,
                           "fallback": "MANUAL_SCORE_ENTRY"},
                       "notes": "No serve, spin, stroke, scorer, or tactics are inferred by BallTrack."}
            summary_path = prepared["run_folder"] / "full_match_summary.json"
            summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            report = _summary_html(summary)
            (prepared["run_folder"] / "full_match_report.html").write_text(report, encoding="utf-8")
            job = {"match_id": match_id, "status": "BALLTRACK_COMPLETE", "stage": "全场球追踪完成；时间轴待人工校正",
                   "cache_key": prepared["cache_key"], "manifest_path": str(path),
                   "output_dir": str(prepared["run_folder"]), "summary_path": str(summary_path),
                   "report_path": str(prepared["run_folder"] / "full_match_report.html"),
                   "csv_path": str(merged_csv), "completed_chunks": len(manifest["chunks"]),
                   "total_chunks": len(manifest["chunks"]), "device": device,
                   "summary": summary}
            self.repo.save_full_match_job(match_id, job)
        except Exception as exc:
            current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else manifest
            current["status"] = "PAUSED"
            current["last_error"] = str(exc)
            if path.is_file():
                save_manifest(path, current)
            job = {"match_id": match_id, "status": current.get("status", "FAILED"),
                   "stage": "处理暂停，可从失败分块继续", "cache_key": prepared["cache_key"],
                   "manifest_path": str(path), "last_error": str(exc),
                   "completed_chunks": sum(c["status"] == "COMPLETE" for c in current.get("chunks", [])),
                   "total_chunks": len(current.get("chunks", [])), "device": device}
            self.repo.save_full_match_job(match_id, job)
        finally:
            with self.lock:
                self.active.discard(match_id)


def quality_report_for_summary(metadata, record):
    return quality_report(metadata, record.get("video_metadata", {}).get("size_bytes", 0),
                          "frozen BallTrack v1", DEFAULT_CHUNK_SECONDS) | {
        "sha256": record.get("video_metadata", {}).get("sha256"),
        "camera_changes": "UNKNOWN"}


def _summary_html(summary):
    cells = "".join(f"<tr><th>{html.escape(key)}</th><td>{html.escape(str(value))}</td></tr>"
                    for key, value in summary.items())
    return ("<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>PTTI 全场比赛摘要</title>"
            "<style>body{font:16px 'Microsoft YaHei',sans-serif;max-width:900px;margin:32px auto}"
            "th,td{padding:8px;text-align:left;border-bottom:1px solid #ddd}</style>"
            "<h1>PTTI · 全场比赛分析摘要</h1><p>只报告视频质量、BallTrack 观测与人工记录结构；不推断战术。</p>"
            f"<table>{cells}</table></html>")


def refresh_timeline_summary(repo, match_id, timeline):
    """Keep persisted full-match outputs aligned with human timeline edits."""
    job = repo.get_full_match_job(match_id)
    if not job or job.get("status") != "BALLTRACK_COMPLETE" or not job.get("output_dir"):
        return
    output_dir = Path(job["output_dir"])
    summary_path = output_dir / "full_match_summary.json"
    if not summary_path.is_file():
        return
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    points = [point for game in timeline.get("games", []) for point in game.get("points", [])]
    rallies = [rally for point in points for rally in point.get("rallies", [])]
    summary.update(games=len(timeline.get("games", [])), points=len(points), rallies=len(rallies),
                   average_rally_duration_ms=(sum(r["end_ms"]-r["start_ms"] for r in rallies)/len(rallies) if rallies else None),
                   analysis_completeness={**summary.get("analysis_completeness", {}),
                     "game_point_segmentation": bool(points),
                     "manual_review_complete": bool(points) and all(p.get("review_status") in {"ACCEPTED", "ADJUSTED"} for p in points)},
                   manual_corrections=sum(p.get("segmentation_source") == "MANUAL" for p in points))
    for name, content in (("match_timeline.json", json.dumps(timeline, ensure_ascii=False, indent=2)),
                          ("full_match_summary.json", json.dumps(summary, ensure_ascii=False, indent=2)),
                          ("full_match_report.html", _summary_html(summary))):
        target = output_dir / name
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output_dir, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        temporary.replace(target)
    job["summary"] = summary
    repo.save_full_match_job(match_id, job)
