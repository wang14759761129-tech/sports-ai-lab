"""Canonical ball observations, immutable manifests and explicit evaluation scope."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import html
import json
import math
from pathlib import Path
import statistics
from typing import Any, Protocol, Sequence

STRATA = frozenset({"NORMAL", "FAST_BALL", "MOTION_BLUR", "FAR_SMALL_BALL",
                    "OCCLUSION", "REFEREE_DISTRACTOR", "CROWD_BACKGROUND",
                    "EDGE_OF_FRAME", "LIGHTING_CHANGE", "CAMERA_CHANGE", "UNKNOWN"})
METRICS_VERSION = "ptti-vision-benchmark-v0.1"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class BallDetection:
    x: float
    y: float
    score: float | None = None
    bbox: tuple[float, float, float, float] | None = None

    def __post_init__(self):
        values = [self.x, self.y] + ([] if self.score is None else [self.score])
        if not all(math.isfinite(v) for v in values):
            raise ValueError("NON_FINITE_DETECTION")
        if self.bbox is not None:
            x1, y1, x2, y2 = self.bbox
            if not all(math.isfinite(v) for v in self.bbox) or x2 <= x1 or y2 <= y1:
                raise ValueError("INVALID_BBOX")
            object.__setattr__(self, "bbox", tuple(self.bbox))


@dataclass(frozen=True)
class FrameObservation:
    source_frame: int
    timestamp_ms: float
    detections: tuple[BallDetection, ...]
    model: str
    source: str

    def __post_init__(self):
        if self.source_frame < 0 or not math.isfinite(self.timestamp_ms) or self.timestamp_ms < 0:
            raise ValueError("INVALID_CANONICAL_TIME")
        object.__setattr__(self, "detections", tuple(self.detections))


class VisionModelAdapter(Protocol):
    """Inference belongs outside the core; score semantics must be declared by each adapter."""
    model_name: str
    model_version: str
    model_sha: str
    license: str

    def observations(self, input_video: Path) -> Sequence[FrameObservation]: ...


def verify_manifest(manifest: dict) -> None:
    if manifest.get("metrics_version") != METRICS_VERSION:
        raise ValueError("METRICS_VERSION_MISMATCH")
    identifiers = set()
    for clip in manifest["clips"]:
        if clip["id"] in identifiers:
            raise ValueError("DUPLICATE_CLIP")
        identifiers.add(clip["id"])
        if clip["split"] not in {"DEV", "TRAIN", "USER_AUTHORIZED_RESEARCH"}:
            raise ValueError("LOCKED_SPLIT_NOT_ALLOWED")
        if not set(clip["scene_strata"]) <= STRATA:
            raise ValueError("UNKNOWN_SCENE_STRATUM")
        for field in ("video", "annotation"):
            asset = clip[field]
            if file_sha256(Path(asset["path"])) != asset["sha256"]:
                raise ValueError("BENCHMARK_ASSET_CHANGED")
        for field in ("canonical_labels", "racketvision_raw"):
            if field not in clip:
                if field == "canonical_labels":
                    raise ValueError("CANONICAL_LABELS_HASH_REQUIRED")
                continue
            if file_sha256(Path(clip[field])) != clip.get(field + "_sha256"):
                raise ValueError("DERIVED_BENCHMARK_ASSET_CHANGED")


def percentile(values: Sequence[float], p: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    index = (len(ordered) - 1) * p
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def trajectory_metrics(observations: Sequence[FrameObservation], expected_step: int = 1) -> dict:
    """Prediction continuity, not trajectory accuracy. Sparse samples cannot describe full clips."""
    if not observations:
        return {"status": "NO_OBSERVATIONS"}
    ordered = sorted(observations, key=lambda row: row.source_frame)
    if any(b.source_frame - a.source_frame != expected_step for a, b in zip(ordered, ordered[1:])):
        return {"status": "SPARSE_NOT_EVALUABLE", "trajectory_fragment_count": None,
                "longest_missing_run": None, "recovery_after_gap": None}
    fragments, gaps = [], []
    current = missing = 0
    recoveries = 0
    started = False
    for row in ordered:
        if row.detections:
            if missing:
                gaps.append(missing)
                if started:
                    recoveries += 1
                missing = 0
            current += 1
            started = True
        else:
            if current:
                fragments.append(current)
                current = 0
            missing += 1
    if current:
        fragments.append(current)
    if missing:
        gaps.append(missing)
    return {"status": "PREDICTION_CONTINUITY_ONLY", "trajectory_fragment_count": len(fragments),
            "average_fragment_length": statistics.mean(fragments) if fragments else 0,
            "longest_continuous_track": max(fragments, default=0),
            "longest_missing_run": max(gaps, default=0), "recovery_after_gap": recoveries}


def evaluate_ball(observations: Sequence[FrameObservation], labels: Sequence[dict],
                  width: int, height: int, fps: float, localization_radius_px: float = 20) -> dict:
    """Presence recall and localized recall are separate. Unlabeled frames are never negatives."""
    if width <= 0 or height <= 0 or fps <= 0 or localization_radius_px <= 0:
        raise ValueError("INVALID_EVALUATION_GEOMETRY")
    predictions = {row.source_frame: row for row in observations}
    if len(predictions) != len(observations):
        raise ValueError("DUPLICATE_OBSERVATION_FRAME")
    reviewed = [row for row in labels if row.get("visible") is not None and
                ("review_status" not in row or row["review_status"] in
                 {"CONFIRMED", "HUMAN_REVIEWED", "NATIVE_GROUND_TRUTH"})]
    if len({row["source_frame"] for row in reviewed}) != len(reviewed):
        raise ValueError("DUPLICATE_GT_FRAME")
    present = localized = visible = negatives = fp = missed = 0
    errors, normalized = [], []
    for row in reviewed:
        detections = predictions.get(row["source_frame"])
        if detections is not None and row.get("timestamp_ms") is not None:
            if abs(detections.timestamp_ms - float(row["timestamp_ms"])) > .05:
                raise ValueError("CANONICAL_TIMESTAMP_ALIGNMENT_FAILURE")
        detections = detections.detections if detections else ()
        if row["visible"]:
            visible += 1
            if not all(math.isfinite(float(row[k])) for k in ("x", "y")):
                raise ValueError("INVALID_GT_POINT")
            if detections:
                present += 1
                error = min(math.hypot(d.x - row["x"], d.y - row["y"]) for d in detections)
                errors.append(error)
                normalized.append(error / math.hypot(width, height))
                matched = int(error <= localization_radius_px)
                localized += matched
                fp += len(detections) - matched
                missed += 1 - matched
            else:
                missed += 1
        else:
            negatives += 1
            fp += len(detections)
    frames = sorted(row["source_frame"] for row in reviewed)
    dense = (bool(frames) and len(frames) == frames[-1] - frames[0] + 1
             and set(frames) == set(predictions))
    minutes = len(frames) / fps / 60 if dense else None
    precision = localized / (localized + fp) if localized + fp else None
    recall = localized / visible if visible else None
    f1 = 2*localized/(2*localized+fp+missed) if visible else None
    return {"metrics_version": METRICS_VERSION, "annotation_scope": "DENSE" if dense else "SPARSE",
            "reviewed_frames": len(reviewed), "unreviewed_labels": len(labels) - len(reviewed),
            "visible_ball_frames": visible, "detected_ball_frames": present,
            "presence_recall": present / visible if visible else None,
            "recall": recall, "precision": precision, "f1": f1,
            "localization_radius_px": localization_radius_px,
            "negative_frames": negatives, "false_detections": fp, "missed_visible_frames": missed,
            "fp_per_annotated_frame": fp / len(reviewed) if reviewed else None,
            "fp_per_min": fp / minutes if minutes else None,
            "fn_per_min": missed / minutes if minutes else None,
            "center_error_mean_px": statistics.mean(errors) if errors else None,
            "center_error_median_px": statistics.median(errors) if errors else None,
            "center_error_p95_px": percentile(errors, .95),
            "normalized_error_mean": statistics.mean(normalized) if normalized else None,
            "catastrophic_errors": {str(t): sum(e > t for e in errors) for t in (20, 50, 100)},
            "catastrophic_normalized_thresholds": {str(t): t/math.hypot(width, height) for t in (20, 50, 100)},
            "trajectory": trajectory_metrics(observations),
            "definition": "Nearest detection localization; extra or wrongly localized detections are FP. "
                          "Sparse labels cannot estimate full-video FP/min or FN/min."}


def write_report(path: Path, report: dict) -> None:
    path = Path(path)
    if path.exists() or path.with_suffix(".html").exists():
        raise FileExistsError("IMMUTABLE_REPORT_ALREADY_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    path.with_suffix(".sha256").write_text(file_sha256(path) + "  " + path.name + "\n", encoding="utf-8")
    body = html.escape(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    path.with_suffix(".html").write_text(
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>PTTI Vision Benchmark</title>'
        '<style>body{max-width:1100px;margin:40px auto;font:16px Microsoft YaHei,Segoe UI,sans-serif}'
        'pre{white-space:pre-wrap;background:#f2f5f8;padding:24px}</style><h1>PTTI Vision Benchmark</h1>'
        '<p>研究评估 · 原始观察保留 · 稀疏标注不代表整场准确率</p><pre>' + body + '</pre></html>',
        encoding="utf-8")


def serialize_observation(row: FrameObservation) -> dict:
    return asdict(row)


def rank_models(results: Sequence[dict]) -> list[dict]:
    """Descriptive ranking on exactly the same locked manifest and metric definition."""
    if not results:
        return []
    if len({r["manifest_sha256"] for r in results}) != 1 or any(
            r["metrics"]["metrics_version"] != METRICS_VERSION for r in results):
        raise ValueError("INCOMPARABLE_MODEL_RUNS")
    if any(r["metrics"]["recall"] is None or r["metrics"]["f1"] is None for r in results):
        raise ValueError("VISIBLE_GROUND_TRUTH_REQUIRED_FOR_RANKING")
    ordered = sorted(results, key=lambda r: (r["metrics"]["f1"], r["metrics"]["recall"] or 0), reverse=True)
    return [{"rank": index+1, "model": result["model"], "f1": result["metrics"]["f1"],
             "scope": "DESCRIPTIVE_SAME_DEV_DATA_ONLY"} for index, result in enumerate(ordered)]
