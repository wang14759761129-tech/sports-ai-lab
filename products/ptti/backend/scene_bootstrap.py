"""Evidence records and user review handling for scene bootstrap candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


MODEL_ID = "IDEA-Research/grounding-dino-base"
MODEL_REVISION = "a062f8edaf7f3aa52714a8f80cb8db7de1e5e170"
MODEL_SHA256 = "5548f844c928c4b6f411fa8cbcc2bfa8dbbba437cb1d513975519f93c2a9ed21"
MODEL_BYTES = 933400872
PROMPT_PROFILES = {
    "bootstrap-a": "table tennis table. person. referee. scoreboard.",
    "bootstrap-b": "table tennis table. table tennis player. referee. table tennis scoreboard.",
}
REVIEW_ROLES = ("NEAR_PLAYER", "FAR_PLAYER", "PLAYER_A", "PLAYER_B", "REFEREE", "OTHER", "UNKNOWN")
SCENE_REVIEW_ROLES = ("NEAR_PLAYER", "FAR_PLAYER", "REFEREE", "OTHER", "UNKNOWN")


@dataclass(frozen=True)
class DetectionCandidate:
    candidate_id: str
    frame: int
    timestamp_ms: int
    label: str
    bbox: tuple[float, float, float, float]
    detector_score: float
    prompt: str
    model: str = MODEL_ID
    source: str = "extended_openttgames"
    role: str = "UNKNOWN"
    spatial_hint: str = "UNKNOWN"
    status: str = "SUGGESTED"

    def __post_init__(self):
        x0, y0, x1, y1 = self.bbox
        if min(x0, y0) < 0 or x1 <= x0 or y1 <= y0:
            raise ValueError("bbox must be positive xyxy coordinates")
        if not 0 <= self.detector_score <= 1:
            raise ValueError("detector_score must be in [0, 1]")
        if not self.prompt.strip():
            raise ValueError("prompt is required for provenance")

    def to_dict(self):
        return asdict(self)


def spatial_role(label: str, bbox, table_bbox=None) -> tuple[str, str]:
    """Provide cautious spatial candidates; never force identities."""
    phrase = label.casefold()
    if "scoreboard" in phrase or "score board" in phrase or "score graphic" in phrase:
        return "UNKNOWN", "SCOREBOARD_CANDIDATE"
    if "referee" in phrase or "umpire" in phrase:
        return "REFEREE", "REFEREE_CANDIDATE"
    if "table tennis table" in phrase or phrase == "table":
        return "UNKNOWN", "TABLE_CANDIDATE"
    if "person" not in phrase and "player" not in phrase and "athlete" not in phrase:
        return "UNKNOWN", "UNKNOWN"
    if table_bbox is None:
        return "UNKNOWN", "HUMAN_CANDIDATE"
    x0, y0, x1, y1 = bbox
    tx0, ty0, tx1, ty1 = table_bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    table_cx = (tx0 + tx1) / 2
    table_w = max(1.0, tx1 - tx0)
    # For this static side-view sample, court-side players lie on opposite
    # horizontal sides of the net/table center. A person near the center above
    # the table (e.g. an umpire) must remain a non-identity candidate.
    if abs(cx - table_cx) <= table_w * 0.12 and cy < ty0:
        return "UNKNOWN", "REFEREE_OTHER_CANDIDATE"
    if cx < table_cx - table_w * 0.12:
        return "UNKNOWN", "PLAYER_LEFT_CANDIDATE"
    if cx > table_cx + table_w * 0.12:
        return "UNKNOWN", "PLAYER_RIGHT_CANDIDATE"
    return "UNKNOWN", "CENTRAL_PERSON_CANDIDATE"


def attach_roles(detections: Iterable[dict], table_bbox=None) -> list[dict]:
    result = []
    for detection in detections:
        role, hint = spatial_role(detection["label"], detection["bbox"], table_bbox)
        result.append({**detection, "role": role, "spatial_hint": hint})
    return result


def table_box_quality(predicted_bbox, ground_truth_bbox, *, image_size) -> dict:
    """Compare a coarse predicted table box with a manually reviewed box."""
    px0, py0, px1, py1 = map(float, predicted_bbox)
    gx0, gy0, gx1, gy1 = map(float, ground_truth_bbox)
    width, height = map(float, image_size)
    if px1 <= px0 or py1 <= py0 or gx1 <= gx0 or gy1 <= gy0 or width <= 0 or height <= 0:
        raise ValueError("boxes and image_size must have positive dimensions")
    ix = max(0.0, min(px1, gx1) - max(px0, gx0))
    iy = max(0.0, min(py1, gy1) - max(py0, gy0))
    intersection = ix * iy
    predicted_area = (px1 - px0) * (py1 - py0)
    truth_area = (gx1 - gx0) * (gy1 - gy0)
    union = predicted_area + truth_area - intersection
    pcx, pcy = (px0 + px1) / 2, (py0 + py1) / 2
    gcx, gcy = (gx0 + gx1) / 2, (gy0 + gy1) / 2
    return {
        "iou": intersection / union if union else 0.0,
        "width_overshoot_fraction": max(0.0, (px1 - px0) / (gx1 - gx0) - 1.0),
        "height_overshoot_fraction": max(0.0, (py1 - py0) / (gy1 - gy0) - 1.0),
        "center_deviation_px": ((pcx - gcx) ** 2 + (pcy - gcy) ** 2) ** 0.5,
        "center_deviation_normalized": (((pcx - gcx) ** 2 + (pcy - gcy) ** 2) ** 0.5) / (width ** 2 + height ** 2) ** 0.5,
    }


def frame_review_priority(detections: Iterable[dict], *, image_size, low_score_threshold=0.35) -> dict:
    """Rank frame review workload; LIKELY_OK is advisory and never verified."""
    width, height = image_size
    rows = [d for d in detections if not d.get("visualization_suppressed") and
            d.get("user_correction", {}).get("status") != "REJECTED"]
    tables = [d for d in rows if "table" in d.get("label", "").casefold()]
    people = [d for d in rows if "person" in d.get("label", "").casefold() or "player" in d.get("label", "").casefold()]
    side_hints = {d.get("spatial_hint") for d in people}
    reasons = []
    advisory_reasons = []
    if len(tables) == 0:
        reasons.append("TABLE_MISSING")
    elif len(tables) > 1:
        reasons.append("MULTIPLE_TABLE_CANDIDATES")
    if not {"PLAYER_LEFT_CANDIDATE", "PLAYER_RIGHT_CANDIDATE"}.issubset(side_hints):
        reasons.append("PLAYER_SIDE_MISSING")
    if any(float(d.get("detector_score", 1.0)) < low_score_threshold for d in tables + people):
        reasons.append("LOW_DETECTOR_SCORE")
    if any(d.get("spatial_hint") in {"CENTRAL_PERSON_CANDIDATE", "REFEREE_OTHER_CANDIDATE"} and
           d.get("role") not in {"REFEREE", "OTHER"} for d in people):
        advisory_reasons.append("PERSON_ROLE_AMBIGUOUS")
    for d in tables + people:
        box = d.get("bbox", (0, 0, width, height))
        if len(box) != 4 or box[0] < 0 or box[1] < 0 or box[2] > width or box[3] > height or box[2] <= box[0] or box[3] <= box[1]:
            reasons.append("GEOMETRY_CONFLICT")
            break
    priority = "HIGH" if reasons else ("MEDIUM" if advisory_reasons else "LOW")
    all_reasons = list(dict.fromkeys(reasons + advisory_reasons))
    return {"priority": priority, "status": "REVIEW_REQUIRED" if priority != "LOW" else "LIKELY_OK",
            "reasons": all_reasons, "candidate_count": len(rows)}


def assign_near_far_candidates(detections: Iterable[dict], table_bbox) -> list[dict]:
    """Attach conservative NEAR/FAR spatial hints; never assign athlete identity.

    The lower foot point in the image is used only as a static-camera depth
    prior. If the frame does not contain exactly two opposing player-side
    candidates, both labels remain UNKNOWN.
    """
    rows = [dict(d) for d in detections]
    table_cx = (float(table_bbox[0]) + float(table_bbox[2])) / 2
    side_people = [d for d in rows if ("person" in d.get("label", "").casefold() or "player" in d.get("label", "").casefold())
                   and d.get("spatial_hint") in {"PLAYER_LEFT_CANDIDATE", "PLAYER_RIGHT_CANDIDATE"}]
    if len(side_people) != 2 or len({d.get("spatial_hint") for d in side_people}) != 2:
        for d in rows:
            d.setdefault("role", "UNKNOWN")
            d["role_candidate"] = "UNKNOWN"
            d["role_evidence"] = "INSUFFICIENT_OPPOSING_PLAYER_CANDIDATES"
        return rows
    # Keep side-to-table association as an explicit check. The role itself is
    # based on foot-point vertical position, never on screen-left == Player A.
    if any(((d["bbox"][0] + d["bbox"][2]) / 2 - table_cx) == 0 for d in side_people):
        for d in rows:
            d.setdefault("role", "UNKNOWN")
            d["role_candidate"] = "UNKNOWN"
            d["role_evidence"] = "TABLE_RELATION_AMBIGUOUS"
        return rows
    far = min(side_people, key=lambda d: float(d["bbox"][3]))
    near = max(side_people, key=lambda d: float(d["bbox"][3]))
    for d in rows:
        d.setdefault("role", "UNKNOWN")
        d["role_candidate"] = "UNKNOWN"
        d["role_evidence"] = "NOT_A_PLAYER_SIDE_CANDIDATE"
    far["role_candidate"], far["role_evidence"] = "FAR_PLAYER_CANDIDATE", "HIGHER_IMAGE_FOOTPOINT"
    near["role_candidate"], near["role_evidence"] = "NEAR_PLAYER_CANDIDATE", "LOWER_IMAGE_FOOTPOINT"
    return rows


def temporal_player_presence(frames: Iterable[dict], *, max_gap_ms: int = 2000) -> list[dict]:
    """Mark short between-keyframe gaps without inventing detections or boxes."""
    ordered = sorted((dict(frame) for frame in frames), key=lambda frame: frame.get("timestamp_ms", 0))
    sides = []
    for frame in ordered:
        sides.append({d.get("spatial_hint") for d in frame.get("detections", [])
                      if d.get("spatial_hint") in {"PLAYER_LEFT_CANDIDATE", "PLAYER_RIGHT_CANDIDATE"}
                      and d.get("user_correction", {}).get("status") != "REJECTED"})
    result = []
    for index, frame in enumerate(ordered):
        state = {}
        for side in ("PLAYER_LEFT_CANDIDATE", "PLAYER_RIGHT_CANDIDATE"):
            if side in sides[index]:
                state[side] = "DETECTED"
            elif (index > 0 and index + 1 < len(ordered) and
                  side in sides[index - 1] and side in sides[index + 1] and
                  frame.get("timestamp_ms", 0) - ordered[index - 1].get("timestamp_ms", 0) <= max_gap_ms and
                  ordered[index + 1].get("timestamp_ms", 0) - frame.get("timestamp_ms", 0) <= max_gap_ms):
                state[side] = "TEMPORARILY_MISSING"
            else:
                state[side] = "NOT_OBSERVED"
        frame["temporal_player_presence"] = state
        result.append(frame)
    return result


def apply_review(raw_detections: list[dict], corrections: list[dict]) -> list[dict]:
    """Project user corrections over immutable raw detections."""
    by_id = {item["candidate_id"]: dict(item) for item in raw_detections}
    for correction in corrections:
        item = by_id.get(correction.get("candidate_id"))
        if item is None:
            continue
        action = correction.get("action")
        if action == "SET_ROLE" and correction.get("role") in REVIEW_ROLES:
            item["user_correction"] = {"role": correction["role"], "status": "CORRECTED"}
        elif action == "REJECT":
            item["user_correction"] = {"role": None, "status": "REJECTED"}
    return list(by_id.values())
