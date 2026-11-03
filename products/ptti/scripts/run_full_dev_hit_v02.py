"""Create a full-game, TRAIN-only Hit Event v0.2 cache and baseline report.

Consumes only a verified full-match BallTrack cache and matching TRAIN labels.
Missing full-match player/Pose evidence remains null and is reported as such.
This script measures the existing DRAFT config; it does not tune it.
"""
from __future__ import annotations

import argparse
import bisect
import csv
from datetime import datetime, timezone
import html
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

from backend.evidence_fusion import (  # noqa: E402
    CanonicalVideoTimeline,
    adapt_training_strokes,
    evaluate_hit_events,
)
from backend.fullmatch import file_sha256  # noqa: E402
from backend.hit_event_v02 import (  # noqa: E402
    HitEventV02Config,
    StrokeIntervalPrior,
    build_hit_event_pipeline,
    config_sha256,
    summarize_hard_negative_overlap,
)

DATASET_REVISION = "36471a76b969a0340df59258a813bf8214e68e7c"


def _read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _sha(path: Path) -> str:
    return file_sha256(path)


def resolve_full_dev_inputs(game: int, local: Path) -> dict:
    """Fail closed unless game, source, annotation, and BallTrack cache are verified DEV."""
    if game not in {1, 2, 3}:
        raise ValueError("ONLY_LOCKED_DEV_GAMES_1_TO_3_ARE_ALLOWED")
    dev_root = Path(local) / "PTTI-Dev"
    dataset_root = dev_root / "research-datasets" / "ExtendedOpenTTGames"
    download_path = dataset_root / "DEV_VIDEO_DOWNLOAD_MANIFEST.json"
    download = _read_json(download_path)
    if (download.get("dataset") != "Extended OpenTTGames" or
            download.get("dataset_revision") != DATASET_REVISION):
        raise ValueError("UNEXPECTED_DATASET_OR_REVISION")
    entry = next((row for row in download.get("games", [])
                  if row.get("game") == f"game_{game}"), None)
    if not entry or entry.get("status") != "VERIFIED" or entry.get("split_role") != "DEV":
        raise ValueError("DEV_VIDEO_NOT_VERIFIED")
    video = Path(entry["video_path"])
    if not video.is_file() or video.stat().st_size != int(entry["expected_bytes"]):
        raise ValueError("VERIFIED_VIDEO_FILE_MISSING_OR_SIZE_CHANGED")
    if _sha(video).lower() != str(entry.get("sha256", "")).lower():
        raise ValueError("VERIFIED_VIDEO_SHA256_CHANGED")

    split_path = PRODUCT_ROOT / "configs" / "evidence-fusion" / "HIT_EVENT_V0_2_SPLIT.json"
    split = _read_json(split_path)
    split_row = next((row for row in split.get("games", [])
                      if row.get("game") == f"game_{game}"), None)
    if (not split_row or split_row.get("role") != "development" or
            f"game_{game}" not in split.get("split_policy", {}).get("development", [])):
        raise ValueError("VIDEO_IS_NOT_IN_LOCKED_DEVELOPMENT_SPLIT")
    annotation = dataset_root / "annotations" / "train" / "game_data" / f"game_{game}.json"
    if not annotation.is_file() or _sha(annotation) != split_row["annotation_sha256"]:
        raise ValueError("TRAIN_ANNOTATION_HASH_MISMATCH")

    fullmatch_root = dev_root / "evidence" / "full_matches"
    complete_runs = []
    for manifest_path in fullmatch_root.glob("*/*/manifest.json"):
        try:
            manifest = _read_json(manifest_path)
        except (OSError, json.JSONDecodeError):
            continue
        match_prefix = f"research:extended-openttgames:game_{game}:"
        if (manifest.get("video_sha256") == entry["sha256"] and
                str(manifest.get("match_id", "")).startswith(match_prefix) and
                manifest.get("status") == "BALLTRACK_COMPLETE" and
                manifest.get("chunks") and
                all(row.get("status") == "COMPLETE" for row in manifest["chunks"])):
            complete_runs.append((manifest_path.stat().st_mtime_ns, manifest_path, manifest))
    if not complete_runs:
        raise FileNotFoundError("COMPLETE_FULL_MATCH_BALLTRACK_CACHE_NOT_FOUND")
    _, ball_manifest_path, ball_manifest = max(complete_runs)
    run_dir = ball_manifest_path.parent
    validation_path = run_dir / "full_match_validation.json"
    validation = _read_json(validation_path)
    csv_path = run_dir / "full_match_balltrack.csv"
    expected_csv_sha = validation.get("artifacts", {}).get("full_match_balltrack.csv", {}).get("sha256")
    if not csv_path.is_file() or _sha(csv_path) != expected_csv_sha:
        raise ValueError("FULL_MATCH_BALLTRACK_CSV_HASH_MISMATCH")
    return {"game": game, "entry": entry, "video": video, "split": split,
            "split_row": split_row, "split_path": split_path, "annotation": annotation,
            "dataset_root": dataset_root, "csv_path": csv_path,
            "ball_manifest_path": ball_manifest_path, "ball_manifest": ball_manifest,
            "validation_path": validation_path, "validation": validation}


def load_ball_frames(csv_path: Path, video_sha256: str, width: int, height: int) -> list[dict]:
    frames = []
    previous_frame = -1
    previous_timestamp = -math.inf
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            frame = int(row["global_frame"])
            source_frame = int(row["source_frame"])
            timestamp = float(row["timestamp_ms"])
            if frame != previous_frame + 1 or source_frame < 0 or timestamp <= previous_timestamp:
                raise ValueError("BALLTRACK_FRAME_OR_TIMESTAMP_SEQUENCE_INVALID")
            visible = row["visible"].strip().lower() in {"true", "1"}
            frames.append({
                "frame": frame, "source_frame": source_frame, "processing_frame": frame,
                "timestamp_ms": timestamp, "video_sha256": video_sha256,
                "frame_size": {"width": width, "height": height},
                "ball": {"visible": visible,
                         "x": float(row["x"]) if visible and row.get("x") else None,
                         "y": float(row["y"]) if visible and row.get("y") else None,
                         "model_evidence": (float(row["raw_model_score"])
                                            if visible and row.get("raw_model_score") else None),
                         "source": "RACKETVISION_RAW"},
                "players": {"NEAR_PLAYER": {"track": None, "pose": None},
                            "FAR_PLAYER": {"track": None, "pose": None}},
                "evidence_level": "BALL_ONLY" if visible else "INSUFFICIENT",
            })
            previous_frame, previous_timestamp = frame, timestamp
    if not frames:
        raise ValueError("EMPTY_FULL_MATCH_BALLTRACK_CACHE")
    return frames


def ball_context_coverage(frames: list[dict], truth: list[dict], window_ms: float) -> dict:
    visible = [(float(frame["timestamp_ms"]), index) for index, frame in enumerate(frames)
               if frame["ball"]["visible"]]
    times = [row[0] for row in visible]
    details = []
    for event in truth:
        timestamp = float(event["timestamp_ms"])
        pivot = bisect.bisect_left(times, timestamp)
        before = [row for row in visible[max(0, pivot - 12):pivot]
                  if timestamp - row[0] <= window_ms]
        after = [row for row in visible[pivot:pivot + 12]
                 if row[0] - timestamp <= window_ms]
        details.append({"event_id": event["event_id"], "timestamp_ms": timestamp,
                        "pre_visible_count": len(before), "post_visible_count": len(after),
                        "ball_context_available": len(before) >= 2 and len(after) >= 2})
    return {"window_ms_each_side": window_ms,
            "events_with_ball_context": sum(row["ball_context_available"] for row in details),
            "ground_truth_strokes": len(truth), "per_event": details}


def _matched_indices(evaluation: dict, tolerance: str) -> set[int]:
    return {int(row["ground_truth_index"])
            for row in evaluation["by_tolerance"][tolerance]["matches"]}


def stage_attrition(truth: list[dict], evaluations: dict[str, dict], tolerance: str) -> list[dict]:
    matched = {name: _matched_indices(value, tolerance) for name, value in evaluations.items()}
    rows = []
    for index, event in enumerate(truth):
        if index not in matched["raw"]:
            loss = "RAW_GENERATOR_MISS"
        elif index not in matched["cluster"]:
            loss = "TEMPORAL_CLUSTER_LOSS"
        elif index in matched["decoded"]:
            loss = "AUTO_SELECTED"
        elif index in matched["review_mode"]:
            loss = "REVIEW_QUEUE_ONLY"
        else:
            loss = "DECODER_DROP_NOT_IN_REVIEW_QUEUE"
        rows.append({"ground_truth_index": index, "event_id": event["event_id"],
                     "timestamp_ms": event["timestamp_ms"], "source_frame": event["source_frame"],
                     "native_label": event["native_label"],
                     "stage_found": {name: index in indices for name, indices in matched.items()},
                     "loss_stage": loss})
    return rows


def _render_report(path: Path, result: dict) -> None:
    label = "plus_minus_2_processing_frames"
    lines = ["<!doctype html><html lang='zh-CN'><meta charset='utf-8'>",
             "<title>PTTI Full DEV Hit Event Baseline</title>",
             "<style>body{font:15px 'Microsoft YaHei',sans-serif;max-width:1050px;margin:32px auto;color:#18212b}"
             "table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}"
             ".note{background:#fff4d6;padding:12px}</style>",
             f"<h1>Full DEV Hit Event · {html.escape(result['game'])}</h1>",
             "<p class='note'>仅用官方 TRAIN/DEV；DRAFT 配置未调参。当前没有 source-matched 全场球员/姿态缓存，"
             "击球方保持 UNKNOWN，侧别准确率不可评估。</p>",
             f"<p>视频 SHA256：<code>{html.escape(result['video_sha256'])}</code></p>",
             f"<p>配置 SHA256：<code>{html.escape(result['config_sha256'])}</code></p>",
             "<table><tr><th>阶段</th><th>候选</th><th>TP</th><th>FP</th><th>FN</th><th>P</th><th>R</th><th>F1</th></tr>"]
    for name in ("raw", "cluster", "decoded", "review_mode"):
        metric = result["stage_metrics"][name]["by_tolerance"][label]
        values = (name, metric["predicted"], metric["matched"], metric["false_positives"],
                  metric["false_negatives"], round(metric["precision"], 4),
                  round(metric["recall"], 4), round(metric["f1"], 4))
        lines.append("<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in values) + "</tr>")
    lines.append("</table><h2>Evidence coverage</h2><pre>" +
                 html.escape(json.dumps(result["evidence_coverage"], ensure_ascii=False, indent=2)) +
                 "</pre><h2>Stage attrition</h2><pre>" +
                 html.escape(json.dumps(result["stage_attrition"], ensure_ascii=False, indent=2)) + "</pre></html>")
    path.write_text("\n".join(lines), encoding="utf-8")


def run(game: int, local: Path | None = None) -> dict:
    local = Path(local or os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")).resolve()
    inputs = resolve_full_dev_inputs(game, local)
    manifest = inputs["ball_manifest"]
    media = manifest["media"]
    fps = float(media["fps"])
    video_sha = str(inputs["entry"]["sha256"])
    if abs(fps - 120.0) > 0.02 or manifest.get("video_sha256") != video_sha:
        raise ValueError("FULL_MATCH_SOURCE_OR_FPS_MISMATCH")
    frames = load_ball_frames(inputs["csv_path"], video_sha, int(media["width"]), int(media["height"]))
    if len(frames) != int(media["frame_count"]):
        raise ValueError("BALLTRACK_FRAME_COUNT_MISMATCH")
    timeline = CanonicalVideoTimeline(
        video_sha256=video_sha, source_fps=fps, processing_fps=fps, source_frame_start=0,
        clip_start_timestamp_ms=0.0, processing_pts_ms=[float(row["timestamp_ms"]) for row in frames],
        clip_duration_ms=float(media["duration"]) * 1000.0,
    )
    annotations = _read_json(inputs["annotation"])
    truth = adapt_training_strokes(annotations, timeline, fps=fps, side_mapping=None)

    config_path = PRODUCT_ROOT / "configs" / "evidence-fusion" / "HIT_EVENT_V0_2_DRAFT_CONFIG.json"
    prior_path = PRODUCT_ROOT / "configs" / "evidence-fusion" / "HIT_EVENT_V0_2_DEV_PRIORS.json"
    config = HitEventV02Config.from_dict(_read_json(config_path))
    if config.status != "DRAFT_DEV_ONLY":
        raise ValueError("FULL_DEV_RUNNER_REQUIRES_DRAFT_DEV_ONLY_CONFIG")
    prior_data = _read_json(prior_path)["within_derived_rally_stroke_intervals_ms"]
    prior = StrokeIntervalPrior(sample_count=int(prior_data["sample_count"]),
        minimum_ms=float(prior_data["min"]), p1_ms=float(prior_data["p1"]),
        p5_ms=float(prior_data["p5"]), median_ms=float(prior_data["median"]),
        p95_ms=float(prior_data["p95"]))
    pipeline = build_hit_event_pipeline(frames, config, prior)
    tolerances = {f"plus_minus_{count}_processing_frames": count * 1000.0 / fps
                  for count in (1, 2, 3)}
    review_candidates = [*pipeline["filtered_candidates"], *pipeline["decoder_review_candidates"]]
    stage_predictions = {"raw": pipeline["raw_candidates"],
                         "cluster": pipeline["clustered_candidates"],
                         "decoded": pipeline["filtered_candidates"],
                         "review_mode": review_candidates}
    stage_metrics = {name: evaluate_hit_events(rows, truth, tolerances_ms=tolerances)
                     for name, rows in stage_predictions.items()}
    evaluation_label = "plus_minus_2_processing_frames"
    attrition = stage_attrition(truth, stage_metrics, evaluation_label)
    from backend.extended_openttgames import ExtendedOpenTTGamesAdapter
    native_events = ExtendedOpenTTGamesAdapter(fps=fps).parse(annotations)
    negative_overlap = summarize_hard_negative_overlap(pipeline["raw_candidates"], native_events,
                                                       window_ms=100.0)
    coverage = ball_context_coverage(frames, truth, config.max_ball_gap_ms)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output = local / "PTTI-Dev" / "evidence" / "hit_event_v0_2" / "full_dev" / f"game_{game}" / timestamp
    output.mkdir(parents=True, exist_ok=False)

    evidence_path = output / "full_match_frame_evidence.jsonl"
    with evidence_path.open("w", encoding="utf-8", newline="\n") as stream:
        for frame in frames:
            stream.write(json.dumps(frame, ensure_ascii=False, separators=(",", ":")) + "\n")
    artifacts = {evidence_path.name: {"size_bytes": evidence_path.stat().st_size,
                                     "sha256": _sha(evidence_path)}}
    for name, rows in (("ground_truth_strokes.json", truth),
                       ("raw_candidates.json", pipeline["raw_candidates"]),
                       ("clustered_candidates.json", pipeline["clustered_candidates"]),
                       ("decoded_candidates.json", pipeline["filtered_candidates"]),
                       ("decoder_review_candidates.json", pipeline["decoder_review_candidates"]),
                       ("stage_attrition.json", attrition)):
        path = output / name
        _atomic_json(path, rows)
        artifacts[name] = {"size_bytes": path.stat().st_size, "sha256": _sha(path)}

    at_two = stage_metrics["decoded"]["by_tolerance"][evaluation_label]
    review_two = stage_metrics["review_mode"]["by_tolerance"][evaluation_label]
    result = {
        "status": "FULL_DEV_BASELINE_MEASUREMENT", "game": f"game_{game}",
        "split_role": "DEV", "official_split": "TRAIN", "dataset": "Extended OpenTTGames",
        "dataset_revision": inputs["split"]["dataset_revision"],
        "license": "CC BY-NC-SA 4.0", "commercial_use": False,
        "video_path": str(inputs["video"]), "video_sha256": video_sha,
        "video_size_bytes": inputs["entry"]["current_bytes"], "media": media,
        "balltrack_model": "BALLTRACK_V1_FROZEN_RAW",
        "balltrack_manifest_path": str(inputs["ball_manifest_path"]),
        "balltrack_manifest_sha256": _sha(inputs["ball_manifest_path"]),
        "balltrack_validation_sha256": _sha(inputs["validation_path"]),
        "balltrack_csv_sha256": _sha(inputs["csv_path"]),
        "annotation_sha256": inputs["split_row"]["annotation_sha256"],
        "timeline_audit": timeline.audit(), "config": config.as_dict(),
        "config_status": config.status, "config_sha256": config_sha256(config),
        "prior_sha256": _sha(prior_path), "prior": prior.as_dict(),
        "pose_policy": "OFF; no Pose candidate creation or reranking",
        "inference_annotation_access": "NONE; TRAIN labels loaded only after candidates are generated",
        "player_evidence": {"status": "NOT_AVAILABLE_FOR_FULL_MATCH", "tracked_frames": 0,
                             "role_assignment": "UNKNOWN", "side_accuracy": "NOT_EVALUABLE"},
        "evidence_coverage": {
            "ground_truth_strokes": len(truth), "ball_frames": len(frames),
            "ball_visible_frames": sum(bool(row["ball"]["visible"]) for row in frames),
            "strokes_with_pre_and_post_ball_context": coverage["events_with_ball_context"],
            "ball_context_window_ms_each_side": coverage["window_ms_each_side"],
            "player_evidence_available_near_ground_truth": 0,
            "pose_evidence_available_near_ground_truth": 0,
            "both_ball_and_player_evidence": 0,
            "side_assignment_not_evaluable": len(truth)},
        "ball_context_by_ground_truth": coverage["per_event"],
        "candidate_counts": pipeline["counts"], "tolerances_ms": tolerances,
        "stage_metrics": stage_metrics, "stage_attrition": attrition,
        "hard_negative_overlap": negative_overlap,
        "review_mode_metrics_at_plus_minus_2_frames": {
            "precision": review_two["precision"], "recall": review_two["recall"],
            "f1": review_two["f1"], "candidates": len(review_candidates),
            "ground_truth_strokes": len(truth), "candidates_per_minute": round(
                len(review_candidates) / max(float(media["duration"]) / 60.0, 1e-9), 4)},
        "decoded_mode_metrics_at_plus_minus_2_frames": {
            "precision": at_two["precision"], "recall": at_two["recall"], "f1": at_two["f1"],
            "player_side_accuracy": at_two["player_side_accuracy"],
            "player_side_evaluable_matches": at_two["player_side_evaluable_matches"],
            "fp_per_minute": round(at_two["false_positives"] / max(float(media["duration"]) / 60.0, 1e-9), 4),
        },
        "production_database": "NOT_ACCESSED", "official_test_split": "NOT_ACCESSED",
        "calibration_game": "NOT_ACCESSED", "internal_holdout": "NOT_ACCESSED",
        "output_dir": str(output), "created_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": artifacts,
    }
    result_path = output / "full_dev_hit_evaluation.json"
    report_path = output / "full_dev_hit_evaluation.html"
    _render_report(report_path, result)
    artifacts[report_path.name] = {"size_bytes": report_path.stat().st_size, "sha256": _sha(report_path)}
    _atomic_json(result_path, result)
    (output / "full_dev_hit_evaluation.json.sha256").write_text(
        f"{_sha(result_path)}  {result_path.name}\n", encoding="ascii")
    print(json.dumps({"status": result["status"], "game": result["game"],
        "ground_truth_strokes": len(truth), "candidate_counts": pipeline["counts"],
        "ball_context_strokes": coverage["events_with_ball_context"],
        "player_evidence": result["player_evidence"],
        "plus_minus_2_frames": {name: value["by_tolerance"][evaluation_label]
                                 for name, value in stage_metrics.items()},
        "output_dir": str(output)}, ensure_ascii=False, indent=2), flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=int, choices=[1, 2, 3], required=True)
    args = parser.parse_args()
    run(args.game)


if __name__ == "__main__":
    main()
