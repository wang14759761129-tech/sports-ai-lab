"""Validate the synthetic point schema with Python's standard library."""
import csv
import sys
from pathlib import Path

REQUIRED = {
    "match_id", "game_number", "point_number", "server", "receiver",
    "serve_length", "serve_location", "serve_spin", "receive_type",
    "third_ball_attack", "rally_length", "point_winner", "point_outcome",
}
PROJECT = Path(__file__).resolve().parents[2]
DATA = PROJECT / "data" / "raw" / "match_001_points.csv"

def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA
    with input_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        columns = set(reader.fieldnames or [])
    missing_columns = sorted(REQUIRED - columns)
    missing_values = sum(1 for row in rows for value in row.values() if value in ("", None))
    print(f"Rows: {len(rows)}")
    print(f"Missing required columns: {missing_columns}")
    print(f"Blank cells: {missing_values}")
    print(f"Input: {input_path}")

if __name__ == "__main__":
    main()
