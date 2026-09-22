"""Describe one small table tennis match using only the Python standard library."""
import csv
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "match_scores.csv"

def load_games(path):
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))

def summarize_games(games):
    games_won = games_lost = points_won = points_lost = 0
    for game in games:
        player_score = int(game["player_score"])
        opponent_score = int(game["opponent_score"])
        points_won += player_score
        points_lost += opponent_score
        if player_score > opponent_score:
            games_won += 1
        else:
            games_lost += 1
    total_games = games_won + games_lost
    return {"games_won": games_won, "games_lost": games_lost, "points_won": points_won, "points_lost": points_lost, "point_difference": points_won - points_lost, "game_win_rate": games_won / total_games if total_games else 0}

def main():
    result = summarize_games(load_games(DATA_PATH))
    print(f"Games won: {result['games_won']}")
    print(f"Games lost: {result['games_lost']}")
    print(f"Total points won: {result['points_won']}")
    print(f"Total points lost: {result['points_lost']}")
    print(f"Point difference: {result['point_difference']}")
    print(f"Game win rate: {result['game_win_rate']:.2f}")

if __name__ == "__main__":
    main()
