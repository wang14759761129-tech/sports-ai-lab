"""Run isolated, synthetic 30-minute full-match engineering QA.

This validates systems behavior only. It makes no tracking-accuracy claim and
uses a temporary TEST database; it never resolves or opens the Production DB.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
for site_packages in (PRODUCT / "vision_worker" / ".venv" / "Lib").glob("python*/site-packages"):
    sys.path.insert(0, str(site_packages))
site_packages = PRODUCT / "vision_worker" / ".venv" / "Lib" / "site-packages"
if site_packages.is_dir():
    sys.path.insert(0, str(site_packages))
os.environ["PTTI_ENV"] = "test"
os.environ["PTTI_DB"] = str(Path(tempfile.gettempdir()) / "ptti-fullmatch-script-sentinel.db")

import psutil
from backend.database import ProductionDatabaseGuard
from backend.full_match_pipeline import FullMatchService
from backend.full_match_pipeline import refresh_timeline_summary, _validation_html
from backend.fullmatch import TimelineAction, apply_timeline_action
from backend.professional import ProfessionalMatchInput
from backend.repository import Repository
from vision.config import VisionConfig
from vision.quality import video_metadata, classify
from backend.fullmatch import file_sha256


def gpu_snapshot():
    try:
        result = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                                 "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "UNAVAILABLE"


def wait_job(repo, match_id, service, run_manifest, interrupt_once, samples, start_time, sample_file):
    last_sample = 0
    killed = False
    while True:
        job = repo.get_full_match_job(match_id) or {}
        manifest_path = Path(job.get("manifest_path", run_manifest))
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
        complete = sum(c.get("status") == "COMPLETE" for c in manifest.get("chunks", []))
        elapsed = time.monotonic() - start_time
        if elapsed - last_sample >= 30:
            children = psutil.Process().children(recursive=True)
            samples.append({"elapsed_seconds": round(elapsed, 1), "completed_chunks": complete,
                "source_minutes_completed": complete, "parent_rss_bytes": psutil.Process().memory_info().rss,
                "worker_rss_bytes": sum((p.memory_info().rss for p in children if p.is_running()), 0),
                "worker_processes": len(children), "gpu": gpu_snapshot()})
            sample_file.write_text(json.dumps(samples, indent=2), encoding="utf-8")
            last_sample = elapsed
        running = next((c for c in manifest.get("chunks", []) if c.get("status") == "RUNNING"), None)
        if interrupt_once and not killed and complete >= 1 and running and running["chunk_index"] >= 1:
            matches = []
            for child in psutil.Process().children(recursive=True):
                try:
                    command = " ".join(child.cmdline())
                    if "balltrack.py" in command and str(service.config.worker_python).casefold() in command.casefold():
                        matches.append(child)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if not matches:
                raise RuntimeError("Could not identify the QA-owned BallTrack worker to inject interruption")
            for worker in matches:
                worker.terminate()
            killed = True
        if job.get("status") == "BALLTRACK_COMPLETE":
            samples.append({"elapsed_seconds": round(time.monotonic() - start_time, 1),
                "completed_chunks": complete, "source_minutes_completed": complete,
                "parent_rss_bytes": psutil.Process().memory_info().rss,
                "worker_rss_bytes": 0, "worker_processes": len(psutil.Process().children(recursive=True)),
                "gpu": gpu_snapshot(), "label": "END"})
            sample_file.write_text(json.dumps(samples, indent=2), encoding="utf-8")
            return manifest, killed
        if job.get("status") == "PAUSED":
            return manifest, killed
        time.sleep(1)


def exercise_manual_timeline(repo, match_id):
    timeline = repo.get_match_timeline(match_id) or {
        "match_id": match_id, "revision": 0, "games": [], "scene_segments": []}
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
        expected_revision = timeline["revision"]
        timeline = apply_timeline_action(timeline, action)
        timeline = repo.save_match_timeline(match_id, timeline, expected_revision)
        refresh_timeline_summary(repo, match_id, timeline)
    return {"actions": [action.action for action in actions],
        "games": len(timeline["games"]), "points": sum(len(g["points"]) for g in timeline["games"]),
        "rallies": sum(len(p["rallies"]) for g in timeline["games"] for p in g["points"]),
        "game_scores": [g["points"][-1].get("score_after") if g["points"] else None for g in timeline["games"]],
        "point_rally_relation": "MANUAL / REVIEW_REQUIRED", "reorder_supported": False}


def main():
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output_root = PRODUCT / "outputs" / "full_match_qa" / run_id
    output_root.mkdir(parents=True, exist_ok=False)
    video = output_root / "SYNTHETIC_LONG_FORM_QA.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
        "testsrc2=size=512x288:rate=2:duration=1800", "-vf",
        "drawbox=x=0:y=0:w=512:h=288:color=black:t=fill:enable='between(t,300,330)+between(t,900,930)+between(t,1770,1800)'",
        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", "-y", str(video)], check=True, timeout=3600)

    isolated_root = Path(tempfile.gettempdir()) / f"pttiqa-{run_id}"
    isolated_root.mkdir(parents=True, exist_ok=False)
    db_root = isolated_root / "db"
    db_root.mkdir()
    db_path = db_root / "matches.db"
    repo = Repository(db_path, guard=ProductionDatabaseGuard("test"))
    registry = json.loads((PRODUCT / "data/professional/registry.json").read_text(encoding="utf-8"))
    repo.seed_professional(registry)
    record = ProfessionalMatchInput(event_name="Synthetic 30-minute engineering QA",
        player_a_id="athlete:121558", player_b_id="athlete:123980", video_source_type="RESEARCH_DATASET",
        rights_status="RESEARCH_DATASET_AUTHORIZED", licence_reference="SYNTHETIC_LONG_FORM_QA",
        video_local_path=str(video)).to_record()
    media = video_metadata(video)
    record["video_metadata"] = {**media, "size_bytes": video.stat().st_size,
        "mtime_ns": video.stat().st_mtime_ns, "sha256": file_sha256(video),
        "quality": classify(media), "qa_classification": "SYNTHETIC_LONG_FORM_QA"}
    record["video_source_note"] = "Synthetic fixture; generated from FFmpeg test pattern; engineering QA only."
    repo.save_professional_match(record)
    service = FullMatchService(repo, isolated_root / "data", VisionConfig.load(), chunk_seconds=60)
    cuda = subprocess.run([str(service.config.worker_python), "-c",
        "import torch; print('yes' if torch.cuda.is_available() else 'no')"], capture_output=True,
        text=True, timeout=60).stdout.strip() == "yes"
    device = "cuda" if cuda else "cpu"
    prepared = service.prepare(record, device)
    job = service.start(record["match_id"], device=device)
    samples = [{"elapsed_seconds": 0, "completed_chunks": 0, "source_minutes_completed": 0,
        "parent_rss_bytes": psutil.Process().memory_info().rss, "worker_rss_bytes": 0,
        "worker_processes": 0, "gpu": gpu_snapshot(), "label": "START"}]
    sample_file = output_root / "memory_samples.json"
    sample_file.write_text(json.dumps(samples, indent=2), encoding="utf-8")
    start = time.monotonic()
    first, interrupted = wait_job(repo, record["match_id"], service, job["manifest_path"], True, samples, start, sample_file)
    if not interrupted or first.get("status") != "PAUSED":
        raise RuntimeError("Worker interruption was not captured and checkpointed")
    completed_before = [c for c in first["chunks"] if c.get("status") == "COMPLETE"]
    if not completed_before:
        raise RuntimeError("Interruption occurred before any completed checkpoint")
    repo_job = repo.get_full_match_job(record["match_id"])
    manifest = json.loads(Path(repo_job["manifest_path"]).read_text(encoding="utf-8"))
    if manifest.get("cache_key") != prepared["cache_key"]:
        raise RuntimeError("Cache key changed before resume")
    resumed_start = time.monotonic()
    service.start(record["match_id"], device=device, resume=True)
    final, _ = wait_job(repo, record["match_id"], service, job["manifest_path"], False, samples, resumed_start, sample_file)
    if final.get("status") != "BALLTRACK_COMPLETE":
        raise RuntimeError(f"Full run did not complete: {final.get('last_error')}")
    timeline_qa = exercise_manual_timeline(repo, record["match_id"])
    while record["match_id"] in service.active:
        time.sleep(0.05)
    service.start(record["match_id"], device=device, resume=True)  # Completed-run cache-hit path.
    final = json.loads(Path(job["manifest_path"]).read_text(encoding="utf-8"))
    failure_injection = {}
    changed = FullMatchService(repo, isolated_root / "data", VisionConfig.load(), chunk_seconds=30)
    try:
        changed.start(record["match_id"], device=device, resume=True)
        failure_injection["config_change"] = "UNEXPECTEDLY_ACCEPTED"
    except ValueError as exc:
        failure_injection["config_change"] = str(exc)
    output_dir = Path(repo.get_full_match_job(record["match_id"])["output_dir"])
    unavailable = output_dir.with_name(output_dir.name + "-unavailable")
    output_dir.rename(unavailable)
    try:
        try:
            service.start(record["match_id"], device=device, resume=True)
            failure_injection["output_directory_unavailable"] = "UNEXPECTEDLY_ACCEPTED"
        except ValueError as exc:
            failure_injection["output_directory_unavailable"] = str(exc)
    finally:
        unavailable.rename(output_dir)
    first_chunk = final["chunks"][0]
    raw_path = Path(first_chunk["raw_prediction_path"])
    raw_backup = raw_path.read_bytes()
    raw_path.write_bytes(b"corrupted checkpoint QA")
    try:
        try:
            service.start(record["match_id"], device=device, resume=True)
            failure_injection["corrupt_checkpoint"] = "UNEXPECTEDLY_ACCEPTED"
        except ValueError as exc:
            failure_injection["corrupt_checkpoint"] = str(exc)
    finally:
        raw_path.write_bytes(raw_backup)
    identity = record["video_metadata"]
    video_backup = output_root / "source-backup.qa"
    video_backup.write_bytes(video.read_bytes())
    try:
        with video.open("ab") as handle:
            handle.write(b"\x00source-mutation")
        try:
            service.prepare(record, device)
            failure_injection["source_modified"] = "UNEXPECTEDLY_ACCEPTED"
        except ValueError as exc:
            failure_injection["source_modified"] = str(exc)
    finally:
        video.write_bytes(video_backup.read_bytes())
        video_backup.unlink()
        os.utime(video, ns=(identity["mtime_ns"], identity["mtime_ns"]))
    moved = video.with_name(video.stem + ".moved" + video.suffix)
    video.rename(moved)
    try:
        try:
            service.prepare(record, device)
            failure_injection["source_moved"] = "UNEXPECTEDLY_ACCEPTED"
        except ValueError as exc:
            failure_injection["source_moved"] = str(exc)
    finally:
        moved.rename(video)
    report_path = Path(repo.get_full_match_job(record["match_id"])["validation_path"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["qa_classification"] = "SYNTHETIC_LONG_FORM_QA"
    report["injected_interruption"] = {"occurred": interrupted,
        "complete_chunks_before_resume": len(completed_before),
        "resumed_chunks": [c["chunk_index"] for c in final["chunks"] if c.get("resumed")],
        "attempt_counts": [c.get("attempt_count") for c in final["chunks"]]}
    report["memory_samples"] = samples
    report["timeline_qa"] = timeline_qa
    report["failure_injection"] = failure_injection
    report["source_file"] = str(video)
    report["artifacts"]["manifest.json"] = {"exists": True,
        "size_bytes": Path(job["manifest_path"]).stat().st_size,
        "sha256": file_sha256(Path(job["manifest_path"]))}
    report["output_directory_size_bytes"] = sum(item.stat().st_size for item in
        Path(repo.get_full_match_job(record["match_id"])["output_dir"]).rglob("*") if item.is_file())
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.with_suffix(".html").write_text(_validation_html(report), encoding="utf-8")
    (output_root / "qa_run.json").write_text(json.dumps({"match_id": record["match_id"],
        "database": str(db_path), "database_mode": "TEST", "device": device,
        "output_directory": str(Path(repo.get_full_match_job(record["match_id"])["output_dir"])),
        "isolated_root": str(isolated_root),
        "validation_report": str(report_path), "synthetic_video": str(video),
        "source_sha256": record["video_metadata"]["sha256"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "qa_classification": "SYNTHETIC_LONG_FORM_QA",
        "duration_seconds": media["duration"], "frame_count": report["output_frames"],
        "chunk_count": report["chunk_count"], "device": device, "interrupted_and_resumed": interrupted,
        "output_directory": str(Path(repo.get_full_match_job(record["match_id"])["output_dir"])),
        "qa_report": str(report_path), "elapsed_wall_seconds": time.monotonic() - start}, indent=2))


if __name__ == "__main__":
    main()
