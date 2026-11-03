# Video Source Scorecard

Purpose: assess whether a video source supports reliable table-tennis tactical annotation. This is a measurement check, not a player-performance comparison. Test no more than three new sources, with 10 points per source under Protocol v0.3.

## Source records

| Source ID | Class | Resolution | FPS | Camera angle | Distance | Rally continuity / cuts | Slow motion | Ball visibility | Serve-contact visibility | First-bounce visibility | Receiver-contact visibility | Serve-length uncertainty | Serve-location uncertainty | Receive-type uncertainty | Third-ball uncertainty | Rally-length uncertainty | Point winner / score uncertainty | Points reviewed | Total minutes | Replay count | Average min/point | Verdict |
|---|---|---|---:|---|---|---|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---|
| P1C-BASELINE (reference only) | Broadcast | 854×480 | 25 | Unknown / not recorded | Unknown | Points 2–10 reported full; point 1 starts mid-rally; transitions noted around points 6 and 10 | Not recorded | Not separately rated; ball trajectory/contact categories were not stable | Serve reviewed for points 2–10; first serve not visible from start | Not reliably classified; not separately rated | Not separately rated | 100% (10/10) | 100% (10/10) | 100% (10/10) | Attack 100%; side/outcome not estimable (0 confirmed eligible) | 100% (10/10) | 0% (10/10) | 10 | Not recorded | Not recorded | Not estimable | NOT SUITABLE |
| P2-A | High-quality broadcast | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting 10-point review | Awaiting 10-point review | Awaiting 10-point review | Awaiting 10-point review | Awaiting 10-point review | Awaiting 10-point review | — | — | — | — | — |
| P2-B | Fixed training camera | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting 10-point review | Awaiting 10-point review | Awaiting 10-point review | Awaiting 10-point review | Awaiting 10-point review | Awaiting 10-point review | — | — | — | — | — |
| P2-C | End-line / diagonal training view | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting source | Awaiting 10-point review | Awaiting 10-point review | Awaiting 10-point review | Awaiting 10-point review | Awaiting 10-point review | Awaiting 10-point review | — | — | — | — | — |

The Pilot 1C baseline is not a Pilot 2 candidate. Its verdict applies only to the tested source and current tactical protocol; it does not establish that tactical variables are generally unmeasurable from table-tennis video. Pilot 2 rows are reserved slots, not actual videos or measured findings.

Allowed verdicts for an assessed source only: **SUITABLE**, **CONDITIONALLY SUITABLE**, **NOT SUITABLE**. Do not convert missing measurements to a score or verdict. `third_ball_side` and `third_ball_outcome` must report confirmed eligible attacks and unresolved eligibility separately.

## Decision thresholds

- Rally length reliably observable in at least 90% of eligible points.
- Point winner / score state reliably observable in at least 95%.
- At least two of `serve_length`, `serve_location`, `receive_type`, and `third_ball_attack` have unknown + unclear ≤30% of eligible observations (preferred ≤20%).
- Record actual annotation start/end, elapsed minutes, points reviewed, replay count, and average minutes per point. Never estimate missed timing.

The scorecard reports each variable independently so a favorable field cannot mask a poor one.
