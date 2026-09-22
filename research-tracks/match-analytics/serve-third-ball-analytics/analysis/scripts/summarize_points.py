"""Create a small descriptive summary from the synthetic sample."""
import csv
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data" / "sample" / "example_points.csv"

def main():
    with DATA.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    attacks = [row for row in rows if row["third_ball_attack"] in ("yes", "no")]
    wins = sum(row["point_outcome"] == "win" for row in rows)
    print(f"Points: {len(rows)}")
    print(f"Serve locations: {dict(Counter(row['serve_location'] for row in rows))}")
    print(f"Third-ball attack rate among classified points: {sum(row['third_ball_attack'] == 'yes' for row in attacks) / len(attacks) if attacks else 0:.2f}")
    print(f"Point win rate: {wins / len(rows) if rows else 0:.2f}")
    print("Synthetic data for workflow testing only.")

if __name__ == "__main__":
    main()
