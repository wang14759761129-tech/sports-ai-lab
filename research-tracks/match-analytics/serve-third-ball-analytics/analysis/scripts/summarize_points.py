"""Summarise observed pilot rows; uncertain categories stay visible."""
import csv
import sys
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = PROJECT / "data" / "raw" / "match_001_points.csv"
FIELDS = ("serve_location", "serve_length", "serve_spin", "receive_type",
          "third_ball_attack", "third_ball_outcome")
UNCERTAIN = {"unknown", "unclear", "not_applicable"}

def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATA
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    print(f"Input: {path}")
    print(f"Points: {len(rows)}")
    winners = Counter(row["point_winner"] for row in rows)
    print(f"Point winners: {dict(winners)}")
    print(f"Player point win rate (Wang / player): {winners['player'] / len(rows) if rows else 0:.2f}")
    for field in FIELDS:
        counts = Counter(row[field] for row in rows)
        uncertain = sum(counts[value] for value in UNCERTAIN)
        rate = uncertain / len(rows) if rows else 0
        print(f"{field}: {dict(counts)}; unknown/unclear/not_applicable rate: {rate:.2f}")
    classified_attacks = [row for row in rows if row["third_ball_attack"] in {"yes", "no"}]
    if classified_attacks:
        attack_rate = sum(row["third_ball_attack"] == "yes" for row in classified_attacks) / len(classified_attacks)
        print(f"Third-ball attack rate among classified points: {attack_rate:.2f}")
    else:
        print("Third-ball attack rate: NOT ESTIMABLE (no points classified yes/no)")
    numeric_rallies = [int(row["rally_length"]) for row in rows if row["rally_length"].isdigit()]
    if numeric_rallies:
        print(f"Mean rally length among recorded points: {sum(numeric_rallies) / len(numeric_rallies):.2f}")
    else:
        print("Rally length summary: NOT ESTIMABLE (no numeric values)")
    if any(row["server"] == "unknown" for row in rows):
        print("Server point win rate: NOT ESTIMABLE (server identity unknown)")

if __name__ == "__main__":
    main()
