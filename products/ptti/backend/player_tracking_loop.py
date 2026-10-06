"""Evidence-first primitives for the experimental SAM2 player tracking loop.

This module owns seed validation, track-health labels, and conservative
re-association scoring. It has no model, database, filesystem, or GPU
dependency so the same interface is used by the worker and tests.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from math import hypot, log
from dataclasses import dataclass, field
from typing import Any


ROLES = ("NEAR_PLAYER", "FAR_PLAYER")
HEALTH = {"HEALTHY", "SUSPECT", "LOST", "OUT_OF_FRAME", "IDENTITY_UNCERTAIN"}


@dataclass
class RecoveryEpisodeGate:
    """Throttle rediscovery and review during one continuous unhealthy episode."""

    retry_interval: int = 30
    review_interval: int = 90
    healthy_reset_frames: int = 3
    last_attempt: dict[str, int] = field(default_factory=dict)
    healthy_streak: dict[str, int] = field(default_factory=dict)
    review_requested_at: dict[str, int] = field(default_factory=dict)
    loss_reported: set[str] = field(default_factory=set)

    def observe(self, role: str, status: str, *, frame: int) -> bool:
        if status == "HEALTHY":
            streak = self.healthy_streak.get(role, 0) + 1
            self.healthy_streak[role] = streak
            if streak >= self.healthy_reset_frames:
                self.last_attempt.pop(role, None)
                self.healthy_streak.pop(role, None)
                self.review_requested_at.pop(role, None)
                self.loss_reported.discard(role)
                return True
            return False
        self.healthy_streak.pop(role, None)
        return False

    def due_roles(self, health_by_role: dict[str, str], *, frame: int) -> list[str]:
        abnormal = {"SUSPECT", "IDENTITY_UNCERTAIN", "LOST", "OUT_OF_FRAME"}
        return [role for role, status in health_by_role.items()
                if status in abnormal and
                (role not in self.last_attempt or frame - self.last_attempt[role] >= self.retry_interval)]

    def mark_attempts(self, roles: list[str], *, frame: int) -> None:
        for role in roles:
            self.last_attempt[role] = frame

    def may_request_review(self, role: str, *, frame: int) -> bool:
        previous = self.review_requested_at.get(role)
        return previous is None or frame - previous >= self.review_interval

    def mark_review_requested(self, role: str, *, frame: int) -> None:
        self.review_requested_at[role] = frame

    def mark_loss_reported(self, role: str) -> bool:
        if role in self.loss_reported:
            return False
        self.loss_reported.add(role)
        return True

    def is_episode_stable(self, role: str) -> bool:
        return self.healthy_streak.get(role, 0) >= self.healthy_reset_frames

    def reset_for_scene_change(self) -> None:
        self.last_attempt.clear()
        self.healthy_streak.clear()
        self.review_requested_at.clear()
        self.loss_reported.clear()


def candidate_identifier(choice: dict[str, Any] | None) -> str | None:
    """Safely return a reassociation candidate id when one was selected."""
    if not isinstance(choice, dict):
        return None
    candidate = choice.get("candidate")
    if not isinstance(candidate, dict):
        return None
    value = candidate.get("candidate_id")
    return str(value) if value is not None else None


def tracking_status_for(*, frame_index: int, seed_frame: int, mask_area: int,
                        health_status: str, direction: str) -> str:
    if frame_index == seed_frame:
        return "SEEDED"
    if direction == "REVERSE":
        return "TRACKED_REVERSE" if mask_area > 0 else "HEALTH_NOT_ASSESSED_REVERSE"
    if health_status in {"SUSPECT", "IDENTITY_UNCERTAIN", "LOST", "OUT_OF_FRAME"}:
        return health_status
    return "TRACKED" if mask_area > 0 else "LOST"


def _area(box: list[float] | tuple[float, ...] | None) -> float:
    if not box or len(box) != 4:
        return 0.0
    return max(0.0, float(box[2]) - float(box[0])) * max(0.0, float(box[3]) - float(box[1]))


def _center(box: list[float] | tuple[float, ...]) -> tuple[float, float]:
    return ((float(box[0]) + float(box[2])) / 2, (float(box[1]) + float(box[3])) / 2)


def box_iou(a: list[float] | tuple[float, ...] | None,
            b: list[float] | tuple[float, ...] | None) -> float:
    if not a or not b:
        return 0.0
    inter = max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    union = _area(a) + _area(b) - inter
    return inter / union if union > 0 else 0.0


def _edge_side(box, width: int, height: int, margin: float = 0.04) -> str | None:
    if not box:
        return None
    x0, y0, x1, y1 = map(float, box)
    distances = {"LEFT": x0 / width, "RIGHT": (width - x1) / width,
                 "TOP": y0 / height, "BOTTOM": (height - y1) / height}
    side = min(distances, key=distances.get)
    return side if distances[side] <= margin else None


def classify_track_health(*, bbox: list[float] | None, mask_area: int,
                          frame_size: tuple[int, int], previous_bbox: list[float] | None = None,
                          previous_area: int | None = None, other_bbox: list[float] | None = None,
                          previous_previous_bbox: list[float] | None = None) -> dict[str, Any]:
    """Classify an observation; absent masks near an outward-moving edge are not called model loss."""
    width, height = frame_size
    frame_area = max(1, width * height)
    area_ratio = max(0, int(mask_area)) / frame_area
    if not bbox or mask_area <= 0:
        side = _edge_side(previous_bbox, width, height)
        moving_out = False
        if side and previous_previous_bbox:
            old_x, old_y = _center(previous_previous_bbox)
            last_x, last_y = _center(previous_bbox)
            outward = {"LEFT": last_x < old_x, "RIGHT": last_x > old_x,
                       "TOP": last_y < old_y, "BOTTOM": last_y > old_y}
            moving_out = outward[side]
        if side and moving_out:
            return {"status": "OUT_OF_FRAME", "reason": "MASK_ABSENT_AFTER_OUTWARD_EDGE_MOTION",
                    "edge": side, "mask_area_ratio": area_ratio}
        return {"status": "LOST", "reason": "MASK_ABSENT", "edge": side,
                "mask_area_ratio": area_ratio}

    if area_ratio < 0.002 or area_ratio > 0.45:
        return {"status": "SUSPECT", "reason": "MASK_AREA_OUTSIDE_REVIEW_RANGE",
                "mask_area_ratio": area_ratio}
    if other_bbox and box_iou(bbox, other_bbox) >= 0.35:
        return {"status": "IDENTITY_UNCERTAIN", "reason": "PLAYER_BOX_OVERLAP",
                "mask_area_ratio": area_ratio}
    if previous_bbox:
        old_x, old_y = _center(previous_bbox)
        new_x, new_y = _center(bbox)
        if hypot(new_x - old_x, new_y - old_y) > hypot(width, height) * 0.18:
            return {"status": "SUSPECT", "reason": "SUDDEN_POSITION_JUMP",
                    "mask_area_ratio": area_ratio}
    if previous_area and mask_area > 0:
        ratio = max(mask_area, previous_area) / max(1, min(mask_area, previous_area))
        if ratio > 3.0:
            return {"status": "SUSPECT", "reason": "SUDDEN_MASK_AREA_CHANGE",
                    "mask_area_ratio": area_ratio}
    return {"status": "HEALTHY", "reason": "MASK_AND_GEOMETRY_OK",
            "mask_area_ratio": area_ratio}


def reassociation_score(*, role: str, candidate_bbox: list[float], previous_bbox: list[float] | None,
                        predicted_bbox: list[float] | None, seed_bbox: list[float],
                        frame_size: tuple[int, int], candidate_appearance: float | None = None,
                        seed_appearance: float | None = None) -> dict[str, Any]:
    """Rank a detector box using multiple weak signals; never changes object identity."""
    if role not in ROLES:
        raise ValueError("INVALID_PLAYER_ROLE")
    width, height = frame_size
    reference = predicted_bbox or previous_bbox or seed_bbox
    diagonal = max(1.0, hypot(width, height))
    ref_x, ref_y = _center(reference)
    cand_x, cand_y = _center(candidate_bbox)
    displacement = hypot(cand_x - ref_x, cand_y - ref_y) / diagonal
    proximity = max(0.0, 1.0 - displacement / 0.42)
    overlap = box_iou(reference, candidate_bbox)
    size_similarity = min(_area(reference), _area(candidate_bbox)) / max(1.0, _area(reference), _area(candidate_bbox))
    ref_w = max(1.0, float(reference[2]) - float(reference[0]))
    ref_h = max(1.0, float(reference[3]) - float(reference[1]))
    cand_w = max(1.0, float(candidate_bbox[2]) - float(candidate_bbox[0]))
    cand_h = max(1.0, float(candidate_bbox[3]) - float(candidate_bbox[1]))
    aspect_similarity = max(0.0, 1.0 - abs(log((cand_w / cand_h) / (ref_w / ref_h))) / 1.8)
    side_reference = "LEFT" if ref_x < width / 2 else "RIGHT"
    side_candidate = "LEFT" if cand_x < width / 2 else "RIGHT"
    side_consistency = 1.0 if side_reference == side_candidate else 0.0
    edge_ref = _edge_side(reference, width, height)
    edge_candidate = _edge_side(candidate_bbox, width, height)
    edge_return = 1.0 if edge_ref and edge_candidate == edge_ref else 0.0
    appearance = None
    if candidate_appearance is not None and seed_appearance is not None:
        appearance = max(0.0, min(1.0, 1.0 - abs(float(candidate_appearance) - float(seed_appearance))))

    # Appearance is a supporting cue only; geometry and persistence remain explicit.
    if appearance is None:
        score = 0.36 * overlap + 0.27 * proximity + 0.18 * size_similarity + 0.12 * aspect_similarity + 0.07 * side_consistency
    else:
        score = 0.30 * overlap + 0.23 * proximity + 0.16 * size_similarity + 0.10 * aspect_similarity + 0.06 * side_consistency + 0.15 * appearance
    if edge_return:
        score = min(1.0, score + 0.10)
    return {"role": role, "score": round(score, 4), "evidence": {
        "bbox_iou": round(overlap, 4), "predicted_center_proximity": round(proximity, 4),
        "size_similarity": round(size_similarity, 4), "aspect_similarity": round(aspect_similarity, 4),
        "same_image_half": bool(side_consistency), "same_edge_return": bool(edge_return),
        "appearance_similarity": None if appearance is None else round(appearance, 4),
    }}


def choose_reassociation(*, role: str, candidates: list[dict], previous_bbox: list[float] | None,
                         predicted_bbox: list[float] | None, seed_bbox: list[float],
                         frame_size: tuple[int, int], minimum_score: float = 0.72,
                         minimum_margin: float = 0.14) -> dict[str, Any]:
    scored = [dict(candidate, association=reassociation_score(
        role=role, candidate_bbox=candidate["bbox"], previous_bbox=previous_bbox,
        predicted_bbox=predicted_bbox, seed_bbox=seed_bbox, frame_size=frame_size,
        candidate_appearance=candidate.get("appearance_signature"),
        seed_appearance=candidate.get("seed_appearance_signature"))) for candidate in candidates]
    scored.sort(key=lambda row: row["association"]["score"], reverse=True)
    if not scored:
        return {"decision": "NO_CANDIDATE", "candidate": None, "ranked": []}

    # Human review should not invite a choice among unrelated detections. Keep a
    # box only when it overlaps the track or has a plausible combination of
    # predicted proximity, scale, and side/edge continuity.
    reviewable = []
    rejected = []
    for row in scored:
        evidence = row["association"]["evidence"]
        has_geometry = evidence["bbox_iou"] >= 0.02
        has_motion_and_scale = (
            evidence["predicted_center_proximity"] >= 0.35
            and evidence["size_similarity"] >= 0.15
            and (evidence["same_image_half"] or evidence["same_edge_return"])
        )
        (reviewable if has_geometry or has_motion_and_scale else rejected).append(row)
    if not reviewable:
        return {"decision": "NO_CANDIDATE", "candidate": None, "ranked": [],
                "rejected_candidates": rejected, "reason": "NO_GEOMETRICALLY_PLAUSIBLE_ASSOCIATION"}

    best = reviewable[0]
    margin = best["association"]["score"] - (reviewable[1]["association"]["score"] if len(reviewable) > 1 else 0.0)
    if best["association"]["score"] >= minimum_score and margin >= minimum_margin:
        return {"decision": "AUTO_REACQUIRED", "candidate": best, "margin": round(margin, 4),
                "ranked": reviewable, "rejected_candidates": rejected}
    return {"decision": "REQUIRES_USER_CONFIRMATION", "candidate": None,
            "margin": round(margin, 4), "ranked": reviewable, "rejected_candidates": rejected}


def confirm_seed(*, sample: dict, raw_detections: list[dict], near_candidate_id: str,
                 far_candidate_id: str, frame_index: int, user_confirmed: bool,
                 near_bbox: list[float] | None = None, far_bbox: list[float] | None = None,
                 athlete_mapping: dict[str, str] | None = None) -> dict[str, Any]:
    """Create an immutable user-confirmed prompt record while preserving detector output."""
    if user_confirmed is not True or near_candidate_id == far_candidate_id:
        raise ValueError("TWO_DISTINCT_USER_CONFIRMED_SEEDS_REQUIRED")
    by_id = {str(item["candidate_id"]): item for item in raw_detections}
    if near_candidate_id not in by_id or far_candidate_id not in by_id:
        raise ValueError("SEED_CANDIDATE_NOT_FOUND")
    if frame_index < 0 or frame_index >= int(sample["frames"]):
        raise ValueError("SEED_FRAME_OUT_OF_RANGE")
    width, height = sample["width"], sample["height"]

    def seed_for(role, object_id, candidate_id, override):
        raw = by_id[candidate_id]
        bbox = list(map(float, override if override is not None else raw["bbox"]))
        if len(bbox) != 4 or bbox[0] < 0 or bbox[1] < 0 or bbox[2] > width or bbox[3] > height or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            raise ValueError("INVALID_SEED_BBOX")
        return {"object_id": object_id, "role": role, "candidate_id": candidate_id,
                "bbox": bbox, "detector_score": raw.get("detector_score", raw.get("score")),
                "detector_source": raw.get("detector", "RT-DETR R18"),
                "user_bbox_adjusted": override is not None,
                "source": "USER_CONFIRMED_SEED"}

    return {
        "schema_version": "player-seed-v1", "sample_id": sample["sample_id"],
        "dataset": "Extended OpenTTGames", "rights": "CC BY-NC-SA 4.0 research/non-commercial",
        "commercial_use": False, "clip_sha256": sample["clip_sha256"],
        "seed_frame": frame_index, "timestamp_ms": round((sample["start_seconds"] + frame_index / sample["sample_fps"]) * 1000),
        "raw_detections": deepcopy(raw_detections),
        "selected_seeds": [seed_for("NEAR_PLAYER", 1, near_candidate_id, near_bbox),
                           seed_for("FAR_PLAYER", 2, far_candidate_id, far_bbox)],
        "user_confirmation": {"confirmed": True, "source": "USER_UI",
                              "timestamp": datetime.now(timezone.utc).isoformat()},
        "athlete_mapping": athlete_mapping or {"NEAR_PLAYER": None, "FAR_PLAYER": None},
    }
