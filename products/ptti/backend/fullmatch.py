"""Full-match ingestion, chunk manifests, and human-reviewed timeline schemas.

This module intentionally does not infer a point winner, spin, stroke, or tactic.
Its pure helpers make frame/time mapping and resume behavior independently testable.
"""
from __future__ import annotations

from hashlib import sha256 as _sha256
import json
import bisect
import os
from pathlib import Path
import re
import subprocess
import time
from collections import deque
from datetime import datetime, timezone
from typing import Literal
from typing import Protocol

from pydantic import BaseModel, Field, model_validator

from vision.quality import video_metadata, classify

SUPPORTED_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi"}
PROCESSING_VERSION = "ptti-full-match-0.1.0"
DEFAULT_CHUNK_SECONDS = 60


class ScoreboardRecognizer(Protocol):
    """Future OCR seam. No implementation is active; manual score entry is canonical."""
    status: Literal["EXPERIMENTAL"]

    def recognize(self, frame) -> dict:
        """Return evidence-bearing candidates or null; never assert an unverified score."""
        ...


def file_sha256(path: Path) -> str:
    digest = _sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_identity(path: Path) -> dict:
    path = Path(path)
    before = path.stat()
    digest = file_sha256(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("SOURCE_CHANGED: video changed while its identity was being verified")
    return {"path": str(path.resolve()), "sha256": digest, "size_bytes": after.st_size,
            "mtime_ns": after.st_mtime_ns}


def verify_chunk_artifacts(chunk: dict) -> None:
    """Fail closed if a COMPLETE chunk's evidence is missing or changed."""
    declared = ("raw_prediction_path", "raw_prediction_sha256", "observations_path",
                "observations_sha256", "runtime_path", "runtime_sha256",
                "resource_sample_log_path", "resource_sample_log_sha256")
    # Pure state-machine fixtures carry no filesystem artifacts. Once any
    # artifacts are declared, every required output must have a valid hash.
    if not any(chunk.get(key) for key in declared):
        return
    for path_key, hash_key in (("raw_prediction_path", "raw_prediction_sha256"),
                               ("observations_path", "observations_sha256"),
                               ("runtime_path", "runtime_sha256"),
                               ("resource_sample_log_path", "resource_sample_log_sha256")):
        path = Path(chunk.get(path_key, ""))
        expected = chunk.get(hash_key)
        if path_key == "resource_sample_log_path" and not expected and not chunk.get(path_key):
            continue
        if not path.is_file() or not expected or file_sha256(path) != expected:
            raise ValueError(f"CORRUPT_CHECKPOINT: chunk {chunk.get('chunk_index')} {path_key}")


def extract_source_frame_timestamps(path: Path, expected_frames: int | None = None) -> list[float]:
    """Read presentation timestamps for VFR mapping; fail closed on incomplete ffprobe output."""
    result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
                            "-show_entries", "frame=best_effort_timestamp_time", "-of", "csv=p=0", str(path)],
                           check=True, capture_output=True, text=True, timeout=3600)
    values = []
    for line in result.stdout.splitlines():
        value = line.strip().split(",", 1)[0]
        try:
            values.append(float(value) * 1000.0)
        except ValueError:
            continue
    if expected_frames is not None and len(values) != expected_frames:
        raise ValueError("VFR timestamp count does not match video frame count; export a CFR licensed copy before processing")
    if not values:
        raise ValueError("Exact video frame timestamps are unavailable")
    origin = values[0]
    normalized = [value - origin for value in values]
    if any(later < earlier for earlier, later in zip(normalized, normalized[1:])):
        raise ValueError("Video frame presentation timestamps are not monotonic")
    return normalized


def cache_key(video_hash: str, checkpoint_hash: str, config_hash: str,
              processing_version: str = PROCESSING_VERSION) -> str:
    parts = [video_hash, checkpoint_hash, config_hash, processing_version]
    return _sha256(json.dumps(parts, separators=(",", ":")).encode()).hexdigest()


def quality_report(metadata: dict, size_bytes: int, device: str,
                   chunk_seconds: int = DEFAULT_CHUNK_SECONDS) -> dict:
    duration = float(metadata["duration"])
    fps = float(metadata["fps"])
    frames = metadata.get("frame_count") or round(duration * fps)
    return {
        "duration_seconds": duration,
        "resolution": {"width": metadata["width"], "height": metadata["height"]},
        "fps": fps,
        "codec": metadata["codec"],
        "bitrate": metadata.get("bitrate"),
        "file_size_bytes": size_bytes,
        "estimated_frames": frames,
        "frame_count_is_estimate": metadata.get("frame_count") is None,
        "variable_frame_rate": bool(metadata.get("rate_variable")),
        "camera_changes": "UNKNOWN",
        "balltrack_device": device,
        "chunk_duration_seconds": chunk_seconds,
        "estimated_chunk_count": (frames + max(1, round(fps * chunk_seconds)) - 1)
                                  // max(1, round(fps * chunk_seconds)),
        "estimated_processing_workload_frames": frames,
        "input_quality": classify(metadata),
        "completion_time_estimate": None,
    }


def build_chunks(frame_count: int, fps: float, chunk_seconds: int = DEFAULT_CHUNK_SECONDS,
                 frame_timestamps_ms: list[float] | None = None) -> list[dict]:
    if frame_count < 0 or fps <= 0 or chunk_seconds <= 0:
        raise ValueError("frame_count, fps, and chunk_seconds must be valid")
    if frame_timestamps_ms is not None and len(frame_timestamps_ms) != frame_count:
        raise ValueError("Frame timestamp manifest must match decoded frame count")
    frames_per_chunk = max(1, round(fps * chunk_seconds))
    chunks = []
    start = 0
    processed_start = 0
    while start < frame_count:
        if frame_timestamps_ms is None:
            end = min(frame_count, start + frames_per_chunk)  # exclusive
            start_ms = start * 1000.0 / fps
            end_ms = end * 1000.0 / fps
        else:
            target_ms = frame_timestamps_ms[start] + chunk_seconds * 1000
            end = bisect.bisect_left(frame_timestamps_ms, target_ms, lo=start + 1)
            end = min(frame_count, max(start + 1, end))
            start_ms = frame_timestamps_ms[start]
            end_ms = (frame_timestamps_ms[end] if end < frame_count
                      else frame_timestamps_ms[-1] + 1000.0 / fps)
        processing_count = max(1, round((end_ms - start_ms) * fps / 1000.0))
        chunks.append({
            "chunk_index": len(chunks),
            "source_frame_start": start,
            "source_frame_end": end - 1,
            "source_timestamp_start_ms": start_ms,
            "source_timestamp_end_ms": end_ms,
            "start_frame_inclusive": start,
            "end_frame_exclusive": end,
            "processing_frame_start": processed_start,
            "expected_processed_frames": processing_count,
            "status": "PENDING",
        })
        processed_start += processing_count
        start = end
    return chunks


def map_chunk_observation(chunk: dict, local_frame: int, fps: float,
                          frame_timestamps_ms: list[float] | None = None) -> dict:
    length = chunk.get("expected_processed_frames", chunk["end_frame_exclusive"] - chunk["start_frame_inclusive"])
    if local_frame < 0 or local_frame >= length:
        raise ValueError("local_frame is outside this chunk")
    processed_frame = chunk.get("processing_frame_start", chunk["start_frame_inclusive"]) + local_frame
    timestamp = chunk["source_timestamp_start_ms"] + local_frame * 1000.0 / fps
    source_frame = processed_frame
    if frame_timestamps_ms is not None:
        position = bisect.bisect_left(frame_timestamps_ms, timestamp)
        candidates = [index for index in (position - 1, position) if 0 <= index < len(frame_timestamps_ms)]
        source_frame = min(candidates, key=lambda index: abs(frame_timestamps_ms[index] - timestamp))
        timestamp = frame_timestamps_ms[source_frame]
    return {"global_frame": processed_frame, "source_frame": source_frame,
            "processed_frame": processed_frame, "timestamp_ms": timestamp}


def merge_chunk_observations(chunks: list[dict]) -> list[dict]:
    merged = []
    seen = set()
    for chunk in sorted(chunks, key=lambda item: item["chunk_index"]):
        if chunk.get("status") != "COMPLETE":
            continue
        for observation in chunk.get("observations", []):
            frame = observation["global_frame"]
            if frame in seen:
                raise ValueError(f"Duplicate global frame in chunk output: {frame}")
            seen.add(frame)
            merged.append(observation)
    return sorted(merged, key=lambda item: item["global_frame"])


def save_manifest(path: Path, manifest: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    last_error = None
    for attempt in range(8):
        try:
            temporary.replace(path)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.025 * (attempt + 1))
    raise last_error


def system_resource_snapshot(process_pid: int | None = None) -> dict:
    """Return a small, best-effort system snapshot without importing GPU frameworks."""
    snapshot = {"available_ram_bytes": None, "process_rss_bytes": None,
                "total_ram_bytes": None, "process_uss_bytes": None,
                "monitored_process_rss_bytes": None, "monitored_process_uss_bytes": None,
                "monitored_process_count": 0,
                "gpu": None, "gpu_temperature_c": None, "gpu_memory_used_mib": None,
                "gpu_memory_free_mib": None, "gpu_utilization_percent": None}
    try:
        import psutil
        memory = psutil.virtual_memory()
        snapshot["available_ram_bytes"] = int(memory.available)
        snapshot["total_ram_bytes"] = int(memory.total)
        own = psutil.Process()
        snapshot["process_rss_bytes"] = int(own.memory_info().rss)
        try:
            snapshot["process_uss_bytes"] = int(getattr(own.memory_full_info(), "uss", 0)) or None
        except (psutil.Error, OSError):
            snapshot["process_uss_bytes"] = None
        if process_pid is not None:
            try:
                process = psutil.Process(process_pid)
                children = process.children(recursive=True)
                tree = [process, *children]
                snapshot["monitored_process_count"] = len(tree)
                snapshot["monitored_process_rss_bytes"] = sum(item.memory_info().rss for item in tree)
                uss_values = [getattr(item.memory_full_info(), "uss", 0) for item in tree]
                snapshot["monitored_process_uss_bytes"] = sum(uss_values) or None
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                snapshot["monitored_process_count"] = 0
    except (ImportError, OSError):
        snapshot["available_ram_bytes"] = _windows_available_ram_bytes()
        if snapshot["available_ram_bytes"] is None and os.name != "nt":
            try:
                snapshot["available_ram_bytes"] = int(os.sysconf("SC_AVPHYS_PAGES") *
                                                       os.sysconf("SC_PAGE_SIZE"))
            except (AttributeError, OSError, ValueError):
                pass
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,memory.used,memory.free,utilization.gpu",
             "--format=csv,noheader,nounits"],
            check=True, capture_output=True, text=True, timeout=5,
            **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}),
        )
        fields = [part.strip() for part in result.stdout.splitlines()[0].split(",")]
        if len(fields) == 5:
            snapshot.update(gpu=fields[0], gpu_temperature_c=int(fields[1]),
                            gpu_memory_used_mib=int(fields[2]), gpu_memory_free_mib=int(fields[3]),
                            gpu_utilization_percent=int(fields[4]))
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        pass
    return snapshot


class ResourceGuardStop(RuntimeError):
    """A recoverable pause raised after the owned worker tree has been stopped."""

    def __init__(self, reason: str, snapshot: dict, sample_log_path: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.snapshot = snapshot
        self.sample_log_path = sample_log_path


class ResourceTrendGuard:
    """Machine-relative RAM guard; fail closed if physical-memory telemetry is missing."""

    GIB = 1024 ** 3

    def __init__(self, initial_snapshot: dict, minimum_start_gib: float | None = None,
                 trend_window_seconds: float = 30.0):
        total = initial_snapshot.get("total_ram_bytes")
        total = int(total) if isinstance(total, (int, float)) and total > 0 else 16 * self.GIB
        machine_floor = max(3 * self.GIB, int(total * .25))
        requested_floor = (machine_floor if minimum_start_gib is None
                           else int(float(minimum_start_gib) * self.GIB))
        self.start_bytes = max(machine_floor, requested_floor)
        self.pause_bytes = max(int(1.5 * self.GIB), int(total * .15))
        self.warning_drop_bytes = max(int(.5 * self.GIB), int(total * .05))
        self.critical_drop_bytes = max(int(.9 * self.GIB), int(total * .08))
        self.trend_window_seconds = float(trend_window_seconds)
        self.samples = deque(maxlen=64)
        self.observe(initial_snapshot)

    def start_check(self, snapshot: dict) -> dict:
        available = snapshot.get("available_ram_bytes")
        if available is None:
            return {"allowed": False, "reason": "RESOURCE_GUARD_UNAVAILABLE", "snapshot": snapshot,
                    "required_available_ram_bytes": self.start_bytes}
        allowed = int(available) >= self.start_bytes
        return {"allowed": allowed,
                "reason": None if allowed else "RESOURCE_GUARD_BEFORE_WORKER",
                "snapshot": snapshot, "required_available_ram_bytes": self.start_bytes}

    def observe(self, snapshot: dict, now: float | None = None) -> dict:
        now = time.monotonic() if now is None else float(now)
        available = snapshot.get("available_ram_bytes")
        self.samples.append((now, int(available) if available is not None else None))
        if available is None:
            return {"pause": True, "warning": True, "reason": "RESOURCE_GUARD_UNAVAILABLE",
                    "snapshot": snapshot, "available_ram_drop_bytes": None}
        available = int(available)
        recent = [(stamp, value) for stamp, value in self.samples
                  if value is not None and now - stamp <= self.trend_window_seconds]
        drop = max(0, recent[0][1] - available) if len(recent) > 1 else 0
        if available < self.pause_bytes:
            reason = "RESOURCE_GUARD_LOW_AVAILABLE_RAM"
        elif available < self.start_bytes and drop >= self.critical_drop_bytes:
            reason = "RESOURCE_GUARD_DECLINING_RAM_TREND"
        else:
            reason = None
        return {"pause": reason is not None,
                "warning": available < self.start_bytes or drop >= self.warning_drop_bytes,
                "reason": reason, "snapshot": snapshot,
                "available_ram_drop_bytes": drop,
                "start_threshold_bytes": self.start_bytes,
                "pause_threshold_bytes": self.pause_bytes,
                "warning_drop_threshold_bytes": self.warning_drop_bytes,
                "critical_drop_threshold_bytes": self.critical_drop_bytes}


def _windows_available_ram_bytes() -> int | None:
    """Read Windows available physical memory using the OS API when psutil is absent."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        api = ctypes.WinDLL("kernel32", use_last_error=True).GlobalMemoryStatusEx
        api.argtypes = [ctypes.POINTER(MemoryStatusEx)]
        api.restype = wintypes.BOOL
        if api(ctypes.byref(status)):
            return int(status.ullAvailPhys)
    except (AttributeError, ImportError, OSError, TypeError):
        return None
    return None


def run_resumable_chunks(path: Path, execute_chunk, progress=None, *,
                         max_new_chunks: int | None = None, before_chunk=None) -> dict:
    """Run pending/failed chunks and durably checkpoint each transition."""
    if max_new_chunks is not None and max_new_chunks < 1:
        raise ValueError("max_new_chunks must be positive")
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    resumed = manifest.get("status") in {"PAUSED", "RUNNING"} or any(
        chunk.get("status") == "COMPLETE" for chunk in manifest["chunks"])
    manifest.setdefault("cache_hits", 0)
    manifest.setdefault("resume_count", 0)
    binding = {key: manifest.get(key) for key in
               ("cache_key", "video_sha256", "checkpoint_sha256", "config_sha256")}
    if all(binding.values()):
        for chunk in manifest["chunks"]:
            previous_binding = chunk.get("cache_binding")
            if previous_binding is not None and previous_binding != binding:
                raise ValueError(f"CACHE_BINDING_MISMATCH: chunk {chunk.get('chunk_index')}")
            chunk["cache_binding"] = binding
    if resumed:
        manifest["resume_count"] += 1
    manifest["status"] = "RUNNING"
    manifest.pop("pause_reason", None)
    save_manifest(path, manifest)
    completed_this_run = 0
    for chunk in manifest["chunks"]:
        if chunk["status"] == "COMPLETE":
            verify_chunk_artifacts(chunk)
            manifest["cache_hits"] += 1
            save_manifest(path, manifest)
            continue
        if max_new_chunks is not None and completed_this_run >= max_new_chunks:
            manifest["status"] = "PAUSED"
            manifest["pause_reason"] = "BATCH_LIMIT_REACHED"
            manifest["paused_after_new_chunks"] = completed_this_run
            save_manifest(path, manifest)
            if progress:
                progress(manifest)
            return manifest
        if before_chunk is not None:
            guard = before_chunk(chunk) or {}
            if guard.get("allowed") is False:
                manifest["status"] = "PAUSED"
                manifest["pause_reason"] = guard.get("reason", "PRE_CHUNK_GUARD")
                manifest["resource_guard_snapshot"] = guard.get("snapshot")
                save_manifest(path, manifest)
                if progress:
                    progress(manifest)
                return manifest
            if guard.get("snapshot") is not None:
                chunk["resource_snapshot_before"] = guard["snapshot"]
        chunk["status"] = "RUNNING"
        chunk["attempt_count"] = chunk.get("attempt_count", 0) + 1
        chunk["resumed"] = chunk["attempt_count"] > 1
        chunk.pop("error", None)
        save_manifest(path, manifest)
        if progress:
            progress(manifest)
        try:
            result = execute_chunk(chunk)
            chunk.update(result or {})
            verify_chunk_artifacts(chunk)
            chunk["status"] = "COMPLETE"
            chunk.pop("failure_class", None)
            chunk.pop("resource_stop_snapshot", None)
            chunk["completed_at"] = datetime.now(timezone.utc).isoformat()
            save_manifest(path, manifest)
            completed_this_run += 1
            if progress:
                progress(manifest)
        except ResourceGuardStop as exc:
            chunk["status"] = "INTERRUPTED"
            chunk["failure_class"] = "RESOURCE_GUARD"
            chunk["error"] = str(exc)
            chunk["resource_stop_snapshot"] = exc.snapshot
            if exc.sample_log_path:
                chunk["resource_sample_log_path"] = exc.sample_log_path
            manifest["status"] = "PAUSED"
            manifest["pause_reason"] = exc.reason
            manifest["resource_guard_snapshot"] = exc.snapshot
            save_manifest(path, manifest)
            if progress:
                progress(manifest)
            return manifest
        except Exception as exc:
            chunk["status"] = "FAILED"
            chunk["failure_class"] = "WORKER_OR_IO_ERROR"
            chunk["error"] = str(exc)
            manifest["status"] = "PAUSED"
            manifest["last_error"] = str(exc)
            save_manifest(path, manifest)
            if progress:
                progress(manifest)
            raise
    manifest["status"] = "CHUNKS_COMPLETE"
    manifest.pop("last_error", None)
    manifest.pop("pause_reason", None)
    save_manifest(path, manifest)
    if progress:
        progress(manifest)
    return manifest


def scan_wtt_inbox(inbox: Path, registered_hashes: set[str] | None = None,
                   athletes: list[dict] | None = None, only_file: Path | None = None) -> list[dict]:
    """Inspect only immediate children of the dedicated inbox; never scan user disks."""
    inbox = Path(inbox).resolve()
    inbox.mkdir(parents=True, exist_ok=True)
    registered_hashes = registered_hashes or set()
    athletes = athletes or []
    items = []
    paths = [Path(only_file)] if only_file is not None else list(inbox.iterdir())
    for path in sorted(paths, key=lambda item: item.name.casefold()):
        if not path.is_file() or path.suffix.casefold() not in SUPPORTED_VIDEO_SUFFIXES:
            continue
        try:
            digest = file_sha256(path)
            metadata = video_metadata(path)
            name = _normalize_name(path.stem)
            candidates = []
            for athlete in athletes:
                labels = [athlete.get("canonical_name_en"), athlete.get("canonical_name_zh")]
                aliases = []
                for label in labels:
                    if not label:
                        continue
                    normalized_label = _normalize_name(label)
                    aliases.append(normalized_label)
                    aliases.extend(_normalize_name(part) for part in re.split(r"[^A-Za-z0-9\u3400-\u9fff]+", label)
                                   if len(_normalize_name(part)) >= 4)
                if any(alias and alias in name for alias in aliases):
                    candidates.append(athlete["athlete_id"])
            items.append({
                "inbox_id": digest,
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": digest,
                "duplicate": digest in registered_hashes,
                "video": metadata,
                "quality": classify(metadata),
                "candidate_athlete_ids": candidates,
                "match_status": "REVIEW_REQUIRED",
            })
        except Exception as exc:
            items.append({"inbox_id": None, "filename": path.name, "size_bytes": path.stat().st_size,
                          "sha256": None, "duplicate": False, "error": str(exc),
                          "match_status": "REVIEW_REQUIRED"})
    return items


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", value.casefold())


class Evidence(BaseModel):
    source: str = "MANUAL"
    note: str = ""
    raw_detector_data: dict | None = None


class Rally(BaseModel):
    rally_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    detected_ball_frames: int = Field(default=0, ge=0)
    missing_ball_frames: int = Field(default=0, ge=0)
    quality_flags: list[str] = Field(default_factory=list)
    observation_refs: list[int] = Field(default_factory=list)
    evidence: Evidence = Field(default_factory=Evidence)

    @model_validator(mode="after")
    def ordered(self):
        if self.end_ms <= self.start_ms:
            raise ValueError("Rally end_ms must be after start_ms")
        return self


class Point(BaseModel):
    point_id: str
    game_number: int = Field(ge=1)
    point_number: int = Field(ge=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    scorer_id: str | None = None
    server_id: str | None = None
    receiver_id: str | None = None
    score_before: dict[str, int] | None = None
    score_after: dict[str, int] | None = None
    segmentation_source: Literal["MANUAL", "MODEL_CANDIDATE", "IMPORTED"] = "MANUAL"
    confidence: float | None = Field(default=None, ge=0, le=1)
    review_status: Literal["CANDIDATE", "ACCEPTED", "ADJUSTED"] = "CANDIDATE"
    evidence: Evidence = Field(default_factory=Evidence)
    rallies: list[Rally] = Field(default_factory=list)

    @model_validator(mode="after")
    def ordered(self):
        if self.end_ms <= self.start_ms:
            raise ValueError("Point end_ms must be after start_ms")
        if any(r.start_ms < self.start_ms or r.end_ms > self.end_ms for r in self.rallies):
            raise ValueError("Rally interval must be inside its point interval")
        return self


class Game(BaseModel):
    game_number: int = Field(ge=1)
    start_ms: int = Field(ge=0)
    end_ms: int | None = Field(default=None, gt=0)
    points: list[Point] = Field(default_factory=list)
    evidence: Evidence = Field(default_factory=Evidence)


class SceneSegment(BaseModel):
    scene_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    scene_type: Literal["MATCH_PLAY", "REPLAY", "CROWD", "TIMEOUT", "BREAK", "UNKNOWN",
                        "PLAY_VIEW", "NON_PLAY_VIEW"] = "UNKNOWN"
    review_status: Literal["CANDIDATE", "ACCEPTED", "ADJUSTED"] = "CANDIDATE"
    evidence: Evidence = Field(default_factory=Evidence)

    @model_validator(mode="after")
    def ordered(self):
        if self.end_ms <= self.start_ms:
            raise ValueError("Scene end_ms must be after start_ms")
        return self


class MatchTimeline(BaseModel):
    match_id: str
    revision: int = Field(default=1, ge=0)
    games: list[Game] = Field(default_factory=list)
    scene_segments: list[SceneSegment] = Field(default_factory=list)
    updated_at: str | None = None


class TimelineAction(BaseModel):
    action: Literal["add_game", "mark_game_end", "delete_game", "add_point", "delete_point", "accept", "adjust", "split", "merge",
                    "set_score", "set_participants", "add_rally", "add_scene", "label_scene"]
    game_number: int = Field(default=1, ge=1)
    point_number: int | None = Field(default=None, ge=1)
    next_point_number: int | None = Field(default=None, ge=1)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, gt=0)
    split_at_ms: int | None = Field(default=None, gt=0)
    game_start_ms: int | None = Field(default=None, ge=0)
    scene_id: str | None = None
    scene_type: Literal["MATCH_PLAY", "REPLAY", "CROWD", "TIMEOUT", "BREAK", "UNKNOWN",
                        "PLAY_VIEW", "NON_PLAY_VIEW"] = "UNKNOWN"
    note: str = ""
    scorer_id: str | None = None
    server_id: str | None = None
    receiver_id: str | None = None
    score_before: dict[str, int] | None = None
    score_after: dict[str, int] | None = None
    rally_start_ms: int | None = Field(default=None, ge=0)
    rally_end_ms: int | None = Field(default=None, gt=0)


def apply_timeline_action(timeline: dict, action: TimelineAction) -> dict:
    """Apply one explicit human action; ambiguous facts remain null/unknown."""
    from copy import deepcopy
    from datetime import datetime, timezone
    from uuid import uuid4

    value = MatchTimeline.model_validate(timeline).model_dump(mode="json")
    game = next((item for item in value["games"] if item["game_number"] == action.game_number), None)
    if action.action == "add_scene":
        if action.start_ms is None or action.end_ms is None or action.end_ms <= action.start_ms:
            raise ValueError("Scene needs a positive start/end interval")
        value["scene_segments"].append({
            "scene_id": str(uuid4()), "start_ms": action.start_ms, "end_ms": action.end_ms,
            "scene_type": "UNKNOWN", "review_status": "CANDIDATE",
            "evidence": {"source": "MANUAL", "note": action.note},
        })
    elif action.action == "label_scene":
        segment = next((s for s in value["scene_segments"] if s["scene_id"] == action.scene_id), None)
        if segment is None:
            raise ValueError("Scene segment does not exist")
        segment["scene_type"] = action.scene_type
        segment["review_status"] = "ACCEPTED"
        segment.setdefault("evidence", {})["note"] = action.note
    elif action.action == "add_game":
        if action.game_start_ms is None:
            raise ValueError("Game needs a start timestamp")
        if game is not None:
            raise ValueError("Game number already exists")
        value["games"].append({"game_number": action.game_number, "start_ms": action.game_start_ms,
                               "end_ms": None, "points": [], "evidence": {"source": "MANUAL", "note": action.note}})
        value["games"].sort(key=lambda item: item["game_number"])
    elif action.action == "mark_game_end":
        if game is None or action.end_ms is None or action.end_ms <= game["start_ms"]:
            raise ValueError("Game end must follow its start")
        if game["points"] and action.end_ms < max(point["end_ms"] for point in game["points"]):
            raise ValueError("Game end cannot precede its last point")
        game["end_ms"] = action.end_ms
    elif action.action == "delete_game":
        if game is None:
            raise ValueError("Game does not exist")
        value["games"].remove(game)
        for index, later_game in enumerate(sorted(value["games"], key=lambda item: item["game_number"]), start=1):
            later_game["game_number"] = index
            for point_index, point in enumerate(later_game["points"], start=1):
                point["game_number"] = index
                point["point_number"] = point_index
    else:
        if game is None:
            if action.action != "add_point" or action.start_ms is None:
                raise ValueError("Game does not exist")
            game = {"game_number": action.game_number, "start_ms": action.start_ms,
                    "end_ms": None, "points": [], "evidence": {"source": "MANUAL", "note": ""}}
            value["games"].append(game)
            value["games"].sort(key=lambda item: item["game_number"])
        points = game["points"]
        if action.action == "add_point":
            if action.start_ms is None or action.end_ms is None or action.end_ms <= action.start_ms:
                raise ValueError("Point needs a positive start/end interval")
            number = action.point_number or (max((p["point_number"] for p in points), default=0) + 1)
            if any(p["point_number"] == number for p in points):
                raise ValueError("Point number already exists")
            points.append(Point(point_id=str(uuid4()), game_number=action.game_number,
                                point_number=number, start_ms=action.start_ms, end_ms=action.end_ms,
                                review_status="ADJUSTED", evidence=Evidence(note=action.note)).model_dump(mode="json"))
            points.sort(key=lambda item: item["point_number"])
        else:
            index = next((i for i, p in enumerate(points) if p["point_number"] == action.point_number), None)
            if index is None:
                raise ValueError("Point does not exist")
            point = points[index]
            if action.action == "delete_point":
                del points[index]
                for point_index, later in enumerate(points, start=1):
                    later["point_number"] = point_index
            elif action.action == "accept":
                point["review_status"] = "ACCEPTED"
            elif action.action == "adjust":
                start = point["start_ms"] if action.start_ms is None else action.start_ms
                end = point["end_ms"] if action.end_ms is None else action.end_ms
                if end <= start:
                    raise ValueError("Adjusted point end must be after start")
                point.update(start_ms=start, end_ms=end, review_status="ADJUSTED")
            elif action.action == "split":
                split_at = action.split_at_ms
                if split_at is None or not point["start_ms"] < split_at < point["end_ms"]:
                    raise ValueError("Split time must be inside the point interval")
                left_rallies = [r for r in point.get("rallies", []) if r["end_ms"] <= split_at]
                right_rallies = [r for r in point.get("rallies", []) if r["start_ms"] >= split_at]
                if len(left_rallies) + len(right_rallies) != len(point.get("rallies", [])):
                    raise ValueError("Adjust rally boundaries before splitting across a rally")
                right = deepcopy(point)
                right.update(point_id=str(uuid4()), point_number=point["point_number"] + 1,
                             start_ms=split_at, review_status="CANDIDATE", scorer_id=None,
                             server_id=None, receiver_id=None, score_before=None,
                             score_after=None, confidence=None, rallies=right_rallies,
                             evidence={"source": "MANUAL", "note": action.note, "raw_detector_data": None})
                point.update(end_ms=split_at, review_status="ADJUSTED", rallies=left_rallies)
                points.insert(index + 1, right)
                for offset, later in enumerate(points[index + 2:], start=index + 2):
                    later["point_number"] = offset + 1
            elif action.action == "merge":
                next_index = index + 1
                if next_index >= len(points):
                    raise ValueError("There is no following point to merge")
                following = points[next_index]
                if action.next_point_number is not None and following["point_number"] != action.next_point_number:
                    raise ValueError("Only adjacent points can be merged")
                if following["start_ms"] < point["start_ms"]:
                    raise ValueError("Point order is invalid")
                point["end_ms"] = following["end_ms"]
                point["rallies"].extend(following["rallies"])
                if following.get("score_after") is not None:
                    point["score_after"] = following["score_after"]
                if following.get("scorer_id") is not None:
                    point["scorer_id"] = following["scorer_id"]
                point["review_status"] = "ADJUSTED"
                point["evidence"]["note"] = action.note or "Merged adjacent point candidates"
                del points[next_index]
                for offset, later in enumerate(points[index + 1:], start=index + 1):
                    later["point_number"] = offset + 1
            elif action.action == "set_score":
                if action.score_before is None and action.score_after is None:
                    raise ValueError("Enter a before or after score")
                for score in (action.score_before, action.score_after):
                    if score is not None and (set(score) != {"player_a", "player_b"} or min(score.values()) < 0):
                        raise ValueError("Scores need non-negative player_a/player_b values")
                if action.score_before is not None:point["score_before"] = action.score_before
                if action.score_after is not None:point["score_after"] = action.score_after
                point["review_status"] = "ADJUSTED"
                point["evidence"] = {"source": "MANUAL", "note": action.note, "raw_detector_data": None}
            elif action.action == "set_participants":
                point.update(scorer_id=action.scorer_id, server_id=action.server_id,
                             receiver_id=action.receiver_id, review_status="ADJUSTED")
                point["evidence"] = {"source": "MANUAL", "note": action.note, "raw_detector_data": None}
            elif action.action == "add_rally":
                if action.rally_start_ms is None or action.rally_end_ms is None:
                    raise ValueError("Rally needs start and end timestamps")
                rally = Rally(rally_id=str(uuid4()), start_ms=action.rally_start_ms, end_ms=action.rally_end_ms,
                              evidence=Evidence(source="MANUAL", note=action.note))
                if rally.start_ms < point["start_ms"] or rally.end_ms > point["end_ms"]:
                    raise ValueError("Rally interval must be inside its point interval")
                point["rallies"].append(rally.model_dump(mode="json"))
                point["review_status"] = "ADJUSTED"
    value["revision"] = int(value.get("revision", 0)) + 1
    value["updated_at"] = datetime.now(timezone.utc).isoformat()
    return MatchTimeline.model_validate(value).model_dump(mode="json")
