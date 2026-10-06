"""Score frozen MatchStructureEngine suggestions against derived research labels."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PRODUCT_ROOT.parents[1]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

from backend.extended_openttgames import ExtendedOpenTTGamesAdapter, derive_rally_ground_truth, evaluate_segments
from backend.match_structure import MatchStructureEngine, configuration_sha256
from backend.fullmatch import extract_source_frame_timestamps
from vision.quality import video_metadata


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_child(path: Path, root: Path, label: str) -> Path:
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(Path(root).resolve())
    except ValueError as exc:
        raise ValueError(f"{label} must be inside {Path(root).resolve()}") from exc
    return resolved


def run(video: Path, game_annotations: Path, ball_annotations: Path, observations_path: Path,
        output_dir: Path, *, video_id: str = "game_4", checkpoint: Path | None = None) -> dict:
    data_root = (Path.home() / "AppData" / "Local" / "PTTI-Dev" / "research-datasets" /
                 "ExtendedOpenTTGames").resolve()
    video = _require_child(video, data_root / "videos" / "train", "Video")
    game_annotations = _require_child(game_annotations, data_root / "annotations" / "train" / "game_data", "Game annotations")
    ball_annotations = _require_child(ball_annotations, data_root / "annotations" / "train" / "ball_data", "Ball annotations")
    dev_root = Path.home() / "AppData" / "Local" / "PTTI-Dev"
    observations_path = _require_child(observations_path, dev_root, "BallTrack observations")
    output_dir = _require_child(output_dir, dev_root, "Evaluation output")
    if video_id not in {f"game_{index}" for index in range(1, 6)}:
        raise ValueError("Only official training videos may be scored during the diagnostic phase")
    output_dir.mkdir(parents=True, exist_ok=True)
    media = video_metadata(video)
    source_pts = extract_source_frame_timestamps(video, media.get("frame_count"))
    pts_ms = {frame: timestamp for frame, timestamp in enumerate(source_pts)}
    adapter = ExtendedOpenTTGamesAdapter(fps=media["fps"])
    annotations = json.loads(game_annotations.read_text(encoding="utf-8"))
    events = adapter.parse(annotations, pts_ms=pts_ms)
    derived = derive_rally_ground_truth(events, frame_count=media.get("frame_count"))
    ball_gt_native = json.loads(ball_annotations.read_text(encoding="utf-8"))
    ball_gt = adapter.parse_ball_track(ball_gt_native, pts_ms=pts_ms)
    event_frames = {str(event["frame"]) for event in events}
    ball_frames = {str(row["frame"]) for row in ball_gt}
    paired_frame_overlap = len(event_frames & ball_frames)
    paired_frame_overlap_rate = paired_frame_overlap / len(event_frames) if event_frames else 0.0
    # Sparse event/position frame overlap is only a sanity signal, not a remapping rule.
    ball_gt_alignment_warning = paired_frame_overlap_rate < 0.20
    observations = [json.loads(line) for line in observations_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    video_hash = sha256(video)
    checkpoint = Path(checkpoint or PRODUCT_ROOT / "models" / "balltrack_best.pth")
    fullmatch_manifest = observations_path.parent / "manifest.json"
    manifest = json.loads(fullmatch_manifest.read_text(encoding="utf-8")) if fullmatch_manifest.is_file() else None
    engine_config = {"class": "MatchStructureEngine", "minimum_gap_ms": 700,
                     "context_window_ms": 1200, "minimum_context_observations": 2,
                     "source_module": "RACKETVISION_RAW", "split": "official_training",
                     "matching_min_temporal_iou": 0.1, "matching_max_boundary_delta_ms": 500}
    suggestions = MatchStructureEngine().suggest(observations, match_id=video_id,
                                                   video_sha256=video_hash)
    predictions = suggestions["rallies"]
    truth = [segment for segment in derived["segments"]
             if segment["start_ms"] is not None and segment["end_ms"] is not None]
    metrics = evaluate_segments(predictions, truth, min_iou=0.1)
    matches = metrics["matches"]
    by_prediction = {item["prediction_index"]: item for item in matches}
    by_truth = {item["ground_truth_index"]: item for item in matches}
    tolerance_values = [("1_frame", 1000/media["fps"]), ("3_frames", 3000/media["fps"]),
                        ("100_ms", 100), ("250_ms", 250), ("500_ms", 500)]
    tolerances = {}
    for label, limit in tolerance_values:
        tolerances[label] = {"tolerance_ms": limit,
            "start_within": sum(abs(row["start_delta_ms"]) <= limit for row in matches),
            "end_within": sum(abs(row["end_delta_ms"]) <= limit for row in matches),
            "both_boundaries_within": sum(abs(row["start_delta_ms"]) <= limit and
                                           abs(row["end_delta_ms"]) <= limit for row in matches),
            "matched_segments": len(matches)}
    endings = defaultdict(lambda: {"gt": 0, "matched": 0, "missed": 0})
    for index, segment in enumerate(truth):
        item = endings[segment["ending_type"]]; item["gt"] += 1
        if index in by_truth: item["matched"] += 1
        else: item["missed"] += 1
    boundary_edits = sum(abs(row["start_delta_ms"]) > 100 for row in matches) + \
                      sum(abs(row["end_delta_ms"]) > 100 for row in matches)
    minor = sum(max(abs(row["start_delta_ms"]), abs(row["end_delta_ms"])) <= 500 for row in matches)
    large = sum(max(abs(row["start_delta_ms"]), abs(row["end_delta_ms"])) > 500 for row in matches)
    review_proxy = {"boundary_edits_over_100ms": boundary_edits,
                    "missing_segments_requiring_creation": metrics["missed_rallies"],
                    "false_suggestions_requiring_rejection": metrics["false_rallies"],
                    "accept_without_edit_rate_100ms": sum(abs(x["start_delta_ms"]) <= 100 and
                        abs(x["end_delta_ms"]) <= 100 for x in matches) / len(matches) if matches else None,
                    "minor_adjustment_rate_within_500ms": minor / len(matches) if matches else None,
                    "large_adjustment_rate_over_500ms": large / len(matches) if matches else None,
                    "note": "Boundary edit counts are a proxy; no review-time saving is claimed."}
    frame_by_time = sorted(observations, key=lambda x: float(x.get("timestamp_ms", 0)))
    raw_by_source_frame = {int(row["source_frame"]): row for row in observations
                           if row.get("source_frame") is not None}
    raw_by_global_frame = {int(row["global_frame"]): row for row in observations
                           if row.get("global_frame") is not None}
    def tracking_context(start_ms: float, end_ms: float) -> dict:
        near = [row for row in frame_by_time if
                start_ms-500 <= float(row.get("timestamp_ms", -1)) <= start_ms+500 or
                end_ms-500 <= float(row.get("timestamp_ms", -1)) <= end_ms+500]
        gt_near = {row["frame"]: row for row in ball_gt if row["visible"] and row.get("timestamp_ms") is not None
                   and (abs(float(row["timestamp_ms"])-start_ms) <= 500 or
                        abs(float(row["timestamp_ms"])-end_ms) <= 500)}
        errors, raw_misses = [], 0
        for frame, target in gt_near.items():
            observed = raw_by_source_frame.get(frame) or raw_by_global_frame.get(frame)
            if not observed or observed.get("visible") is not True or observed.get("x") is None or observed.get("y") is None:
                raw_misses += 1
                continue
            errors.append(((float(observed["x"])-float(target["x"]))**2 +
                           (float(observed["y"])-float(target["y"]))**2)**0.5)
        diagonal = (media["width"]**2 + media["height"]**2)**0.5
        severe = sum(error > 0.05*diagonal for error in errors)
        return {"observations_near_boundary_window": len(near),
                "visible_near_boundary_window": sum(row.get("visible") is True for row in near),
                "missing_near_boundary_window": sum(row.get("visible") is False for row in near),
                "visible_ball_gt_samples_near_boundaries": len(gt_near),
                "raw_missed_visible_ball_gt_samples": raw_misses,
                "raw_coordinate_errors_px": errors,
                "raw_severe_coordinate_errors_over_5pct_diagonal": severe,
                "chunk_indices": sorted({row.get("chunk_index") for row in near if row.get("chunk_index") is not None})}
    worst = []
    for gi, segment in enumerate(truth):
        match = by_truth.get(gi)
        pred = predictions[match["prediction_index"]] if match else None
        context = tracking_context(float(segment["start_ms"]), float(segment["end_ms"]))
        tracking_failures = context["raw_missed_visible_ball_gt_samples"] + context["raw_severe_coordinate_errors_over_5pct_diagonal"]
        if ball_gt_alignment_warning:
            taxonomy = "UNKNOWN"
        elif not pred:
            if context["visible_ball_gt_samples_near_boundaries"] and tracking_failures == context["visible_ball_gt_samples_near_boundaries"]:
                taxonomy = "BALLTRACK_INPUT_FAILURE"
            elif context["visible_ball_gt_samples_near_boundaries"] and tracking_failures == 0:
                taxonomy = "STRUCTURE_LOGIC_FAILURE"
            else:
                taxonomy = "UNKNOWN"
        elif max(abs(match["start_delta_ms"]), abs(match["end_delta_ms"])) > 500:
            if context["visible_ball_gt_samples_near_boundaries"] and tracking_failures == context["visible_ball_gt_samples_near_boundaries"]:
                taxonomy = "BALLTRACK_INPUT_FAILURE"
            elif context["visible_ball_gt_samples_near_boundaries"] and tracking_failures == 0:
                taxonomy = "STRUCTURE_LOGIC_FAILURE"
            else:
                taxonomy = "UNKNOWN"
        else:
            continue
        worst.append({"video": video_id, "ground_truth": segment, "suggestion": pred,
                      "start_delta_ms": match["start_delta_ms"] if match else None,
                      "end_delta_ms": match["end_delta_ms"] if match else None,
                      "ending_event": next((event for event in events if event["event_id"] == segment["end_event_id"]), None),
                      "balltrack_context": context, "failure_taxonomy": taxonomy})
    for pi in metrics["unmatched_prediction_indices"]:
        pred = predictions[pi]
        context = tracking_context(float(pred["start_ms"]), float(pred["end_ms"]))
        worst.append({"video": video_id, "ground_truth": None, "suggestion": pred,
                      "start_delta_ms": None, "end_delta_ms": None,
                      "balltrack_context": context, "failure_taxonomy": "UNKNOWN"})
    worst.sort(key=lambda item: max(abs(item.get("start_delta_ms") or 0), abs(item.get("end_delta_ms") or 0)), reverse=True)
    preview_dir = output_dir / "worst_cases"; preview_dir.mkdir(exist_ok=True)
    for index, item in enumerate(worst[:20], 1):
        candidate = item["ground_truth"] or item["suggestion"]
        timestamp_ms = candidate.get("start_ms")
        if timestamp_ms is None:
            continue
        preview_path = preview_dir / f"{index:02d}-{video_id}-{candidate.get('start_frame', 'prediction')}.jpg"
        try:
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{float(timestamp_ms)/1000:.3f}",
                            "-i", str(video), "-frames:v", "1", "-vf", "scale=960:-1",
                            "-q:v", "4", "-y", str(preview_path)], check=True, timeout=60,
                           capture_output=True, text=True)
            item["frame_preview"] = str(preview_path)
        except (OSError, subprocess.SubprocessError):
            item["frame_preview"] = None
    event_counts = Counter(event["event_type"] for event in events)
    native_label_counts = Counter(event["native_label_tail"] for event in events)
    taxonomy_categories = ("STRUCTURE_LOGIC_FAILURE", "BALLTRACK_INPUT_FAILURE",
                           "ANNOTATION_AMBIGUITY", "UNKNOWN")
    taxonomy_counts = {category: sum(item["failure_taxonomy"] == category for item in worst)
                       for category in taxonomy_categories}
    config_hash = configuration_sha256(engine_config)
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    git_status = subprocess.run(["git", "status", "--porcelain"], cwd=REPOSITORY_ROOT,
                                capture_output=True, text=True, check=True).stdout
    result = {"status": "TRAINING_BASELINE_MEASURED", "dataset": "Extended OpenTTGames",
        "rights": "CC BY-NC-SA 4.0", "commercial_use": False, "split": "training",
        "video_id": video_id, "video_sha256": video_hash,
        "dataset_revision": "36471a76b969a0340df59258a813bf8214e68e7c",
        "match_structure_engine_commit": git_head,
        "evaluation_git_head": git_head, "evaluation_working_tree_dirty": bool(git_status),
        "evaluation_script_sha256": sha256(Path(__file__)),
        "match_structure_code_sha256": sha256(PRODUCT_ROOT / "backend" / "match_structure.py"),
        "balltrack_default": "BALLTRACK_V1_FROZEN_RAW", "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": sha256(checkpoint),
        "adapter_code_sha256": sha256(PRODUCT_ROOT / "backend" / "extended_openttgames.py"),
        "fullmatch_manifest_sha256": sha256(fullmatch_manifest) if fullmatch_manifest.is_file() else None,
        "fullmatch_config": manifest.get("config") if manifest else None,
        "fullmatch_cache_key": manifest.get("cache_key") if manifest else None,
        "media": media, "annotation_sha256": {"game_events": sha256(game_annotations),
                                                "ball_coordinates": sha256(ball_annotations)},
        "ground_truth_timestamp_basis": "SOURCE_PTS",
        "frame_count": media.get("frame_count"), "ball_coordinate_annotations": len(ball_gt),
        "ball_coordinate_visible_annotations": sum(row["visible"] for row in ball_gt),
        "native_event_count": len(events), "native_event_type_counts": dict(event_counts),
        "native_label_tail_counts": dict(native_label_counts), "derived_rally_ground_truth": derived,
        "event_ball_annotation_pairing": {"policy": "official same-index filename pairing; never remapped by heuristic",
            "event_frame_count": len(event_frames), "ball_coordinate_frame_count": len(ball_frames),
            "exact_shared_frame_count": paired_frame_overlap,
            "event_frame_overlap_rate": paired_frame_overlap_rate,
            "alignment_warning": ball_gt_alignment_warning,
            "warning": "Sparse frame overlap limits BallTrack-to-coordinate-GT attribution; review pairing before interpreting these classifications."
                if ball_gt_alignment_warning else None},
        "engine_config": engine_config, "engine_config_sha256": config_hash,
        "suggestion_count": len(predictions),
        "metrics": metrics, "boundary_tolerances": tolerances,
        "ending_type_performance": dict(endings), "human_review_effort_proxy": review_proxy,
        "failure_cases": worst, "failure_taxonomy_counts": taxonomy_counts,
        "test_split_status": "NOT_ACCESSED", "recorded_at": datetime.now(timezone.utc).isoformat(),
        "interpretation": "One-video training diagnostic only. Rally intervals are derived from event annotations; not native rally ground truth. No tuning or model training is included."}
    (output_dir / "MATCH_STRUCTURE_V1_BASELINE.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    for item in worst[:100]:
        preview = Path(item["frame_preview"]).relative_to(output_dir).as_posix() if item.get("frame_preview") else None
        rows.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(item["video"]), item["ground_truth"].get("start_frame") if item["ground_truth"] else "—",
            item["ground_truth"].get("end_frame") if item["ground_truth"] else "—",
            html.escape(str(item.get("start_delta_ms"))), html.escape(str(item.get("end_delta_ms"))),
            html.escape(item["failure_taxonomy"]) + (f"<br><img width='320' src='{html.escape(preview)}'>" if preview else "")))
    page = "<!doctype html><meta charset='utf-8'><title>Match structure baseline failure analysis</title>" \
        "<h1>Match Structure · 真实训练集基线</h1><p>Extended OpenTTGames · training · one video</p>" \
        f"<p>GT {metrics['gt_rallies']} · 建议 {metrics['suggested_rallies']} · 匹配 {metrics['matched_rallies']} · " \
        f"precision {metrics['precision']:.3f} · recall {metrics['recall']:.3f} · F1 {metrics['f1']:.3f}</p>" \
        "<p>回合边界由 serve→ending 标注推导，属于 DERIVED，不是 native rally ground truth。" \
        "官方 test split 未访问。</p><h2>错误案例</h2><table border='1'><tr><th>Video</th><th>GT start frame</th>" \
        "<th>GT end frame</th><th>Start delta ms</th><th>End delta ms</th><th>分类</th></tr>" + "".join(rows) + "</table>"
    (output_dir / "match_structure_failure_analysis.html").write_text(page, encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--game-annotations", type=Path, required=True)
    parser.add_argument("--ball-annotations", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True, help="full_match_balltrack.jsonl, never annotation-derived")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--video-id", default="game_4")
    parser.add_argument("--checkpoint", type=Path)
    args = parser.parse_args()
    result = run(args.video, args.game_annotations, args.ball_annotations,
                 args.observations, args.output, video_id=args.video_id, checkpoint=args.checkpoint)
    print(json.dumps({"video": result["video_id"], "metrics": result["metrics"],
                      "config_sha256": result["engine_config_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
