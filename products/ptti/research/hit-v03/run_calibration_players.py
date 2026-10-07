"""Run frozen RT-DETR only at game_4 RAW hit-candidate frames.

This runner is restricted to the locked CALIBRATION source. Ground-truth
annotations are neither read nor passed to the worker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

PRODUCT = Path(__file__).resolve().parents[2]
if str(PRODUCT) not in sys.path:
    sys.path.insert(0, str(PRODUCT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.person_detector import FROZEN_MANIFEST_SHA  # noqa: E402
from calibration import (enforce_calibration_scope, immutable_json,
                         resolve_ptti_dev_root)  # noqa: E402
from resources import available_ram  # noqa: E402


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _table_bbox(scene_path: Path) -> tuple[list[float] | None, int]:
    if _sha(scene_path).lower() != FROZEN_MANIFEST_SHA.lower():
        raise ValueError("SCENE_EVIDENCE_MANIFEST_CHANGED")
    scene = _read_json(scene_path)
    boxes = []
    for row in scene.get("frame_results", []):
        if row.get("game") != "game_4":
            continue
        choices = [d["bbox"] for d in row.get("detections", [])
                   if "table" in str(d.get("label", "")).casefold()]
        if choices:
            boxes.append(max(choices, key=lambda box: (box[2]-box[0])*(box[3]-box[1])))
    if not boxes:
        return None, 0
    return [float(statistics.median(float(box[i]) for box in boxes)) for i in range(4)], len(boxes)


def _write_immutable(path: Path, payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise ValueError("IMMUTABLE_CALIBRATION_REQUEST_CHANGED")
        return _sha(path)
    return immutable_json(path, payload)


def run(source_path: Path, raw_candidates_path: Path, output_dir: Path | None = None) -> dict:
    source_path = Path(source_path).resolve()
    source = _read_json(source_path)
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
    identity = source["video"]
    initial_stat = video.stat()
    if (initial_stat.st_size != int(identity["size_bytes"]) or
            _sha(video).lower() != identity["sha256"].lower()):
        raise ValueError("CALIBRATION_SOURCE_CHANGED_BEFORE_PLAYER_INFERENCE")
    if initial_stat.st_mtime_ns <= 0:
        raise ValueError("INVALID_CALIBRATION_SOURCE_MTIME")
    raw_candidates_path = Path(raw_candidates_path).resolve()
    raw_candidates = _read_json(raw_candidates_path)
    if not isinstance(raw_candidates, list):
        raise ValueError("RAW_CANDIDATE_LIST_REQUIRED")
    frames = sorted({int(row["source_frame"]) for row in raw_candidates})
    if not frames or frames[0] < 0 or frames[-1] >= int(identity["frame_count"]):
        raise ValueError("RAW_CANDIDATE_FRAME_SET_INVALID")

    scene_path = (dev_root / "vision-v2" / "scene-bootstrap" /
                  "scene_bootstrap_eval_manifest.json").resolve()
    table_bbox, table_rows = _table_bbox(scene_path)
    source_digest = _sha(source_path)
    scene_digest = _sha(scene_path)
    output_dir = Path(output_dir or (source_path.parent / "player-evidence-candidate-centered")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    jobs = []
    for batch_index, start in enumerate(range(0, len(frames), 256)):
        subset = frames[start:start+256]
        request = {
            "schema": "ptti-game4-calibration-rtdetr-request-v1",
            "game": "game_4", "split_role": "CALIBRATION", "official_split": "TRAIN",
            "game_5": "NOT_ACCESSED", "official_test": "NOT_ACCESSED",
            "video_path": str(video), "video_sha256": identity["sha256"],
            "video_mtime_ns": initial_stat.st_mtime_ns,
            "source_verification_path": str(source_path),
            "source_verification_sha256": source_digest,
            "scene_manifest_path": str(scene_path), "scene_manifest_sha256": scene_digest,
            "table_bbox": table_bbox, "table_source_rows": table_rows,
            "fps": 120.0, "frames": subset,
            "purpose": "RAW_HIT_CANDIDATE_NEIGHBORHOOD_PLAYER_EVIDENCE",
            "ground_truth_passed_to_worker": False,
        }
        request_path = output_dir / f"game_4-candidates-{batch_index:04d}.request.json"
        _write_immutable(request_path, request)
        jobs.append({"request": str(request_path),
                     "output": str(output_dir / f"game_4-candidates-{batch_index:04d}.result.json")})
    jobs_path = output_dir / "jobs.json"
    _write_immutable(jobs_path, {"jobs": jobs, "frames": frames,
                                "raw_candidate_count": len(raw_candidates),
                                "source_sha256": identity["sha256"],
                                "source_verification_sha256": source_digest,
                                "scene_manifest_sha256": scene_digest,
                                "table_bbox": table_bbox, "table_source_rows": table_rows,
                                "game_5": "NOT_ACCESSED", "official_test": "NOT_ACCESSED"})

    worker_python = PRODUCT / "vision_worker" / ".venv" / "Scripts" / "python.exe"
    worker = Path(__file__).with_name("calibration_player_worker.py")
    if not worker_python.is_file() or available_ram() < 3 * 1024**3:
        raise RuntimeError("CALIBRATION_PLAYER_WORKER_OR_RESOURCE_GUARD_BLOCKED")
    completed = cached = 0
    runtime_rows = []
    for job in jobs:
        request_path, output_path = Path(job["request"]), Path(job["output"])
        request_digest = _sha(request_path)
        request = _read_json(request_path)
        if output_path.exists():
            result = _read_json(output_path)
            if (result.get("status") != "COMPLETE" or
                    result.get("request_sha256") != request_digest or
                    [row["source_frame"] for row in result.get("frames", [])] != request["frames"]):
                raise ValueError("INVALID_CALIBRATION_PLAYER_CHECKPOINT")
            cached += 1
        else:
            log_path = output_path.with_suffix(f".{time.time_ns()}.log")
            with log_path.open("x", encoding="utf-8") as log:
                process = subprocess.run([str(worker_python), str(worker), str(request_path), str(output_path)],
                                         stdout=log, stderr=subprocess.STDOUT, check=False)
            if process.returncode:
                print(f"PLAYER_WORKER_BLOCKED log={log_path}", flush=True)
                raise RuntimeError("CALIBRATION_PLAYER_WORKER_FAILED_CHECKPOINT_PRESERVED")
            result = _read_json(output_path)
            if result.get("request_sha256") != request_digest:
                raise ValueError("CALIBRATION_PLAYER_RESULT_REQUEST_HASH_MISMATCH")
            completed += 1
            print(json.dumps({"player_batches_complete": completed, "total_batches": len(jobs)},
                             ensure_ascii=False), flush=True)
        runtime_rows.append(result["runtime"])

    final_stat = video.stat()
    if (final_stat.st_size != initial_stat.st_size or
            final_stat.st_mtime_ns != initial_stat.st_mtime_ns or
            _sha(video).lower() != identity["sha256"].lower()):
        raise ValueError("CALIBRATION_SOURCE_CHANGED_DURING_PLAYER_INFERENCE")
    all_rows = []
    for job in jobs:
        all_rows.extend(_read_json(Path(job["output"]))["frames"])
    all_rows.sort(key=lambda row: row["source_frame"])
    if [row["source_frame"] for row in all_rows] != frames:
        raise ValueError("CALIBRATION_PLAYER_FRAME_COVERAGE_MISMATCH")
    model_provenance = _read(Path(jobs[0]["output"]))["model_provenance"]
    if any(_read(Path(job["output"])).get("model_provenance") != model_provenance for job in jobs):
        raise ValueError("RT_DETR_PROVENANCE_CHANGED_BETWEEN_BATCHES")
    role_counts = {name: 0 for name in ("NEAR_PLAYER", "FAR_PLAYER", "UNKNOWN", "OTHER")}
    frames_with_role = {name: 0 for name in ("NEAR_PLAYER", "FAR_PLAYER", "UNKNOWN", "OTHER")}
    for row in all_rows:
        roles = {person.get("role_candidate", "UNKNOWN") for person in row["resolved_people"]}
        for name in role_counts:
            role_counts[name] += sum(person.get("role_candidate", "UNKNOWN") == name
                                     for person in row["resolved_people"])
            frames_with_role[name] += name in roles
    summary = {
        "schema": "ptti-game4-calibration-player-evidence-v1", "status": "COMPLETE",
        "game": "game_4", "official_split": "TRAIN", "split_role": "CALIBRATION",
        "video_sha256": identity["sha256"], "source_verification_sha256": source_digest,
        "scene_manifest_sha256": scene_digest, "table_bbox": table_bbox,
        "table_source_rows": table_rows, "raw_candidate_count": len(raw_candidates),
        "unique_candidate_frames": len(frames), "detected_person_boxes": role_counts,
        "candidate_frames_with_roles": frames_with_role,
        "no_person_candidate_frames": sum(not row["resolved_people"] for row in all_rows),
        "no_near_or_far_role_frames": len(frames) - frames_with_role["NEAR_PLAYER"] -
            frames_with_role["FAR_PLAYER"] + frames_with_role["both_near_and_far"],
        "player_evidence_coverage": {key: {"frames": value,
            "fraction": value/len(frames) if frames else None} for key, value in frames_with_role.items()},
        "model_provenance": model_provenance,
        "completed_batches": completed, "cache_hits": cached,
        "runtime": runtime_rows,
        "game_5": "NOT_ACCESSED", "official_test": "NOT_ACCESSED",
        "production_database": "NOT_ACCESSED",
    }
    summary_path = output_dir / "player_evidence_summary.json"
    _write_immutable(summary_path, summary)
    jsonl_path = output_dir / "player_evidence_frames.jsonl"
    if jsonl_path.exists():
        raise FileExistsError("CALIBRATION_PLAYER_FRAME_EVIDENCE_IS_IMMUTABLE")
    with jsonl_path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in all_rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps(summary["player_evidence_coverage"], ensure_ascii=False, indent=2), flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-verification", type=Path, required=True)
    parser.add_argument("--raw-candidates", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    run(args.source_verification, args.raw_candidates, args.output_dir)


if __name__ == "__main__":
    main()
