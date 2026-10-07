"""Optional unchanged PTTI Hit-engine downstream comparison; no ML framework or GT inference."""
from pathlib import Path
import sys

from .core import trajectory_metrics


def evaluate_raw_hit_downstream(observations, ground_truth, *, video_sha256, width, height,
                                processing_fps, config, player_evidence=None, source_frame_stride=1):
    if ground_truth is None:
        return {"status": "NOT_AVAILABLE_NO_ALIGNED_STROKE_GT", "raw_hit_recall": None,
                "raw_hit_fp_per_min": None}
    if not isinstance(source_frame_stride, int) or source_frame_stride < 1:
        raise ValueError("INVALID_REGISTERED_SOURCE_FRAME_STRIDE")
    if trajectory_metrics(observations, expected_step=source_frame_stride).get("status") != "PREDICTION_CONTINUITY_ONLY":
        return {"status": "NOT_EVALUABLE_SPARSE_OBSERVATIONS", "raw_hit_recall": None,
                "raw_hit_fp_per_min": None}
    if processing_fps <= 0 or width <= 0 or height <= 0:
        raise ValueError("INVALID_DOWNSTREAM_GEOMETRY")
    product = Path(__file__).resolve().parents[3]
    if str(product) not in sys.path:
        sys.path.insert(0, str(product))
    from backend.evidence_fusion import evaluate_hit_events
    from backend.hit_event_v02 import HitEventV02Config, RawHitCandidateGenerator, config_sha256

    rows = []
    for processing_frame, observation in enumerate(observations):
        # Explicit downstream policy only; pure detector metrics retain every candidate.
        selected = max(observation.detections, key=lambda d: d.score if d.score is not None else 0,
                       default=None)
        rows.append({"video_sha256": video_sha256, "source_frame": observation.source_frame,
                     "processing_frame": processing_frame, "timestamp_ms": observation.timestamp_ms,
                     "frame_size": {"width": width, "height": height},
                     "ball": {"visible": selected is not None, "x": selected.x if selected else None,
                              "y": selected.y if selected else None, "model_evidence": selected.score if selected else None},
                     "players": (player_evidence or {}).get(observation.source_frame, {})})
    settings = HitEventV02Config.from_dict(config)
    candidates = RawHitCandidateGenerator(settings).generate(rows)
    duration_ms = observations[-1].timestamp_ms - observations[0].timestamp_ms + 1000/processing_fps
    tolerances = {f"plus_minus_{n}_processing_frames": n*1000/processing_fps for n in (1, 2, 3)}
    metrics = evaluate_hit_events(candidates, ground_truth, tolerances_ms=tolerances)
    primary = metrics["by_tolerance"]["plus_minus_2_processing_frames"]
    return {"status": "MEASURED_UNCHANGED_RAW_GENERATOR", "config_sha256": config_sha256(settings),
            "selection_policy": "HIGHEST_WITHIN_MODEL_SCORE_FOR_DOWNSTREAM_ONLY",
            "candidate_count": len(candidates), "raw_hit_recall": primary["recall"],
            "raw_hit_fp_per_min": primary["false_positives"]/(duration_ms/60000),
            "metrics": metrics, "model": observations[0].model,
            "player_evidence": "PROVIDED_SAME_STREAM" if player_evidence else "UNAVAILABLE",
            "legacy_engine_module_label": "RACKETVISION_RAW_IS_A_LEGACY_STRING_NOT_NEW_MODEL_PROVENANCE",
            "candidate_creation_uses_gt": False}
