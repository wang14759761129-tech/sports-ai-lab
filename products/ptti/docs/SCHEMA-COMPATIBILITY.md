# Protocol v0.3 → PTTI 0.1.1

Canonical [schema](../../../research-tracks/match-analytics/serve-third-ball-analytics/DATA_SCHEMA.md), [protocol](../../../research-tracks/match-analytics/serve-third-ball-analytics/PROTOCOL.md), [guide](../../../research-tracks/match-analytics/serve-third-ball-analytics/ANNOTATION_GUIDE.md), revision `1b30e8ea0f8a90a745fb6c30105599f0334fdf7c`. Both formats use one point per row. Native `1.0.0-new` remains separate and strict; only historical conversion permits uncertainty in internal fields.

All original values survive in `provenance.original_points` and `source_*` point columns. Primary classifications for 21 fields: DIRECT 2, RENAMED 3, DERIVED 6, OPTIONAL 4, UNSUPPORTED 3, CONFLICT 3. Unsupported analytic fields are preserved, not discarded.

| Research field | PTTI field | Compatibility | Transformation | Potential information loss | Validation rule | Notes |
|---|---|---|---|---|---|---|
| match_id | source_match_id | OPTIONAL | retain | none | one nonblank match ID per file | product UUID separate |
| game_number | game | RENAMED | name | none | contiguous from 1 | no reorder |
| point_number | point | RENAMED | name | none | per-game contiguous from 1 | no mid-game clips |
| server | server | DERIVED | player=A, opponent=B | none under declared perspective | known identity | never infer from scores |
| receiver | source_receiver | OPTIONAL | retain and validate opposite server | none | known opposite identity | native receiver implicit |
| server_score_before | score_a/score_b | DERIVED | map identity, add one to winner | before-score retained | known numeric score and progression | not guessed if unknown |
| receiver_score_before | score_a/score_b | DERIVED | map identity, add one to winner | before-score retained | known numeric score and progression | perspective swaps on service change |
| serve_side | source_serve_side | UNSUPPORTED | retain only | no product metric | protocol category/uncertainty | not placement |
| serve_length | serve_placement | DERIVED | combine short/long with observed zone | half_long has no native code | explicit valid pair | warn unavailable mapping |
| serve_location | serve_placement | DERIVED | forehand=fh, backhand=bh, middle=middle | needs length too | valid zone plus length | both raw labels retained |
| serve_spin | serve_type | RENAMED | same known codes | none | category/uncertainty | never infer spin |
| receive_type | receive_type | CONFLICT | chiquita→flick; drive/loop→attack; long_push/short_touch→push | grouped subtype detail | allowed code; per-row warning | source_receive_type exact |
| receive_location | source_receive_location | UNSUPPORTED | retain only | no product metric | category/uncertainty | not silently mapped |
| third_ball_attack | third_ball_attack | DIRECT | preserve yes/no/uncertainty | none | protocol code | denominator yes/no only |
| third_ball_side | source_third_ball_side | UNSUPPORTED | retain and report quality | no performance metric | category/uncertainty | eligible only with yes attack |
| third_ball_outcome | source_third_ball_outcome | CONFLICT | retain, never map to final point win | immediate success ≠ final win | category/uncertainty | product conversion differs |
| rally_length | rally_length | DIRECT | contacts including serve | none | positive number or uncertainty | uncertain excluded from numeric stats |
| point_winner | winner | DERIVED | player=A, opponent=B | none under declared perspective | known winner | never guess from win/loss |
| point_outcome | source_point_outcome | CONFLICT | retain win/loss, leave native outcome blank | win/loss ≠ winner/error | known summary agrees with winner | no guessed error attribution |
| video_timestamp | source_video_timestamp | OPTIONAL | verbatim | none | retained text, no parsing claim | partial clip flag stays in notes |
| notes | source_notes | OPTIONAL | verbatim | none | text | audit information |

## Explicit limits

Import UI fixes research player=A and opponent=B; users enter names accordingly, with no inferred athlete identity. Unknown core identities or score-before fields are preserved in failed-import provenance but rejected because canonical scoring cannot be generated reliably. Missing optional tactical fields warn and remain blank. Unknown, unclear and N/A never become certain labels; a composite placement has only one uncertainty code, with both input codes retained in source columns.

Reject mixed protocols, multiple matches, duplicate headers, malformed rows, invalid codes and impossible score/service sequences. Both schemas require complete game prefixes from point 1. Cross-field annotation consistency, doubles identities, cross-game first server and match-length rules are unvalidated. Syntactic validity is not measurement reliability.

The original research synthetic example has a service order incompatible with the product's two-point rule. It is preserved unchanged, not advertised as a valid product template. A newly generated, labeled synthetic Protocol v0.3 example is delivered instead. The real Pilot 1C fixture is tested separately, with no tactical conclusions.
