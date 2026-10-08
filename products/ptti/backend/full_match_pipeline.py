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
import time
from datetime import datetime, timezone

from backend.fullmatch import (DEFAULT_CHUNK_SECONDS, PROCESSING_VERSION, build_chunks,
                               cache_key, file_sha256, map_chunk_observation,
                               extract_source_frame_timestamps, quality_report, source_identity,
                               system_resource_snapshot, ResourceGuardStop, ResourceTrendGuard,
                               run_resumable_chunks, save_manifest)
from vision.config import VisionConfig, RV_COMMIT
from vision.quality import video_metadata, classify


def _json_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _atomic_text(path, text):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


class FullMatchService:
    def __init__(self, repo, data_root, config=None, chunk_seconds=DEFAULT_CHUNK_SECONDS,
                 min_available_ram_gib=None, max_new_chunks_per_run=None,
                 resource_sample_seconds=5.0):
        self.repo = repo
        self.data_root = Path(data_root).resolve()
        self.config = config or VisionConfig.load()
        self.chunk_seconds = int(chunk_seconds)
        if not 30 <= self.chunk_seconds <= 120:
            raise ValueError("Chunk duration must be between 30 and 120 seconds")
        self.min_available_ram_gib = (None if min_available_ram_gib is None
                                      else float(min_available_ram_gib))
        if self.min_available_ram_gib is not None and self.min_available_ram_gib < 1.0:
            raise ValueError("Resource guard must reserve at least 1 GiB of available RAM")
        self.resource_sample_seconds = max(1.0, float(resource_sample_seconds))
        if max_new_chunks_per_run is not None and int(max_new_chunks_per_run) < 1:
            raise ValueError("Chunk batch limit must be positive")
        self.max_new_chunks_per_run = (None if max_new_chunks_per_run is None
                                       else int(max_new_chunks_per_run))
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
        identity = source_identity(video)
        registered = record.get("video_metadata", {})
        if registered.get("sha256") and registered["sha256"] != identity["sha256"]:
            raise ValueError("SOURCE_CHANGED: registered video SHA256 no longer matches")
        if registered.get("size_bytes") is not None and registered["size_bytes"] != identity["size_bytes"]:
            raise ValueError("SOURCE_CHANGED: registered video size no longer matches")
        if registered.get("mtime_ns") is not None and registered["mtime_ns"] != identity["mtime_ns"]:
            raise ValueError("SOURCE_CHANGED: registered video modification time no longer matches")
        video_hash = identity["sha256"]
        checkpoint_hash = file_sha256(checkpoint)
        options = {"device": device, "chunk_seconds": self.chunk_seconds, "fps": meta["fps"],
                   "batchsize": 2, "rv_commit": RV_COMMIT, "normalization": "CFR per chunk",
                   "background": "whole-match median from up to 100 deterministic samples"}
        config_hash = _json_sha(options)
        key = cache_key(video_hash, checkpoint_hash, config_hash)
        match_folder = self.root / hashlib.sha256(record["match_id"].encode()).hexdigest()[:20]
        run_folder = match_folder / key
        manifest_path = run_folder / "manifest.json"
        return {"video": video, "source_identity": identity, "checkpoint": checkpoint, "metadata": meta,
                "video_sha256": video_hash, "checkpoint_sha256": checkpoint_hash,
                "config": options, "config_sha256": config_hash, "cache_key": key,
                "run_folder": run_folder, "manifest_path": manifest_path}

    def start(self, match_id, device="cuda", resume=False):
        record = self.repo.get_professional_match(match_id)
        if not record:
            raise ValueError("Professional match not found")
        prepared = self.prepare(record, device)
        existing = self.repo.get_full_match_job(match_id) or {}
        with self.lock:
            if match_id in self.active:
                if resume and existing.get("status") == "BALLTRACK_COMPLETE":
                    return existing
                raise ValueError("A full-match job is already active for this match")
            self.active.add(match_id)
        try:
            if resume:
                manifest_path = Path(existing.get("manifest_path") or "")
                if not manifest_path.is_file():
                    raise ValueError("No resumable full-match manifest exists")
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest.get("cache_key") != prepared["cache_key"]:
                    raise ValueError("Video/checkpoint/config changed; refusing to resume a different analysis")
                if manifest.get("status") == "BALLTRACK_COMPLETE":
                    from backend.fullmatch import verify_chunk_artifacts
                    for chunk in manifest.get("chunks", []):
                        verify_chunk_artifacts(chunk)
                    manifest["cache_hits"] = manifest.get("cache_hits", 0) + len(manifest.get("chunks", []))
                    save_manifest(manifest_path, manifest)
                    existing["cache_hits"] = manifest["cache_hits"]
                    self.repo.save_full_match_job(match_id, existing)
                    with self.lock:
                        self.active.discard(match_id)
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
                "qa_classification": record.get("video_metadata", {}).get("qa_classification", "AUTHORIZED_LOCAL_VIDEO"),
                "input_path": str(prepared["video"]), "media": media,
                "source_identity": prepared["source_identity"],
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

        initial_resources = system_resource_snapshot()
        resource_guard = ResourceTrendGuard(initial_resources, self.min_available_ram_gib)
        resource_check = resource_guard.start_check(initial_resources)
        resource_lock = threading.Lock()

        def persist_resource_sample(sample_log, phase, snapshot, guard_result):
            sample = {"at": datetime.now(timezone.utc).isoformat(), "phase": phase,
                      "snapshot": snapshot, "warning": guard_result.get("warning", False),
                      "available_ram_drop_bytes": guard_result.get("available_ram_drop_bytes")}
            with resource_lock:
                sample_log.parent.mkdir(parents=True, exist_ok=True)
                with sample_log.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(sample, ensure_ascii=False, separators=(",", ":")) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())

        def terminate_owned_process_tree(process):
            try:
                import psutil
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                for child in reversed(children):
                    try:
                        child.terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                try:
                    parent.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                _, alive = psutil.wait_procs([*children, parent], timeout=3)
                for item in alive:
                    try:
                        item.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except ImportError:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
            process.wait()

        def run_monitored(command, *, phase, chunk_index, sample_log, stdout=None, stderr=None,
                          timeout=3600, capture_output=False):
            snapshot = system_resource_snapshot()
            check = resource_guard.start_check(snapshot)
            persist_resource_sample(sample_log, f"{phase}_START", snapshot, check)
            if not check["allowed"]:
                raise ResourceGuardStop(check["reason"], snapshot, str(sample_log))
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            capture_file = tempfile.TemporaryFile(mode="w+t", encoding="utf-8") if capture_output else None
            process = subprocess.Popen(command, stdout=stdout if not capture_output else capture_file,
                stderr=stderr if not capture_output else capture_file, text=True,
                creationflags=creationflags)
            started = time.monotonic()
            last_sample = 0.0
            try:
                while process.poll() is None:
                    if time.monotonic() - started > timeout:
                        terminate_owned_process_tree(process)
                        raise subprocess.TimeoutExpired(command, timeout)
                    if time.monotonic() - last_sample >= self.resource_sample_seconds:
                        snapshot = system_resource_snapshot(process.pid)
                        result = resource_guard.observe(snapshot)
                        persist_resource_sample(sample_log, phase, snapshot, result)
                        last_sample = time.monotonic()
                        if result["pause"]:
                            terminate_owned_process_tree(process)
                            raise ResourceGuardStop(result["reason"], snapshot, str(sample_log))
                    time.sleep(min(1.0, self.resource_sample_seconds / 2))
                process.wait()
                if capture_file:
                    capture_file.seek(0)
                    output = capture_file.read()
                    error = output if process.returncode else ""
                else:
                    output, error = None, None
                if process.returncode:
                    detail = (error or output or "").strip()[-4000:] if capture_output else ""
                    raise subprocess.CalledProcessError(process.returncode, command,
                        output=output, stderr=error or detail)
                final = system_resource_snapshot()
                result = resource_guard.observe(final)
                persist_resource_sample(sample_log, f"{phase}_END", final, result)
                return output
            finally:
                if process.poll() is None:
                    terminate_owned_process_tree(process)
                if capture_file:
                    capture_file.close()

        def persist(current):
            job = {"match_id": match_id, "status": current["status"], "stage": "BALLTRACK" if any(c['status']=='RUNNING' for c in current['chunks']) else "PREPARING",
                   "cache_key": current["cache_key"], "manifest_path": str(path),
                   "completed_chunks": sum(c["status"] == "COMPLETE" for c in current["chunks"]),
                   "total_chunks": len(current["chunks"]), "device": device,
                   "last_error": current.get("last_error"),
                   "current_chunk": next((c["chunk_index"] for c in current["chunks"] if c["status"] == "RUNNING"), None)}
            self.repo.save_full_match_job(match_id, job)

        def execute(chunk):
            try:
                current_stat = prepared["video"].stat()
                unchanged = (current_stat.st_size == prepared["source_identity"]["size_bytes"] and
                             current_stat.st_mtime_ns == prepared["source_identity"]["mtime_ns"])
            except OSError:
                unchanged = False
            if not unchanged:
                raise ValueError("SOURCE_CHANGED: video identity changed during processing")
            chunk_root = prepared["run_folder"] / "chunks" / f"{chunk['chunk_index'] + 1:06d}"
            chunk_root.mkdir(parents=True, exist_ok=True)
            chunk_video = chunk_root / "input.mp4"
            transcode_temp = chunk_root / "input.part.mp4"
            resource_log = logs / f"resource-chunk-{chunk['chunk_index'] + 1:06d}.jsonl"
            expected_frames = chunk.get("expected_processed_frames",chunk["end_frame_exclusive"] - chunk["start_frame_inclusive"])
            start_seconds = chunk["source_timestamp_start_ms"] / 1000.0
            duration_seconds = (chunk["source_timestamp_end_ms"]-chunk["source_timestamp_start_ms"])/1000.0
            command = ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{start_seconds:.9f}",
                       "-i", str(prepared["video"]), "-t", f"{duration_seconds:.9f}",
                       "-map", "0:v:0", "-an", "-vf", f"fps={prepared['metadata']['fps']}",
                       "-frames:v", str(expected_frames), "-c:v", "libx264", "-preset", "ultrafast",
                       "-crf", "18", "-y", str(transcode_temp)]
            transcode_started = time.perf_counter()
            try:
                run_monitored(command, phase="FFMPEG_TRANSCODE", chunk_index=chunk["chunk_index"],
                              sample_log=resource_log, timeout=3600, capture_output=True)
            except Exception:
                transcode_temp.unlink(missing_ok=True)
                raise
            if not transcode_temp.is_file() or transcode_temp.stat().st_size == 0:
                raise RuntimeError("FFMPEG produced no complete chunk video")
            transcode_temp.replace(chunk_video)
            transcode_seconds = time.perf_counter() - transcode_started
            output = chunk_root / "balltrack"
            output.mkdir(exist_ok=True)
            for stale in (output / "raw_prediction.json", output / "runtime.json",
                          output / "global_observations.json"):
                stale.unlink(missing_ok=True)
            log_path = logs / f"chunk-{chunk['chunk_index'] + 1:06d}.log"
            worker_command = [str(self.config.worker_python), str(worker),
                              "--runtime", str(self.config.runtime_root), "--checkpoint", str(prepared["checkpoint"]),
                              "--video", str(chunk_video), "--output", str(output), "--device", device,
                              "--batchsize", "2", "--median-input",
                              str(prepared["run_folder"] / "global_median.npz")]
            worker_started = time.perf_counter()
            with log_path.open("w", encoding="utf-8") as log:
                try:
                    run_monitored(worker_command, phase="BALLTRACK_WORKER", chunk_index=chunk["chunk_index"],
                              sample_log=resource_log,
                              stdout=log, stderr=subprocess.STDOUT, timeout=3600)
                except ResourceGuardStop:
                    for incomplete in (output / "raw_prediction.json", output / "runtime.json",
                                       output / "global_observations.json"):
                        incomplete.unlink(missing_ok=True)
                    raise
            worker_wall_seconds = time.perf_counter() - worker_started
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
            _atomic_text(mapped_path, json.dumps(mapped, ensure_ascii=False))
            runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
            return {"raw_prediction_path": str(raw_path), "observations_path": str(mapped_path),
                    "runtime_path": str(runtime_path), "log_path": str(log_path),
                    "raw_prediction_sha256": file_sha256(raw_path),
                    "observations_sha256": file_sha256(mapped_path),
                    "runtime_sha256": file_sha256(runtime_path),
                    "chunk_transcode_seconds": transcode_seconds,
                    "worker_wall_seconds": worker_wall_seconds,
                    "decoded_frames": len(raw), "runtime": runtime,
                    "resource_sample_log_path": str(resource_log),
                    "resource_sample_log_sha256": file_sha256(resource_log) if resource_log.is_file() else None,
                    "resource_snapshot_after": system_resource_snapshot(),
                    "completed_at": datetime.now(timezone.utc).isoformat()}

        try:
            if not resource_check["allowed"]:
                manifest["status"] = "PAUSED"
                manifest["pause_reason"] = resource_check["reason"]
                manifest["resource_guard_snapshot"] = initial_resources
                manifest["resource_guard_thresholds"] = {
                    "start_bytes": resource_guard.start_bytes,
                    "pause_bytes": resource_guard.pause_bytes,
                    "warning_drop_bytes": resource_guard.warning_drop_bytes,
                    "critical_drop_bytes": resource_guard.critical_drop_bytes}
                save_manifest(path, manifest)
                self.repo.save_full_match_job(match_id, {
                    "match_id": match_id, "status": "PAUSED", "stage": "可用内存不足，等待继续",
                    "cache_key": prepared["cache_key"], "manifest_path": str(path),
                    "completed_chunks": sum(c["status"] == "COMPLETE" for c in manifest["chunks"]),
                    "total_chunks": len(manifest["chunks"]), "device": device,
                    "resource_snapshot": initial_resources,
                    "required_available_ram_bytes": resource_check["required_available_ram_bytes"],
                })
                return
            background_path = prepared["run_folder"] / "global_median.npz"
            if not background_path.is_file():
                background_script = Path(__file__).resolve().parents[1] / "vision_worker" / "background.py"
                background_temp = prepared["run_folder"] / "global_median.part.npz"
                background_log = logs / "resource-background.jsonl"
                background_temp.unlink(missing_ok=True)
                try:
                    run_monitored([str(self.config.worker_python), str(background_script),
                                "--runtime", str(self.config.runtime_root), "--video", str(prepared["video"]),
                                "--output", str(background_temp)], phase="BACKGROUND_BUILD",
                              chunk_index=0, sample_log=background_log, timeout=3600)
                except ResourceGuardStop:
                    background_temp.unlink(missing_ok=True)
                    background_temp.with_suffix(".json").unlink(missing_ok=True)
                    raise
                if not background_temp.is_file() or background_temp.stat().st_size == 0:
                    raise RuntimeError("Background worker produced no complete median file")
                background_temp.replace(background_path)
                background_temp.with_suffix(".json").replace(background_path.with_suffix(".json"))
            manifest = json.loads(path.read_text(encoding="utf-8"))
            background_info = background_path.with_suffix(".json")
            manifest["background"] = {"path": str(background_path), "metadata_path": str(background_info),
                                      "sha256": file_sha256(background_path),
                                      "sampling": json.loads(background_info.read_text(encoding="utf-8")),
                                      "resource_sample_log_path": str(logs / "resource-background.jsonl"),
                                      "resource_sample_log_sha256": (file_sha256(logs / "resource-background.jsonl")
                                          if (logs / "resource-background.jsonl").is_file() else None)}
            save_manifest(path, manifest)
            def before_chunk(_chunk):
                snapshot = system_resource_snapshot()
                check = resource_guard.start_check(snapshot)
                return {"allowed": check["allowed"], "reason": check["reason"],
                        "snapshot": snapshot}

            manifest = run_resumable_chunks(
                path, execute, persist, max_new_chunks=self.max_new_chunks_per_run,
                before_chunk=before_chunk)
            if manifest.get("status") == "PAUSED":
                reason = manifest.get("pause_reason", "RESOURCE_GUARD_BEFORE_CHUNK")
                snapshot = manifest.get("resource_guard_snapshot")
                self.repo.save_full_match_job(match_id, {
                    "match_id": match_id, "status": "PAUSED",
                    "stage": ("可用内存不足，等待继续" if reason.startswith("RESOURCE_GUARD")
                              else "分块批次已保存，可恢复继续"),
                    "cache_key": prepared["cache_key"], "manifest_path": str(path),
                    "completed_chunks": sum(c["status"] == "COMPLETE" for c in manifest["chunks"]),
                    "total_chunks": len(manifest["chunks"]), "device": device,
                    "pause_reason": reason, "resource_snapshot": snapshot,
                })
                return
            report_job=self.repo.get_full_match_job(match_id) or {}
            report_job.update(status='RUNNING',stage='GENERATING_REPORT')
            self.repo.save_full_match_job(match_id,report_job)
            if source_identity(prepared["video"]) != prepared["source_identity"]:
                raise ValueError("SOURCE_CHANGED: video identity changed before output finalization")
            merged_csv = prepared["run_folder"] / "full_match_balltrack.csv"
            merged_jsonl = prepared["run_folder"] / "full_match_balltrack.jsonl"
            merged_csv_tmp = merged_csv.with_suffix(merged_csv.suffix + ".tmp")
            merged_jsonl_tmp = merged_jsonl.with_suffix(merged_jsonl.suffix + ".tmp")
            columns = ["global_frame", "source_frame", "timestamp_ms", "local_frame", "chunk_index", "visible", "x", "y",
                       "raw_model_score", "raw_score_semantics"]
            frame_count = visible = 0
            previous_global_frame = -1
            previous_timestamp = -1.0
            boundary_frames = set()
            for item in manifest["chunks"][:-1]:
                boundary = item["processing_frame_start"] + item["expected_processed_frames"]
                boundary_frames.update(range(max(0, boundary - 2), boundary + 3))
            boundary_samples = []
            with merged_csv_tmp.open("w", encoding="utf-8", newline="") as output, \
                    merged_jsonl_tmp.open("w", encoding="utf-8") as jsonl:
                writer = csv.DictWriter(output, fieldnames=columns)
                writer.writeheader()
                for chunk in sorted(manifest["chunks"],key=lambda item:item["chunk_index"]):
                    observations=json.loads(Path(chunk["observations_path"]).read_text(encoding="utf-8"))
                    for item in observations:
                        if item["global_frame"]<=previous_global_frame:
                            raise ValueError("Chunk outputs are duplicated or out of global timeline order")
                        if item["global_frame"] != previous_global_frame + 1:
                            raise ValueError("Global output frame sequence has a missing frame")
                        if item["timestamp_ms"] < 0 or item["timestamp_ms"] < previous_timestamp:
                            raise ValueError("Output timestamps are negative or not monotonic")
                        previous_global_frame=item["global_frame"]
                        previous_timestamp=item["timestamp_ms"]
                        writer.writerow(item)
                        jsonl.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
                        if item["global_frame"] in boundary_frames:
                            boundary_samples.append(item)
                        frame_count+=1;visible+=bool(item["visible"])
            merged_csv_tmp.replace(merged_csv)
            merged_jsonl_tmp.replace(merged_jsonl)
            if frame_count != sum(c.get("decoded_frames", 0) for c in manifest["chunks"]):
                raise ValueError("Output frame count does not match completed chunk evidence")
            if previous_global_frame != frame_count - 1:
                raise ValueError("Global frame sequence contains a gap")
            timeline = self.repo.get_match_timeline(match_id) or {
                "match_id": match_id, "revision": 0, "games": [], "scene_segments": manifest["scene_segments"]}
            timeline_path = prepared["run_folder"] / "match_timeline.json"
            _atomic_text(timeline_path, json.dumps(timeline, ensure_ascii=False, indent=2))
            media = manifest["media"]
            points = [point for game in timeline.get("games", []) for point in game.get("points", [])]
            rallies = [rally for point in points for rally in point.get("rallies", [])]
            summary = {"match_id": match_id, "event": record["event_name"], "round": record.get("round"),
                       "player_a_id": record["player_a_id"], "player_b_id": record["player_b_id"],
                       "duration_seconds": media["duration"], "games": len(timeline.get("games", [])),
                       "game_scores": [{"game_number": game["game_number"], "score":
                           (game["points"][-1].get("score_after") if game.get("points") else None),
                           "source": "MANUAL"} for game in timeline.get("games", [])],
                       "points": len(points), "rallies": len(rallies),
                       "average_rally_duration_ms": (sum(r["end_ms"] - r["start_ms"] for r in rallies) / len(rallies) if rallies else None),
                       "balltrack_frames": frame_count, "balltrack_visible_frames": visible,
                       "balltrack_coverage": visible / frame_count if frame_count else None,
                       "video_quality": quality_report_for_summary(
                           media, record, manifest.get("chunk_seconds", DEFAULT_CHUNK_SECONDS)),
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
            _atomic_text(summary_path, json.dumps(summary, ensure_ascii=False, indent=2))
            report = _summary_html(summary)
            _atomic_text(prepared["run_folder"] / "full_match_report.html", report)
            try:
                overlay_started = time.perf_counter()
                manifest["preview_overlays"] = generate_preview_overlays(
                    prepared["video"], merged_csv, prepared["metadata"], prepared["run_folder"],
                    self.config.worker_python)
                manifest["overlay_encoding_seconds"] = time.perf_counter() - overlay_started
            except Exception as overlay_error:
                manifest["overlay_encoding_seconds"] = time.perf_counter() - overlay_started
                manifest.setdefault("warnings", []).append(f"PREVIEW_OVERLAY_FAILED: {overlay_error}")
            save_manifest(path, manifest)
            validation = build_full_match_validation(manifest, summary, prepared["source_identity"],
                prepared["run_folder"], frame_count, timeline, boundary_samples)
            validation_path = prepared["run_folder"] / "full_match_validation.json"
            manifest["status"] = "BALLTRACK_COMPLETE"
            manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
            manifest["output_artifacts_ready"] = True
            save_manifest(path, manifest)
            refresh_manifest_artifact(validation, path)
            _atomic_text(validation_path, json.dumps(validation, ensure_ascii=False, indent=2))
            _atomic_text(prepared["run_folder"] / "full_match_validation.html",
                         _validation_html(validation))
            job = {"match_id": match_id, "status": "BALLTRACK_COMPLETE", "stage": "全场球追踪完成；时间轴待人工校正",
                   "cache_key": prepared["cache_key"], "manifest_path": str(path),
                   "output_dir": str(prepared["run_folder"]), "summary_path": str(summary_path),
                   "report_path": str(prepared["run_folder"] / "full_match_report.html"),
                   "csv_path": str(merged_csv), "completed_chunks": len(manifest["chunks"]),
                   "jsonl_path": str(merged_jsonl), "validation_path": str(validation_path),
                   "total_chunks": len(manifest["chunks"]), "device": device,
                   "summary": summary}
            self.repo.save_full_match_job(match_id, job)
        except Exception as exc:
            current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else manifest
            current["status"] = "PAUSED"
            current["last_error"] = str(exc)
            if isinstance(exc, ResourceGuardStop):
                current["pause_reason"] = exc.reason
                current["resource_guard_snapshot"] = exc.snapshot
                current["failure_class"] = "RESOURCE_GUARD"
                if exc.sample_log_path:
                    current["resource_sample_log_path"] = exc.sample_log_path
            else:
                current["failure_class"] = "WORKER_OR_IO_ERROR"
            if path.is_file():
                save_manifest(path, current)
            job = {"match_id": match_id, "status": current.get("status", "FAILED"),
                   "stage": "处理暂停，可从失败分块继续", "cache_key": prepared["cache_key"],
                   "manifest_path": str(path), "last_error": str(exc),
                   "pause_reason": current.get("pause_reason"),
                   "failure_class": current.get("failure_class"),
                   "resource_snapshot": current.get("resource_guard_snapshot"),
                   "completed_chunks": sum(c["status"] == "COMPLETE" for c in current.get("chunks", [])),
                   "total_chunks": len(current.get("chunks", [])), "device": device}
            self.repo.save_full_match_job(match_id, job)
        finally:
            with self.lock:
                self.active.discard(match_id)


def quality_report_for_summary(metadata, record, chunk_seconds=DEFAULT_CHUNK_SECONDS):
    return quality_report(metadata, record.get("video_metadata", {}).get("size_bytes", 0),
                          "frozen BallTrack v1", chunk_seconds) | {
        "sha256": record.get("video_metadata", {}).get("sha256"),
        "camera_changes": "UNKNOWN"}


def build_full_match_validation(manifest, summary, identity, output_dir, frame_count, timeline, boundary_samples=None):
    chunks = sorted(manifest.get("chunks", []), key=lambda item: item["chunk_index"])
    boundaries = []
    missing = []
    for index, chunk in enumerate(chunks):
        if chunk.get("status") != "COMPLETE":
            missing.append(chunk["chunk_index"])
        if index:
            previous = chunks[index - 1]
            boundaries.append({"before_chunk": chunk["chunk_index"],
                "global_frame_before": previous["processing_frame_start"] + previous["expected_processed_frames"] - 1,
                "global_frame_after": chunk["processing_frame_start"],
                "continuous": previous["processing_frame_start"] + previous["expected_processed_frames"] == chunk["processing_frame_start"],
                "tracker_state": "RESET_PER_CHUNK"})
    output_dir = Path(output_dir)
    artifacts = {}
    for name in ("full_match_balltrack.csv", "full_match_balltrack.jsonl", "full_match_summary.json",
                 "full_match_report.html", "match_timeline.json", "manifest.json"):
        item = output_dir / name
        artifacts[name] = {"exists": item.is_file(), "size_bytes": item.stat().st_size if item.is_file() else None,
                           "sha256": file_sha256(item) if item.is_file() else None}
    profile = [chunk.get("runtime", {}) for chunk in chunks]
    resource_samples = []
    resource_warnings = []
    log_records = [(chunk.get("chunk_index"), chunk.get("resource_sample_log_path")) for chunk in chunks]
    background_log = (manifest.get("background") or {}).get("resource_sample_log_path")
    if background_log:
        log_records.insert(0, ("BACKGROUND", background_log))
    for chunk_index, log_path in log_records:
        resource_path = Path(log_path or "")
        if not resource_path.is_file():
            continue
        with resource_path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                try:
                    sample = json.loads(line)
                    sample["chunk_index"] = chunk_index
                    resource_samples.append(sample)
                except (json.JSONDecodeError, TypeError):
                    resource_warnings.append(
                        f"RESOURCE_SAMPLE_LOG_CORRUPT: chunk {chunk_index} line {line_number}")
    snapshots = [sample.get("snapshot", {}) for sample in resource_samples]
    available_values = [int(item["available_ram_bytes"]) for item in snapshots
                        if isinstance(item.get("available_ram_bytes"), (int, float))]
    monitored_rss = [int(item["monitored_process_rss_bytes"]) for item in snapshots
                     if isinstance(item.get("monitored_process_rss_bytes"), (int, float))]
    monitored_uss = [int(item["monitored_process_uss_bytes"]) for item in snapshots
                     if isinstance(item.get("monitored_process_uss_bytes"), (int, float))]
    gpu_values = [int(item["gpu_memory_used_mib"]) for item in snapshots
                  if isinstance(item.get("gpu_memory_used_mib"), (int, float))]
    profile_totals = {}
    for chunk, runtime in zip(chunks, profile):
        for name, seconds in runtime.get("profile", {}).items():
            profile_totals[name] = profile_totals.get(name, 0.0) + float(seconds or 0.0)
        profile_totals["chunk_transcode_seconds"] = profile_totals.get("chunk_transcode_seconds", 0.0) + float(chunk.get("chunk_transcode_seconds", 0.0))
        profile_totals["worker_wall_seconds"] = profile_totals.get("worker_wall_seconds", 0.0) + float(chunk.get("worker_wall_seconds", 0.0))
    return {"qa_classification": manifest.get("qa_classification", "ENGINEERING_VALIDATION"),
        "input": {**identity, "duration_seconds": manifest["media"]["duration"],
                  "resolution": [manifest["media"]["width"], manifest["media"]["height"]],
                  "fps": manifest["media"]["fps"], "variable_frame_rate": bool(manifest["media"].get("rate_variable"))},
        "cache_key": manifest["cache_key"], "chunk_count": len(chunks),
        "processed_chunks": sum(c.get("status") == "COMPLETE" for c in chunks),
        "resumed_chunks": sum(bool(c.get("resumed")) for c in chunks),
        "initial_cache_misses": sum(c.get("attempt_count", 0) > 0 for c in chunks),
        "single_attempt_chunks": sum(c.get("attempt_count", 0) == 1 for c in chunks),
        "chunk_retries": sum(max(0, c.get("attempt_count", 0) - 1) for c in chunks),
        "cache_hits": manifest.get("cache_hits", 0), "resume_count": manifest.get("resume_count", 0),
        "output_frames": frame_count, "missing_chunks": missing, "duplicate_frames": 0,
        "timestamp_order": "MONOTONIC_GLOBAL_PTS_MAPPING",
        "chunk_boundaries": boundaries, "boundary_frame_samples": boundary_samples or [],
        "tracker_state_boundary_policy": "RESET_PER_CHUNK; raw model temporal history does not cross chunk boundaries",
        "runtime_seconds_by_chunk": [p.get("processing_seconds") for p in profile],
        "runtime_profile_totals_seconds": profile_totals,
        "peak_cpu_ram_bytes": max((p.get("peak_cpu_ram_bytes") or 0 for p in profile), default=0),
        "peak_vram_bytes": max((p.get("peak_vram_bytes") or 0 for p in profile), default=0),
        "resource_monitoring": {
            "sample_count": len(resource_samples),
            "available_ram_min_bytes": min(available_values) if available_values else None,
            "monitored_process_tree_rss_peak_bytes": max(monitored_rss) if monitored_rss else None,
            "monitored_process_tree_uss_peak_bytes": max(monitored_uss) if monitored_uss else None,
            "gpu_memory_used_peak_mib": max(gpu_values) if gpu_values else None,
            "samples": resource_samples,
        },
        "effective_fps": frame_count / sum(p.get("processing_seconds", 0) for p in profile) if sum(p.get("processing_seconds", 0) for p in profile) else None,
        "realtime_factor": manifest["media"]["duration"] / sum(p.get("processing_seconds", 0) for p in profile) if sum(p.get("processing_seconds", 0) for p in profile) else None,
        "overlay_encoding_seconds": manifest.get("overlay_encoding_seconds", 0.0),
        "disk_io_profile": "NOT_INSTRUMENTED; output file sizes and hashes are reported",
        "timeline": {"games": len(timeline.get("games", [])),
            "points": sum(len(g.get("points", [])) for g in timeline.get("games", [])),
            "rallies": sum(len(p.get("rallies", [])) for g in timeline.get("games", []) for p in g.get("points", [])),
            "segmentation": "MANUAL / REVIEW_REQUIRED"},
        "artifacts": artifacts, "errors": manifest.get("errors", []), "warnings": [
            "Synthetic QA is not an accuracy evaluation." if manifest.get("qa_classification") == "SYNTHETIC_LONG_FORM_QA" else "",
            "BallTrack temporal state resets at each chunk boundary.", *resource_warnings,
            *manifest.get("warnings", [])],
        "preview_overlays": manifest.get("preview_overlays", []),
        "scoreboard_recognition": "NOT_ENABLED", "tactical_inference": "NOT_PERFORMED"}


def refresh_manifest_artifact(validation, manifest_path):
    """Record the final manifest hash after its terminal status has been saved."""
    manifest_path = Path(manifest_path)
    validation.setdefault("artifacts", {})["manifest.json"] = {
        "exists": manifest_path.is_file(),
        "size_bytes": manifest_path.stat().st_size if manifest_path.is_file() else None,
        "sha256": file_sha256(manifest_path) if manifest_path.is_file() else None,
    }
    return validation


def _validation_html(report):
    rows = "".join(f"<tr><th>{html.escape(str(key))}</th><td><pre>{html.escape(json.dumps(value, ensure_ascii=False, indent=2))}</pre></td></tr>"
                   for key, value in report.items())
    return ("<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>全场工程验收</title>"
            "<style>body{font:15px 'Microsoft YaHei',sans-serif;max-width:1100px;margin:32px auto}"
            "th,td{padding:10px;vertical-align:top;border-bottom:1px solid #ddd;text-align:left}pre{white-space:pre-wrap}</style>"
            "<h1>PTTI 全场工程验收报告</h1><p>工程稳定性记录，不构成职业比赛准确率认证。</p>" + f"<table>{rows}</table></html>")


def generate_preview_overlays(video, csv_path, metadata, output_dir, worker_python):
    """Render only three bounded 30-second review windows, never a whole-match overlay."""
    preview_dir = Path(output_dir) / "preview_overlays"
    preview_dir.mkdir(exist_ok=True)
    duration = float(metadata["duration"])
    fps = float(metadata["fps"])
    window = min(30.0, duration)
    starts = sorted(set((0.0, max(0.0, (duration - window) / 2), max(0.0, duration - window))))
    rows = []
    with Path(csv_path).open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    overlay_script = Path(__file__).resolve().parents[1] / "vision_worker" / "overlay.py"
    previews = []
    for index, start in enumerate(starts, start=1):
        source_clip = preview_dir / f"preview-{index:02d}-source.mp4"
        prediction_path = preview_dir / f"preview-{index:02d}-predictions.json"
        destination = preview_dir / f"preview-{index:02d}.mp4"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{start:.3f}", "-i", str(video),
            "-t", f"{window:.3f}", "-map", "0:v:0", "-an", "-c:v", "libx264", "-preset", "ultrafast",
            "-crf", "20", "-y", str(source_clip)], check=True, timeout=3600, capture_output=True,
                       creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        start_frame = round(start * fps)
        end_frame = round((start + window) * fps)
        values = []
        for row in rows:
            frame = int(row["global_frame"])
            if start_frame <= frame < end_frame:
                visible = row["visible"].lower() == "true"
                values.append({"frame": frame - start_frame, "pixel_x": float(row["x"] or 0),
                    "pixel_y": float(row["y"] or 0), "visible": visible,
                    "confidence": float(row["raw_model_score"]) if row["raw_model_score"] else None})
        prediction_path.write_text(json.dumps(values), encoding="utf-8")
        subprocess.run([str(worker_python), str(overlay_script), str(source_clip), str(prediction_path),
                        str(destination)], check=True, timeout=3600,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        source_clip.unlink(missing_ok=True)
        prediction_path.unlink(missing_ok=True)
        previews.append({"path": str(destination), "start_seconds": start, "duration_seconds": window,
                         "frames": len(values), "bounded_preview": True})
    return previews


def _summary_html(summary):
    def text(value): return html.escape(str(value)) if value is not None else '—'
    quality=summary.get('video_quality') or {}
    resolution=quality.get('resolution') or {}
    duration=summary.get('duration_seconds')
    duration_label=f'{int(duration)//60} 分 {int(duration)%60} 秒' if duration is not None else '—'
    coverage=summary.get('balltrack_coverage')
    metrics=[('视频时长',duration_label),('画面分辨率',f"{resolution.get('width','—')} × {resolution.get('height','—')}"),
             ('帧率',str(quality.get('fps','—'))+' FPS'),('处理帧数',summary.get('balltrack_frames')),
             ('有效球坐标',summary.get('balltrack_visible_frames')),
             ('轨迹覆盖率',f'{coverage*100:.1f}%' if coverage is not None else '—')]
    cards=''.join(f'<div class="metric"><span>{label}</span><strong>{text(value)}</strong></div>' for label,value in metrics)
    score_rows=''
    for game in summary.get('game_scores',[]):
        score=game.get('score')
        value=f"{score.get('player_a','—')} : {score.get('player_b','—')}" if score else '未记录'
        score_rows+=f"<tr><td>第 {text(game.get('game_number'))} 局</td><td>{text(value)}</td><td>人工记录</td></tr>"
    review='已完成人工审核' if summary.get('analysis_completeness',{}).get('manual_review_complete') else '尚未完成人工审核'
    structure=(f"<p>已记录 {text(summary.get('games',0))} 局 · {text(summary.get('points',0))} 分 · {text(summary.get('rallies',0))} 个回合。{review}。</p>"
               +('<table><tr><th>局</th><th>比分</th><th>来源</th></tr>'+score_rows+'</table>' if score_rows else '<p>等待人工确认比赛结构。</p>'))
    return ("<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>PTTI 比赛分析报告</title>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'><style>"
            "body{font:16px 'Microsoft YaHei UI','Microsoft YaHei',sans-serif;max-width:960px;margin:40px auto;padding:0 24px;color:#193c38;background:#f7faf9;line-height:1.8}"
            "h1{font-size:30px}h2{font-size:22px}section{background:white;border:1px solid #dce8e3;border-radius:12px;padding:24px;margin:22px 0}"
            ".metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.metric{padding:16px;background:#eef5f1;border-radius:8px}.metric span{display:block;color:#5a716c;font-size:13px}.metric strong{font-size:22px}"
            "th,td{padding:10px 18px;text-align:left;border-bottom:1px solid #dce8e3}small{color:#637c74}@media(max-width:600px){.metrics{grid-template-columns:1fr 1fr}}@media print{body{background:white}section{break-inside:avoid}}</style></head><body>"
            "<small>TABLE TENNIS INTELLIGENCE · Professional Preview</small><h1>比赛分析报告</h1>"
            f"<h2>{text(summary.get('player_a_name') or '球员 A')} vs {text(summary.get('player_b_name') or '球员 B')}</h2>"
            f"<p>{text(summary.get('event') or '比赛名称未记录')}</p>"
            f"<section><h2>球轨迹与视频</h2><div class='metrics'>{cards}</div>"
            "<p>RacketVision RAW / BallTrack v1。覆盖率表示球坐标观测可用比例，不代表识别准确率。</p></section>"
            f"<section><h2>比赛结构与人工审核</h2>{structure}</section>"
            "<section><h2>证据边界</h2><p>球轨迹和人工记录不会自动成为发球旋转、技术动作、得分归因或战术结论。暂无这些分析数据。</p>"
            "<p>不知道的，不猜。此报告仅描述本次视频处理与人工确认记录。</p></section>"
            f"<details><summary>来源与完整性</summary><p>视频 SHA256：{text(quality.get('sha256'))}</p></details></body></html>")


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
                   game_scores=[{"game_number": game["game_number"], "score":
                       (game["points"][-1].get("score_after") if game.get("points") else None),
                       "source": "MANUAL"} for game in timeline.get("games", [])],
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
