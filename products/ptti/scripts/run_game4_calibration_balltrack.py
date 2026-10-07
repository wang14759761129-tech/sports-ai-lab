"""Run frozen BallTrack RAW on game_4 calibration without opening any database.

The short-lived in-memory repository only adapts the existing resumable
FullMatchService interface. It does not create SQLite files or access PTTI data.
Only the locked game_4 calibration source is accepted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

from backend.fullmatch import file_sha256, source_identity  # noqa: E402
from backend.full_match_pipeline import FullMatchService  # noqa: E402
from vision.config import VisionConfig  # noqa: E402
from vision.quality import classify, video_metadata  # noqa: E402
sys.path.insert(0, str(PRODUCT_ROOT / "research" / "hit-v03"))
from calibration import enforce_calibration_scope, resolve_ptti_dev_root  # noqa: E402


class MemoryRepository:
    """Only the methods needed by FullMatchService; intentionally no DB layer."""

    def __init__(self, record: dict):
        self.record = record
        self.jobs: dict[str, dict] = {}

    def get_professional_match(self, match_id: str):
        return self.record if match_id == self.record["match_id"] else None

    def get_full_match_job(self, match_id: str):
        return self.jobs.get(match_id)

    def save_full_match_job(self, match_id: str, job: dict):
        self.jobs[match_id] = dict(job)

    def get_match_timeline(self, _match_id: str):
        return None


def read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_record(source: dict) -> dict:
    video = Path(source["video"]["path"]).resolve()
    identity = source_identity(video)
    if identity["sha256"].lower() != source["video"]["sha256"].lower():
        raise ValueError("SOURCE_SHA256_CHANGED_BEFORE_BALLTRACK")
    if identity["size_bytes"] != source["video"]["size_bytes"]:
        raise ValueError("SOURCE_SIZE_CHANGED_BEFORE_BALLTRACK")
    metadata = video_metadata(video)
    match_id = (f"research:extended-openttgames:game_4:{identity['sha256'][:12]}:"
                "hit-v03-calibration-20261008")
    return {
        "match_id": match_id,
        "event_name": "Extended OpenTTGames game_4 · calibration only",
        "round": "Research calibration",
        "player_a_id": "extended-openttgames:left",
        "player_b_id": "extended-openttgames:right",
        "video_source_type": "RESEARCH_DATASET",
        "video_local_path": str(video),
        "rights_status": "RESEARCH_DATASET_AUTHORIZED",
        "licence_reference": "Extended OpenTTGames CC BY-NC-SA 4.0; non-commercial research only",
        "video_metadata": {
            **metadata,
            "sha256": identity["sha256"],
            "size_bytes": identity["size_bytes"],
            "mtime_ns": identity["mtime_ns"],
            "quality": classify(metadata),
            "dataset": source["dataset"],
            "rights": source["license"],
            "commercial_use": False,
            "official_split": "TRAIN",
            "split_role": "CALIBRATION",
            "balltrack_model": "BALLTRACK_V1_FROZEN_RAW",
        },
    }


def run(source_path: Path, *, chunk_seconds: int = 30, poll_seconds: float = 5.0) -> dict:
    source_path = Path(source_path).resolve()
    source = read_json(source_path)
    enforce_calibration_scope(source.get("game"), source.get("split_role"), source.get("official_split"))
    if source.get("game_5") != "NOT_ACCESSED" or source.get("official_test") != "NOT_ACCESSED":
        raise ValueError("CALIBRATION_SOURCE_SCOPE_MARKER_INVALID")
    source_video = Path(source["video"]["path"]).resolve()
    dev_root = resolve_ptti_dev_root(source_video)
    expected_source = (dev_root / "evidence" / "hit_event_v0_3" /
                       "game4-calibration-20261008" / "GAME4_CALIBRATION_SOURCE_VERIFICATION.json").resolve()
    if source_path != expected_source:
        raise ValueError("CALIBRATION_SOURCE_VERIFICATION_PATH_NOT_CANONICAL")
    record = build_record(source)
    repo = MemoryRepository(record)
    config = VisionConfig.load()
    checkpoint = config.model_root / "balltrack_best.pth"
    checkpoint_sha = file_sha256(checkpoint)
    if not config.worker_python.is_file() or not config.runtime_root.is_dir():
        raise FileNotFoundError("FROZEN_BALLTRACK_RUNTIME_MISSING")
    data_root = dev_root / "evidence"
    service = FullMatchService(repo, data_root, config,
                               chunk_seconds=chunk_seconds,
                               min_available_ram_gib=2.0,
                               max_new_chunks_per_run=1)
    prepared = service.prepare(record, "cuda")
    if prepared["video_sha256"].lower() != source["video"]["sha256"].lower():
        raise ValueError("PREPARED_SOURCE_HASH_MISMATCH")

    manifest_path = prepared["manifest_path"]
    existing = manifest_path.is_file()
    if existing:
        manifest = read_json(manifest_path)
        if (manifest.get("video_sha256") != source["video"]["sha256"] or
                manifest.get("checkpoint_sha256") != checkpoint_sha or
                manifest.get("config_sha256") != prepared["config_sha256"]):
            raise ValueError("CALIBRATION_CACHE_IDENTITY_MISMATCH")
        repo.save_full_match_job(record["match_id"], {
            "match_id": record["match_id"], "status": manifest.get("status"),
            "manifest_path": str(manifest_path), "cache_key": manifest.get("cache_key"),
            "completed_chunks": sum(c.get("status") == "COMPLETE" for c in manifest.get("chunks", [])),
            "total_chunks": len(manifest.get("chunks", [])),
        })

    run_record = {
        "schema": "ptti-game4-calibration-balltrack-run-v1",
        "game": "game_4", "split_role": "CALIBRATION", "model": "BALLTRACK_V1_FROZEN_RAW",
        "video_sha256": prepared["video_sha256"], "checkpoint_sha256": checkpoint_sha,
        "runtime_root": str(config.runtime_root), "worker_python": str(config.worker_python),
        "chunk_seconds": chunk_seconds, "device": "cuda", "database": "NONE_IN_MEMORY_REPOSITORY_ONLY",
        "output_manifest": str(manifest_path), "cache_key": prepared["cache_key"],
    }
    run_record_path = source_path.parent / "BALLTRACK_RUN_PLAN.json"
    payload = json.dumps(run_record, ensure_ascii=False, indent=2)
    if run_record_path.exists():
        if run_record_path.read_text(encoding="utf-8") != payload:
            raise ValueError("BALLTRACK_RUN_PLAN_IS_IMMUTABLE")
    else:
        with run_record_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)

    resume = existing
    last = None
    while True:
        job = service.start(record["match_id"], device="cuda", resume=resume)
        resume = True
        while True:
            job = repo.get_full_match_job(record["match_id"]) or {}
            state = (job.get("status"), job.get("completed_chunks"), job.get("total_chunks"),
                     job.get("pause_reason"), job.get("last_error"))
            if state != last:
                print(json.dumps({"progress": state, "checkpoint": str(manifest_path)}, ensure_ascii=False), flush=True)
                last = state
            if job.get("status") == "BALLTRACK_COMPLETE":
                final = read_json(manifest_path)
                return {**run_record, "status": "BALLTRACK_COMPLETE",
                        "completed_chunks": len(final.get("chunks", [])),
                        "validation_path": str(manifest_path.parent / "full_match_validation.json"),
                        "output_csv": str(manifest_path.parent / "full_match_balltrack.csv")}
            if job.get("status") in {"FAILED", "SOURCE_CHANGED"} or job.get("last_error"):
                raise RuntimeError(f"BALLTRACK_STOPPED: {job}")
            if job.get("status") == "PAUSED":
                if job.get("pause_reason") != "BATCH_LIMIT_REACHED":
                    raise RuntimeError(f"BALLTRACK_PAUSED_WITHOUT_SAFE_BATCH_CHECKPOINT: {job}")
                while record["match_id"] in service.active:
                    time.sleep(.25)
                break
            time.sleep(max(1.0, poll_seconds))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-verification", required=True, type=Path)
    parser.add_argument("--chunk-seconds", default=30, type=int, choices=[30, 60])
    parser.add_argument("--poll-seconds", default=5.0, type=float)
    args = parser.parse_args()
    result = run(args.source_verification, chunk_seconds=args.chunk_seconds,
                 poll_seconds=args.poll_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
