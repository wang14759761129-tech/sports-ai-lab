"""Immutable A-versus-D first pass for the single locked game_4 calibration."""
from __future__ import annotations

import argparse
from collections import Counter
import html
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile

PRODUCT = Path(__file__).resolve().parents[2]
if str(PRODUCT) not in sys.path:
    sys.path.insert(0, str(PRODUCT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.evidence_fusion import evaluate_hit_events  # noqa: E402
from backend.hit_event_v02 import (  # noqa: E402
    HitEventV02Config, HitSequenceDecoder, StrokeIntervalPrior, TemporalCandidateClusterer,
)
from backend.fullmatch import file_sha256  # noqa: E402
from backend.person_detector import FROZEN_MANIFEST_SHA  # noqa: E402
from calibration import (  # noqa: E402
    canonical_config_sha256, enforce_calibration_scope, immutable_json,
    resolve_ptti_dev_root,
)
from runtime import player_proximity, review_workload, soft_adjustment, table_coordinates  # noqa: E402

EXPECTED_D_CONFIG_SHA256 = "9703ec102f0bf11ff545ee2772ebea16fd708d7e8a52d6693fafe1ceb22ba530"
CONFIG_MODES = {"table_center_penalty": 0.08,
                "person_distance_penalty": 0.12, "distance_scale": 0.12}
def _read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _metric_summary(value: dict, duration_s: float) -> dict:
    two = value["by_tolerance"]["plus_minus_2_processing_frames"]
    fp = int(two["false_positives"])
    fn = int(two["false_negatives"])
    workload = review_workload(int(two["predicted"]), duration_s)
    return {"tp": int(two["matched"]), "fp": fp, "fn": fn,
            "precision": two["precision"], "recall": two["recall"], "f1": two["f1"],
            "fp_per_minute": fp * 60.0 / duration_s,
            "fn_per_minute": fn * 60.0 / duration_s,
            "review_candidates": int(two["predicted"]),
            "review_candidates_per_minute": workload["candidates_per_minute"],
            "estimated_review_minutes_per_45_minute_match":
                workload["estimated_review_minutes_per_45_minute_match"],
            "review_time_is_measured": False}


def _player_coverage(raw: list[dict], by_frame: dict[int, dict], table_bbox,
                     ball_points: dict) -> dict:
    unique_frames = sorted({int(row["source_frame"]) for row in raw})
    counts = Counter()
    neutral_player = 0
    table_coordinates_rows = []
    for frame in unique_frames:
        point = ball_points.get(str(frame))
        if table_bbox and point and all(value is not None for value in point):
            table_coordinates_rows.append(table_coordinates(tuple(map(float, point)), table_bbox))
        evidence = by_frame.get(frame)
        if not evidence:
            counts["missing_evidence_frame"] += 1
            neutral_player += 1
            continue
        people = evidence.get("resolved_people", [])
        roles = {person.get("role_candidate", "UNKNOWN") for person in people}
        counts["person_boxes"] += len(people)
        counts["frame_with_person"] += bool(people)
        counts["near"] += "NEAR_PLAYER" in roles
        counts["far"] += "FAR_PLAYER" in roles
        counts["both_near_and_far"] += {"NEAR_PLAYER", "FAR_PLAYER"}.issubset(roles)
        counts["unknown_role_person_frame"] += any(role in {"UNKNOWN", "OTHER"} for role in roles)
        has_player_role = bool({"NEAR_PLAYER", "FAR_PLAYER"} & roles)
        if not has_player_role:
            counts["no_assigned_player_role"] += 1
            neutral_player += 1
        if people and all(person.get("role_candidate") == "UNKNOWN" for person in people):
            counts["all_people_unknown_role"] += 1
        if not people:
            counts["no_person_box"] += 1
    denominator = len(unique_frames)
    fractions = {name: value / denominator if denominator else None
                 for name, value in counts.items()
                 if name in {"frame_with_person", "near", "far", "both_near_and_far",
                             "unknown_role_person_frame", "no_assigned_player_role",
                             "missing_evidence_frame"}}
    return {"candidate_count": len(raw), "unique_candidate_neighborhoods": denominator,
            "role_frames": dict(counts), "role_frame_fraction": fractions,
            "player_neutral_fallback_frames": neutral_player,
            "player_evidence_source": "RT-DETR R18 at RAW candidate source frames",
            "unknown_role_policy": "NEUTRAL_NO_PLAYER_DISTANCE_PENALTY",
            "table_geometry": {"table_bbox": table_bbox,
                               "candidate_frames_with_valid_geometry": len(table_coordinates_rows),
                               "coverage": len(table_coordinates_rows) / denominator if denominator else None,
                               "coordinate_scope": "COARSE_IMAGE_BBOX_NOT_TABLE_PLANE",
                               "inside_bbox_count": sum(row["inside_bbox"] for row in table_coordinates_rows),
                               "inside_bbox_fraction": (sum(row["inside_bbox"] for row in table_coordinates_rows) /
                                                        len(table_coordinates_rows)
                                                        if table_coordinates_rows else None),
                               "median_center_distance_proxy": (statistics.median(
                                   row["center_distance_proxy"] for row in table_coordinates_rows)
                                   if table_coordinates_rows else None)},
            "candidate_neighborhoods_processed": denominator,
            "person_boxes_by_frame": sum(len(row.get("resolved_people", [])) for row in by_frame.values()),
            "all_person_evidence_frames_returned": len(by_frame),
            "role_assignment_is_identity": False}


def _candidate_player_features(raw: list[dict], ball_points: dict, by_frame: dict) -> tuple[dict, dict]:
    features, rows_by_frame = {}, {}
    for candidate in raw:
        frame = int(candidate["source_frame"])
        evidence = by_frame.get(frame)
        if not evidence:
            continue
        people = evidence.get("resolved_people", [])
        point = ball_points.get(str(frame))
        if point is None or len(point) != 2 or any(value is None for value in point):
            continue
        feature = player_proximity(tuple(map(float, point)), people, (1920, 1080))
        features[frame] = feature
        rows_by_frame[frame] = {"source_frame": frame, "timestamp_ms": candidate["timestamp_ms"],
                                "candidate_event_id": candidate["event_id"],
                                "ball_point": point, "player_evidence": feature}
    return features, rows_by_frame


def run(source_verification: Path, prepared_dir: Path, player_dir: Path) -> dict:
    source_verification = Path(source_verification).resolve()
    source = _read(source_verification)
    enforce_calibration_scope(source.get("game"), source.get("split_role"),
                              source.get("official_split"))
    if source.get("game_5") != "NOT_ACCESSED" or source.get("official_test") != "NOT_ACCESSED":
        raise ValueError("CALIBRATION_LOCK_MARKERS_REQUIRED")
    dev_root = resolve_ptti_dev_root(Path(source["video"]["path"]))
    expected_source = (dev_root / "evidence" / "hit_event_v0_3" /
                       "game4-calibration-20261008" / "GAME4_CALIBRATION_SOURCE_VERIFICATION.json").resolve()
    if source_verification != expected_source:
        raise ValueError("NONCANONICAL_CALIBRATION_SOURCE_VERIFICATION")
    prepared_dir = Path(prepared_dir).resolve()
    player_dir = Path(player_dir).resolve()
    prepared = _read(prepared_dir / "CALIBRATION_INPUT_MANIFEST.json")
    if (prepared.get("status") != "PREPARED_NO_CALIBRATION_RESULTS" or
            prepared.get("game") != "game_4" or prepared.get("split_role") != "CALIBRATION" or
            prepared.get("video_sha256") != source["video"]["sha256"] or
            prepared.get("source_verification_sha256") != file_sha256(source_verification) or
            prepared.get("official_test") != "NOT_ACCESSED" or
            prepared.get("game_5") != "NOT_ACCESSED"):
        raise ValueError("PREPARED_CALIBRATION_INPUTS_SCOPE_MISMATCH")
    raw_path = prepared_dir / "raw_candidates.json"
    truth_path = prepared_dir / "ground_truth_strokes.json"
    points_path = prepared_dir / "raw_candidate_ball_points.json"
    for path in (raw_path, truth_path, points_path):
        expected_hash = prepared.get("artifact_hashes", {}).get(path.name)
        if not expected_hash or file_sha256(path) != expected_hash:
            raise ValueError("PREPARED_CALIBRATION_ARTIFACT_HASH_MISMATCH")
    raw, truth, ball_points = _read(raw_path), _read(truth_path), _read(points_path)
    player_summary = _read(player_dir / "player_evidence_summary.json")
    player_jsonl = player_dir / "player_evidence_frames.jsonl"
    if (player_summary.get("status") != "COMPLETE" or
            player_summary.get("video_sha256") != source["video"]["sha256"] or
            player_summary.get("source_verification_sha256") != file_sha256(source_verification) or
            player_summary.get("scene_manifest_sha256", "").lower() != FROZEN_MANIFEST_SHA.lower() or
            player_summary.get("game_5") != "NOT_ACCESSED" or
            player_summary.get("official_test") != "NOT_ACCESSED" or not player_jsonl.is_file()):
        raise ValueError("CALIBRATION_PLAYER_EVIDENCE_SCOPE_MISMATCH")
    by_frame = {}
    for line in player_jsonl.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            frame = int(row["source_frame"])
            if frame in by_frame or row.get("video_sha256") != source["video"]["sha256"]:
                raise ValueError("DUPLICATE_OR_MISMATCHED_PLAYER_EVIDENCE_FRAME")
            if abs(float(row["timestamp_ms"]) - frame * 1000.0 / 120.0) > 0.001:
                raise ValueError("PLAYER_EVIDENCE_CANONICAL_TIME_MISMATCH")
            by_frame[frame] = row
    candidate_frames = {int(row["source_frame"]) for row in raw}
    if set(by_frame) != candidate_frames:
        raise ValueError("PLAYER_EVIDENCE_DOES_NOT_MATCH_RAW_CANDIDATE_NEIGHBORHOODS")

    d_config_path = (dev_root / "evidence" / "hit_event_v0_3" /
                     "ablation-ABCD-20261008" / "V03_DEV_EXPERIMENT_CONFIG.json")
    if (file_sha256(d_config_path).lower() != EXPECTED_D_CONFIG_SHA256 or
            prepared.get("dev_selected_d_config_sha256", "").lower() != EXPECTED_D_CONFIG_SHA256):
        raise ValueError("DEV_SELECTED_D_CONFIG_SHA_CHANGED")
    d_config = _read(d_config_path)
    if d_config != CONFIG_MODES or prepared.get("dev_selected_d_config") != CONFIG_MODES:
        raise ValueError("DEV_SELECTED_D_CONFIG_CONTENT_CHANGED")
    product_config_path = PRODUCT / "configs" / "evidence-fusion" / "HIT_EVENT_V0_2_DRAFT_CONFIG.json"
    prior_path = PRODUCT / "configs" / "evidence-fusion" / "HIT_EVENT_V0_2_DEV_PRIORS.json"
    config_data = _read(product_config_path)
    if config_data != prepared.get("hit_event_v02_config"):
        raise ValueError("HIT_EVENT_V02_CONFIG_CHANGED_AFTER_PREPARATION")
    config = HitEventV02Config.from_dict(config_data)
    prior_data = _read(prior_path)["within_derived_rally_stroke_intervals_ms"]
    prior = StrokeIntervalPrior(
        sample_count=int(prior_data["sample_count"]), minimum_ms=float(prior_data["min"]),
        p1_ms=float(prior_data["p1"]), p5_ms=float(prior_data["p5"]),
        median_ms=float(prior_data["median"]), p95_ms=float(prior_data["p95"]),
    )
    table_bbox = player_summary.get("table_bbox")
    player_features, candidate_rows = _candidate_player_features(raw, ball_points, by_frame)
    duration_s = float(prepared["media"]["duration"])
    fps = float(prepared["media"]["fps"])
    tolerances = {f"plus_minus_{count}_processing_frames": count * 1000.0 / fps
                  for count in (1, 2, 3)}
    mode_results = {}
    for mode in ("A", "D"):
        adjusted = []
        for candidate in raw:
            frame = int(candidate["source_frame"])
            point = ball_points[str(frame)]
            player = player_features.get(frame) if mode == "D" else None
            adjusted.append(soft_adjustment(candidate, ball_point=tuple(point) if point else None,
                                            table=table_bbox if mode == "D" else None,
                                            player=player, mode=mode, config=d_config))
        clustered = TemporalCandidateClusterer(config.cluster_window_ms).cluster(adjusted)
        decoded = HitSequenceDecoder(config, prior).decode(clustered["kept"])
        review_candidates = decoded["accepted"] + decoded["review_candidates"]
        automatic_metrics = evaluate_hit_events(decoded["accepted"], truth,
                                                tolerances_ms=tolerances)
        review_metrics = evaluate_hit_events(review_candidates, truth,
                                             tolerances_ms=tolerances)
        automatic_summary = _metric_summary(automatic_metrics, duration_s)
        review_summary = _metric_summary(review_metrics, duration_s)
        automatic_summary["review_candidates"] = review_summary["review_candidates"]
        automatic_summary["review_candidates_per_minute"] = review_summary["review_candidates_per_minute"]
        automatic_summary["estimated_review_minutes_per_45_minute_match"] = (
            review_summary["estimated_review_minutes_per_45_minute_match"])
        mode_results[mode] = {
            "automatic_metrics": automatic_metrics,
            "review_mode_metrics": review_metrics,
            "summary": automatic_summary,
            "review_summary": review_summary,
            "candidate_counts": {"raw": len(raw), "clustered": len(clustered["kept"]),
                                 "cluster_suppressed": len(clustered["suppressed"]),
                                 "accepted": len(decoded["accepted"]),
                                 "decoder_removed": len(decoded["suppressed"]),
                                 "review_queue": len(decoded["review_candidates"]),
                                 "accepted_plus_review": len(review_candidates)},
            "decoder": decoded,
            "clustered": clustered,
        }

    two = "plus_minus_2_processing_frames"
    a, d = mode_results["A"]["summary"], mode_results["D"]["summary"]
    deltas = {key: d[key] - a[key] for key in ("precision", "recall", "f1",
                                                 "fp_per_minute", "fn_per_minute",
                                                 "review_candidates_per_minute",
                                                 "estimated_review_minutes_per_45_minute_match")}
    coverage = _player_coverage(raw, by_frame, table_bbox, ball_points)
    output_parent = source_verification.parent
    target = output_parent / "CALIBRATION_FIRST_PASS_UNTOUCHED"
    if target.exists():
        raise FileExistsError("CALIBRATION_FIRST_PASS_UNTOUCHED_ALREADY_EXISTS")
    staging = Path(tempfile.mkdtemp(prefix="CALIBRATION_FIRST_PASS_UNTOUCHED.pending-",
                                    dir=output_parent))
    try:
        artifacts = {}
        for mode in ("A", "D"):
            for suffix, value in (("decoded", mode_results[mode]["decoder"]),
                                  ("clustered", mode_results[mode]["clustered"]),
                                  ("metrics", {"automatic": mode_results[mode]["automatic_metrics"],
                                               "review_mode": mode_results[mode]["review_mode_metrics"],
                                               "summary": mode_results[mode]["summary"],
                                               "review_summary": mode_results[mode]["review_summary"],
                                               "candidate_counts": mode_results[mode]["candidate_counts"]})):
                path = staging / f"{mode}_{suffix}.json"
                artifacts[path.name] = immutable_json(path, value)
        player_evidence_path = staging / "candidate_player_evidence.jsonl"
        with player_evidence_path.open("x", encoding="utf-8", newline="\n") as stream:
            for frame in sorted(candidate_rows):
                stream.write(json.dumps(candidate_rows[frame], ensure_ascii=False,
                                         separators=(",", ":")) + "\n")
        artifacts[player_evidence_path.name] = file_sha256(player_evidence_path)
        report = {
            "schema": "ptti-hit-event-v0.3-game4-first-pass-v1",
            "status": "CALIBRATION_FIRST_PASS_UNTOUCHED",
            "branch": "research/hit-v03-event-disambiguation",
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=PRODUCT.parent, text=True).strip(),
            "game": "game_4", "official_split": "TRAIN", "split_role": "CALIBRATION",
            "dataset": source["dataset"], "dataset_revision": source["dataset_revision"],
            "license": source["license"], "commercial_use": False,
            "video_sha256": source["video"]["sha256"],
            "annotation_sha256": source["annotation"]["sha256"],
            "source_verification_sha256": file_sha256(source_verification),
            "prepared_manifest_sha256": file_sha256(prepared_dir / "CALIBRATION_INPUT_MANIFEST.json"),
            "player_evidence_summary_sha256": file_sha256(player_dir / "player_evidence_summary.json"),
            "player_evidence_frames_sha256": file_sha256(player_jsonl),
            "scene_manifest_sha256": player_summary["scene_manifest_sha256"],
            "balltrack": "BALLTRACK_V1_FROZEN_RAW",
            "balltrack_checkpoint_sha256": prepared["balltrack_checkpoint_sha256"],
            "balltrack_csv_sha256": prepared["balltrack_csv_sha256"],
            "d_config": d_config, "d_config_file_sha256": file_sha256(d_config_path),
            "d_config_canonical_sha256": canonical_config_sha256(d_config),
            "hit_event_v02_config": config_data,
            "hit_event_v02_config_sha256": file_sha256(product_config_path),
            "dev_prior_sha256": file_sha256(prior_path),
            "media": prepared["media"], "timeline_audit": prepared["timeline_audit"],
            "gt_strokes": len(truth), "raw_candidates": len(raw),
            "unique_candidate_neighborhoods": len(candidate_frames),
            "primary_tolerance": {"name": two, "milliseconds": tolerances[two]},
            "tolerances_ms": tolerances,
            "A_ball_only": mode_results["A"]["summary"],
            "D_ball_table_player": mode_results["D"]["summary"],
            "D_minus_A": deltas,
            "A_all_tolerances": mode_results["A"]["automatic_metrics"]["by_tolerance"],
            "D_all_tolerances": mode_results["D"]["automatic_metrics"]["by_tolerance"],
            "A_review_all_tolerances": mode_results["A"]["review_mode_metrics"]["by_tolerance"],
            "D_review_all_tolerances": mode_results["D"]["review_mode_metrics"]["by_tolerance"],
            "player_and_table_evidence_coverage": coverage,
            "player_detector_runtime": player_summary.get("runtime"),
            "player_model_provenance": player_summary.get("model_provenance"),
            "pose": "OFF", "unknown_role_fallback": "NEUTRAL",
            "parameter_tuning_before_this_pass": False,
            "variants_tested_before_first_pass": 0,
            "game_5": "NOT_ACCESSED", "official_test": "NOT_ACCESSED",
            "production_database": "NOT_ACCESSED",
            "artifact_sha256": dict(artifacts),
        }
        main_path = staging / "CALIBRATION_FIRST_PASS_UNTOUCHED.json"
        artifacts[main_path.name] = immutable_json(main_path, report)
        rows = ["<!doctype html><html lang='zh-CN'><meta charset='utf-8'>",
                "<title>PTTI game_4 calibration first pass</title>",
                "<h1>game_4 校准首轮（不可覆盖）</h1>",
                "<p>仅比较冻结 D 与 A；无参数调整；Pose 关闭；未知角色中性回退。</p>",
                "<table><tr><th>模式</th><th>TP</th><th>FP</th><th>FN</th><th>Precision</th><th>Recall</th><th>F1</th><th>FP/min</th><th>Review/min</th></tr>"]
        for name, label in (("A", "A · Ball-only"), ("D", "D · Ball+Table+Player")):
            s = mode_results[name]["summary"]
            rows.append("<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in
                (label, s["tp"], s["fp"], s["fn"], f'{s["precision"]:.4f}', f'{s["recall"]:.4f}',
                 f'{s["f1"]:.4f}', f'{s["fp_per_minute"]:.3f}',
                 f'{s["review_candidates_per_minute"]:.3f}')) + "</tr>")
        rows.append("</table><h2>完整指标与证据覆盖</h2><pre>" +
                    html.escape(json.dumps(report, ensure_ascii=False, indent=2)) + "</pre></html>")
        html_path = staging / "CALIBRATION_FIRST_PASS_UNTOUCHED.html"
        with html_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write("\n".join(rows))
        artifacts[html_path.name] = file_sha256(html_path)
        manifest_path = staging / "artifact_manifest.json"
        immutable_json(manifest_path, {"status": "IMMUTABLE_FIRST_PASS",
                                       "artifacts": artifacts,
                                       "game_5": "NOT_ACCESSED",
                                       "official_test": "NOT_ACCESSED"})
        os.rename(staging, target)
    except Exception:
        # Leave the uniquely named pending directory intact for forensic review;
        # it is never mistaken for a completed, immutable first pass.
        raise
    print(json.dumps({"first_pass": str(target), "A": a, "D": d,
                      "D_minus_A": deltas}, ensure_ascii=False, indent=2), flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-verification", type=Path, required=True)
    parser.add_argument("--prepared-dir", type=Path, required=True)
    parser.add_argument("--player-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.source_verification, args.prepared_dir, args.player_dir)


if __name__ == "__main__":
    main()
