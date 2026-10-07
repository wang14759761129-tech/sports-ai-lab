"""Read scoped runtime metadata and saved DEV evidence. Never opens any SQLite database."""
from collections import Counter
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import subprocess

PRODUCT = Path(__file__).resolve().parents[2]
DEV = Path.home() / "AppData/Local/PTTI-Dev"
ROOT = DEV / "technology-foundation"


def main():
    environments = {"desktop": PRODUCT / ".venv", "balltrack": PRODUCT / "vision_worker/.venv",
                    "scene_person": DEV / "vision-v2/venv", "sam2": DEV / "vision-v2-sam2/venv",
                    "pose": DEV / "vision-v2-rtmpose/venv", "research_tools": ROOT / "tools-env",
                    "supervision": ROOT / "supervision-project/.venv", "rf_detr": ROOT / "rf-detr-env"}
    result = {"status": "SCOPED_READ_ONLY_AUDIT", "production_db": "NOT_OPENED", "environments": {}}
    for name, environment in environments.items():
        distributions = {dist.metadata.get("Name"): dist.version
                         for dist in metadata.distributions(path=[str(environment / "Lib/site-packages")])
                         if dist.metadata.get("Name")}
        result["environments"][name] = {"path": str(environment), "exists": environment.exists(),
                                          "packages": distributions}
    result["tools"] = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe", "docker", "uv", "ruff")}
    result["docker_standard_location_exists"] = Path("C:/Program Files/Docker/Docker/resources/bin/docker.exe").exists()
    result["base_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PRODUCT, text=True).strip()
    result["frontend"] = json.loads((PRODUCT / "frontend/package.json").read_text(encoding="utf-8"))
    result["requirements"] = {str(path.relative_to(PRODUCT)): path.read_text(encoding="utf-8")
                               for path in (PRODUCT / "requirements.txt", PRODUCT / "vision_worker/requirements.txt",
                                            PRODUCT / "scripts/requirements-player-motion-runtime.txt")}
    root = DEV / "evidence/hit_event_v0_2/full_dev/cross_game_baseline_20261007"
    cross = json.loads((root / "cross_game_full_dev_baseline.json").read_text(encoding="utf-8"))
    diagnostics = {"raw_fp": 0, "raw_fn": Counter(), "raw_candidates": 0,
                   "raw_fp_near_annotated_bounce": 0, "raw_fp_near_annotated_net": 0,
                   "raw_evidence_components": Counter(), "player_available": 0}
    for game in cross["games"]:
        if game["game"] not in {"game_1", "game_2", "game_3"}:
            raise ValueError("LOCKED_SPLIT_ACCESS_FORBIDDEN")
        evaluation_path = Path(game["evaluation_path"])
        evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
        raw = json.loads((evaluation_path.parent / "raw_candidates.json").read_text(encoding="utf-8"))
        fp = set(evaluation["stage_metrics"]["raw"]["by_tolerance"]["plus_minus_2_processing_frames"]["unmatched_prediction_ids"])
        diagnostics["raw_fp"] += len(fp)
        diagnostics["raw_candidates"] += len(raw)
        context = {row["event_id"]: row["ball_context_available"] for row in evaluation["ball_context_by_ground_truth"]}
        for row in evaluation["stage_attrition"]:
            if row["loss_stage"] == "RAW_GENERATOR_MISS":
                diagnostics["raw_fn"]["ball_context_available" if context[row["event_id"]] else "ball_context_insufficient"] += 1
        for row in raw:
            for key, value in row["evidence_components"].items():
                if value is not None:
                    diagnostics["raw_evidence_components"][key] += 1
        for event in ("BOUNCE", "NET"):
            overlap = evaluation["hard_negative_overlap"]["by_event_type"][event]
            # Exact original report field names are retained for reproducibility.
            ids = {r["candidate_id"] for r in overlap.get("matches", [])}
            diagnostics[f"raw_fp_near_annotated_{event.lower()}"] += len(fp & ids)
    result["bottleneck_diagnostics"] = diagnostics
    result["bottleneck_scope"] = "Event matching FP is not ball-detection GT. Bounce/net windows can include nearby genuine strokes."
    target = ROOT / "stack_inventory.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"inventory": str(target), "environment_count": len(environments),
                      "docker": result["tools"]["docker"], "diagnostics": diagnostics}))


if __name__ == "__main__":
    main()
