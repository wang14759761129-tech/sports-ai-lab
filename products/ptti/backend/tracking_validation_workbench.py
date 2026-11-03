"""Append-only human labels for isolated player-tracking QA windows."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_JOB_ID = re.compile(r"[0-9a-f]{32}\Z")
_ROLES = {"NEAR_PLAYER", "FAR_PLAYER"}
_VISIBILITY = {"VISIBLE", "PARTIAL", "OUT_OF_FRAME", "UNKNOWN"}
_IDENTITY = {"NEAR_PLAYER", "FAR_PLAYER", "UNCERTAIN"}
_QUALITY = {"GOOD", "BAD", "UNKNOWN"}


def workbench_root(localappdata: str | Path | None = None) -> Path:
    local = Path(localappdata or os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    return local.resolve() / "PTTI-Dev" / "vision-v2-sam2" / "validation-workbench"


def record_tracking_window_review(*, job_id: str, sample_id: str, source_sha256: str,
                                  start_frame: int, end_frame: int, role: str,
                                  visibility: str, identity: str, track_quality: str,
                                  localappdata: str | Path | None = None) -> dict[str, Any]:
    if (not _JOB_ID.fullmatch(job_id) or role not in _ROLES or visibility not in _VISIBILITY
            or identity not in _IDENTITY or track_quality not in _QUALITY
            or start_frame < 0 or end_frame <= start_frame
            or not re.fullmatch(r"[0-9a-f]{64}", source_sha256)):
        raise ValueError("INVALID_TRACKING_VALIDATION_REVIEW")
    row = {
        "review_id": uuid.uuid4().hex,
        "job_id": job_id,
        "sample_id": sample_id,
        "source_sha256": source_sha256,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "role": role,
        "visibility": visibility,
        "identity": identity,
        "track_quality": track_quality,
        "source": "USER_REVIEW",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    root = workbench_root(localappdata)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "reviews.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def list_tracking_window_reviews(localappdata: str | Path | None = None) -> list[dict[str, Any]]:
    path = workbench_root(localappdata) / "reviews.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
