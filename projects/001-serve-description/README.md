# Candidate study: within-game serve outcomes

**Status: proposed; data collection has not started.**

## Question and scope

For one selected table tennis match, describe each player's point-winning proportion when serving in the first versus second half of each game. Define a game as one scoring unit within a match and a point as one completed scoring event. This small analysis cannot support general conclusions about performance.

## Definitions to use if the study proceeds

- Unit of observation: one completed point.
- Required fields: `match_id`, `game_id`, `point_index`, `server_id`, `point_winner_id`, `source_reference`.
- Player IDs: anonymous labels `P1` and `P2`.
- Half: for a game with N points, point indices 1 through floor(N/2) are the first half; the remaining points are the second half. This is retrospective and is not a real-time predictor.
- Serve point-win proportion: points won by the server divided by service points, separately for each player and half.
- If a cell has no service points, report it as undefined rather than zero.
- Report numerator and denominator with every proportion.

## Before collecting data

- [ ] Find a lawful source and record its citation and permission conditions.
- [ ] Decide whether derived annotations may be shared; public access to video does not imply redistribution permission.
- [ ] Verify point order, serving identity, game boundaries, and completeness.
- [ ] Review a small annotated sample manually and record any uncertain points.
- [ ] Specify how unresolved missing points affect inclusion; never silently guess.

## Planned output

A data dictionary, a checked point table if shareable, a count-and-proportion table, one labelled chart, reproducible analysis instructions, and a short English report with Chinese learning notes.

## Interpretation limits

One match is a small, context-dependent sample. Opponent, score state, tactical changes, serving sequence, and annotation errors can affect the description. A difference between halves does not establish fatigue or improvement. There is no basis yet for machine learning or a causal conclusion.
