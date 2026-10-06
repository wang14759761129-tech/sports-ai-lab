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
REVIEW_ROLES = ("PLAYER_A", "PLAYER_B", "REFEREE", "OTHER", "UNKNOWN")


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
    if "person" not in phrase and "player" not in phrase:
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
