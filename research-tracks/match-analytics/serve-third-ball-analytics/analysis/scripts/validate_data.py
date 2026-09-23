"""Check point CSV structure and basic consistency using the standard library."""
import csv
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = PROJECT / "data" / "raw" / "match_001_points.csv"
REQUIRED = [
    "match_id", "game_number", "point_number", "server", "receiver",
    "server_score_before", "receiver_score_before", "serve_side",
    "serve_length", "serve_location", "serve_spin", "receive_type",
    "receive_location", "third_ball_attack", "third_ball_side",
    "third_ball_outcome", "rally_length", "point_winner", "point_outcome",
    "video_timestamp", "notes",
]
CATEGORIES = {
    "server": {"player", "opponent", "unknown"},
    "receiver": {"player", "opponent", "unknown"},
    "serve_side": {"forehand", "backhand", "unknown", "unclear", "not_applicable"},
    "serve_length": {"short", "half_long", "long", "unknown", "unclear", "not_applicable"},
    "serve_location": {"forehand", "middle", "backhand", "unknown", "unclear", "not_applicable"},
    "serve_spin": {"backspin", "sidespin", "topspin", "no_spin", "mixed", "unknown", "unclear", "not_applicable"},
    "receive_type": {"push", "flick", "chiquita", "drive", "loop", "long_push", "short_touch", "other", "unknown", "unclear", "not_applicable"},
    "receive_location": {"forehand", "middle", "backhand", "unknown", "unclear", "not_applicable"},
    "third_ball_attack": {"yes", "no", "unknown", "unclear", "not_applicable"},
    "third_ball_side": {"forehand", "backhand", "other", "unknown", "unclear", "not_applicable"},
    "third_ball_outcome": {"successful", "unsuccessful", "unknown", "unclear", "not_applicable"},
    "point_winner": {"player", "opponent", "unknown"},
    "point_outcome": {"win", "loss", "unknown"},
}

def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATA
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        columns = reader.fieldnames or []

    errors = []
    missing_columns = [name for name in REQUIRED if name not in columns]
    if missing_columns:
        errors.append(f"Missing required columns: {missing_columns}")
    blank_cells = sum(1 for row in rows for name in REQUIRED if name in row and not (row[name] or "").strip())
    missing_ids = sum(1 for row in rows if not row.get("match_id") or not row.get("game_number") or not row.get("point_number"))
    duplicates = []
    seen = set()
    bad_categories = []
    bad_numbers = []
    bad_outcomes = []
    for row in rows:
        key = (row.get("match_id"), row.get("game_number"), row.get("point_number"))
        if key in seen:
            duplicates.append(key)
        seen.add(key)
        for field, allowed in CATEGORIES.items():
            value = row.get(field, "")
            if value not in allowed:
                bad_categories.append((key, field, value))
        for field in ("game_number", "point_number"):
            try:
                if int(row.get(field, "")) < 1:
                    raise ValueError
            except ValueError:
                bad_numbers.append((key, field, row.get(field)))
        for field in ("server_score_before", "receiver_score_before", "rally_length"):
            value = row.get(field, "")
            if value not in ("unknown", "unclear", "not_applicable"):
                try:
                    if int(value) < 0:
                        raise ValueError
                except ValueError:
                    bad_numbers.append((key, field, value))
        expected = {"player": "win", "opponent": "loss"}.get(row.get("point_winner"))
        if expected and row.get("point_outcome") != expected:
            bad_outcomes.append((key, expected, row.get("point_outcome")))

    game_groups = {}
    for row in rows:
        key = (row.get("match_id"), row.get("game_number"))
        game_groups.setdefault(key, []).append(row)
    sequence_errors = []
    for key, group in game_groups.items():
        numbers = [int(r["point_number"]) for r in group if r.get("point_number", "").isdigit()]
        if numbers and numbers != list(range(1, len(numbers) + 1)):
            sequence_errors.append((key, numbers))

    print(f"Input: {path}")
    print(f"Rows: {len(rows)}")
    print(f"Required columns missing: {missing_columns}")
    print(f"Blank cells: {blank_cells}")
    print(f"Missing identifiers: {missing_ids}")
    print(f"Duplicate point IDs: {len(duplicates)}")
    print(f"Invalid categories: {len(bad_categories)}")
    print(f"Invalid numeric values: {len(bad_numbers)}")
    print(f"Point outcome inconsistencies: {len(bad_outcomes)}")
    print(f"Point sequence errors: {len(sequence_errors)}")
    print("Score consistency: not assessable when server/receiver scores are unknown.")
    if errors or blank_cells or missing_ids or duplicates or bad_categories or bad_numbers or bad_outcomes or sequence_errors:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
