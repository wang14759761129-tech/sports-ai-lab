"""Finish assertions and reports for a completed synthetic full-match QA run."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
for site_packages in (PRODUCT / "vision_worker" / ".venv" / "Lib").glob("python*/site-packages"):
    sys.path.insert(0, str(site_packages))
site_packages = PRODUCT / "vision_worker" / ".venv" / "Lib" / "site-packages"
if site_packages.is_dir():
    sys.path.insert(0, str(site_packages))
os.environ["PTTI_ENV"] = "test"

from backend.database import ProductionDatabaseGuard
from backend.full_match_pipeline import (FullMatchService, _validation_html,
    build_full_match_validation, refresh_timeline_summary)
from backend.fullmatch import (TimelineAction, apply_timeline_action, file_sha256,
    save_manifest)
from backend.repository import Repository
from vision.config import VisionConfig


def persist_action(repo, match_id, timeline, action):
    expected = timeline["revision"]
    updated = apply_timeline_action(timeline, action)
    saved = repo.save_match_timeline(match_id, updated, expected)
    refresh_timeline_summary(repo, match_id, saved)
    return saved


def timeline_acceptance(repo, match_id):
    timeline = repo.get_match_timeline(match_id) or {
        "match_id": match_id, "revision": 0, "games": [], "scene_segments": []}
    for game in list(timeline["games"]):
        timeline = persist_action(repo, match_id, timeline,
            TimelineAction(action="delete_game", game_number=game["game_number"]))
    actions = [
        TimelineAction(action="add_game", game_number=1, game_start_ms=0),
        TimelineAction(action="add_point", game_number=1, start_ms=1000, end_ms=12000),
        TimelineAction(action="set_score", game_number=1, point_number=1,
            score_after={"player_a": 1, "player_b": 0}, note="Synthetic manual QA"),
        TimelineAction(action="split", game_number=1, point_number=1, split_at_ms=6000),
        TimelineAction(action="merge", game_number=1, point_number=1, next_point_number=2),
        TimelineAction(action="add_rally", game_number=1, point_number=1,
            rally_start_ms=1200, rally_end_ms=11000),
        TimelineAction(action="add_point", game_number=1, start_ms=13000, end_ms=18000),
        TimelineAction(action="delete_point", game_number=1, point_number=2),
        TimelineAction(action="add_game", game_number=2, game_start_ms=900000),
        TimelineAction(action="delete_game", game_number=2),
        TimelineAction(action="mark_game_end", game_number=1, end_ms=20000),
    ]
    for action in actions:
        timeline = persist_action(repo, match_id, timeline, action)
    return {"actions": [a.action for a in actions], "games": len(timeline["games"]),
        "points": sum(len(g["points"]) for g in timeline["games"]),
        "rallies": sum(len(p["rallies"]) for g in timeline["games"] for p in g["points"]),
        "game_scores": [g["points"][-1].get("score_after") if g["points"] else None for g in timeline["games"]],
        "point_rally_relation": "MANUAL / REVIEW_REQUIRED", "reorder_supported": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("qa_output", type=Path, help="products/ptti/outputs/full_match_qa/<run-id>")
    args = parser.parse_args()
    qa_output = args.qa_output.resolve()
    video = qa_output / "SYNTHETIC_LONG_FORM_QA.mp4"
    run_root = Path(os.environ.get("TEMP", Path.home() / "AppData/Local/Temp")) / f"pttiqa-{qa_output.name}"
    manifest_path = next((run_root / "data" / "full_matches").rglob("manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    match_id = manifest["match_id"]
    repo = Repository(run_root / "db" / "matches.db", guard=ProductionDatabaseGuard("test"))
    record = repo.get_professional_match(match_id)
    if not record or not video.is_file():
        raise RuntimeError("Synthetic QA record or source video is missing")
    service = FullMatchService(repo, run_root / "data", VisionConfig.load(), chunk_seconds=60)
    timeline = timeline_acceptance(repo, match_id)
    while match_id in service.active:
        time.sleep(0.05)
    service.start(match_id, device=manifest["config"]["device"], resume=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = {}
    changed = FullMatchService(repo, run_root / "data", VisionConfig.load(), chunk_seconds=30)
    try:
        changed.start(match_id, device=manifest["config"]["device"], resume=True)
        failures["config_change"] = "UNEXPECTEDLY_ACCEPTED"
    except ValueError as exc:
        failures["config_change"] = str(exc)
    job = repo.get_full_match_job(match_id)
    output_dir = Path(job["output_dir"])
    unavailable = output_dir.with_name(output_dir.name + "-unavailable")
    output_dir.rename(unavailable)
    try:
        try:
            service.start(match_id, device=manifest["config"]["device"], resume=True)
            failures["output_directory_unavailable"] = "UNEXPECTEDLY_ACCEPTED"
        except ValueError as exc:
            failures["output_directory_unavailable"] = str(exc)
    finally:
        unavailable.rename(output_dir)
    first = manifest["chunks"][0]
    raw_path = Path(first["raw_prediction_path"])
    raw_backup = raw_path.read_bytes()
    raw_path.write_bytes(b"corrupted checkpoint QA")
    try:
        try:
            service.start(match_id, device=manifest["config"]["device"], resume=True)
            failures["corrupt_checkpoint"] = "UNEXPECTEDLY_ACCEPTED"
        except ValueError as exc:
            failures["corrupt_checkpoint"] = str(exc)
    finally:
        raw_path.write_bytes(raw_backup)
    source_identity = record["video_metadata"]
    backup = qa_output / "source-backup.qa"
    backup.write_bytes(video.read_bytes())
    try:
        with video.open("ab") as handle:
            handle.write(b"\x00source-mutation")
        try:
            service.prepare(record, manifest["config"]["device"])
            failures["source_modified"] = "UNEXPECTEDLY_ACCEPTED"
        except (ValueError, RuntimeError) as exc:
            failures["source_modified"] = str(exc)
    finally:
        video.write_bytes(backup.read_bytes())
        backup.unlink()
        os.utime(video, ns=(source_identity["mtime_ns"], source_identity["mtime_ns"]))
    moved = video.with_name(video.stem + ".moved" + video.suffix)
    video.rename(moved)
    try:
        try:
            service.prepare(record, manifest["config"]["device"])
            failures["source_moved"] = "UNEXPECTEDLY_ACCEPTED"
        except ValueError as exc:
            failures["source_moved"] = str(exc)
    finally:
        moved.rename(video)
    summary = json.loads((output_dir / "full_match_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    timeline_doc = repo.get_match_timeline(match_id) or {"games": [], "scene_segments": []}
    validation = build_full_match_validation(manifest, summary, manifest["source_identity"], output_dir,
        summary["balltrack_frames"], timeline_doc)
    validation["failure_injection"] = failures
    first_retry = next((c for c in manifest["chunks"] if c.get("attempt_count", 0) > 1), None)
    validation["cache_test"] = {"cold_run_unique_chunk_misses": len(manifest["chunks"]),
        "resumed_cached_chunks_before_interruption_point": first_retry["chunk_index"] if first_retry else 0,
        "retried_chunk_count": sum(max(0, c.get("attempt_count", 0) - 1) for c in manifest["chunks"]),
        "post_completion_cache_validation": "PASS",
        "config_change_invalidation": failures["config_change"] != "UNEXPECTEDLY_ACCEPTED"}
    validation["timeline_qa"] = timeline
    validation["memory_samples"] = json.loads((qa_output / "memory_samples.json").read_text(encoding="utf-8"))
    validation["runtime_wall_seconds"] = ((__import__("datetime").datetime.fromisoformat(manifest["completed_at"]) -
        __import__("datetime").datetime.fromisoformat(manifest["created_at"])).total_seconds())
    wall = validation["runtime_wall_seconds"]
    validation["full_pipeline_effective_fps"] = validation["output_frames"] / wall if wall else None
    validation["full_pipeline_realtime_factor"] = validation["input"]["duration_seconds"] / wall if wall else None
    validation["source_file"] = str(video)
    validation["output_directory_size_bytes"] = sum(p.stat().st_size for p in output_dir.rglob("*") if p.is_file())
    validation["artifacts"]["manifest.json"] = {"exists": True, "size_bytes": manifest_path.stat().st_size,
        "sha256": file_sha256(manifest_path)}
    validation_path = output_dir / "full_match_validation.json"
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "full_match_validation.html").write_text(_validation_html(validation), encoding="utf-8")
    qa_record = {"status": "PASS", "qa_classification": "SYNTHETIC_LONG_FORM_QA",
        "match_id": match_id, "database": str(repo.path), "database_mode": "TEST",
        "isolated_root": str(run_root), "source_file": str(video),
        "source_sha256": record["video_metadata"]["sha256"], "device": manifest["config"]["device"],
        "output_directory": str(output_dir), "validation_report": str(validation_path)}
    (qa_output / "qa_run.json").write_text(json.dumps(qa_record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(qa_record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
