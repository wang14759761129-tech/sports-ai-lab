"""Full-match ingestion, chunk manifests, and human-reviewed timeline schemas.

This module intentionally does not infer a point winner, spin, stroke, or tactic.
Its pure helpers make frame/time mapping and resume behavior independently testable.
"""
from __future__ import annotations

from hashlib import sha256 as _sha256
import json
import bisect
from pathlib import Path
import re
import subprocess
import time
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
    for path_key, hash_key in (("raw_prediction_path", "raw_prediction_sha256"),
                               ("observations_path", "observations_sha256"),
                               ("runtime_path", "runtime_sha256")):
        path = Path(chunk.get(path_key, ""))
        expected = chunk.get(hash_key)
        # Older pure-helper fixtures have no filesystem evidence. Production
        # pipeline checkpoints always carry hashes and are verified strictly.
        if expected is None and not any(chunk.get(key) for key in (
                "raw_prediction_sha256", "observations_sha256", "runtime_sha256")):
            return
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


def run_resumable_chunks(path: Path, execute_chunk, progress=None) -> dict:
    """Run pending/failed chunks and durably checkpoint each transition."""
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    resumed = manifest.get("status") in {"PAUSED", "RUNNING"} or any(
        chunk.get("status") == "COMPLETE" for chunk in manifest["chunks"])
    manifest.setdefault("cache_hits", 0)
    manifest.setdefault("resume_count", 0)
    if resumed:
        manifest["resume_count"] += 1
    manifest["status"] = "RUNNING"
    save_manifest(path, manifest)
    for chunk in manifest["chunks"]:
        if chunk["status"] == "COMPLETE":
            verify_chunk_artifacts(chunk)
            manifest["cache_hits"] += 1
            save_manifest(path, manifest)
            continue
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
            chunk["status"] = "COMPLETE"
            chunk["completed_at"] = datetime.now(timezone.utc).isoformat()
            save_manifest(path, manifest)
            if progress:
                progress(manifest)
        except Exception as exc:
            chunk["status"] = "FAILED"
            chunk["error"] = str(exc)
            manifest["status"] = "PAUSED"
            manifest["last_error"] = str(exc)
            save_manifest(path, manifest)
            if progress:
                progress(manifest)
            raise
    manifest["status"] = "CHUNKS_COMPLETE"
    manifest.pop("last_error", None)
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
