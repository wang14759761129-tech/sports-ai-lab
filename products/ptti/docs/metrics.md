# Metrics and missing data

All percentages use `rate(rows, predicate)` and report numerator, denominator, value, status. Empty denominators return null / insufficient data. No imputation. Both player views use the same recorded-match rally distribution (not a player-specific distribution).

| Metric | Definition |
|---|---|
| Points won | player wins / all points |
| Serve win | wins on own serve / own service points |
| Receive win | wins on opponent serve / opponent service points |
| Third-ball attack rate | yes annotations / yes-or-no annotations on own serve |
| Third-ball conversion | point wins after yes annotation / yes annotations on own serve; not necessarily direct third-ball winners |
| Average rally | sum of annotated contact counts / annotated points |
| Short / medium / long | annotated rallies of 1–4 / 5–8 / 9+ contacts divided by annotated rallies |
| By server / receiver | player point win rate grouped by who served/received |
| By serve placement/type | player win rate on own serve, grouped by nonblank annotation |
| By receive type | player win rate on opponent serve, grouped by annotation |
| By phase | player win rate grouped by decisive phase |
| Outcomes | counts of winner/error endings among points won; error attribution unavailable |
| Progression | actual post-point score for each recorded point, resetting by game |
| Momentum | consecutive point wins by same player, reset at game boundaries |

Reusable functions: `rate`, `groups`, and `analyze` in core/engine.py. Tests independently check numerators, group partitions, bands, mean, progression and runs; missing annotations are tested separately. Do not use small samples as causal coaching evidence.
