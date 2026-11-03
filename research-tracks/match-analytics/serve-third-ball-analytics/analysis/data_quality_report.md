# Pilot 1C — data quality report

**Grain:** one row per point; 10 rows, Game 1 points 1–10 only.

## Structural and consistency checks

- Columns: exact existing 21-column schema; no rows added.
- Blank required cells: 0
- Missing identifiers: 0
- Duplicate point IDs: 0
- Invalid categories/numbers: 0
- Point winner/outcome contradictions: 0
- Server/receiver identity conflicts: 0
- Point sequence errors: 0
- Adjacent score progression errors: 0
- Scores and winners reconcile across this segment through 5–5.

## Missingness and uncertainty

Uncertainty rate = `(unknown + unclear) / eligible observations`; `not_applicable` is counted separately and excluded from numerator and denominator.

| Field | Eligible | Unknown | Unclear | Not applicable | Uncertainty rate |
|---|---:|---:|---:|---:|---:|
| `server`, `receiver`, score-before fields | 10 each | 0 | 0 | 0 | 0% each |
| `serve_side`, `serve_length`, `serve_location` | 10 each | 1 each | 9 each | 0 | 100% each |
| `serve_spin` | 10 | 10 | 0 | 0 | 100% |
| `receive_type`, `receive_location` | 10 each | 1 each | 9 each | 0 | 100% each |
| `third_ball_attack` | 10 | 1 | 9 | 0 | 100% |
| `third_ball_side`, `third_ball_outcome` | 0 confirmed; 10 unresolved eligibility | 1 each in stored rows | 9 each in stored rows | 0 | Not estimable |
| `rally_length` | 10 | 10 | 0 | 0 | 100% |
| `point_winner`, `point_outcome` | 10 each | 0 | 0 | 0 | 0% each |

No `not_applicable` values were supplied. Third-ball side/outcome are conditional on a confirmed `third_ball_attack=yes`; there are no such rows, and ten points have unresolved attack eligibility. Their stored labels are retained but not used to claim an eligible denominator of ten.

## Timestamp caveat

Nine timestamps are supplied as point times. For point 1, `00:00:00` is the clip offset while the rally is already underway, not the true point start. The row note flags this boundary condition; schema wording now permits this explicit partial-point anchor.

## Analytical use

The CSV is structurally sound for the 10-point outcome/match-state description. Serve/receive/third-ball/rally fields fail the 30% uncertainty threshold or lack a confirmed conditional denominator, so they are not fit for association analysis in this sample/source.
