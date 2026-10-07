"""Format adapters only. Frameworks and model inference remain outside benchmark core."""
from dataclasses import dataclass
from pathlib import Path

from .core import BallDetection, FrameObservation, file_sha256


@dataclass(frozen=True)
class CachedVisionModelAdapter:
    model_name: str
    model_version: str
    model_sha: str
    license: str
    weights_license: str
    input_video: Path
    video_sha256: str
    raw_observations: tuple[FrameObservation, ...]

    def __post_init__(self):
        if len(self.model_sha) != 64 or any(c not in "0123456789abcdef" for c in self.model_sha):
            raise ValueError("INVALID_MODEL_SHA256")
        if not all((self.model_name, self.model_version, self.license, self.weights_license)):
            raise ValueError("MODEL_PROVENANCE_REQUIRED")

    def observations(self, input_video: Path):
        if Path(input_video).resolve() != self.input_video.resolve():
            raise ValueError("ADAPTER_SOURCE_MISMATCH")
        if file_sha256(self.input_video) != self.video_sha256:
            raise ValueError("ADAPTER_SOURCE_CHANGED")
        return self.raw_observations


class RacketVisionAdapter(CachedVisionModelAdapter):
    @classmethod
    def from_rows(cls, *, rows, fps, **provenance):
        return cls(raw_observations=tuple(racketvision_rows(rows, fps, model=provenance["model_name"])), **provenance)


class RFDETRAdapter(CachedVisionModelAdapter):
    @classmethod
    def from_rows(cls, *, rows, **provenance):
        return cls(raw_observations=tuple(rfdetr_rows(rows, model=provenance["model_name"])), **provenance)


def racketvision_rows(rows, fps, model="RacketVision Official RAW"):
    result = []
    for row in rows:
        frame = int(row["frame"])
        detections = ()
        if row["visible"]:
            # Older cache calls this confidence; retain value but never call it probability.
            detections = (BallDetection(float(row["pixel_x"]), float(row["pixel_y"]),
                                        row.get("confidence")),)
        result.append(FrameObservation(frame, frame * 1000 / fps, detections,
                                       model, "FROZEN_RAW_CACHE"))
    return result


def rfdetr_rows(rows, model="RF-DETR Nano"):
    return [FrameObservation(int(row["source_frame"]), float(row["timestamp_ms"]),
                             tuple(BallDetection(**d) for d in row["detections"]),
                             model, "PRETRAINED_SPORTS_BALL") for row in rows]


def select_named_sports_balls(boxes, scores, class_ids, class_names):
    """Use official per-detection mapped names, never index a contiguous name list with sparse COCO IDs."""
    if class_names is None or not (len(boxes) == len(scores) == len(class_ids) == len(class_names)):
        raise ValueError("RFDETR_NATIVE_CLASS_NAMES_REQUIRED")
    selected = []
    for box, score, class_id, name in zip(boxes, scores, class_ids, class_names):
        if str(name).lower() == "sports ball":
            x1, y1, x2, y2 = map(float, box)
            selected.append({"x": (x1+x2)/2, "y": (y1+y2)/2, "bbox": [x1,y1,x2,y2],
                             "score": float(score)})
    return selected
