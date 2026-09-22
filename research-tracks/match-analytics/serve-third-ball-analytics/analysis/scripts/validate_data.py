"""Validate the synthetic point schema with Python's standard library."""
import csv
from pathlib import Path

REQUIRED = {
    "match_id", "game_number", "point_number", "server", "receiver",
    "serve_length", "serve_location", "serve_spin", "receive_type",
    "third_ball_attack", "rally_length", "point_winner", "point_outcome",
}
DATA = Path(__file__).resolve().parents[2] / "data" / "sample" / "example_points.csv"

def main():
    with DATA.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    columns = set(rows[0]) if rows else set()
    missing_columns = sorted(REQUIRED - columns)
    missing_values = sum(1 for row in rows for value in row.values() if value in ("", None))
    print(f"Rows: {len(rows)}")
    print(f"Missing required columns: {missing_columns}")
    print(f"Blank cells: {missing_values}")
    print("Synthetic data for workflow testing only.")

if __name__ == "__main__":
    main()
