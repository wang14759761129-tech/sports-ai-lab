"""Run TRAIN-only BallTrack + player/pose hit-event evidence fusion.

All research inputs and outputs remain under PTTI-Dev. The official dataset
test split and Production database are not used by this runner.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import sys

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

from backend.evidence_fusion import (
    CanonicalVideoTimeline,
    DatasetSideMapping,
    EvidenceFusionConfig,
    HitCandidateEngine,
    adapt_training_strokes,
    aggregate_hit_evaluations,
    build_frame_evidence,
    configuration_sha256,
    evaluate_hit_events,
)
from backend.fullmatch import extract_source_frame_timestamps
from backend.player_motion import pose_file_sha256
from vision.quality import video_metadata


LOCAL = Path.home() / "AppData" / "Local" / "PTTI-Dev"
DATASET = LOCAL / "research-datasets" / "ExtendedOpenTTGames"
CLIPS = LOCAL / "vision-v2-sam2" / "datasets" / "extended-openttgames"
TRACK_JOBS = LOCAL / "vision-v2-sam2" / "runs" / "closed-loop" / "jobs"
POSE_JOBS = LOCAL / "vision-v2-rtmpose" / "runs" / "jobs"
BALL_RUNS = LOCAL / "vision-v2-evidence-fusion" / "balltrack-runs"
OUTPUT_ROOT = LOCAL / "vision-v2-evidence-fusion" / "evaluation"
CONFIG_PATH = PRODUCT_ROOT / "configs" / "evidence-fusion" / "HIT_EVENT_V0_1_CONFIG.json"
LOCK_PATH = PRODUCT_ROOT / "configs" / "evidence-fusion" / "HIT_EVENT_V0_1_LOCK.json"
EXPECTED_CHECKPOINT_SHA256 = "00d707b9db7a49561c411e4765956e79bcd7c7e20c7a0a535073440b3e972342"
DATASET_REVISION = "36471a76b969a0340df59258a813bf8214e68e7c"
SAMPLES = (
    {"game": 1, "start_seconds": 60, "sample_id": "game_1-t60", "ball_id": "20261007T023029_afee222d9ab9"},
    {"game": 2, "start_seconds": 60, "sample_id": "game_2-t60", "ball_id": "20261007T023103_7c529d4b7b10"},
    {"game": 3, "start_seconds": 60, "sample_id": "game_3-t60", "ball_id": "20261007T023132_24d9bf560a1b"},
    {"game": 4, "start_seconds": 30, "sample_id": "game_4-t30", "ball_id": "20261007T023202_78a7699104ab"},
    {"game": 5, "start_seconds": 60, "sample_id": "game_5-t60", "ball_id": "20261007T023232_d3418a2deff0"},
)


def sha256(path: Path) -> str:
    return pose_file_sha256(path)


def _side_mapping(game: int) -> DatasetSideMapping:
    mappings = {
        2: {"left": "FAR_PLAYER", "right": "NEAR_PLAYER"},
        3: {"left": "NEAR_PLAYER", "right": "FAR_PLAYER"},
        4: {"left": "FAR_PLAYER", "right": "NEAR_PLAYER"},
        5: {"left": "NEAR_PLAYER", "right": "FAR_PLAYER"},
    }
    mapping = mappings.get(game, {"left": "FAR_PLAYER", "right": "NEAR_PLAYER"})
    review = game in mappings
    return DatasetSideMapping(
        match_id=f"game_{game}", dataset_side_to_role=mapping,
        source="Extended OpenTTGames frame-keyed left/right stroke labels",
        evidence=("Manually compared the exact annotated stroke frame with the source clip and the "
                  "seed-confirmed PTTI Near/Far tracks; mapping is per match and based on visible "
                  "screen-side positions." if review else "No labeled stroke occurs in this reviewed clip window."),
        review_status="HUMAN_REVIEWED" if review else "UNREVIEWED",
    )


def _ball_analysis(sample: dict) -> tuple[dict, Path]:
    analysis_path = BALL_RUNS / sample["ball_id"] / "analysis.json"
    result = json.loads(analysis_path.read_text(encoding="utf-8"))
    video = CLIPS / f"game_{sample['game']}_t{sample['start_seconds']}_10s.mp4"
    digest = sha256(video)
    provenance = result.get("provenance", {})
    if provenance.get("video_sha256") != digest:
        raise ValueError(f"BALLTRACK_VIDEO_HASH_MISMATCH:{sample['sample_id']}")
    if provenance.get("checkpoint_sha256") != EXPECTED_CHECKPOINT_SHA256:
        raise ValueError("BALLTRACK_CHECKPOINT_NOT_FROZEN_RAW")
    if provenance.get("racketvision_commit") != "c44af2a08524d3cb54d818f19686f4cdea4d2793":
        raise ValueError("BALLTRACK_UPSTREAM_COMMIT_MISMATCH")
    return result, analysis_path.parent


def _pose_tracking(sample: dict) -> tuple[dict, dict, Path, Path]:
    pose_candidates = []
    for path in POSE_JOBS.glob("*/player_motion.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        if (value.get("sample_id") == sample["sample_id"] and
                value.get("official_split") == "TRAIN"):
            pose_candidates.append((value, path))
    if not pose_candidates:
        raise FileNotFoundError(f"POSE_TRAIN_RESULT_NOT_FOUND:{sample['sample_id']}")
    pose_candidates.sort(key=lambda row: row[1].stat().st_mtime_ns)
    pose, pose_path = pose_candidates[-1]
    tracking_path = TRACK_JOBS / str(pose["tracking_job_id"]) / "tracking.json"
    tracking = json.loads(tracking_path.read_text(encoding="utf-8"))
    digest = sha256(CLIPS / f"game_{sample['game']}_t{sample['start_seconds']}_10s.mp4")
    if pose.get("source_sha256") != digest or tracking.get("source_sha256") != digest:
        raise ValueError(f"PLAYER_EVIDENCE_VIDEO_HASH_MISMATCH:{sample['sample_id']}")
    if tracking.get("dataset") != "Extended OpenTTGames" or tracking.get("commercial_use") is not False:
        raise ValueError("PLAYER_EVIDENCE_PROVENANCE_INVALID")
    return pose, tracking, pose_path, tracking_path


def _tolerances(processing_fps: float) -> dict[str, float]:
    frame_ms = 1000.0 / processing_fps
    return {"plus_minus_1_processing_frame": frame_ms,
            "plus_minus_2_processing_frames": 2 * frame_ms,
            "plus_minus_3_processing_frames": 3 * frame_ms}


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _render_html(path: Path, phase: str, summary: dict, per_clip: list[dict], config_sha: str) -> None:
    lines = ["<!doctype html><html lang='zh-CN'><meta charset='utf-8'>",
             "<title>PTTI 击球候选证据融合</title>",
             "<style>body{font:15px 'Microsoft YaHei',sans-serif;max-width:1180px;margin:32px auto;color:#18212b}"
             "table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}"
             "pre{white-space:pre-wrap;overflow-wrap:anywhere}.warn{color:#8a5b00}</style>",
             f"<h1>击球候选 · {html.escape(phase.upper())}</h1>",
             "<p>输出是待复核候选，不是确认击球，也不是校准概率。数据限 Extended OpenTTGames 官方 TRAIN，CC BY-NC-SA 4.0。</p>",
             f"<p>冻结配置 SHA256：<code>{html.escape(config_sha)}</code></p>",
             "<h2>逐容差汇总</h2><table><tr><th>容差</th><th>候选</th><th>GT stroke</th><th>匹配</th><th>FP</th><th>FN</th><th>Precision</th><th>Recall</th><th>F1</th><th>时间误差中位数 / P90</th><th>击球方准确率</th></tr>"]
    for label, row in summary["by_tolerance"].items():
        values = [label, row["predicted"], row["ground_truth"], row["matched"], row["false_positives"],
                  row["false_negatives"], row["precision"], row["recall"], row["f1"],
                  f"{row['median_absolute_timing_error_ms']} / {row['p90_absolute_timing_error_ms']}",
                  row["player_side_accuracy"]]
        lines.append("<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in values) + "</tr>")
    lines.append("</table><h2>逐比赛结果</h2><table><tr><th>比赛</th><th>片段</th><th>帧数</th><th>stroke GT</th><th>候选数</th><th>时间戳审计</th><th>左右侧映射</th></tr>")
    for clip in per_clip:
        values = [clip["match_id"], clip["sample_id"], clip["timeline_audit"]["processing_frames"],
                  len(clip["ground_truth"]), len(clip["predictions"]), clip["alignment_audit"]["status"],
                  clip["side_mapping"]["review_status"]]
        lines.append("<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in values) + "</tr>")
    lines.append("</table><h2>解释</h2><pre>" + html.escape(json.dumps(summary, ensure_ascii=False, indent=2)) + "</pre></html>")
    path.write_text("\n".join(lines), encoding="utf-8")


def run(phase: str) -> dict:
    config_value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config = EvidenceFusionConfig.from_dict(config_value)
    config_sha = configuration_sha256(config)
    if phase == "validation":
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        if lock.get("locked") is not True or lock.get("config_sha256") != config_sha:
            raise ValueError("VALIDATION_REQUIRES_FROZEN_CONFIG_HASH")
    allowed = {1, 2, 3} if phase == "dev" else {4, 5}
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    destination = OUTPUT_ROOT / phase / run_id
    destination.mkdir(parents=True, exist_ok=False)
    engine = HitCandidateEngine(config)
    tolerances = _tolerances(30.0)
    per_clip = []
    for sample in SAMPLES:
        if sample["game"] not in allowed:
            continue
        clip = CLIPS / f"game_{sample['game']}_t{sample['start_seconds']}_10s.mp4"
        game_annotations_path = DATASET / "annotations" / "train" / "game_data" / f"game_{sample['game']}.json"
        video_digest = sha256(clip)
        ball_analysis, ball_root = _ball_analysis(sample)
        pose, tracking, pose_path, tracking_path = _pose_tracking(sample)
        metadata = video_metadata(clip)
        if metadata.get("frame_count") != 300 or abs(float(metadata["fps"]) - 30.0) > .02:
            raise ValueError(f"UNEXPECTED_PROCESSING_VIDEO_TIMELINE:{sample['sample_id']}")
        if tracking.get("source_fps") != 120 or pose.get("official_split") != "TRAIN":
            raise ValueError(f"UNEXPECTED_SOURCE_RATE_OR_SPLIT:{sample['sample_id']}")
        pts = extract_source_frame_timestamps(clip, metadata["frame_count"])
        start_frame = sample["start_seconds"] * 120
        timeline = CanonicalVideoTimeline(
            video_sha256=video_digest, source_fps=120, processing_fps=float(metadata["fps"]),
            source_frame_start=start_frame, clip_start_timestamp_ms=sample["start_seconds"] * 1000.0,
            processing_pts_ms=pts, clip_duration_ms=float(metadata["duration"]) * 1000.0,
        )
        ball_rows = json.loads((ball_root / "ball_track.json").read_text(encoding="utf-8"))
        annotations = json.loads(game_annotations_path.read_text(encoding="utf-8"))
        side_mapping = _side_mapping(sample["game"])
        truth = adapt_training_strokes(annotations, timeline, fps=120.0, side_mapping=side_mapping)
        frames = build_frame_evidence(
            timeline, ball_rows, tracking.get("records", []), pose.get("records", []),
            source_sha256s={"ball": ball_analysis["provenance"]["video_sha256"],
                            "tracking": tracking["source_sha256"], "pose": pose["source_sha256"]},
        )
        predictions = engine.suggest(frames)
        # Keep the annotation mapping explicit; do not convert native stroke
        # classes into product predictions.
        evaluation = evaluate_hit_events(predictions, truth, tolerances_ms=tolerances,
                                         side_mapping=side_mapping)
        track_deltas, pose_deltas = [], []
        for frame in frames:
            for item in frame["players"].values():
                for module, target in (("track", track_deltas), ("pose", pose_deltas)):
                    row = item[module]
                    if row is not None:
                        target.append(abs(float(row["canonical_alignment_delta_ms"])))
        alignment = {
            "status": "ALIGNED" if max(track_deltas + pose_deltas + [0]) <= 3.0 else "MISALIGNED",
            "ball_pts_max_delta_ms": max((abs(float(row["timestamp_ms"]) - pts[int(row["frame"])])
                                           for row in ball_rows), default=0.0),
            "tracking_max_delta_ms": max(track_deltas, default=None),
            "pose_max_delta_ms": max(pose_deltas, default=None),
            "source_gt_time_basis": "120 FPS source-frame rate estimate; full source PTS unavailable for all five games",
        }
        if alignment["status"] != "ALIGNED":
            raise ValueError(f"CROSS_MODULE_ALIGNMENT_FAILED:{sample['sample_id']}")
        clip_record = {
            "sample_id": sample["sample_id"], "match_id": f"game_{sample['game']}",
            "official_split": "TRAIN", "dataset": "Extended OpenTTGames",
            "rights": "CC BY-NC-SA 4.0", "commercial_use": False,
            "video_path": str(clip), "video_sha256": video_digest,
            "annotation_sha256": sha256(game_annotations_path),
            "balltrack_analysis_id": ball_analysis["analysis_id"],
            "balltrack_checkpoint_sha256": ball_analysis["provenance"]["checkpoint_sha256"],
            "tracking_job_id": tracking["job_id"], "tracking_result_sha256": sha256(tracking_path),
            "pose_result_sha256": sha256(pose_path), "timeline_audit": timeline.audit(),
            "alignment_audit": alignment, "side_mapping": side_mapping.as_dict(),
            "ground_truth": truth, "predictions": predictions, "evaluation": evaluation,
        }
        clip_dir = destination / sample["sample_id"]
        clip_dir.mkdir(parents=True, exist_ok=True)
        _write_json(clip_dir / "ground_truth_strokes.json", truth)
        _write_json(clip_dir / "hit_candidates.json", predictions)
        _write_json(clip_dir / "evaluation.json", evaluation)
        with (clip_dir / "frame_evidence.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
            for frame in frames:
                stream.write(json.dumps(frame, ensure_ascii=False, separators=(",", ":")) + "\n")
        _write_json(clip_dir / "clip_manifest.json", clip_record)
        per_clip.append(clip_record)
    summary = aggregate_hit_evaluations([(row["sample_id"], row["evaluation"])
                                         for row in per_clip])
    result = {
        "status": "CONFIG_FROZEN_VALIDATION" if phase == "validation" else "DEVELOPMENT_MEASUREMENT",
        "phase": phase, "dataset": "Extended OpenTTGames", "dataset_revision": DATASET_REVISION,
        "rights": "CC BY-NC-SA 4.0", "commercial_use": False, "official_split": "TRAIN_ONLY",
        "official_test_split": "NOT_ACCESSED", "production_database": "NOT_ACCESSED",
        "config": config.as_dict(), "config_sha256": config_sha,
        "dataset_side_mapping": "per-match manually reviewed; left/right is never assumed to equal Near/Far",
        "tolerances_ms": tolerances, "aggregate": summary,
        "per_match": [{"match_id": row["match_id"], "sample_id": row["sample_id"],
                       "ground_truth_strokes": len(row["ground_truth"]),
                       "suggested_candidates": len(row["predictions"]),
                       "evaluation": row["evaluation"]} for row in per_clip],
        "clips": per_clip, "recorded_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(destination),
    }
    _write_json(destination / "hit_event_evaluation.json", result)
    _render_html(destination / "hit_event_evaluation.html", phase, summary, per_clip, config_sha)
    print(json.dumps({"phase": phase, "status": result["status"], "config_sha256": config_sha,
                      "clips": result["per_match"], "aggregate": summary,
                      "output_dir": str(destination)}, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="TRAIN-only Hit Event Engine evaluation")
    parser.add_argument("--phase", choices=("dev", "validation"), required=True)
    args = parser.parse_args()
    run(args.phase)


if __name__ == "__main__":
    main()
