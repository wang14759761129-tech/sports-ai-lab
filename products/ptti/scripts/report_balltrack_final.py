"""Freeze the official RAW default after the bounded BallTrack tuning pass."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vision.specialist import sha256, validate_model


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def persist(path, text):
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise FileExistsError(f"Refusing to overwrite frozen artifact: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main():
    out = ROOT / "outputs/vision/balltrack_final"
    a = load(out / "A_official.json")["known_evaluation"]
    d = load(out / "D_known_evaluation.json")
    training = load(out / "D_training.json")
    prov = training["provenance"]
    study = load(out / "decoder_study.json")
    split = load(out / "split.json")
    official = ROOT / "models/balltrack_best.pth"
    tuned = ROOT / "models/tti_tabletennis/tti_balltrack_final_v1_D.pth"
    validate_model(official, prov["parent_checkpoint_sha256"])
    validate_model(tuned, prov["checkpoint_sha256"])

    am, dm = a["tti_style"], d["tti_style"]
    accepted = (
        dm["recall"] >= am["recall"]
        and dm["false_positives"] <= am["false_positives"]
        and all(dm["catastrophic"][str(n)] <= am["catastrophic"][str(n)] for n in (20, 50, 100))
        and (dm["mean"] < am["mean"] or dm["p95"] < am["p95"])
    )
    if accepted:
        raise RuntimeError("Candidate met numeric guard; manual acceptance review required")
    decision = "BALLTRACK_V1_FROZEN_RAW"
    config = {
        "status": decision,
        "default_pipeline": "RacketVision RAW",
        "default_checkpoint": "products/ptti/models/balltrack_best.pth",
        "default_checkpoint_sha256": sha256(official),
        "tuned_candidate_checkpoint_sha256": sha256(tuned),
        "tuned_candidate_accepted": False,
        "decoder": {"threshold": 0.5, "method": "upstream largest thresholded contour bounding-box center", "local_refinement": "disabled", "diagnostic_candidate_nms_radius": 5},
        "training_config_sha256": sha256(out / "training_config.json"),
        "decoder_config_sha256": sha256(out / "decoder_config.json"),
        "split_sha256": sha256(out / "split.json"),
        "known_raw_sha256": sha256(out / "A_official.json"),
        "known_tuned_sha256": sha256(out / "D_known_evaluation.json"),
        "release_gate": "HISTORICAL_DB_UNVERIFIED",
        "vision_gate": decision,
        "final_untouched": "NOT_SELECTED_OR_RUN; candidate failed KNOWN and available official matches were exposed",
        "scope": "bounded post-match rally processing only; not live officiating or full-match structure/segmentation",
        "further_balltrack_v1_tuning": "FROZEN",
        "training": {k: prov[k] for k in ("racketvision_commit", "tti_commit", "epochs", "best_epoch", "gpu", "torch", "cuda", "training_seconds")},
    }
    cfg_path = ROOT / "configs/experiments/BALLTRACK_V1_FROZEN.json"
    persist(cfg_path, json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    cfg_sha = sha256(cfg_path)
    matches = lambda role: len({x.split("/")[1] for x in split[role]})
    lines = [
        "# BallTrack v1 frozen: Official RAW remains default", "",
        f"Vision Gate: `{decision}`. Release Gate: `HISTORICAL_DB_UNVERIFIED`. This finite tuning pass is complete. No production database access, release, merge, tag, RacketPose or TrajPred.", "",
        "## A. Background reproduction", "",
        "Upstream `create_median.py` sorts rally directories and frame paths, optionally chooses global evenly spaced indices from the combined frame list, computes a uint8 per-pixel median, and writes match-level `median.npz` (key `median`) plus PNG. The loader prefers this match-level asset, then a rally-level fallback. The earlier experiment sampled up to 100 frames inside each rally. This pass used the global sampling/median operation across all selected rally videos available for each match. It is the closest reproducible source-backed approximation, not a complete-match median: missing rallies and breaks are absent.", "",
        "## B. Expanded TRAIN / DEV", "",
        f"TRAIN: {len(split['train'])} clips / {matches('train')} matches; DEV: {len(split['dev'])} clips / {matches('dev')} matches; KNOWN: {len(split['known_evaluation'])} clips / {matches('known_evaluation')} matches. Match IDs are disjoint across roles. Frames are 1920×1080. Venue, camera, lighting, apparel and referee metadata were not reliably available and remain UNKNOWN.", "",
        "## C–E. Fine-tuning and decoder", "",
        f"One architecture-preserving run: Adam 1e-5, batch 2, seed 20261005, 15-epoch cap, patience 4, unchanged loss/mixup and upstream metric. It stopped after {prov['epochs']} epochs; best epoch {prov['best_epoch']} by DEV F1 {prov['validation_metric']['DEV_official_F1']:.6f}; training took {prov['training_seconds']:.2f}s on {prov['gpu']} ({prov['torch']}, CUDA {prov['cuda']}). DEV decoder study covered five thresholds (.35–.55), contour-box/global-max decoding and no/weighted-centroid/soft-argmax refinement. Selected setting stayed at threshold .50, largest contour box, no refinement. The 5×5 subpixel methods worsened mean/median error; threshold .40 raised recall but also >20px errors. No complex temporal tracker was reintroduced.", "",
        "## F. KNOWN evaluation: A Official RAW vs D tuned candidate", "",
        "| Measure | A RAW | D candidate |", "|---|---:|---:|",
        f"| Recall | {am['recall']:.4%} | {dm['recall']:.4%} |",
        f"| False positives / negative frames | {am['false_positives']}/{am['negative']} | {dm['false_positives']}/{dm['negative']} |",
        f"| Mean px | {am['mean']:.3f} | {dm['mean']:.3f} |",
        f"| Median px | {am['median']:.3f} | {dm['median']:.3f} |",
        f"| P95 px | {am['p95']:.3f} | {dm['p95']:.3f} |",
        f"| >20 px | {am['catastrophic']['20']} | {dm['catastrophic']['20']} |",
        f"| >50 px | {am['catastrophic']['50']} | {dm['catastrophic']['50']} |",
        f"| >100 px | {am['catastrophic']['100']} | {dm['catastrophic']['100']} |",
        f"| Official F1 | {a['official_style']['f1']:.6f} | {d['official_style']['f1']:.6f} |", "",
        f"Peak ranks (out of {a['peak_rank']['visible']} visible frames), cumulative: A `{a['peak_rank']}`; D `{d['peak_rank']}`.", "",
        "Fixed `match10/001 frame184` regression: A ball/clothing heatmap response .0445/.6646, GT rank 35; D .0517/.6504, rank 19. D improved ranking, but decoder landed at the same distractor coordinate with 429.79px error. This did not resolve the pink-referee failure. Heatmap responses are not calibrated confidence.", "",
        "The candidate failed acceptance: recall fell, mean/P95 and all catastrophic buckets worsened, while FP count stayed level. Official RAW remains default.", "",
        "## G. Final untouched evaluation", "",
        "Not selected or run: D failed KNOWN acceptance, and the pinned official match pool had already been exposed. No >=5-match unseen authorized test was consumed.", "",
        "## H–I. Frozen default and hashes", "",
        f"Default checkpoint SHA256: `{config['default_checkpoint_sha256']}`. Rejected D checkpoint SHA256: `{config['tuned_candidate_checkpoint_sha256']}`. Frozen config SHA256: `{cfg_sha}`.", "",
        "## J–L. Verification and gates", "",
        "Prior full suite: 124 passed, 0 failed, one existing Starlette/httpx deprecation warning. Training, GPU inference, decoder sweep and KNOWN evaluation completed. See Git history for code/test state; this report does not claim native GUI verification.", "",
        "Branch: `codex/ptti-v0.2-racketvision`. Release Gate remains `HISTORICAL_DB_UNVERIFIED`; Vision Gate is `BALLTRACK_V1_FROZEN_RAW`. No main merge, tag or release.", "",
        "## M. Limitations and real-match phase", "",
        "This is a bounded rally dataset, not full-match validation. Cross-match venue/camera/apparel diversity is unverified. Sparse annotations limit interpretation between labeled frames. Existing worker is capped at 1,800 frames and does not segment points/rallies. The only local personal MP4 found was a 22.45-second clip and was not used; no complete authorized WTT match was identified. The real professional-match pipeline therefore awaits a full-match local video path. Development and QA databases remain isolated from Production.", "",
    ]
    report = ROOT / "docs/BALLTRACK-V1-FROZEN.md"
    persist(report, "\n".join(lines))
    print(f"Frozen {decision}; config SHA256 {cfg_sha}; report {report}")


if __name__ == "__main__":
    main()
