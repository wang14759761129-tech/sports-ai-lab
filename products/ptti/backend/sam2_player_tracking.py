"""Read-only access to the isolated SAM 2 player-tracking QA run.

The research video and all generated artifacts live under PTTI-Dev. This
module never reads or writes a match database and never imports SAM 2.
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


RUN_ID = "multi-match-final/game_4-t30"
RUN_STATUS = "REAL_GPU_PROPAGATION_COMPLETE"
ALLOWED_VIDEO_ASSETS = {
    "player_tracking_overlay.mp4",
    "player_tracking_near.mp4",
    "player_tracking_far.mp4",
    "player_tracking_original.mp4",
}
_REVIEW_LOCK = threading.RLock()


def player_tracking_root(localappdata: str | Path | None = None) -> Path:
    local = Path(localappdata or Path.home() / "AppData/Local").resolve()
    return local / "PTTI-Dev" / "vision-v2-sam2" / "runs" / RUN_ID


def player_tracking_snapshot(root: str | Path) -> dict:
    root = Path(root).resolve()
    manifest_path = root / "tracking.json"
    if not manifest_path.is_file():
        return {
            "status": "NOT_RUN",
            "frames": [],
            "message": "尚无已完成的真实视频追踪结果。",
            "production_database": "NOT_ACCESSED",
        }
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != RUN_STATUS:
        raise ValueError("PLAYER_TRACKING_STATUS_INVALID")
    if manifest.get("dataset") != "Extended OpenTTGames" or manifest.get("rights") != "CC BY-NC-SA 4.0 research/non-commercial":
        raise ValueError("PLAYER_TRACKING_PROVENANCE_INVALID")
    if manifest.get("frames") != len(manifest.get("records", [])) // 2:
        raise ValueError("PLAYER_TRACKING_FRAME_COUNT_INVALID")

    frames = sorted({int(row["frame"]) for row in manifest["records"]})
    if len(frames) != manifest["frames"] or frames != list(range(manifest["frames"])):
        raise ValueError("PLAYER_TRACKING_TIMELINE_INVALID")

    available_assets = []
    for name in sorted(ALLOWED_VIDEO_ASSETS):
        path = root / name
        if path.is_file() and path.stat().st_size > 0:
            available_assets.append({"name": name, "bytes": path.stat().st_size})

    sample_indices = sorted(set([0, 59, 119, 179, 239, manifest["frames"] - 1]))
    samples = []
    for frame in sample_indices:
        by_role = [row for row in manifest["records"] if int(row["frame"]) == frame]
        samples.append({
            "frame": frame,
            "timestamp_ms": by_role[0]["timestamp_ms"] if by_role else None,
            "statuses": {row["role"]: row["tracking_status"] for row in by_role},
            "source": {row["role"]: row["source"] for row in by_role},
        })

    review_path = root / "tracking_reviews.json"
    try:
        reviews = json.loads(review_path.read_text(encoding="utf-8")) if review_path.is_file() else []
    except (OSError, ValueError):
        reviews = []
    multi_match_path = root.parent / "cross_match_validation.json"
    try:
        multi_match = json.loads(multi_match_path.read_text(encoding="utf-8")) if multi_match_path.is_file() else None
    except (OSError, ValueError):
        multi_match = {"status": "UNAVAILABLE"}
    if multi_match and multi_match.get("tracker_config_sha256") != manifest.get("tracker_config_sha256"):
        raise ValueError("PLAYER_TRACKING_CROSS_MATCH_CONFIG_MISMATCH")
    if multi_match and (
        multi_match.get("dataset") != "Extended OpenTTGames"
        or multi_match.get("rights") != "CC BY-NC-SA 4.0 research/non-commercial"
        or multi_match.get("commercial_use") is not False
        or not isinstance(multi_match.get("videos"), list)
    ):
        raise ValueError("PLAYER_TRACKING_CROSS_MATCH_PROVENANCE_INVALID")
    return {
        "status": manifest["status"],
        "run_id": RUN_ID,
        "dataset": manifest["dataset"],
        "rights": manifest["rights"],
        "commercial_use": False,
        "source_sha256": manifest["source_sha256"],
        "source_bytes": manifest["source_bytes"],
        "duration_seconds": manifest["duration_seconds"],
        "source_fps": manifest["source_fps"],
        "sample_fps": manifest["sample_fps"],
        "frames": manifest["frames"],
        "seed_assignment": manifest["seed_assignment"],
        "seeds": [{key: value for key, value in seed.items() if key != "bbox"} for seed in manifest["seeds"]],
        "role_summary": manifest["role_summary"],
        "identity_uncertain_events": manifest["identity_uncertain_events"],
        "scene_cut_candidates": manifest["scene_cut_candidates"],
        "scene_cut_real_video_verified": manifest["scene_cut_real_video_verified"],
        "sam2": manifest["sam2"],
        "runtime": manifest["runtime"],
        "available_assets": available_assets,
        "samples": samples,
        "multi_match_validation": multi_match,
        "reviews": reviews,
        "review_status": "USER_REVIEWED" if any(item.get("action") == "CONFIRM_ROLE_ASSIGNMENT" for item in reviews) else "REVIEW_REQUIRED",
        "limitations": [
            "当前为 10 秒片段的研究验证；不代表整场比赛级稳定性。",
            "起始角色由实验操作员预置；尚未在桌面内完成追踪前的用户种子确认。",
            "Extended OpenTTGames 仅限 CC BY-NC-SA 4.0 研究 / 非商业用途。",
            "真实镜头切换后的 SAM2 重置尚未验证。",
            "SAM2 输出是人物分割候选，不是球员身份事实。",
        ],
        "production_database": "NOT_ACCESSED",
    }


def player_tracking_video_asset(root: str | Path, name: str) -> Path:
    if name not in ALLOWED_VIDEO_ASSETS:
        raise ValueError("INVALID_PLAYER_TRACKING_ASSET")
    base = Path(root).resolve()
    path = (base / name).resolve()
    if not path.is_relative_to(base):
        raise ValueError("PLAYER_TRACKING_ASSET_OUTSIDE_RUN")
    return path


def player_tracking_frame_asset(root: str | Path, frame: int, view: str) -> Path:
    if not isinstance(frame, int) or frame < 0 or view not in {"source", "overlay"}:
        raise ValueError("INVALID_PLAYER_TRACKING_FRAME")
    base = Path(root).resolve()
    folder = "frames" if view == "source" else "overlay-frames"
    path = (base / folder / f"{frame + 1:05d}.jpg").resolve()
    if not path.is_relative_to(base):
        raise ValueError("PLAYER_TRACKING_FRAME_OUTSIDE_RUN")
    return path


def record_player_tracking_review(root: str | Path, *, action: str, note: str = "") -> dict:
    if action not in {"CONFIRM_ROLE_ASSIGNMENT", "FLAG_ROLE_ASSIGNMENT"}:
        raise ValueError("INVALID_PLAYER_TRACKING_REVIEW_ACTION")
    note = str(note).strip()
    if len(note) > 500:
        raise ValueError("PLAYER_TRACKING_REVIEW_NOTE_TOO_LONG")
    root = Path(root).resolve()
    snapshot = player_tracking_snapshot(root)
    if snapshot["status"] != RUN_STATUS:
        raise ValueError("PLAYER_TRACKING_NOT_AVAILABLE")
    path = root / "tracking_reviews.json"
    with _REVIEW_LOCK:
        reviews = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
        review = {
            "review_id": str(uuid.uuid4()),
            "action": action,
            "note": note,
            "source": "USER_UI",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "run_id": RUN_ID,
            "source_sha256": snapshot["source_sha256"],
        }
        reviews.append(review)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(reviews, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    return {"status": "SAVED", "raw_preserved": True, "review": review}
