"""Regenerate original SIMULATED_ONLY 11:8 input and review-targets output."""
import json
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from review_targets import build_review_targets


def make_game():
    match = "SIMULATED_ONLY:review-targets-11-8"
    points = []
    for n in range(1, 20):
        stage = ("END_AFTER_3_4_CONTACTS" if n in (2, 4, 6) else
                 "END_AFTER_5_PLUS_CONTACTS" if n in (8, 10, 12) else
                 "UNKNOWN" if n in (14, 16) else "END_AFTER_1_2_CONTACTS")
        points.append({
            "point_id": f"{quote(match, safe='')}/g01/p{n:03d}",
            "server": "unknown", "winner": "player" if n % 2 or n > 16 else "opponent",
            "observed_tactics": {}, "observed_rally_stage": stage,
            "rally_start_ms": n * 2000 if n <= 12 else None,
            "rally_end_ms": n * 2000 + 1500 if n <= 12 else None,
        })
    return {
        "contract_version": "ptti.quick-annotation/0.2",
        "dataset_id": "SIMULATED_ONLY:review-targets-dataset", "dataset_class": "SIMULATED_ONLY",
        "match_id": match,
        "video_context": {"source_id": None, "duration_ms": 60000, "duration_status": "PLAYER_METADATA_REPORTED"},
        "rules_context": {"games": [{"game_number": 1, "coverage": "COMPLETE_FROM_GAME_START", "first_server": "player"}]},
        "points": points,
    }


if __name__ == "__main__":
    data = make_game()
    for name, value in (("review-targets-11-8-input.json", data),
                        ("review-targets-11-8-output.json", build_review_targets(data))):
        (ROOT / "fixtures" / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SIMULATED_ONLY 19-point 11:8 fixture and output regenerated")
