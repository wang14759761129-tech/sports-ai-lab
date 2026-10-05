# New schema 1.0.0-new

Historical v0.3 source was absent; this does not assert compatibility with it. One CSV row = one point. UTF-8 or UTF-8 BOM, comma-separated, exact headers, case-sensitive codes. Extra columns are preserved. Scores are post-point. Row references include the header, so the first point is CSV row 2.

Required: `game` and `point` positive integers, starting at 1; `server` and `winner` A/B; `score_a`, `score_b` nonnegative integers. Games and points must be contiguous. Games end at 11+ with a two-point lead; no further point may occur in that game. Service alternates every two points, every point from 10–10. The first server of each game is inferred from its first recorded point; cross-game first-server alternation is not enforced because singles/doubles and match context are not represented. Only complete game prefixes are valid; the final game may be incomplete with a warning. Partial mid-game clips need a future starting-state adapter.

Optional categorical annotations (blank permitted, unknown values fatal):

| Column | Codes |
|---|---|
| serve_placement | short_fh, short_bh, short_middle, long_fh, long_bh, long_middle |
| serve_type | backspin, topspin, sidespin, no_spin, mixed |
| receive_type | push, flick, attack, block, other |
| third_ball_attack | yes, no |
| point_phase | serve, receive, third_ball, rally |
| outcome | winner, error |

`rally_length`: positive integer, number of ball contacts including serve. A service fault can be annotated 1. `third_ball_attack` describes the server's third-ball opportunity; `no` means annotated no attack, blank means unknown. `outcome` describes how the point ended and is counted for the point winner; it does not identify which player committed an error. `point_phase` is annotator-defined decisive phase: serve (contact 1), receive (contact 2), third_ball (contact 3), rally (contact 4+). Semantic agreement between optional fields is not currently enforced; annotations should be reviewed by both players.

Metadata: name, player_a, player_b, date, event, synthetic. Synthetic label is persisted and displayed. Product 0.1.0; analytics 0.1.0.
