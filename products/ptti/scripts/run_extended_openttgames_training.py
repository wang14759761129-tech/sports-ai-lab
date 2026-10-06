"""Run one licensed research training video through the frozen full-match path.

Uses a dedicated TEST-mode SQLite database under OS temp and stores pipeline
artifacts only under PTTI-Dev. Dataset annotations are never passed to inference.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

from backend.database import ProductionDatabaseGuard
from backend.full_match_pipeline import FullMatchService
from backend.professional import ProfessionalMatchInput
from backend.repository import Repository
from backend.fullmatch import source_identity
from vision.config import VisionConfig
from vision.quality import video_metadata, classify


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True, help="Must be inside PTTI-Dev")
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    parser.add_argument("--poll-seconds", type=int, default=30)
    args = parser.parse_args()
    args.video = args.video.resolve(); data_root = args.data_root.resolve()
    local = Path(os.environ["LOCALAPPDATA"]).resolve()
    standard_dev_root = (Path.home() / "AppData" / "Local" / "PTTI-Dev").resolve()
    configured_dev_root = (local / "PTTI-Dev").resolve()
    # Python tool environments can expose the same Windows directory through a
    # package alias. Verify both roots identify the same directory, then apply
    # the descendant check using the normal user-visible Windows path.
    if not os.path.samefile(standard_dev_root, configured_dev_root):
        raise RuntimeError("LOCALAPPDATA does not resolve to the expected PTTI-Dev directory")
    data_root.relative_to(standard_dev_root)
    training_root = data_root / "research-datasets" / "ExtendedOpenTTGames" / "videos" / "train"
    args.video.relative_to(training_root.resolve())
    if args.video.stem not in {f"game_{index}" for index in range(1, 6)}:
        raise RuntimeError("Only official Extended OpenTTGames training videos may enter this runner")
    run_id = uuid.uuid4().hex
    db_path = Path(tempfile.gettempdir()) / f"ptti-opentt-{run_id}.db"
    repo = Repository(db_path, guard=ProductionDatabaseGuard("test"))
    root = Path(__file__).resolve().parents[1]
    seed = json.loads((root / "data/professional/registry.json").read_text(encoding="utf-8"))
    repo.seed_professional(seed)
    athletes = seed["athletes"]
    if len(athletes) < 2:
        raise RuntimeError("Professional athlete seed does not contain two valid participants")
    media = video_metadata(args.video)
    identity = source_identity(args.video)
    record = ProfessionalMatchInput.model_validate({
        "event_name": "Extended OpenTTGames game_4 · research only",
        "competition_level": "Research dataset",
        "player_a_id": athletes[0]["athlete_id"], "player_b_id": athletes[1]["athlete_id"],
        "video_source_type": "RESEARCH_DATASET", "video_local_path": str(args.video),
        "rights_status": "RESEARCH_DATASET_AUTHORIZED",
        "licence_reference": "Extended OpenTTGames CC BY-NC-SA 4.0; non-commercial research; repo revision 36471a76b969a0340df59258a813bf8214e68e7c",
    }).to_record()
    record["video_metadata"] = {**media, **identity, "quality": classify(media),
                                "dataset": "Extended OpenTTGames", "rights": "CC BY-NC-SA 4.0",
                                "commercial_use": False, "split": "training"}
    repo.save_professional_match(record)
    config = VisionConfig.load()
    service = FullMatchService(repo, data_root, config)
    job = service.start(record["match_id"], device=args.device)
    print(json.dumps({"run_id": run_id, "match_id": record["match_id"], "job": job,
                      "media": media, "source_identity": identity,
                      "isolated_database": str(db_path), "pipeline_data_root": str(data_root)},
                     ensure_ascii=False), flush=True)
    last = None
    while True:
        job = repo.get_full_match_job(record["match_id"])
        snapshot = (job.get("status"), job.get("completed_chunks"), job.get("total_chunks"), job.get("current_chunk"))
        if snapshot != last:
            print(json.dumps({"progress": snapshot, "stage": job.get("stage"),
                              "last_error": job.get("last_error")}, ensure_ascii=False), flush=True)
            last = snapshot
        if job.get("status") in {"BALLTRACK_COMPLETE", "FAILED", "SOURCE_CHANGED"}:
            print(json.dumps({"final_job": job}, ensure_ascii=False), flush=True)
            if job.get("status") != "BALLTRACK_COMPLETE":
                raise SystemExit(2)
            manifest = json.loads(Path(job["manifest_path"]).read_text(encoding="utf-8"))
            output = Path(job["manifest_path"]).parent / "full_match_balltrack.jsonl"
            print(json.dumps({"observations": str(output), "manifest": str(job["manifest_path"]),
                              "frame_count": manifest.get("output", {}).get("frame_count"),
                              "cache_key": job.get("cache_key")}, ensure_ascii=False), flush=True)
            break
        time.sleep(max(5, args.poll_seconds))


if __name__ == "__main__":
    main()
