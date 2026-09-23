# Pilot 1 Mini Pilot — data quality report

**Status:** Structural validation passed; tactical variables have HIGH MEASUREMENT UNCERTAINTY.

## Dataset checks

- Points: 10
- Schema fields: 21 (existing schema retained)
- Blank cells: 0
- Missing identifiers: 0
- Duplicate point IDs: 0
- Invalid categories / numeric values: 0
- Outcome consistency errors: 0
- Point sequence errors: 0
- Score consistency by server/receiver: Not assessable because server and receiver are unknown.

## Uncertainty by tracked field

| Field | Unknown | Unclear | Not applicable | Uncertain / not applicable | Rate |
|---|---:|---:|---:|---:|---:|
| `serve_spin` | 10 | 0 | 0 | 10 | 100% |
| `serve_location` | 0 | 10 | 0 | 10 | 100% |
| `serve_length` | 0 | 10 | 0 | 10 | 100% |
| `receive_type` | 0 | 10 | 0 | 10 | 100% |
| `third_ball_attack` | 0 | 10 | 0 | 10 | 100% |
| `third_ball_outcome` | 0 | 10 | 0 | 10 | 100% |

Each core field exceeds the 30% stop threshold. Tactical rates are not estimable and expanded annotation is paused pending a reliable full-point visual review method.

## Outcome-only description

The inspected scoreboard transitions recorded 5 points for `player` (Wang Chuqin as displayed) and 5 for `opponent` (Fan Zhendong as displayed), reaching 5–5. This describes only the first 10 recorded points and does not establish tactical patterns or match-level performance.

Third-ball attack rate, rally-length summary, and server point-win rate are not estimable. The validator and summary scripts use Python standard library only.
