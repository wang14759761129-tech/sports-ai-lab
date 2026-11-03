"""Prepare a deterministic research benchmark from existing TRAIN assets; no downloads or tuning."""
from collections import Counter
import csv
import json
from pathlib import Path

import cv2
import numpy as np

from ptti_benchmark.adapters import racketvision_rows
from ptti_benchmark.core import METRICS_VERSION, file_sha256, serialize_observation

PRODUCT = Path(__file__).resolve().parents[2]
DEV = Path.home() / "AppData/Local/PTTI-Dev"
OUT = DEV / "technology-foundation/benchmark-v0"


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def export_image(video, source_frame, target):
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, source_frame)
    ok, image = cap.read()
    cap.release()
    if not ok:
        raise ValueError("SOURCE_FRAME_UNREADABLE")
    target.parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(".jpg", image)[1].tofile(str(target))
    return image


def main():
    lock = OUT / "PTTI_VISION_BENCHMARK_V0_MANIFEST.json"
    if lock.exists():
        raise FileExistsError("BENCHMARK_V0_ALREADY_EXISTS")
    baseline_home = PRODUCT / "outputs/vision/balltrack_final"
    baseline = json.loads((baseline_home / "A_official.json").read_text())
    official_train = set(tuple(row) for row in json.loads(
        (PRODUCT / "datasets/racketvision/tabletennis/info/train.json").read_text()))
    prepared = {row["source_id"]: row for row in json.loads((baseline_home / "prepared_inputs.json").read_text())}
    clips, seen_matches = [], set()
    for cached in baseline["train"]["clips"]:
        sid = cached["source_id"]
        _, match, rally = sid.split("/")
        if (match, rally) not in official_train or match in seen_matches:
            continue
        seen_matches.add(match)
        meta = prepared[sid]
        video = PRODUCT / f"datasets/racketvision/tabletennis/videos/{match}_{rally}.mp4"
        annotation = baseline_home / f"dataset/tabletennis/all/{match}/csv/{rally}_ball.csv"
        if file_sha256(video) != meta["video_sha256"] or file_sha256(annotation) != meta["gt_sha256"]:
            raise ValueError("BASELINE_ASSET_HASH_CHANGED")
        labels = []
        with annotation.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                frame = int(row["Frame"])
                labels.append({"source_frame": frame, "timestamp_ms": frame*1000/meta["fps"],
                               "visible": bool(int(row["Visibility"])),
                               "x": float(row["X"]), "y": float(row["Y"]),
                               "source": "RACKETVISION_NATIVE_BALL_GT"})
        predictions = racketvision_rows(cached["raw_predictions"], meta["fps"])
        clip_dir = OUT / f"clips/{match}_{rally}"
        label_file = clip_dir / "canonical_labels.json"
        save_json(label_file, labels)
        save_json(clip_dir / "racketvision_raw.json", [serialize_observation(p) for p in predictions])
        images, frame_map = [], {}
        for local, gt in enumerate(labels):
            target = clip_dir / "images" / f"frame_{gt['source_frame']:06d}.jpg"
            export_image(video, gt["source_frame"], target)
            images.append({"source_frame": gt["source_frame"], "timestamp_ms": gt["timestamp_ms"],
                           "path": str(target), "sha256": file_sha256(target)})
            frame_map[local] = {"source_frame": gt["source_frame"], "timestamp_ms": gt["timestamp_ms"]}
        save_json(clip_dir / "cvat_frame_map.json", frame_map)
        clips.append({"id": sid, "dataset": "RacketVision tabletennis", "split": "TRAIN",
                      "license": "UPSTREAM_DATASET_RESEARCH_ACCESS; REDISTRIBUTION_NOT_ESTABLISHED",
                      "commercial_use": False, "scene_strata": ["UNKNOWN"],
                      "strata_review": "PENDING_HUMAN_REVIEW",
                      "video": {"path": str(video), "sha256": file_sha256(video)},
                      "annotation": {"path": str(annotation), "sha256": file_sha256(annotation)},
                      "canonical_labels": str(label_file), "canonical_labels_sha256": file_sha256(label_file),
                      "racketvision_raw": str(clip_dir / "racketvision_raw.json"),
                      "racketvision_raw_sha256": file_sha256(clip_dir / "racketvision_raw.json"),
                      "width": meta["resolution"][0], "height": meta["resolution"][1],
                      "fps": meta["fps"], "frames": meta["frames"], "images": images,
                      "baseline_source_sha256": file_sha256(baseline_home / "A_official.json"),
                      "sampling": "ALL_NATIVE_SPARSE_GT_FRAMES; NO_BEST_FRAME_SELECTION"})
        if len(clips) == 5:
            break
    if len(clips) != 5:
        raise ValueError("INSUFFICIENT_VERIFIED_TRAIN_CLIPS")
    # Only games 1..3 DEV; neither locked games nor official TEST paths are opened.
    cross_path = DEV / "evidence/hit_event_v0_2/full_dev/cross_game_baseline_20261007/cross_game_full_dev_baseline.json"
    cross = json.loads(cross_path.read_text(encoding="utf-8"))
    queue, fn_context = [], Counter()
    for game in cross["games"]:
        if game["game"] not in {"game_1", "game_2", "game_3"}:
            raise ValueError("LOCKED_GAME_NOT_ALLOWED")
        evaluation = json.loads(Path(game["evaluation_path"]).read_text(encoding="utf-8"))
        directory = Path(game["evaluation_path"]).parent
        context = {row["event_id"]: row for row in evaluation["ball_context_by_ground_truth"]}
        for row in evaluation["stage_attrition"]:
            if row["loss_stage"] == "RAW_GENERATOR_MISS":
                state = "PRE_POST_BALL_AVAILABLE" if context[row["event_id"]]["ball_context_available"] else "PRE_POST_BALL_INSUFFICIENT"
                fn_context[state] += 1
        raw = json.loads((directory / "raw_candidates.json").read_text(encoding="utf-8"))
        metric = evaluation["stage_metrics"]["raw"]["by_tolerance"]["plus_minus_2_processing_frames"]
        false_ids = set(metric["unmatched_prediction_ids"])
        candidates = [row for row in raw if row["event_id"] in false_ids]
        indices = np.linspace(0, len(candidates)-1, 3, dtype=int)
        for index in indices:
            row = candidates[int(index)]
            target = OUT / "annotation_queue" / game["game"] / f"fp_{row['source_frame']:06d}.jpg"
            export_image(Path(evaluation["video_path"]), row["source_frame"], target)
            queue.append({"task_id": f"{game['game']}:hit-fp:{row['event_id']}",
                          "video": evaluation["video_path"], "video_sha256": evaluation["video_sha256"],
                          "source_frame": row["source_frame"], "timestamp_ms": row["timestamp_ms"],
                          "window_start_ms": max(0, row["timestamp_ms"]-500),
                          "window_end_ms": row["timestamp_ms"]+500, "image": str(target),
                          "raw_candidate": row, "hit_matching_status": "UNMATCHED_AT_16_667_MS",
                          "ball_negative_truth": "UNKNOWN_REQUIRES_REVIEW", "scene_strata": ["UNKNOWN"],
                          "source": "Extended OpenTTGames TRAIN DEV", "license": "CC BY-NC-SA 4.0",
                          "commercial_use": False})
    manifest = {"name": "PTTI Vision Benchmark v0", "metrics_version": METRICS_VERSION,
                "status": "RESEARCH_DEV_BASELINE; NOT_UNTOUCHED_EVALUATION", "clips": clips,
                "data_sources": {"A": "Extended OpenTTGames TRAIN DEV: pending ball annotations",
                                 "B": "RacketVision official TRAIN: native sparse ball GT",
                                 "C": "Legally-held user/professional video: NOT_AVAILABLE"},
                "locked": ["game_4", "game_5", "official_TEST"],
                "racketvision_checkpoint_sha256": "00d707b9db7a49561c411e4765956e79bcd7c7e20c7a0a535073440b3e972342",
                "localization_radius_px": 20, "rf_detr_threshold": .3,
                "comparison": "RAW_DETECTOR; NO_TRACKER_OR_POSTPROCESS; NO_THRESHOLD_TUNING",
                "ranking_policy": "DESCRIPTIVE_DEV_ONLY; require both localization recall and FP constraints",
                "downstream_hit": "Extended TRAIN full DEV frozen baseline available; new sparse detector comparison not event-evaluable",
                "annotation_queue": str(OUT / "annotation_queue.json")}
    save_json(OUT / "annotation_queue.json", queue)
    save_json(OUT / "bottleneck_measurements.json", {
        "source_report_sha256": file_sha256(cross_path), "raw_fn": dict(fn_context),
        "player_evidence": 0, "player_evidence_effect": "NOT_MEASURED_NO_SAME_VIDEO_ABLATION",
        "wrong_ball_observations": "UNKNOWN_NO_DENSE_BALL_GT", "sampled_hit_fp_tasks": len(queue),
        "hit_fp_is_not_ball_fp": True})
    save_json(lock, manifest)
    lock.with_suffix(".sha256").write_text(file_sha256(lock) + "  " + lock.name + "\n")
    print(json.dumps({"manifest": str(lock), "sha256": file_sha256(lock), "clips": len(clips),
                      "native_gt_frames": sum(len(c["images"]) for c in clips), "fn_context": dict(fn_context),
                      "annotation_tasks": len(queue)}))


if __name__ == "__main__":
    main()
