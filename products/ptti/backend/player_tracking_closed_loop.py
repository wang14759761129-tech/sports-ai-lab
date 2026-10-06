"""Isolated, allowlisted storage for the experimental player-tracking loop.

All source videos and job artifacts live under PTTI-Dev. No database or
production data path is accepted by this module.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.player_tracking_loop import confirm_seed


RIGHTS = "CC BY-NC-SA 4.0 research/non-commercial"
DATASET = "Extended OpenTTGames"
SAMPLE_ID = re.compile(r"game_[1-5]-t(?:30|45|60)\Z")
JOB_ID = re.compile(r"[0-9a-f]{32}\Z")
SEED_ID = re.compile(r"[0-9a-f]{64}\Z")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def closed_loop_root(localappdata: str | Path | None = None) -> Path:
    local = Path(localappdata or os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    return local.resolve() / "PTTI-Dev" / "vision-v2-sam2" / "runs" / "closed-loop"


def _research_root(localappdata: str | Path | None = None) -> Path:
    local = Path(localappdata or os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    return local.resolve() / "PTTI-Dev" / "vision-v2-sam2"


def _manifest(localappdata: str | Path | None = None) -> dict[str, Any]:
    path = _research_root(localappdata) / "runs" / "multi-match-final" / "cross_match_validation.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if (value.get("dataset") != DATASET or value.get("rights") != RIGHTS
            or value.get("commercial_use") is not False
            or value.get("official_split") != "TRAIN_ONLY; official test split not used"):
        raise ValueError("TRAIN_SAMPLE_PROVENANCE_INVALID")
    return value


def _player_tracking_config_path() -> Path:
    return (Path(__file__).resolve().parents[1] / "configs" / "vision"
            / "PLAYER_TRACKING_V1_CANDIDATE.json")


def _player_tracking_validation_manifest(localappdata: str | Path | None = None) -> dict[str, Any] | None:
    path = (_research_root(localappdata) / "runs" / "player-tracking-v1-validation"
            / "validation_manifest.json")
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if (value.get("schema_version") != "player-tracking-v1-validation-set-v1"
            or value.get("dataset") != DATASET or value.get("rights") != RIGHTS
            or value.get("commercial_use") is not False
            or value.get("official_split") != "TRAIN_ONLY; official test split not used"
            or value.get("evaluation_role") != "FROZEN_VALIDATION"):
        raise ValueError("PLAYER_TRACKING_VALIDATION_PROVENANCE_INVALID")
    config_path = _player_tracking_config_path()
    if not config_path.is_file() or _sha(config_path) != value.get("frozen_config_sha256"):
        raise ValueError("PLAYER_TRACKING_VALIDATION_CONFIG_NOT_FROZEN")
    rows = value.get("videos")
    if not isinstance(rows, list) or len(rows) < 5:
        raise ValueError("PLAYER_TRACKING_VALIDATION_SET_TOO_SMALL")
    validation_ids = [row.get("video_id") for row in rows if isinstance(row, dict)]
    validation_matches = [row.get("match_id") for row in rows if isinstance(row, dict)]
    if (len(validation_ids) != len(rows) or len(set(validation_ids)) != len(rows)
            or len(set(validation_matches)) < 5):
        raise ValueError("PLAYER_TRACKING_VALIDATION_MATCHES_NOT_INDEPENDENT")
    dev = _manifest(localappdata)
    dev_intervals = []
    for row in dev.get("videos", []):
        clip = row.get("clip") or {}
        try:
            start = float(clip["start_seconds"])
            end = start + float(clip["duration_seconds"])
        except (KeyError, TypeError, ValueError):
            continue
        dev_intervals.append((row.get("match_id"), start, end))
    for row in rows:
        clip = row.get("clip") or {}
        if row.get("official_split") != "TRAIN":
            raise ValueError("PLAYER_TRACKING_VALIDATION_TEST_SPLIT_FORBIDDEN")
        try:
            start = float(clip["start_seconds"])
            end = start + float(clip["duration_seconds"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("PLAYER_TRACKING_VALIDATION_INTERVAL_INVALID") from exc
        if end <= start or any(match == row.get("match_id")
                               and start < dev_end and dev_start < end
                               for match, dev_start, dev_end in dev_intervals):
            raise ValueError("PLAYER_TRACKING_VALIDATION_OVERLAPS_DEVELOPMENT")
    return value


def list_closed_loop_samples(localappdata: str | Path | None = None, *, verify_hashes: bool = True) -> list[dict[str, Any]]:
    research = _research_root(localappdata)
    manifest = _manifest(localappdata)
    validation = _player_tracking_validation_manifest(localappdata)
    source_manifests = [(manifest, "DEVELOPMENT")]
    if validation is not None:
        source_manifests.append((validation, "FROZEN_VALIDATION"))
    result = []
    seen = set()
    source_rows = [(row, role) for source_manifest, role in source_manifests
                   for row in source_manifest.get("videos", [])]
    for row, evaluation_role in source_rows:
        clip = row.get("clip") or {}
        video_id = row.get("video_id")
        if (not isinstance(video_id, str) or not SAMPLE_ID.fullmatch(video_id)
                or video_id in seen or row.get("official_split") != "TRAIN"
                or row.get("seed_screening", {}).get("status") not in
                   {"SEEDS_READY", "INITIALIZATION_FAILED", "PENDING_SEED_REVIEW"}):
            continue
        name = clip.get("file")
        if not isinstance(name, str) or Path(name).name != name or not name.lower().endswith(".mp4"):
            continue
        source = (research / "datasets" / "extended-openttgames" / name).resolve()
        if not source.is_relative_to((research / "datasets" / "extended-openttgames").resolve()):
            continue
        if not source.is_file():
            continue
        expected_sha = str(clip.get("sha256", "")).lower()
        expected_bytes = int(clip.get("bytes", -1))
        if len(expected_sha) != 64 or source.stat().st_size != expected_bytes:
            continue
        if verify_hashes and _sha(source) != expected_sha:
            continue
        width, height = map(int, str(clip.get("resolution", "0x0")).split("x", 1))
        seen.add(video_id)
        result.append({
            "sample_id": video_id,
            "match_id": row.get("match_id"),
            "start_seconds": int(video_id.rsplit("-t", 1)[1]),
            "dataset": DATASET,
            "rights": RIGHTS,
            "commercial_use": False,
            "official_split": "TRAIN",
            "clip_sha256": expected_sha,
            "bytes": expected_bytes,
            "duration_seconds": float(clip["duration_seconds"]),
            "frames": int(clip["frames"]),
            "sample_fps": float(clip["sample_fps"]),
            "source_fps": float(clip["source_fps"]),
            "width": width,
            "height": height,
            "seed_screening": row.get("seed_screening", {}).get("status"),
            "evaluation_role": evaluation_role,
            "validation_config_sha256": (validation.get("frozen_config_sha256")
                                          if evaluation_role == "FROZEN_VALIDATION" else None),
            "evaluation_role": evaluation_role,
            "video_path": source,
        })
    return sorted(result, key=lambda item: (item["match_id"], item["sample_id"]))


def resolve_sample(sample_id: str, localappdata: str | Path | None = None, *, verify_hash: bool = True) -> dict[str, Any]:
    if not SAMPLE_ID.fullmatch(sample_id):
        raise ValueError("INVALID_SAMPLE_ID")
    for sample in list_closed_loop_samples(localappdata, verify_hashes=verify_hash):
        if sample["sample_id"] == sample_id:
            return sample
    raise FileNotFoundError("AUTHORIZED_TRAIN_SAMPLE_UNAVAILABLE_OR_CHANGED")


def seed_review_root(localappdata: str | Path | None = None) -> Path:
    return closed_loop_root(localappdata) / "seed-review"


def _seed_key(sample_id: str, frame_index: int, localappdata: str | Path | None = None) -> tuple[Path, dict[str, Any]]:
    if not SAMPLE_ID.fullmatch(sample_id) or not isinstance(frame_index, int) or frame_index < 0:
        raise ValueError("INVALID_SEED_FRAME")
    sample = resolve_sample(sample_id, localappdata)
    if frame_index >= sample["frames"]:
        raise ValueError("SEED_FRAME_OUT_OF_RANGE")
    # Short opaque folder names keep Windows paths comfortably below MAX_PATH.
    key = hashlib.sha256(f"{sample_id}:{frame_index}:{sample['clip_sha256']}".encode()).hexdigest()[:20]
    return seed_review_root(localappdata) / key, sample


def seed_detection_dir(sample_id: str, frame_index: int, detection_set_id: str,
                       localappdata: str | Path | None = None) -> Path:
    if not SEED_ID.fullmatch(detection_set_id):
        raise ValueError("INVALID_DETECTION_SET")
    base, _ = _seed_key(sample_id, frame_index, localappdata)
    return base / detection_set_id[:16]


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        for attempt in range(6):
            try:
                temporary.replace(path)
                return
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.02 * (2 ** attempt))
    finally:
        temporary.unlink(missing_ok=True)


def load_seed_detection(sample_id: str, frame_index: int, detection_set_id: str,
                        localappdata: str | Path | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not SEED_ID.fullmatch(detection_set_id):
        raise ValueError("INVALID_DETECTION_SET")
    sample = resolve_sample(sample_id, localappdata)
    folder = seed_detection_dir(sample_id, frame_index, detection_set_id, localappdata)
    path = folder / "detections.json"
    if not path.is_file():
        raise FileNotFoundError("SEED_DETECTIONS_NOT_READY")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (payload.get("detection_set_id") != detection_set_id
            or payload.get("sample_id") != sample_id
            or payload.get("frame_index") != frame_index
            or payload.get("clip_sha256") != sample["clip_sha256"]
            or not isinstance(payload.get("detections"), list)):
        raise ValueError("SEED_DETECTION_EVIDENCE_MISMATCH")
    return sample, payload["detections"]


def seed_review_asset(sample_id: str, frame_index: int, detection_set_id: str,
                      view: str, localappdata: str | Path | None = None) -> Path:
    if view not in {"source", "overlay"}:
        raise ValueError("INVALID_SEED_REVIEW_VIEW")
    folder = seed_detection_dir(sample_id, frame_index, detection_set_id, localappdata).resolve()
    path = (folder / ("seed-frame.jpg" if view == "source" else "seed-overlay.jpg")).resolve()
    if not path.is_relative_to(folder):
        raise ValueError("SEED_REVIEW_ASSET_OUTSIDE_FOLDER")
    return path


def create_closed_loop_job(*, sample_id: str, frame_index: int, detection_set_id: str,
                           near_candidate_id: str, far_candidate_id: str,
                           user_confirmed: bool, near_bbox: list[float] | None = None,
                           far_bbox: list[float] | None = None,
                           athlete_mapping: dict[str, str] | None = None,
                           candidate_review: dict[str, str] | None = None,
                           tracking_architecture: str = "CLOSED_LOOP_SINGLE_SEED",
                           anchor_interval_seconds: float = 1.0,
                           localappdata: str | Path | None = None) -> tuple[str, Path, dict[str, Any]]:
    if tracking_architecture not in {"CLOSED_LOOP_SINGLE_SEED", "DETECTION_ANCHORED_MASK_TRACKING"}:
        raise ValueError("INVALID_TRACKING_ARCHITECTURE")
    if (tracking_architecture == "DETECTION_ANCHORED_MASK_TRACKING"
            and anchor_interval_seconds not in {0.5, 1.0, 2.0}):
        raise ValueError("UNSUPPORTED_ANCHOR_INTERVAL")
    sample, raw = load_seed_detection(sample_id, frame_index, detection_set_id, localappdata)
    seed = confirm_seed(sample=sample, raw_detections=raw, near_candidate_id=near_candidate_id,
                        far_candidate_id=far_candidate_id, frame_index=frame_index,
                        user_confirmed=user_confirmed, near_bbox=near_bbox, far_bbox=far_bbox,
                        athlete_mapping=athlete_mapping)
    review = candidate_review or {}
    if any(candidate_id not in {str(item["candidate_id"]) for item in raw}
           or action not in {"MARK_OTHER", "IGNORE"} for candidate_id, action in review.items()):
        raise ValueError("INVALID_RAW_DETECTION_REVIEW")
    seed["candidate_review"] = [{"candidate_id": candidate_id, "action": action,
                                 "source": "USER_UI", "raw_preserved": True}
                                for candidate_id, action in review.items()]
    seed["tracking_architecture"] = tracking_architecture
    seed["anchor_interval_seconds"] = float(anchor_interval_seconds)
    seed["evaluation_role"] = sample.get("evaluation_role", "DEVELOPMENT")
    seed["frozen_config_sha256"] = sample.get("validation_config_sha256")
    if seed["evaluation_role"] == "FROZEN_VALIDATION" and not seed["frozen_config_sha256"]:
        raise ValueError("PLAYER_TRACKING_VALIDATION_CONFIG_NOT_FROZEN")
    root = closed_loop_root(localappdata)
    job_id = uuid.uuid4().hex
    job_root = root / "jobs" / job_id
    job_root.mkdir(parents=True, exist_ok=False)
    seed["job_id"] = job_id
    seed["seed_confirmation_id"] = uuid.uuid4().hex
    atomic_json(job_root / "seed.json", seed)
    atomic_json(job_root / "manual-actions.json", {
        "schema_version": "player-tracking-manual-actions-v1",
        "actions": [{"action_id": uuid.uuid4().hex, "action": "initial_seed",
                     "source": "USER_UI", "frame": frame_index,
                     "timestamp": datetime.now(timezone.utc).isoformat()}],
    })
    progress = {
        "job_id": job_id, "sample_id": sample_id, "status": "QUEUED",
        "stage": "等待隔离视觉 worker 启动", "frame_count": sample["frames"],
        "processed_frames": 0, "events": [{
            "type": "INITIAL_SEED", "frame": frame_index, "timestamp_ms": seed["timestamp_ms"],
            "source": "USER_UI", "object_ids": {"NEAR_PLAYER": 1, "FAR_PLAYER": 2},
        }], "created_at": datetime.now(timezone.utc).isoformat(),
        "tracking_architecture": tracking_architecture,
        "anchor_interval_seconds": float(anchor_interval_seconds),
        "evaluation_role": seed["evaluation_role"],
        "frozen_config_sha256": seed["frozen_config_sha256"],
        "production_database": "NOT_ACCESSED",
    }
    atomic_json(job_root / "progress.json", progress)
    return job_id, job_root, seed


def job_root(job_id: str, localappdata: str | Path | None = None) -> Path:
    if not JOB_ID.fullmatch(job_id):
        raise ValueError("INVALID_JOB_ID")
    base = (closed_loop_root(localappdata) / "jobs").resolve()
    path = (base / job_id).resolve()
    if not path.is_relative_to(base):
        raise ValueError("JOB_PATH_OUTSIDE_CLOSED_LOOP")
    return path


def load_job_progress(job_id: str, localappdata: str | Path | None = None) -> dict[str, Any]:
    path = job_root(job_id, localappdata) / "progress.json"
    if not path.is_file():
        raise FileNotFoundError("CLOSED_LOOP_JOB_NOT_FOUND")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("job_id") != job_id:
        raise ValueError("CLOSED_LOOP_JOB_ID_MISMATCH")
    return value


def save_job_progress(job_id: str, progress: dict[str, Any], localappdata: str | Path | None = None) -> None:
    if progress.get("job_id") != job_id:
        raise ValueError("CLOSED_LOOP_JOB_ID_MISMATCH")
    atomic_json(job_root(job_id, localappdata) / "progress.json", progress)


def append_manual_action(*, job_id: str, action: str, details: dict[str, Any] | None = None,
                         source: str = "USER_UI",
                         action_id: str | None = None,
                         localappdata: str | Path | None = None) -> dict[str, Any]:
    """Append a user action to the allowlisted development job audit trail."""
    allowed = {"initial_seed", "out_of_frame_confirm", "mask_choice", "manual_rebox", "identity_confirm"}
    if action not in allowed or source not in {"USER_UI", "QA_UI"}:
        raise ValueError("INVALID_MANUAL_ACTION")
    root = job_root(job_id, localappdata)
    path = root / "manual-actions.json"
    payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {
        "schema_version": "player-tracking-manual-actions-v1", "actions": []}
    if payload.get("schema_version") != "player-tracking-manual-actions-v1" or not isinstance(payload.get("actions"), list):
        raise ValueError("MANUAL_ACTION_LOG_INVALID")
    requested_id = action_id or uuid.uuid4().hex
    if not re.fullmatch(r"[0-9a-f]{32}", requested_id):
        raise ValueError("INVALID_MANUAL_ACTION_ID")
    existing = next((row for row in payload["actions"]
                     if row.get("action_id") == requested_id), None)
    if existing is not None:
        return existing
    row = {"action_id": requested_id, "action": action, "source": source,
           "timestamp": datetime.now(timezone.utc).isoformat(), "details": details or {}}
    payload["actions"].append(row)
    atomic_json(path, payload)
    return row


def player_tracking_conflict_asset(job_id: str, event_id: str, view: str,
                                   localappdata: str | Path | None = None) -> Path:
    if (not isinstance(event_id, str)
            or not re.fullmatch(r"MASK_CONFLICT_(?:NEAR|FAR)_PLAYER_\d{5}_\d{5}", event_id)
            or view not in {"source", "forward", "reverse"}):
        raise ValueError("INVALID_MASK_CONFLICT_ASSET")
    root = job_root(job_id, localappdata).resolve()
    manifest_path = root / "tracking.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("TRACKING_MANIFEST_NOT_FOUND")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    event = next((item for item in manifest.get("events", [])
                  if item.get("event_id") == event_id and item.get("type") == "MASK_CONFLICT"), None)
    if event is None:
        raise FileNotFoundError("MASK_CONFLICT_NOT_FOUND")
    relative = (event.get("review_assets") or {}).get(view)
    if not isinstance(relative, str):
        raise FileNotFoundError("MASK_CONFLICT_ASSET_NOT_FOUND")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise ValueError("MASK_CONFLICT_ASSET_OUTSIDE_JOB")
    return path


def queue_reacquisition(*, job_id: str, role: str, candidate_id: str,
                        localappdata: str | Path | None = None) -> dict[str, Any]:
    if role not in {"NEAR_PLAYER", "FAR_PLAYER"}:
        raise ValueError("INVALID_PLAYER_ROLE")
    root = job_root(job_id, localappdata)
    progress = load_job_progress(job_id, localappdata)
    if progress.get("status") != "NEEDS_USER_CONFIRMATION":
        raise ValueError("REACQUISITION_NOT_WAITING_FOR_USER")
    candidates_path = root / "review_candidates.json"
    if not candidates_path.is_file():
        raise FileNotFoundError("REACQUISITION_CANDIDATES_NOT_FOUND")
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    if not any(row.get("candidate_id") == candidate_id for row in candidates.get("detections", [])):
        raise ValueError("REACQUISITION_CANDIDATE_NOT_FOUND")
    allowed_by_role = candidates.get("candidate_ids_by_role")
    if isinstance(allowed_by_role, dict) and candidate_id not in allowed_by_role.get(role, []):
        raise ValueError("REACQUISITION_CANDIDATE_ROLE_MISMATCH")
    command = {
        "command_id": uuid.uuid4().hex, "action": "MANUAL_REACQUIRE",
        "role": role, "object_id": 1 if role == "NEAR_PLAYER" else 2,
        "candidate_id": candidate_id, "frame": candidates["frame_index"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    atomic_json(root / "reacquisition-command.json", command)
    return {"status": "QUEUED", "command_id": command["command_id"],
            "object_id": command["object_id"], "role": role}


def closed_loop_asset(job_id: str, asset_name: str, localappdata: str | Path | None = None) -> Path:
    if not isinstance(asset_name, str) or not re.fullmatch(
            r"(?:player_tracking_overlay\.mp4|anchor_guided_tracking_overlay\.mp4|review-frames/\d{5}\.jpg|overlay-frames/\d{5}\.jpg|masks/(?:near_player|far_player)/\d{5}\.png)\Z",
            asset_name):
        raise ValueError("INVALID_CLOSED_LOOP_ASSET")
    base = job_root(job_id, localappdata).resolve()
    path = (base / asset_name).resolve()
    if not path.is_relative_to(base):
        raise ValueError("CLOSED_LOOP_ASSET_OUTSIDE_JOB")
    return path
