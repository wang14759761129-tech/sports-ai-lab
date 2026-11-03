"""Quality-gated 2D player pose contracts and interpretable motion proxies."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import acos, degrees, hypot, isfinite
from typing import Any, Iterable, Mapping, Sequence
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


UNRESOLVED_TRACK_EVENTS = {
    "IDENTITY_UNCERTAIN", "MASK_CONFLICT", "TRACK_LOST", "SCENE_RESET",
    "REQUIRES_USER_CONFIRMATION",
}
VISIBLE_STATES = {"VISIBLE", "PARTIAL"}
POSE_JOINTS = (
    "nose", "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip", "left_knee",
    "right_knee", "left_ankle", "right_ankle",
)
HALPE26_JOINTS = (
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip", "left_knee",
    "right_knee", "left_ankle", "right_ankle", "head", "neck", "hip",
    "left_big_toe", "right_big_toe", "left_small_toe", "right_small_toe",
    "left_heel", "right_heel",
)
TRACKING_JOB_ID = re.compile(r"[0-9a-f]{32}\Z")


@dataclass(frozen=True)
class TrackWindowDecision:
    role: str
    start_frame: int
    end_frame: int
    status: str
    coverage: float
    usable_frames: int
    expected_frames: int
    motion_eligible: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_person_crop(frame_size: tuple[int, int], bbox: Sequence[float], *,
                      margin_x: float = 0.12, margin_y: float = 0.08) -> dict[str, int]:
    """Return a frame-clipped crop around an XYXY person box with proportional margin."""
    width, height = map(int, frame_size)
    if width <= 0 or height <= 0 or len(bbox) != 4:
        raise ValueError("INVALID_FRAME_OR_BBOX")
    x0, y0, x1, y1 = map(float, bbox)
    if not all(isfinite(value) for value in (x0, y0, x1, y1)) or x1 <= x0 or y1 <= y0:
        raise ValueError("INVALID_PERSON_BBOX")
    if not 0 <= margin_x <= 0.5 or not 0 <= margin_y <= 0.5:
        raise ValueError("INVALID_CROP_MARGIN")
    pad_x, pad_y = (x1 - x0) * margin_x, (y1 - y0) * margin_y
    left = max(0, int(x0 - pad_x))
    top = max(0, int(y0 - pad_y))
    right = min(width, int(x1 + pad_x + 0.999999))
    bottom = min(height, int(y1 + pad_y + 0.999999))
    if right <= left or bottom <= top:
        raise ValueError("EMPTY_PERSON_CROP")
    return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def globalize_keypoints(points: Iterable[Mapping[str, Any]], *,
                        origin: tuple[int, int]) -> list[dict[str, Any]]:
    """Map crop-space observations into original-video coordinates, preserving scores."""
    origin_x, origin_y = map(float, origin)
    result = []
    for point in points:
        x, y, score = float(point["x"]), float(point["y"]), float(point["score"])
        result.append({"joint": str(point["joint"]), "x_global": x + origin_x,
                       "y_global": y + origin_y, "score": score})
    return result


def halpe26_observations(keypoints: Sequence[Sequence[float]], scores: Sequence[float], *,
                         origin: tuple[int, int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Name the model's documented Halpe26 output and preserve crop/global coordinates."""
    if len(keypoints) != len(HALPE26_JOINTS) or len(scores) != len(HALPE26_JOINTS):
        raise ValueError("HALPE26_OUTPUT_SHAPE_MISMATCH")
    raw = []
    for name, point, score in zip(HALPE26_JOINTS, keypoints, scores):
        if len(point) < 2:
            raise ValueError("INVALID_MODEL_KEYPOINT")
        raw.append({"joint": name, "x_global": float(point[0]) + origin[0],
                    "y_global": float(point[1]) + origin[1], "score": float(score)})
    selected = [point for point in raw if point["joint"] in POSE_JOINTS]
    return raw, selected


def _valid_bbox(record: Mapping[str, Any], frame_size: tuple[int, int]) -> bool:
    bbox = record.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return False
    try:
        x0, y0, x1, y1 = map(float, bbox)
    except (TypeError, ValueError):
        return False
    width, height = frame_size
    box_width, box_height = x1 - x0, y1 - y0
    area_fraction = box_width * box_height / max(1, width * height)
    aspect = box_width / box_height if box_height > 0 else 0
    return (all(isfinite(value) for value in (x0, y0, x1, y1))
            and box_width > 0 and box_height > 0
            and -width * 0.05 <= x0 < width * 1.05
            and -height * 0.05 <= y0 < height * 1.05
            and -width * 0.05 <= x1 <= width * 1.05
            and -height * 0.05 <= y1 <= height * 1.05
            and 0.0001 <= area_fraction <= 0.75 and 0.08 <= aspect <= 3.5)


def _record_is_pose_usable(record: Mapping[str, Any], frame_size: tuple[int, int]) -> bool:
    return (
        record.get("tracking_status") == "ACCEPTED"
        and record.get("visibility") in VISIBLE_STATES
        and int(record.get("mask_area") or 0) > 0
        and _valid_bbox(record, frame_size)
        and "CONFLICT" not in str(record.get("decision", ""))
        and record.get("tracking_state") not in {"LOST", "IDENTITY_UNCERTAIN", "OUT_OF_FRAME"}
    )


def evaluate_track_window(records: Iterable[Mapping[str, Any]],
                          events: Iterable[Mapping[str, Any]], *, role: str,
                          start_frame: int, end_frame: int,
                          frame_size: tuple[int, int],
                          pose_ready_coverage: float = 0.80,
                          review_coverage: float = 0.35) -> TrackWindowDecision:
    """Gate a short window before inference; uncertainty suppresses pose output."""
    if start_frame < 0 or end_frame <= start_frame or not 0 < review_coverage <= pose_ready_coverage <= 1:
        raise ValueError("INVALID_TRACK_WINDOW")
    expected = end_frame - start_frame
    selected = [row for row in records if row.get("role") == role
                and start_frame <= int(row.get("frame", -1)) < end_frame]
    by_frame: dict[int, Mapping[str, Any]] = {}
    for row in selected:
        frame = int(row["frame"])
        if frame in by_frame:
            # Duplicate role/frame evidence is ambiguous and never silently accepted.
            by_frame.pop(frame, None)
        else:
            by_frame[frame] = row
    usable = {frame for frame, row in by_frame.items() if _record_is_pose_usable(row, frame_size)}
    coverage = len(usable) / expected
    reasons: list[str] = []
    for event in events:
        if event.get("role") not in (None, role):
            continue
        event_frame = event.get("frame")
        if event_frame is None or not start_frame <= int(event_frame) < end_frame:
            continue
        event_type = str(event.get("type", event.get("event_type", "")))
        event_status = str(event.get("status", "")).upper()
        if event_type in UNRESOLVED_TRACK_EVENTS and event_status not in {"CONFIRMED", "RESOLVED", "REJECTED"}:
            reasons.append("UNRESOLVED_TRACK_EVENT")
        if event_type == "OUT_OF_FRAME" and event_status == "CONFIRMED":
            reasons.append("PLAYER_OUT_OF_FRAME")
    if not selected or not usable:
        reasons.append("PLAYER_NOT_VISIBLE")
    if any(frame not in usable for frame in range(start_frame, end_frame)) and usable:
        reasons.append("INCOMPLETE_TRACK_EVIDENCE")
    if "UNRESOLVED_TRACK_EVENT" in reasons:
        status = "REVIEW"
    elif "PLAYER_OUT_OF_FRAME" in reasons:
        status = "NO_POSE"
    elif coverage >= pose_ready_coverage:
        status = "POSE_READY"
    elif coverage >= review_coverage:
        status = "REVIEW"
    else:
        status = "NO_POSE"
    return TrackWindowDecision(
        role=role, start_frame=start_frame, end_frame=end_frame, status=status,
        coverage=round(coverage, 6), usable_frames=len(usable), expected_frames=expected,
        motion_eligible=status == "POSE_READY" and not reasons,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def build_track_windows(records: Sequence[Mapping[str, Any]], events: Sequence[Mapping[str, Any]], *,
                        frame_count: int, fps: float, frame_size: tuple[int, int],
                        window_seconds: float = 1.0) -> list[dict[str, Any]]:
    if frame_count <= 0 or fps <= 0 or window_seconds <= 0:
        raise ValueError("INVALID_POSE_WINDOW_PLAN")
    window_frames = max(1, round(fps * window_seconds))
    windows = []
    for start in range(0, frame_count, window_frames):
        end = min(frame_count, start + window_frames)
        decisions = {
            role: evaluate_track_window(records, events, role=role, start_frame=start,
                                        end_frame=end, frame_size=frame_size)
            for role in ("NEAR_PLAYER", "FAR_PLAYER")
        }
        windows.append({"start_frame": start, "end_frame": end,
                        "start_timestamp_seconds": start / fps,
                        "end_timestamp_seconds": end / fps,
                        "players": {role: decision.to_dict()
                                    for role, decision in decisions.items()}})
    return windows


def pose_quality_state(scores: Mapping[str, float], *, track_quality: str,
                       minimum_joint_score: float = 0.35) -> str:
    """Classify actual joint observations; untrusted upstream windows never pass."""
    if track_quality != "POSE_READY":
        return "NO_POSE"
    valid = {name for name, score in scores.items()
             if name in POSE_JOINTS and isfinite(float(score))
             and float(score) >= minimum_joint_score}
    if len(valid) >= 8:
        return "GOOD"
    if len(valid) >= 4:
        return "PARTIAL"
    return "LOW_CONFIDENCE"


def _point(keypoints: Mapping[str, Mapping[str, Any]], name: str) -> tuple[float, float] | None:
    value = keypoints.get(name)
    if not value or float(value.get("score", 0)) < 0.35:
        return None
    return float(value["x_global"]), float(value["y_global"])


def _angle(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float | None:
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])
    denominator = hypot(*ba) * hypot(*bc)
    if denominator <= 1e-9:
        return None
    cosine = max(-1.0, min(1.0, (ba[0] * bc[0] + ba[1] * bc[1]) / denominator))
    return degrees(acos(cosine))


def motion_metrics(poses: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compute small 2D proxies only from uninterrupted, quality-gated identity rows."""
    eligible = [pose for pose in poses if pose.get("track_quality") == "POSE_READY"
                and pose.get("identity_continuous") is True
                and pose.get("pose_quality") in {"GOOD", "PARTIAL"}]
    eligible.sort(key=lambda pose: int(pose["timestamp_ms"]))
    # Never bridge a skipped/review interval and present two separate fragments as
    # one continuous movement measurement. Keep only the longest valid run.
    segments: list[list[Mapping[str, Any]]] = []
    for pose in eligible:
        if not segments or int(pose["timestamp_ms"]) - int(segments[-1][-1]["timestamp_ms"]) > 250:
            segments.append([pose])
        else:
            segments[-1].append(pose)
    eligible = max(segments, key=len, default=[])
    if len(eligible) < 2:
        return {"status": "INSUFFICIENT_CONTINUOUS_IDENTITY", "claims":
                "2D estimates; not biomechanical conclusions", "wrist_observations": 0,
                "continuous_segment_count": len(segments)}
    centers = []
    stance_widths = []
    knee_angles = []
    wrists = []
    for pose in eligible:
        points = pose.get("keypoints", {})
        center_points = [_point(points, joint) for joint in
                         ("left_shoulder", "right_shoulder", "left_hip", "right_hip")]
        center_points = [point for point in center_points if point is not None]
        if center_points:
            centers.append((int(pose["timestamp_ms"]),
                            sum(point[0] for point in center_points) / len(center_points)))
        left_ankle, right_ankle = _point(points, "left_ankle"), _point(points, "right_ankle")
        if left_ankle and right_ankle:
            stance_widths.append(hypot(right_ankle[0] - left_ankle[0], right_ankle[1] - left_ankle[1]))
        for side in ("left", "right"):
            hip, knee, ankle = (_point(points, f"{side}_{joint}") for joint in ("hip", "knee", "ankle"))
            if hip and knee and ankle:
                value = _angle(hip, knee, ankle)
                if value is not None:
                    knee_angles.append(value)
            wrist = _point(points, f"{side}_wrist")
            if wrist:
                wrists.append({"timestamp_ms": int(pose["timestamp_ms"]), "side": side,
                               "x_global": wrist[0], "y_global": wrist[1]})
    if len(centers) < 2:
        return {"status": "INSUFFICIENT_CONTINUOUS_IDENTITY", "claims":
                "2D estimates; not biomechanical conclusions", "wrist_observations": len(wrists)}
    return {
        "status": "AVAILABLE",
        "body_center_proxy": {"axis": "x_global_px", "start": round(centers[0][1], 2),
                              "end": round(centers[-1][1], 2)},
        "stance_width_proxy_px": round(sum(stance_widths) / len(stance_widths), 2) if stance_widths else None,
        "knee_angle_2d_estimate_degrees": round(sum(knee_angles) / len(knee_angles), 2) if knee_angles else None,
        "lateral_movement_proxy_px": round(centers[-1][1] - centers[0][1], 2),
        "wrist_observations": len(wrists), "wrist_trajectory_2d_estimate": wrists,
        "continuous_segment_count": len(segments),
        "claims": "2D estimates; not biomechanical conclusions",
    }


def supports_pose_tracking_manifest(manifest: Mapping[str, Any]) -> bool:
    """Accept current anchor-guided results and structurally verifiable v1 manifests."""
    common = (
        manifest.get("status") in {"ANCHOR_GUIDED_COMPLETE", "COMPLETE"}
        and manifest.get("dataset") == "Extended OpenTTGames"
        and manifest.get("commercial_use") is False
        and isinstance(manifest.get("records"), list)
        and isinstance(manifest.get("anchors"), list)
        and bool(manifest.get("anchors"))
        and bool(re.fullmatch(r"[0-9a-f]{64}", str(manifest.get("source_sha256", ""))))
    )
    if not common:
        return False
    if manifest.get("tracking_architecture") == "DETECTION_ANCHORED_MASK_TRACKING":
        return True
    # Early v1 anchor-guided files predate the explicit architecture field. Accept
    # only the documented schema with stable role/object IDs and retained anchors.
    if manifest.get("schema_version") != "anchor-guided-player-tracking-v1":
        return False
    records = manifest["records"]
    return bool(records) and all(
        row.get("role") in {"NEAR_PLAYER", "FAR_PLAYER"}
        and row.get("object_id") in ({"NEAR_PLAYER": 1, "FAR_PLAYER": 2}[row.get("role")],)
        for row in records
    )


def player_motion_root(localappdata: str | Path | None = None) -> Path:
    local = Path(localappdata or os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    return local.resolve() / "PTTI-Dev" / "vision-v2-rtmpose"


def player_motion_job_root(job_id: str, localappdata: str | Path | None = None) -> Path:
    if not TRACKING_JOB_ID.fullmatch(job_id):
        raise ValueError("INVALID_PLAYER_MOTION_JOB_ID")
    return player_motion_root(localappdata) / "runs" / "jobs" / job_id


def motion_review_path(job_id: str, localappdata: str | Path | None = None) -> Path:
    if not TRACKING_JOB_ID.fullmatch(job_id):
        raise ValueError("INVALID_PLAYER_MOTION_JOB_ID")
    return player_motion_root(localappdata) / "validation-workbench" / f"{job_id}.jsonl"


def list_motion_exclusions(job_id: str, localappdata: str | Path | None = None) -> list[dict[str, Any]]:
    path = motion_review_path(job_id, localappdata)
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("action") == "EXCLUDE_FROM_MOTION_ANALYSIS":
            rows.append(row)
    return rows


def record_motion_exclusion(*, job_id: str, source_sha256: str, start_frame: int,
                            end_frame: int, role: str, localappdata: str | Path | None = None
                            ) -> dict[str, Any]:
    if (not TRACKING_JOB_ID.fullmatch(job_id) or not re.fullmatch(r"[0-9a-f]{64}", source_sha256)
            or start_frame < 0 or end_frame <= start_frame
            or role not in {"NEAR_PLAYER", "FAR_PLAYER"}):
        raise ValueError("INVALID_PLAYER_MOTION_EXCLUSION")
    row = {"review_id": uuid.uuid4().hex, "tracking_job_id": job_id,
           "source_sha256": source_sha256, "start_frame": start_frame,
           "end_frame": end_frame, "role": role,
           "action": "EXCLUDE_FROM_MOTION_ANALYSIS", "source": "USER_REVIEW",
           "created_at": datetime.now(timezone.utc).isoformat()}
    path = motion_review_path(job_id, localappdata)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return row


def tracking_job_path(job_id: str, localappdata: str | Path | None = None) -> Path:
    if not TRACKING_JOB_ID.fullmatch(job_id):
        raise ValueError("INVALID_PLAYER_MOTION_JOB_ID")
    local = Path(localappdata or os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    return local.resolve() / "PTTI-Dev" / "vision-v2-sam2" / "runs" / "closed-loop" / "jobs" / job_id / "tracking.json"


def load_tracking_evidence(job_id: str, localappdata: str | Path | None = None) -> tuple[dict[str, Any], Path]:
    path = tracking_job_path(job_id, localappdata)
    if not path.is_file():
        raise FileNotFoundError("TRACKING_RESULT_UNAVAILABLE")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("job_id") != job_id or not supports_pose_tracking_manifest(manifest):
        raise ValueError("TRACKING_EVIDENCE_NOT_POSE_ELIGIBLE")
    from backend.player_tracking_closed_loop import resolve_sample
    sample = resolve_sample(str(manifest.get("sample_id", "")), localappdata, verify_hash=True)
    if sample["clip_sha256"] != manifest.get("source_sha256"):
        raise ValueError("TRACKING_SOURCE_HASH_MISMATCH")
    return manifest, Path(sample["video_path"])


def atomic_pose_json(path: str | Path, value: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)


def pose_file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
