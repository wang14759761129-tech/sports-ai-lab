"""Small, evidence-preserving contracts for the hybrid scene detector.

This module deliberately has no MMDetection dependency. The isolated worker
converts RTMDet output into these contracts; the desktop/backend environment
can validate and review candidates without importing the model runtime.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Iterable, Mapping, Sequence


RTMDET_TINY_MODEL = "rtmdet_tiny_8xb32-300e_coco"
COCO_PERSON_CLASS_ID = 0


@dataclass(frozen=True)
class ScoreboardModule:
    status: str = "NOT_IMPLEMENTED"
    blocks_scene_gate: bool = False
    message: str = "Scoreboard ROI discovery and OCR are separate future work."


SCOREBOARD_MODULE = ScoreboardModule()


@dataclass(frozen=True)
class PersonDetectionCandidate:
    candidate_id: str
    frame: int
    timestamp_ms: int
    bbox: tuple[float, float, float, float]
    detector_score: float
    detector: str = "RTMDet"
    model: str = RTMDET_TINY_MODEL
    class_id: int = COCO_PERSON_CLASS_ID
    label: str = "person"
    role: str = "UNKNOWN"
    role_candidate: str = "UNKNOWN"
    role_evidence: tuple[str, ...] = ()
    status: str = "SUGGESTED"

    def __post_init__(self):
        if not self.candidate_id or self.frame < 0 or self.timestamp_ms < 0:
            raise ValueError("candidate identity and non-negative source position are required")
        x0, y0, x1, y1 = self.bbox
        if not all(isfinite(v) for v in self.bbox) or x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0:
            raise ValueError("bbox must contain finite, positive xyxy coordinates")
        if not isfinite(self.detector_score) or not 0 <= self.detector_score <= 1:
            raise ValueError("detector_score must be in [0, 1]")
        if self.class_id != COCO_PERSON_CLASS_ID or self.label != "person":
            raise ValueError("only the COCO person class is accepted")

    def to_dict(self) -> dict:
        row = asdict(self)
        row["bbox"] = list(self.bbox)
        row["role_evidence"] = list(self.role_evidence)
        return row


class RTMDetPredictionAdapter:
    """Convert worker-neutral predictions into TTI person candidates."""

    def __init__(self, score_threshold: float = 0.25):
        if not isfinite(score_threshold) or not 0 <= score_threshold <= 1:
            raise ValueError("score_threshold must be in [0, 1]")
        self.score_threshold = float(score_threshold)

    def adapt(self, *, frame: int, timestamp_ms: int, predictions: Iterable[Mapping]) -> list[PersonDetectionCandidate]:
        result = []
        for prediction in predictions:
            class_id = int(prediction.get("class_id", -1))
            score = float(prediction.get("score", float("nan")))
            if class_id != COCO_PERSON_CLASS_ID or not isfinite(score) or score < self.score_threshold:
                continue
            bbox = tuple(float(v) for v in prediction.get("bbox", ()))
            result.append(PersonDetectionCandidate(
                candidate_id=f"rtmdet-f{frame:06d}-d{len(result):02d}",
                frame=frame,
                timestamp_ms=timestamp_ms,
                bbox=bbox,
                detector_score=score,
            ))
        return result


class PlayerRoleResolver:
    """Produce conservative spatial role *candidates*, never player identity."""

    def __init__(self, *, referee_center_fraction: float = 0.24):
        if not 0 < referee_center_fraction < 1:
            raise ValueError("referee_center_fraction must be between 0 and 1")
        self.referee_center_fraction = referee_center_fraction

    def resolve(self, table_bbox: Sequence[float], people: Iterable[Mapping], *, image_size: Sequence[int]) -> list[dict]:
        tx0, ty0, tx1, ty1 = map(float, table_bbox)
        width, height = map(float, image_size)
        if tx1 <= tx0 or ty1 <= ty0 or width <= 0 or height <= 0:
            raise ValueError("table_bbox and image_size must be positive")
        rows = [dict(person) for person in people]
        center_x = (tx0 + tx1) / 2
        center_half_width = (tx1 - tx0) * self.referee_center_fraction / 2
        for person in rows:
            x0, y0, x1, y1 = map(float, person["bbox"])
            person_center_x = (x0 + x1) / 2
            foot_y = y1
            person["role"] = "UNKNOWN"
            person["role_candidate"] = "UNKNOWN"
            person["role_evidence"] = []
            person["spatial_hint"] = "UNKNOWN"
            person["role_basis"] = {
                "person_center_x_relative_to_table_center": round((person_center_x - center_x) / max(1.0, tx1 - tx0), 4),
                "footpoint_y_normalized": round(foot_y / height, 4),
                "box_height_normalized": round((y1 - y0) / height, 4),
            }

        if len(rows) > 2:
            for person in rows:
                person["role_evidence"] = ["AMBIGUOUS_PERSON_COUNT"]
            return rows

        sides: dict[str, list[dict]] = {"LEFT": [], "RIGHT": []}
        for person in rows:
            x0, _y0, x1, y1 = map(float, person["bbox"])
            cx = (x0 + x1) / 2
            if abs(cx - center_x) <= center_half_width:
                person["spatial_hint"] = "REFEREE_CANDIDATE"
                person["role_candidate"] = "REFEREE"
                person["role_evidence"] = ["PERSON_CENTER_NEAR_TABLE_CENTER", "TABLE_RELATIVE_POSITION"]
                continue
            side = "LEFT" if cx < center_x else "RIGHT"
            sides[side].append(person)
            person["spatial_hint"] = f"PLAYER_{side}_CANDIDATE"
            person["role_evidence"] = [f"PERSON_CENTER_{side}_OF_TABLE", "TABLE_RELATIVE_POSITION"]

        # A referee or another person in the frame makes side assignment ambiguous.
        if len(rows) != 2 or len(sides["LEFT"]) != 1 or len(sides["RIGHT"]) != 1:
            return rows

        far = min(rows, key=lambda person: float(person["bbox"][3]))
        near = max(rows, key=lambda person: float(person["bbox"][3]))
        if far is near:
            return rows
        far["role_candidate"] = "FAR_PLAYER"
        far["role_evidence"].append("HIGHER_IMAGE_FOOTPOINT")
        near["role_candidate"] = "NEAR_PLAYER"
        near["role_evidence"].append("LOWER_IMAGE_FOOTPOINT")
        return rows


def review_priority_v2(people: Iterable[Mapping]) -> dict:
    """Flag incomplete/ambiguous person proposals for human review."""
    rows = list(people)
    roles = {row.get("role_candidate", "UNKNOWN") for row in rows}
    reasons = []
    if "NEAR_PLAYER" not in roles:
        reasons.append("NEAR_PLAYER_MISSING")
    if "FAR_PLAYER" not in roles:
        reasons.append("FAR_PLAYER_MISSING")
    if any(row.get("role_candidate") in {"UNKNOWN", "REFEREE"} or
           "AMBIGUOUS_PERSON_COUNT" in row.get("role_evidence", []) for row in rows):
        reasons.append("PERSON_ROLE_AMBIGUOUS")
    if len(rows) > 2:
        reasons.append("TOO_MANY_PERSON_CANDIDATES")
    return {
        "priority": "HIGH" if reasons else "LOW",
        "status": "REVIEW_REQUIRED" if reasons else "LIKELY_OK",
        "reasons": reasons,
    }


def to_pose_adapter_input(person: PersonDetectionCandidate) -> dict:
    """Create only the crop input contract; this does not run or imply pose."""
    return {
        "frame": person.frame,
        "timestamp_ms": person.timestamp_ms,
        "person_id": person.candidate_id,
        "bbox": list(person.bbox),
        "status": "INPUT_READY_NOT_INFERRED",
    }
