"""Run a resumable, resource-guarded BallTrack baseline on one verified DEV game.

Only Extended OpenTTGames game_1 through game_3 are accepted. Output and state
remain under PTTI-Dev; the small SQLite job store is TEST-mode and lives in OS
temporary storage. No annotations are passed to the inference worker.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

from backend.fullmatch import file_sha256, source_identity
from scripts.stage_extended_openttgames_train import EXPECTED_BYTES

DEV_RUN_NAMESPACE = "full-dev-v1-compact-path"


def resolve_verified_dev_video(game: int, dataset_root: Path, manifest_path: Path | None = None) -> tuple[Path, dict]:
    if game not in {1, 2, 3}:
        raise ValueError("ONLY_DEV_GAMES_1_TO_3_CAN_ENTER_FULL_EVIDENCE_PIPELINE")
    dataset_root = Path(dataset_root).resolve()
    manifest_path = Path(manifest_path or dataset_root / "DEV_VIDEO_DOWNLOAD_MANIFEST.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    game_id = f"game_{game}"
    if manifest.get("dataset") != "Extended OpenTTGames":
        raise ValueError("UNEXPECTED_DATASET_MANIFEST")
    if manifest.get("dataset_revision") != "36471a76b969a0340df59258a813bf8214e68e7c":
        raise ValueError("UNEXPECTED_DATASET_REVISION")
    entry = next((row for row in manifest.get("games", []) if row.get("game") == game_id), None)
    if not entry or entry.get("split_role") != "DEV" or entry.get("status") != "VERIFIED":
        raise ValueError(f"DEV_VIDEO_NOT_VERIFIED:{game_id}")
    video = (dataset_root / "videos" / "train" / f"{game_id}.mp4").resolve()
    if not video.is_file() or video.stat().st_size != EXPECTED_BYTES[game_id]:
        raise ValueError(f"DEV_VIDEO_SIZE_INVALID:{game_id}")
    expected_path = Path(entry.get("video_path") or "").resolve()
    if expected_path != video or int(entry.get("current_bytes", -1)) != EXPECTED_BYTES[game_id]:
        raise ValueError(f"DEV_VIDEO_MANIFEST_PATH_OR_SIZE_MISMATCH:{game_id}")
    identity = source_identity(video)
    if identity["sha256"].lower() != str(entry.get("sha256") or "").lower():
        raise ValueError(f"DEV_VIDEO_SHA256_MISMATCH:{game_id}")
    return video, identity


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=int, choices=[1, 2, 3], required=True)
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    parser.add_argument("--chunk-seconds", type=int, choices=[30, 60], default=30)
    parser.add_argument("--max-new-chunks", type=int, default=1)
    parser.add_argument("--min-available-ram-gib", type=float, default=2.0)
    parser.add_argument("--poll-seconds", type=int, default=10)
    args = parser.parse_args()
    if args.max_new_chunks < 1 or args.min_available_ram_gib < 1.0:
        raise ValueError("BATCH_LIMIT_MUST_BE_POSITIVE_AND_RAM_GUARD_AT_LEAST_1_GIB")

    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")).resolve()
    dev_root = (local / "PTTI-Dev").resolve()
    dataset_root = dev_root / "research-datasets" / "ExtendedOpenTTGames"
    video, identity = resolve_verified_dev_video(args.game, dataset_root)

    from backend.database import ProductionDatabaseGuard
    from backend.full_match_pipeline import FullMatchService
    from backend.professional import ProfessionalMatchInput
    from backend.repository import Repository
    from vision.config import VisionConfig
    from vision.quality import classify, video_metadata

    db_path = (Path(tempfile.gettempdir()) /
               f"ptti-opentt-dev-game-{args.game}-{identity['sha256'][:12]}-compact.db").resolve()
    db_path.relative_to(Path(tempfile.gettempdir()).resolve())
    repo = Repository(db_path, guard=ProductionDatabaseGuard("test"))
    registry_path = PRODUCT_ROOT / "data" / "professional" / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    repo.seed_professional(registry)
    match_id = (f"research:extended-openttgames:game_{args.game}:"
                f"{identity['sha256'][:12]}:{DEV_RUN_NAMESPACE}")
    record = repo.get_professional_match(match_id)
    if record is None:
        athletes = registry.get("athletes", [])
        if len(athletes) < 2:
            raise RuntimeError("PROFESSIONAL_ATHLETE_SEED_MISSING")
        media = video_metadata(video)
        record = ProfessionalMatchInput.model_validate({
            "event_name": f"Extended OpenTTGames game_{args.game} · TRAIN research only",
            "competition_level": "Research dataset",
            "player_a_id": athletes[0]["athlete_id"],
            "player_b_id": athletes[1]["athlete_id"],
            "video_source_type": "RESEARCH_DATASET",
            "video_local_path": str(video),
            "rights_status": "RESEARCH_DATASET_AUTHORIZED",
            "licence_reference": "Extended OpenTTGames CC BY-NC-SA 4.0; non-commercial research; revision 36471a76b969a0340df59258a813bf8214e68e7c",
        }).to_record()
        record["match_id"] = match_id
        record["video_metadata"] = {
            **media, "sha256": identity["sha256"], "size_bytes": identity["size_bytes"],
            "mtime_ns": identity["mtime_ns"], "quality": classify(media),
            "dataset": "Extended OpenTTGames", "rights": "CC BY-NC-SA 4.0",
            "commercial_use": False, "official_split": "TRAIN", "split_role": "DEV",
            "balltrack_model": "BALLTRACK_V1_FROZEN_RAW",
        }
        repo.save_professional_match(record)
    elif record.get("video_metadata", {}).get("sha256") != identity["sha256"]:
        raise ValueError("EXISTING_DEV_MATCH_SOURCE_HASH_MISMATCH")

    # Keep this path compact: the packaged Windows host may resolve LocalAppData
    # through a long AppX alias, and FullMatchService adds hashed subdirectories.
    data_root = dev_root / "evidence"
    service = FullMatchService(repo, data_root, VisionConfig.load(),
                               chunk_seconds=args.chunk_seconds,
                               min_available_ram_gib=args.min_available_ram_gib,
                               max_new_chunks_per_run=args.max_new_chunks)
    existing_job = repo.get_full_match_job(match_id) or {}
    resume = bool(existing_job.get("manifest_path"))
    job = service.start(match_id, device=args.device, resume=resume)
    print(json.dumps({"game": f"game_{args.game}", "official_split": "TRAIN", "dev_role": "DEV",
                      "status": job.get("status"), "stage": job.get("stage"),
                      "video_sha256": identity["sha256"], "isolated_test_database": str(db_path),
                      "data_root": str(data_root), "chunk_seconds": args.chunk_seconds,
                      "max_new_chunks": args.max_new_chunks,
                      "min_available_ram_gib": args.min_available_ram_gib}, ensure_ascii=False), flush=True)
    last = None
    while True:
        job = repo.get_full_match_job(match_id) or {}
        snapshot = (job.get("status"), job.get("completed_chunks"), job.get("total_chunks"),
                    job.get("current_chunk"), job.get("pause_reason"))
        if snapshot != last:
            print(json.dumps({"progress": snapshot, "stage": job.get("stage"),
                              "resource_snapshot": job.get("resource_snapshot"),
                              "last_error": job.get("last_error")}, ensure_ascii=False), flush=True)
            last = snapshot
        if job.get("status") in {"BALLTRACK_COMPLETE", "PAUSED", "FAILED", "SOURCE_CHANGED"}:
            print(json.dumps({"final_job": job}, ensure_ascii=False), flush=True)
            if job.get("status") in {"FAILED", "SOURCE_CHANGED"}:
                raise SystemExit(2)
            break
        time.sleep(max(5, args.poll_seconds))


if __name__ == "__main__":
    main()
