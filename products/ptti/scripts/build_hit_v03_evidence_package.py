"""Convert cached frozen Hit Event v0.3 D outputs to a local JSONL review package.

This script reads only the cached TRAIN development outputs for game_1..game_3.
It never reads annotations, GAME_4/GAME_5, or the official test split.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/evidence-fusion/HIT_EVENT_V0_3_FROZEN_CONFIG.json"
EXPECTED_CONFIG_SHA = "fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3"
FROZEN_CONFIG_CANONICAL_SHA = "7b3715807699180b1559d28df5a456046c870035c3d3e9e728e6981185f8ef98"
SOURCE_VIDEO_SHA = {
    "game_1": "1297b3db91f2e3e160337643695dff07eabf9785ea2d88c2f7b59687ba511148",
    "game_2": "330ac07730bae6d899dbbbd00ad43500c583e6af6ea6dd261565bc77811eba66",
    "game_3": "e0f6a1ddbb838ac6acc67fb50f763728b589ec8f8cb7ababd9fa95f13c853e49",
}
SOURCE_RESULT_SHA = {
    "game_1": "9b92c4a6d4f33bcca4016d7667276feda8db7dafe09cd51498e9a9cb1974df77",
    "game_2": "fbb96373b194ce505bf353890c012d1ee5a7fc61af3864e4f49ea44481ee4ec7",
    "game_3": "23ae3797b75da751283536cc53c217cfdfc280dc8ddf0b447c380e8220e9475e",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package(game: str, output: Path) -> dict:
    config_sha = sha256(CONFIG)
    if config_sha != EXPECTED_CONFIG_SHA:
        raise RuntimeError(f"Frozen config file SHA mismatch: {config_sha}")
    cache = Path(os.environ["LOCALAPPDATA"]) / "PTTI-Dev/evidence/hit_event_v0_3/ablation-ABCD-20261008"
    source = cache / f"{game}-D-decoded.json"
    if not source.is_file():
        raise FileNotFoundError(source)
    result_sha = sha256(source)
    if result_sha != SOURCE_RESULT_SHA[game]:
        raise RuntimeError(f"Frozen result SHA mismatch: {result_sha}")
    decoded = json.loads(source.read_text(encoding="utf-8"))
    groups = (
        ("ACCEPTED", decoded.get("accepted", [])),
        ("REVIEW", decoded.get("review_candidates", [])),
        ("FILTERED", decoded.get("suppressed", [])),
    )
    total = sum(len(items) for _, items in groups)
    manifest = {
        "schema": "ptti-ai-evidence-package-v1",
        "dataset": "Extended OpenTTGames",
        "dataset_license": "CC BY-NC-SA 4.0",
        "commercial_use": False,
        "split": "train",
        "match_reference": f"Extended OpenTTGames TRAIN {game}",
        "source_video_sha256": SOURCE_VIDEO_SHA[game],
        "result_sha256": result_sha,
        "hit_event_version": "v0.3",
        "variant": "D",
        "model_version": "Hit Event v0.3 Frozen D (BallTrack RAW + Table + Player)",
        "frozen_config_sha256": FROZEN_CONFIG_CANONICAL_SHA,
        "frozen_config_file_sha256": config_sha,
        "timestamp_mapping": {
            "kind": "CANONICAL_SOURCE_TIMESTAMP_MS",
            "source_fps": 120.0,
            "timebase": "1/120",
            "frame_field": "source_frame",
            "timestamp_field": "timestamp_ms",
        },
        "counts": {
            "accepted": len(groups[0][1]),
            "review": len(groups[1][1]),
            "filtered": len(groups[2][1]),
            "total": total,
        },
        "source_result_path": str(source),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({"kind": "manifest", "manifest": manifest}, ensure_ascii=False) + "\n")
        for disposition, candidates in groups:
            for candidate in candidates:
                stream.write(json.dumps({"kind": "candidate", "disposition": disposition, "candidate": candidate}, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(output)
    return {"game": game, "path": str(output), "package_sha256": sha256(output), **manifest["counts"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", choices=sorted(SOURCE_VIDEO_SHA), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or (Path(os.environ["LOCALAPPDATA"]) / "PTTI-Dev/evidence/hit_v0_3_desktop_packages" / f"{args.game}-v0.3-d.jsonl")
    print(json.dumps(package(args.game, output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
