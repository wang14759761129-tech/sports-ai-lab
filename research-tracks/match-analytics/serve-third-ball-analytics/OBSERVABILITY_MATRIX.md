# Observability matrix — Pilot 1C

**Evidence:** Human-supplied dense frame-by-frame visual annotations for the same 10 points of Game 1. No additional points were added. Total annotation time and replay count were not recorded. Tier C means not reliably observable under the completed inspection of this 480p source; it is not a universal claim about all camera views or future tools.

**Uncertainty definition:** `(unknown + unclear) / eligible observations`. `not_applicable` is shown separately and excluded from numerator and denominator. A point that could not be reviewed from its start remains an eligible event for serve/receive variables, but the unobserved value is marked unknown. For `third_ball_side` and `third_ball_outcome`, eligibility requires `third_ball_attack=yes`; rows where attack is unknown/unclear have unresolved eligibility and are not forced into the denominator.

| Field | Current definition | Tier | Eligible | Unknown | Unclear | Not applicable | Uncertainty | Evidence / decision |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `match_id` | Match identifier | A* | 10 | 0 | 0 | 0 | 0% | Constant project metadata; retain |
| `game_number` | Game within match | A* | 10 | 0 | 0 | 0 | 0% | Fixed sample boundary; retain |
| `point_number` | Ordered point in game | A* | 10 | 0 | 0 | 0 | 0% | Ten sequential rows; retain |
| `server` | Serving side | A | 10 | 0 | 0 | 0 | 0% | Human annotation populated all 10; retain |
| `receiver` | Receiving side | A | 10 | 0 | 0 | 0% | Human annotation populated all 10; retain |
| `server_score_before` | Server score before point | A | 10 | 0 | 0 | 0 | 0% | Populated across 10 and agrees with the sequence; retain |
| `receiver_score_before` | Receiver score before point | A | 10 | 0 | 0 | 0% | Populated across 10 and agrees with the sequence; retain |
| `serve_side` | Broad service side | C | 10 | 1 | 9 | 0 | 100% | Serve sequence reviewed; current view/definitions did not support stable coding |
| `serve_length` | Short / half-long / long by bounce/end-line rule | C | 10 | 1 | 9 | 0 | 100% | No stable classifications under dense review |
| `serve_location` | Broad forehand / middle / backhand zone | C | 10 | 1 | 9 | 0 | 100% | No stable classifications under dense review |
| `serve_spin` | Backspin / sidespin / topspin / no-spin / mixed | C | 10 | 10 | 0 | 0 | 100% | No reliable spin label in any point; optional/future specialized observation for this source |
| `receive_type` | First receive action | C | 10 | 1 | 9 | 0 | 100% | Complete rallies reviewed for points 2–10; no stable classification |
| `receive_location` | Broad receive placement | C | 10 | 1 | 9 | 0 | 100% | No stable placement classification |
| `third_ball_attack` | Server's intentional attacking third contact | C | 10 | 1 | 9 | 0 | 100% | Third-ball sequence visible in some points, but attack classification failed the reliability threshold |
| `third_ball_side` | Side used for an established third-ball attack | C | 0 confirmed; 10 unresolved | 1 | 9 | 0 | N/E | No `third_ball_attack=yes`; eligibility unresolved. Do not treat 10 row labels as eligible-rate denominator |
| `third_ball_outcome` | Immediate outcome of an established third-ball attack | C | 0 confirmed; 10 unresolved | 1 | 9 | 0 | N/E | No `third_ball_attack=yes`; eligibility unresolved. Do not treat 10 row labels as eligible-rate denominator |
| `rally_length` | Ball contacts, serve included | C | 10 | 10 | 0 | 0 | 100% | Complete rally visible in reviewed points, but contacts were not counted reliably |
| `point_winner` | Side winning the point | A | 10 | 0 | 0 | 0 | 0% | Human visual annotation complete; retain |
| `point_outcome` | Player-perspective win/loss | A | 10 | 0 | 0 | 0 | 0% | Matches point winner; retain |
| `video_timestamp` | Point start, or first visible fragment if clipped | A† | 10 | 0 | 0 | 0 | 0% coded | Nine point starts are timestamped; point 1 uses clip offset 00:00:00 because its rally is already underway. Flag as partial, not exact start |
| `notes` | Evidence and ambiguity note | A* | 10 | 0 | 0 | 0 | Not applicable | Human-authored audit notes; present on all rows |

`A*` means directly available from sample/project structure or annotation record, not a sport-action measurement. `A†` is operationally useful after the partial-clip convention; one timestamp is a clip anchor rather than a true point start. **Tier B:** no field was shown to become reliably classifiable specifically through replay; replay count is unrecorded.

## Field-level interpretation

- **Core match-state fields:** 10/10 populated; scores and winners reconcile across the sequence.
- **Tactical serve/receive/attack/rally fields:** each unconditional core field has 100% unknown + unclear. These fail the ≤30% threshold for this source and current operational definitions.
- **Conditional third-ball fields:** zero confirmed eligible observations and 10 unresolved eligibility cases; uncertainty rate is not estimable. Their stored unknown/unclear labels remain preserved.
- `not_applicable` count is zero throughout these 10 supplied rows; it is not counted as uncertainty.
