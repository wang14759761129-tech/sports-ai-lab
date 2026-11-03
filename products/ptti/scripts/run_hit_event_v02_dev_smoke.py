"""Run a non-tuning smoke check on already cached v0.1 DEV frame evidence.

This explicitly does not substitute for whole-video DEV evaluation. It never
reads calibration or holdout event timings and never accesses official TEST.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import sys
import time

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

from backend.evidence_fusion import aggregate_hit_evaluations, evaluate_hit_events
from backend.extended_openttgames import ExtendedOpenTTGamesAdapter, derive_rally_ground_truth
from backend.hit_event_v02 import HitEventV02Config, StrokeIntervalPrior, build_hit_event_pipeline


LOCAL = Path.home() / "AppData" / "Local" / "PTTI-Dev"
EVALUATION_ROOT = LOCAL / "vision-v2-evidence-fusion" / "evaluation"
OUTPUT_ROOT = LOCAL / "vision-v2-evidence-fusion" / "v0.2-dev-smoke"
CONFIG_PATH = PRODUCT_ROOT / "configs" / "evidence-fusion" / "HIT_EVENT_V0_2_DRAFT_CONFIG.json"
PRIOR_PATH = PRODUCT_ROOT / "configs" / "evidence-fusion" / "HIT_EVENT_V0_2_DEV_PRIORS.json"
SPLIT_PATH = PRODUCT_ROOT / "configs" / "evidence-fusion" / "HIT_EVENT_V0_2_SPLIT.json"
ANNOTATIONS = LOCAL / "research-datasets" / "ExtendedOpenTTGames" / "annotations" / "train" / "game_data"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _latest_complete_dev_run() -> Path:
    required = {"game_1-t60", "game_2-t60", "game_3-t60"}
    candidates = []
    for path in EVALUATION_ROOT.glob("dev/*"):
        if not path.is_dir():
            continue
        if all((path / sample / "frame_evidence.jsonl").is_file() and
               (path / sample / "ground_truth_strokes.json").is_file() and
               (path / sample / "clip_manifest.json").is_file() for sample in required):
            candidates.append(path)
    if not candidates:
        raise FileNotFoundError("CACHED_V01_DEV_EVIDENCE_NOT_FOUND")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _matched_ground_truth_indices(evaluation: dict) -> set[int]:
    rows = evaluation["by_tolerance"]["plus_minus_2_processing_frames"]["matches"]
    return {int(row["ground_truth_index"]) for row in rows}


def _nearest_candidate(candidate_rows: list[dict], truth_row: dict, tolerance_ms: float) -> dict | None:
    if not candidate_rows:
        return None
    target = float(truth_row["timestamp_ms"])
    candidate = min(candidate_rows, key=lambda row: abs(float(row["timestamp_ms"]) - target))
    delta = float(candidate["timestamp_ms"]) - target
    return {
        "event_id": candidate.get("event_id"),
        "timestamp_ms": candidate.get("timestamp_ms"),
        "delta_ms": round(delta, 6),
        "within_plus_minus_2_frames": abs(delta) <= tolerance_ms + 0.001,
        "evidence_score": candidate.get("evidence_score"),
        "candidate_player": candidate.get("candidate_player"),
        "identity_status": candidate.get("identity_status"),
        "ball_quality": candidate.get("ball_quality"),
        "filter_reason": candidate.get("filter_reason"),
        "evidence_components": candidate.get("evidence_components"),
    }


def _ground_truth_stage_diagnostics(truth_rows: list[dict], *, raw: list[dict], clustered: list[dict],
                                    decoded: list[dict], review: list[dict],
                                    raw_evaluation: dict, clustered_evaluation: dict,
                                    decoded_evaluation: dict, tolerance_ms: float,
                                    cluster_suppressed: list[dict], decoder_suppressed: list[dict]) -> list[dict]:
    matched = {
        "RAW": _matched_ground_truth_indices(raw_evaluation),
        "CLUSTERED": _matched_ground_truth_indices(clustered_evaluation),
        "DECODED": _matched_ground_truth_indices(decoded_evaluation),
    }
    cluster_drops = {str(row.get("event_id")): row for row in cluster_suppressed}
    decoder_drops = {str(row.get("event_id")): row for row in decoder_suppressed}
    diagnostics = []
    for index, gt in enumerate(truth_rows):
        nearest = {
            "RAW": _nearest_candidate(raw, gt, tolerance_ms),
            "CLUSTERED": _nearest_candidate(clustered, gt, tolerance_ms),
            "DECODED": _nearest_candidate(decoded, gt, tolerance_ms),
            "REVIEW_QUEUE": _nearest_candidate(review, gt, tolerance_ms),
        }
        if index not in matched["RAW"]:
            loss_stage = "RAW_GENERATOR_MISS"
        elif index not in matched["CLUSTERED"]:
            loss_stage = "TEMPORAL_CLUSTER_LOSS"
        elif index not in matched["DECODED"]:
            loss_stage = "SEQUENCE_DECODER_LOSS"
        else:
            loss_stage = "MATCHED"
        rejection = None
        if loss_stage == "TEMPORAL_CLUSTER_LOSS" and nearest["RAW"]:
            rejection = cluster_drops.get(str(nearest["RAW"]["event_id"]))
        elif loss_stage == "SEQUENCE_DECODER_LOSS" and nearest["CLUSTERED"]:
            rejection = decoder_drops.get(str(nearest["CLUSTERED"]["event_id"]))
        diagnostics.append({
            "ground_truth_index": index,
            "event_id": gt.get("event_id"),
            "timestamp_ms": gt.get("timestamp_ms"),
            "source_frame": gt.get("source_frame"),
            "player_role": gt.get("player_role"),
            "technique": gt.get("technique"),
            "stage_status": {stage: ("FOUND" if index in matched[stage] else "MISSED")
                             for stage in ("RAW", "CLUSTERED", "DECODED")},
            "elimination_stage": loss_stage,
            "nearest_candidates_by_stage": nearest,
            "decoder_rejection": ({
                "decision": rejection.get("decision"),
                "rejection_reasons": rejection.get("rejection_reasons", []),
                "decoder_trace": rejection.get("decoder_trace"),
            } if rejection else None),
        })
    return diagnostics


def run() -> dict:
    split_bytes = SPLIT_PATH.read_bytes()
    split_sha = hashlib.sha256(split_bytes).hexdigest()
    expected_sha = SPLIT_PATH.with_suffix(SPLIT_PATH.suffix + ".sha256").read_text(encoding="utf-8").split()[0]
    if split_sha != expected_sha:
        raise ValueError("HIT_EVENT_V02_SPLIT_MANIFEST_HASH_MISMATCH")
    split = json.loads(split_bytes)
    if split["official_test_split"] != "NOT_ACCESSED" or split["production_database"] != "NOT_ACCESSED":
        raise ValueError("RESEARCH_ISOLATION_MANIFEST_INVALID")
    config = HitEventV02Config.from_dict(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    prior_value = json.loads(PRIOR_PATH.read_text(encoding="utf-8"))["within_derived_rally_stroke_intervals_ms"]
    prior = StrokeIntervalPrior(
        sample_count=prior_value["sample_count"], minimum_ms=prior_value["min"],
        p1_ms=prior_value["p1"], p5_ms=prior_value["p5"], median_ms=prior_value["median"],
        p95_ms=prior_value["p95"],
    )
    source_run = _latest_complete_dev_run()
    outputs, stage_results = [], {"raw": [], "clustered": [], "filtered": []}
    for sample_id in ("game_1-t60", "game_2-t60", "game_3-t60"):
        sample = source_run / sample_id
        manifest = json.loads((sample / "clip_manifest.json").read_text(encoding="utf-8"))
        if manifest.get("official_split") != "TRAIN" or manifest.get("match_id") not in split["split_policy"]["development"]:
            raise ValueError("SMOKE_INPUT_OUTSIDE_LOCKED_DEV_SPLIT")
        frames = _read_jsonl(sample / "frame_evidence.jsonl")
        truth = json.loads((sample / "ground_truth_strokes.json").read_text(encoding="utf-8"))
        if len(frames) != manifest.get("timeline_audit", {}).get("processing_frames"):
            raise ValueError("SMOKE_FRAME_EVIDENCE_COUNT_MISMATCH")
        if any(frame.get("video_sha256") != manifest.get("video_sha256") for frame in frames):
            raise ValueError("SMOKE_FRAME_EVIDENCE_SOURCE_MISMATCH")
        inference_started = time.perf_counter()
        pipeline = build_hit_event_pipeline(frames, config, prior)
        inference_seconds = time.perf_counter() - inference_started
        processing_fps = float(manifest["timeline_audit"]["processing_fps"])
        tolerances = {f"plus_minus_{frames_count}_processing_frames": frames_count * 1000 / processing_fps
                      for frames_count in (1, 2, 3)}
        raw_evaluation = evaluate_hit_events(pipeline["raw_candidates"], truth, tolerances_ms=tolerances)
        clustered_evaluation = evaluate_hit_events(pipeline["clustered_candidates"], truth,
                                                   tolerances_ms=tolerances)
        evaluation = evaluate_hit_events(pipeline["filtered_candidates"], truth, tolerances_ms=tolerances)
        review_queue_candidates = pipeline["filtered_candidates"] + pipeline["decoder_review_candidates"]
        review_queue_evaluation = evaluate_hit_events(review_queue_candidates, truth,
                                                      tolerances_ms=tolerances)
        stage_results["raw"].append((sample_id, raw_evaluation))
        stage_results["clustered"].append((sample_id, clustered_evaluation))
        stage_results["filtered"].append((sample_id, evaluation))
        duration_ms = float(manifest["timeline_audit"]["processing_frames"]) * 1000 / processing_fps
        annotation_path = ANNOTATIONS / f"{manifest['match_id']}.json"
        native_events = ExtendedOpenTTGamesAdapter(fps=120.0).parse(
            json.loads(annotation_path.read_text(encoding="utf-8")))
        derived_rallies = derive_rally_ground_truth(native_events)
        clip_start_frame = int(manifest["timeline_audit"]["source_frame_start"])
        clip_end_frame = int(manifest["timeline_audit"]["source_frame_end"])
        rally_count = sum(1 for segment in derived_rallies["segments"]
                          if int(segment["start_frame"]) <= clip_end_frame and
                          int(segment["end_frame"]) >= clip_start_frame)
        filtered_two = evaluation["by_tolerance"]["plus_minus_2_processing_frames"]
        tolerance_ms = 2 * 1000 / processing_fps
        row = {
            "sample_id": sample_id, "match_id": manifest["match_id"],
            "official_split": "TRAIN", "video_sha256": manifest["video_sha256"],
            "source_run": str(source_run), "frame_count": len(frames),
            "duration_ms": duration_ms, "ground_truth_count": len(truth),
            "derived_gt_rallies_intersecting_clip": rally_count,
            "video_path": manifest["video_path"],
            "clip_start_timestamp_ms": manifest["timeline_audit"]["first_timestamp_ms"],
            "inference_seconds": inference_seconds,
            "pipeline_counts": pipeline["counts"], "evaluation": evaluation,
            "raw_evaluation": raw_evaluation, "clustered_evaluation": clustered_evaluation,
            "review_queue_potential_evaluation": review_queue_evaluation,
            "ground_truth_stage_diagnostics": _ground_truth_stage_diagnostics(
                truth, raw=pipeline["raw_candidates"], clustered=pipeline["clustered_candidates"],
                decoded=pipeline["filtered_candidates"], review=pipeline["decoder_review_candidates"],
                raw_evaluation=raw_evaluation, clustered_evaluation=clustered_evaluation,
                decoded_evaluation=evaluation, tolerance_ms=tolerance_ms,
                cluster_suppressed=pipeline["cluster_suppressed"],
                decoder_suppressed=pipeline["decoder_suppressed"]),
            "decoder_review_candidate_count": len(pipeline["decoder_review_candidates"]),
            "review_burden_per_minute": round(
                len(pipeline["filtered_candidates"]) / max(duration_ms / 60_000, 1e-9), 4),
            "false_positives_per_rally_at_plus_minus_2": round(
                filtered_two["false_positives"] / max(rally_count, 1), 4),
            "max_timing_error_ms_at_plus_minus_2": max(
                (abs(float(match["signed_timing_error_ms"]))
                 for match in filtered_two.get("matches", [])), default=None),
            "raw_candidates": pipeline["raw_candidates"],
            "clustered_candidates": pipeline["clustered_candidates"],
            "filtered_candidates": pipeline["filtered_candidates"],
            "cluster_suppressed": pipeline["cluster_suppressed"],
            "decoder_suppressed": pipeline["decoder_suppressed"],
            "decoder_review_candidates": pipeline["decoder_review_candidates"],
        }
        outputs.append(row)
    aggregates = {stage: aggregate_hit_evaluations(values) for stage, values in stage_results.items()}
    aggregate = aggregates["filtered"]
    total_duration_ms = sum(row["duration_ms"] for row in outputs)
    at_two = aggregate["by_tolerance"]["plus_minus_2_processing_frames"]
    result = {
        "status": "DEV_SMOKE_ONLY_INSUFFICIENT_FOR_TUNING",
        "purpose": "algorithm wiring smoke check only; no threshold tuning on the prior 10-second samples",
        "dataset": "Extended OpenTTGames", "dataset_revision": split["dataset_revision"],
        "license": "CC BY-NC-SA 4.0", "commercial_use": False,
        "official_split": "TRAIN_DEV_ONLY", "official_test_split": "NOT_ACCESSED",
        "production_database": "NOT_ACCESSED", "calibration_game": "NOT_ACCESSED",
        "internal_holdout": "NOT_ACCESSED",
        "historical_exposure_caveat": split["split_policy"]["historical_exposure"],
        "split_manifest_sha256": split_sha,
        "source_v01_dev_run": str(source_run),
        "config": config.as_dict(), "config_status": config.status,
        "config_sha256": pipeline["config_sha256"], "stroke_interval_prior": prior.as_dict(),
        "stage_aggregates": aggregates,
        "dev_sample_counts": [
            {"sample_id": row["sample_id"], "gt_strokes": row["ground_truth_count"],
             "raw": row["pipeline_counts"]["raw"], "clustered": row["pipeline_counts"]["clustered"],
             "decoded": row["pipeline_counts"]["decoded"],
             "review_queue": row["decoder_review_candidate_count"],
             "derived_gt_rallies_intersecting_clip": row["derived_gt_rallies_intersecting_clip"]}
            for row in outputs],
        "aggregate_smoke_metrics": aggregate,
        "fp_per_minute_at_plus_minus_2_frames": round(
            at_two["false_positives"] / max(total_duration_ms / 60_000, 1e-9), 4),
        "clips": outputs,
        "limitations": [
            "Only previously processed 10-second slices were available at this smoke-run time.",
            "The 7 DEV-slice strokes are insufficient for tuning or validation.",
            "Review-queue potential is post-hoc diagnostics, not a human-reviewed or automated result.",
            "The config remains DRAFT_DEV_ONLY; no calibration or holdout evaluation has run.",
            "No official TEST annotation or video was opened.",
        ],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    destination = OUTPUT_ROOT / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "hit_event_v0_2_dev_smoke.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = ["<!doctype html><html lang='zh-CN'><meta charset='utf-8'>",
            "<title>PTTI Hit Event v0.2 DEV smoke</title>",
            "<style>body{font:15px 'Microsoft YaHei',sans-serif;max-width:1050px;margin:32px auto;color:#18212b}"
            "table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}</style>",
            "<h1>Hit Event v0.2 · DEV wiring smoke</h1>",
            "<p>仅验证代码链路；不是完整 DEV 评估，不用于调参。配置仍为 DRAFT_DEV_ONLY。</p>",
            f"<p>split SHA256: <code>{html.escape(split_sha)}</code></p>",
            "<table><tr><th>片段</th><th>GT stroke</th><th>Raw</th><th>Clustered</th>"
            "<th>Decoded</th><th>复核建议</th></tr>"]
    for row in result["dev_sample_counts"]:
        rows.append("<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in row.values()) + "</tr>")
    rows.append("</table><h2>Stage metrics</h2><pre>" +
                 html.escape(json.dumps({key: value["by_tolerance"]["plus_minus_2_processing_frames"]
                                         for key, value in aggregates.items()},
                                        ensure_ascii=False, indent=2)) + "</pre></html>")
    (destination / "hit_event_v0_2_dev_smoke.html").write_text("\n".join(rows), encoding="utf-8")
    print(json.dumps({"status": result["status"], "output_dir": str(destination),
                      "samples": result["dev_sample_counts"],
                      "plus_minus_2_frames": at_two,
                      "fp_per_minute": result["fp_per_minute_at_plus_minus_2_frames"]},
                     ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    run()
