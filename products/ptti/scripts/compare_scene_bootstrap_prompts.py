"""Compare the two bounded scene prompt probes on the same sampled frames."""

import json
import os
from pathlib import Path

from backend.scene_bootstrap import PROMPT_PROFILES, attach_roles


def summarize(path: Path) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    grouped = {}
    for item in report["detections"]:
        grouped.setdefault(item["frame"], []).append(item)
    table_frames = player_frames = scoreboard_frames = 0
    for frame in report["keyframes"]:
        rows = grouped.get(frame["frame"], [])
        tables = [d for d in rows if "table" in d["label"].casefold() and
                  d["bbox"][2]-d["bbox"][0] >= frame["width"]*0.2 and
                  (d["bbox"][2]-d["bbox"][0])*(d["bbox"][3]-d["bbox"][1]) >= frame["width"]*frame["height"]*0.03]
        table = max(tables, key=lambda d: d["detector_score"], default=None)
        table_frames += int(table is not None)
        roles = attach_roles(rows, table["bbox"] if table else None)
        hints = {d["spatial_hint"] for d in roles
                 if "person" in d["label"].casefold() or "player" in d["label"].casefold()}
        player_frames += int({"PLAYER_LEFT_CANDIDATE", "PLAYER_RIGHT_CANDIDATE"}.issubset(hints))
        scoreboard_frames += int(any("scoreboard" in d["label"].casefold() for d in rows))
    n = len(report["keyframes"])
    prompt_id = report["model"].get("prompt_id") or path.stem.rsplit("_", 1)[-1]
    return {"prompt_id": prompt_id, "prompt": report["model"].get("prompt", PROMPT_PROFILES[f"bootstrap-{prompt_id}"]),
            "sampled_frames": n,
            "table_candidate_frames_percent": round(100*table_frames/max(1,n), 1),
            "two_side_person_candidate_frames_percent": round(100*player_frames/max(1,n), 1),
            "scoreboard_candidate_frames_percent": round(100*scoreboard_frames/max(1,n), 1)}


def main():
    root = Path(os.environ.get("LOCALAPPDATA", Path.home()/"AppData/Local")) / "PTTI-Dev/vision-v2/scene-bootstrap"
    records = [summarize(root/"scene_bootstrap_prompt_a.json"), summarize(root/"scene_bootstrap_prompt_b.json")]
    result = {"purpose": "DEVELOPMENT_PROMPT_COMPARISON_ONLY", "same_sample": True,
              "prompt_definitions": PROMPT_PROFILES, "runs": records,
              "warning": "Coverage counts only; no object ground truth, accuracy claim, or holdout evaluation."}
    (root/"scene_bootstrap_prompt_comparison.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
