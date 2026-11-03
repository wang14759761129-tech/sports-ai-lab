# 01 — Match Descriptive Analysis

**Status:** PROJECT IN PROGRESS — EARLY EXPLORATION

## Question

**What happened in a table tennis match?**

## First phase

This study describes game scores, total points won and lost, point difference, game win rate, and a basic match summary. The input is a small synthetic practice CSV so another learner can run the same analysis.

## Method and output

The standard-library script in [`analysis/analyze_match.py`](analysis/analyze_match.py) reads [`data/match_scores.csv`](data/match_scores.csv), loops through each game, and applies a simple win/loss condition. The reproducible output is recorded in [`analysis/results.md`](analysis/results.md); field definitions are in [`data/DATA_DICTIONARY.md`](data/DATA_DICTIONARY.md).

The practice input produces 3 games won, 2 lost, 49 points won, 45 lost, a +4 point difference, and a 0.60 game win rate.

## Limitations

This is synthetic practice data, one match, and a descriptive baseline. It is not a real athlete finding and cannot explain causes, fatigue, tactics, or general performance.

## Upgrade route

1. **Level 1:** Describe what happened.
2. **Level 2:** Compare games and matches.
3. **Level 3:** Look for patterns.
4. **Level 4:** Use statistics.
5. **Level 5:** Form a research question.
6. **Level 6:** Develop a small research study.

The next step is to improve data definitions and learn multi-match comparison before adding advanced tools.
