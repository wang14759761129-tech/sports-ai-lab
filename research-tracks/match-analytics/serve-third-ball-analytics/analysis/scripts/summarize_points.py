"""Summarise observed pilot rows; uncertain categories stay visible."""
import csv
import sys
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = PROJECT / "data" / "raw" / "match_001_points.csv"
FIELDS = ("serve_side", "serve_location", "serve_length", "serve_spin",
          "receive_type", "receive_location", "third_ball_attack",
          "third_ball_side", "third_ball_outcome", "rally_length")
UNCERTAIN = {"unknown", "unclear"}

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
        not_applicable = counts["not_applicable"]
        if field in {"third_ball_side", "third_ball_outcome"}:
            eligible_rows = [row for row in rows if row["third_ball_attack"] == "yes"]
            unresolved_eligibility = sum(row["third_ball_attack"] in {"unknown", "unclear"} for row in rows)
        else:
            eligible_rows = [row for row in rows if row[field] != "not_applicable"]
            unresolved_eligibility = 0
        eligible_counts = Counter(row[field] for row in eligible_rows)
        uncertain = sum(eligible_counts[value] for value in UNCERTAIN)
        rate = uncertain / len(eligible_rows) if eligible_rows else None
        rate_text = f"{rate:.2f}" if rate is not None else "NOT ESTIMABLE (0 eligible)"
        extra = f"; unresolved third-ball eligibility: {unresolved_eligibility}" if field in {"third_ball_side", "third_ball_outcome"} else ""
        print(f"{field}: row labels {dict(counts)}; eligible={len(eligible_rows)}; unknown={eligible_counts['unknown']}; unclear={eligible_counts['unclear']}; not_applicable={not_applicable}; uncertainty rate={rate_text}{extra}")
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
