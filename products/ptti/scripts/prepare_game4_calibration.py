"""Prepare immutable game_4 A/D candidates from frozen RAW BallTrack output."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

PRODUCT = Path(__file__).resolve().parents[1]
if str(PRODUCT) not in sys.path:
    sys.path.insert(0, str(PRODUCT))
sys.path.insert(0, str(PRODUCT / "research" / "hit-v03"))
sys.path.insert(0, str(PRODUCT / "scripts"))

from backend.evidence_fusion import (  # noqa: E402
    CanonicalVideoTimeline, adapt_training_strokes,
)
from backend.fullmatch import file_sha256  # noqa: E402
from backend.hit_event_v02 import (  # noqa: E402
    HitEventV02Config, StrokeIntervalPrior, build_hit_event_pipeline,
)
from calibration import (  # noqa: E402
    enforce_calibration_scope, immutable_json, resolve_ptti_dev_root,
)
from run_full_dev_hit_v02 import load_ball_frames  # noqa: E402

EXPECTED_D_CONFIG_SHA256 = "9703ec102f0bf11ff545ee2772ebea16fd708d7e8a52d6693fafe1ceb22ba530"


def _read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_new(path: Path, value) -> str:
    return immutable_json(path, value)


def prepare(source_path: Path) -> dict:
    source_path = Path(source_path).resolve()
    source = _read(source_path)
    enforce_calibration_scope(source.get("game"), source.get("split_role"),
                              source.get("official_split"))
    if source.get("game_5") != "NOT_ACCESSED" or source.get("official_test") != "NOT_ACCESSED":
        raise ValueError("CALIBRATION_LOCK_MARKERS_REQUIRED")
    video = Path(source["video"]["path"]).resolve()
    dev_root = resolve_ptti_dev_root(video)
    expected_source = (dev_root / "evidence" / "hit_event_v0_3" /
                       "game4-calibration-20261008" / "GAME4_CALIBRATION_SOURCE_VERIFICATION.json").resolve()
    if source_path != expected_source:
        raise ValueError("NONCANONICAL_CALIBRATION_SOURCE_VERIFICATION")
    if video.stat().st_size != int(source["video"]["size_bytes"]):
        raise ValueError("CALIBRATION_VIDEO_SIZE_CHANGED")
    if file_sha256(video).lower() != source["video"]["sha256"].lower():
        raise ValueError("CALIBRATION_VIDEO_SHA_CHANGED")
    annotation_path = Path(source["annotation"]["path"]).resolve()
    if (annotation_path.stat().st_size != int(source["annotation"]["size_bytes"]) or
            file_sha256(annotation_path).lower() != source["annotation"]["sha256"].lower()):
        raise ValueError("CALIBRATION_ANNOTATION_IDENTITY_CHANGED")
    split_path = Path(source["split_manifest"]["path"]).resolve()
    if file_sha256(split_path).lower() != source["split_manifest"]["sha256"].lower():
        raise ValueError("LOCKED_SPLIT_MANIFEST_CHANGED")
    split = _read(split_path)
    row = next((item for item in split["games"] if item.get("game") == "game_4"), None)
    if (not row or row.get("role") != "calibration" or
            row.get("official_split", "TRAIN").upper() != "TRAIN"):
        raise ValueError("GAME4_CALIBRATION_SPLIT_MISMATCH")

    run_plan = _read(source_path.parent / "BALLTRACK_RUN_PLAN.json")
    if (run_plan.get("game") != "game_4" or run_plan.get("split_role") != "CALIBRATION" or
            run_plan.get("video_sha256") != source["video"]["sha256"] or
            run_plan.get("database") != "NONE_IN_MEMORY_REPOSITORY_ONLY"):
        raise ValueError("CALIBRATION_BALLTRACK_RUN_PLAN_MISMATCH")
    manifest_path = Path(run_plan["output_manifest"]).resolve()
    manifest = _read(manifest_path)
    validation_path = manifest_path.parent / "full_match_validation.json"
    validation = _read(validation_path)
    csv_path = manifest_path.parent / "full_match_balltrack.csv"
    artifact = validation.get("artifacts", {}).get(csv_path.name, {})
    if (manifest.get("status") != "BALLTRACK_COMPLETE" or
            any(chunk.get("status") != "COMPLETE" for chunk in manifest.get("chunks", [])) or
            manifest.get("video_sha256") != source["video"]["sha256"] or
            manifest.get("checkpoint_sha256") != run_plan.get("checkpoint_sha256") or
            not csv_path.is_file() or file_sha256(csv_path) != artifact.get("sha256")):
        raise ValueError("FROZEN_RAW_BALLTRACK_ARTIFACTS_NOT_VERIFIED")

    media = manifest["media"]
    fps = float(media["fps"])
    frames = load_ball_frames(csv_path, source["video"]["sha256"],
                              int(media["width"]), int(media["height"]))
    if fps != 120.0 or len(frames) != int(media["frame_count"]):
        raise ValueError("CALIBRATION_TIMELINE_FRAME_RATE_OR_COUNT_MISMATCH")
    timeline = CanonicalVideoTimeline(
        video_sha256=source["video"]["sha256"], source_fps=fps,
        processing_fps=fps, source_frame_start=0, clip_start_timestamp_ms=0.0,
        processing_pts_ms=[float(frame["timestamp_ms"]) for frame in frames],
        clip_duration_ms=float(media["duration"]) * 1000.0,
    )
    timeline_audit = timeline.audit()
    if timeline_audit["status"] != "ALIGNED" or timeline_audit["maximum_processing_interval_error_ms"] > 0.001:
        raise ValueError("CALIBRATION_CANONICAL_TIMELINE_NOT_ALIGNED")

    product_config_path = PRODUCT / "configs" / "evidence-fusion" / "HIT_EVENT_V0_2_DRAFT_CONFIG.json"
    prior_path = PRODUCT / "configs" / "evidence-fusion" / "HIT_EVENT_V0_2_DEV_PRIORS.json"
    config_data = _read(product_config_path)
    config = HitEventV02Config.from_dict(config_data)
    if config.status != "DRAFT_DEV_ONLY":
        raise ValueError("GAME4_CALIBRATION_REQUIRES_UNCHANGED_V02_DRAFT_CONFIG")
    prior_data = _read(prior_path)["within_derived_rally_stroke_intervals_ms"]
    prior = StrokeIntervalPrior(
        sample_count=int(prior_data["sample_count"]), minimum_ms=float(prior_data["min"]),
        p1_ms=float(prior_data["p1"]), p5_ms=float(prior_data["p5"]),
        median_ms=float(prior_data["median"]), p95_ms=float(prior_data["p95"]),
    )
    dev_config_path = (dev_root / "evidence" / "hit_event_v0_3" /
                       "ablation-ABCD-20261008" / "V03_DEV_EXPERIMENT_CONFIG.json")
    dev_config_sha = file_sha256(dev_config_path)
    if dev_config_sha.lower() != EXPECTED_D_CONFIG_SHA256:
        raise ValueError("DEV_SELECTED_D_CONFIG_SHA_CHANGED")
    d_config = _read(dev_config_path)
    if d_config != {"table_center_penalty": 0.08,
                    "person_distance_penalty": 0.12, "distance_scale": 0.12}:
        raise ValueError("DEV_SELECTED_D_CONFIG_CONTENT_CHANGED")

    annotations = _read(annotation_path)
    truth = adapt_training_strokes(annotations, timeline, fps=fps, side_mapping=None)
    pipeline = build_hit_event_pipeline(frames, config, prior)
    points = {}
    by_source = {int(frame["source_frame"]): frame for frame in frames}
    for candidate in pipeline["raw_candidates"]:
        source_frame = int(candidate["source_frame"])
        ball = by_source[source_frame]["ball"]
        points[str(source_frame)] = [ball["x"], ball["y"]]

    output_dir = source_path.parent / "prepared-inputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "raw_candidates.json"
    truth_path = output_dir / "ground_truth_strokes.json"
    points_path = output_dir / "raw_candidate_ball_points.json"
    manifest_out = output_dir / "CALIBRATION_INPUT_MANIFEST.json"
    artifact_hashes = {
        raw_path.name: _write_new(raw_path, pipeline["raw_candidates"]),
        truth_path.name: _write_new(truth_path, truth),
        points_path.name: _write_new(points_path, points),
    }
    result = {
        "schema": "ptti-game4-calibration-inputs-v1", "status": "PREPARED_NO_CALIBRATION_RESULTS",
        "game": "game_4", "official_split": "TRAIN", "split_role": "CALIBRATION",
        "dataset": source["dataset"], "dataset_revision": source["dataset_revision"],
        "license": source["license"], "commercial_use": False,
        "video_sha256": source["video"]["sha256"],
        "annotation_sha256": source["annotation"]["sha256"],
        "source_verification_sha256": file_sha256(source_path),
        "split_manifest_sha256": source["split_manifest"]["sha256"],
        "full_match_manifest_sha256": file_sha256(manifest_path),
        "balltrack_csv_sha256": artifact["sha256"],
        "balltrack_checkpoint_sha256": manifest["checkpoint_sha256"],
        "frozen_balltrack": "BALLTRACK_V1_FROZEN_RAW",
        "media": media, "timeline_audit": timeline_audit,
        "hit_event_v02_config": config_data,
        "hit_event_v02_config_sha256": file_sha256(product_config_path),
        "dev_selected_d_config": d_config,
        "dev_selected_d_config_sha256": dev_config_sha,
        "dev_prior_sha256": file_sha256(prior_path),
        "raw_candidate_count": len(pipeline["raw_candidates"]),
        "gt_stroke_count": len(truth),
        "artifact_hashes": artifact_hashes,
        "game_5": "NOT_ACCESSED", "official_test": "NOT_ACCESSED",
        "production_database": "NOT_ACCESSED",
        "side_mapping": "UNKNOWN_NO_UNREVIEWED_LEFT_RIGHT_TO_NEAR_FAR_MAPPING",
    }
    _write_new(manifest_out, result)
    result["prepared_inputs_dir"] = str(output_dir)
    result["raw_candidates_path"] = str(raw_path)
    result["ground_truth_path"] = str(truth_path)
    result["candidate_ball_points_path"] = str(points_path)
    print(json.dumps({"prepared": True, "raw_candidates": len(pipeline["raw_candidates"]),
                      "ground_truth_strokes": len(truth), "timeline": timeline_audit,
                      "output_dir": str(output_dir)}, ensure_ascii=False, indent=2), flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-verification", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.source_verification)


if __name__ == "__main__":
    main()
