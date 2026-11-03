# Pilot 1C — Human / Visual Annotation Calibration

## Purpose

Calibrate the existing 21-field protocol using external human visual inspection of the same first 10 points of Game 1. This is a method test, not a tactical finding or final study.

## Sample

- Match shown in supplied metadata: Wang Chuqin vs Fan Zhendong
- Sample: Game 1, points 1–10 only
- No new points added
- Point 1 begins mid-rally in the video; serve and early contacts are not visible reliably.

## Observation method

The supplied observer reports dense frame-by-frame visual review. Points 2–10 include full serve/rally review. The observer says the video was not reviewed through a normal player replay workflow. Total annotation time and replay count were not recorded; no duration or replay frequency is inferred.

## Observability

- **Tier A:** Match/game/point identifiers, server/receiver, before-point scores, point winner, and point outcome were recorded for all 10 points. These objective match-state fields are suitable for the Core Schema in this sample. `video_timestamp` is usable with a partial-point flag for point 1.
- **Tier B:** None demonstrated. Replay was not counted as a distinct operation and no tactical field became reliably classifiable.
- **Tier C:** Serve side, length, location, spin, receive type/location, third-ball attack, and rally length were not reliably classifiable under the supplied dense review of this 480p source. This is a source-and-method-specific result, not a universal claim about other footage.
- **Conditional fields:** `third_ball_side` and `third_ball_outcome` have no confirmed eligible observations because no attack is coded `yes`; their uncertainty rates are not estimable. The 10 row-level `unknown`/`unclear` values remain as supplied.

**Serve-spin question:** No — serve spin was not reliably inferable from this 480p source under the supplied dense visual review (10/10 `unknown`). Keep the field in the schema, but treat it as optional/future specialized observation for this source; do not force-code it.

See `OBSERVABILITY_MATRIX.md` for all 21 fields and their counts.

## Uncertainty

Using `(unknown + unclear) / eligible observations`, with `not_applicable` excluded:

| Field group | Eligible | Unknown | Unclear | Not applicable | Uncertainty |
|---|---:|---:|---:|---:|---:|
| Identifiers and match state (`match_id`, `game_number`, `point_number`, `server`, `receiver`, score-before fields, winner, outcome) | 10 each | 0 | 0 | 0 | 0% each |
| `serve_side`, `serve_length`, `serve_location` | 10 each | 1 each | 9 each | 0 | 100% each |
| `serve_spin` | 10 | 10 | 0 | 0 | 100% |
| `receive_type`, `receive_location` | 10 each | 1 each | 9 each | 0 | 100% each |
| `third_ball_attack` | 10 | 1 | 9 | 0 | 100% |
| `third_ball_side`, `third_ball_outcome` | 0 confirmed; 10 unresolved eligibility cases | 1 each in the submitted rows | 9 each in the submitted rows | 0 | Not estimable |
| `rally_length` | 10 | 10 | 0 | 0 | 100% |

All tactical fields with an established denominator exceed the 30% stop threshold. No `not_applicable` values were supplied. Timestamp: 9 exact point-start timestamps and one clip-start anchor for the partial first point; it is flagged in notes.

## Annotation cost

Not measurable: 10 points checked, but total time and replay count were explicitly not recorded. Scale costs for 50 points, 5 matches, or 20 matches are not estimable. See `ANNOTATION_BURDEN.md`.

## Schema decision

- **Core Schema:** retain identifiers, server/receiver, score state, point winner/outcome, and timestamp with a partial-point note. These are the only fields that passed the supplied calibration in this clip.
- **Tactical Extension:** retain the fields in the 21-column raw schema for auditability, but do not use them in association analysis from this source. Treat serve spin as optional/future specialized observation for this 480p footage. The CSV schema remains unchanged.
- Conditional eligibility for third-ball side/outcome must be determined only after `third_ball_attack=yes`; unresolved attack status is reported separately.

## Research question decision

**PIVOT for this source.** The primary question about serve characteristics, third-ball opportunities, and point outcomes requires tactical fields that all failed the ≤30% uncertainty gate (or had no confirmed eligible denominator). Keep Serve & Third-Ball Analytics as the long-term project direction, but do not claim this video can answer its current association question.

A suitable next methods question is: *Which point-level fields can be coded with acceptable uncertainty from this 480p match video, and what additional viewing conditions are required?* This 10-point, single-observer pass is pilot evidence only; absent timing and independent/repeated annotation mean reliability and scalability remain untested.

## Protocol changes

Version **v0.3** clarifies partial-point timestamp handling, makes conditional third-ball denominators explicit, and restricts tactical analysis from this source unless a future calibration succeeds. The 21-column schema is unchanged; the timestamp definition is clarified in `DATA_SCHEMA.md`.

## Limitations

One match, one 10-point segment, one observer, no annotation duration, no replay count, no second annotator, and no repeated coding pass. Tactical uncertainty remains high. No causal, strategy-superiority, or population-level conclusion is supported.

## Decision

**REVISE / HOLD expansion.** Do not expand to 30–80 points for the current serve/third-ball association question using this video. The core match-state fields may be retained for descriptive recordkeeping, but the tactical research question needs a more suitable video source or redesigned measurements. Annotation time is unknown, so acceptable cost has not been demonstrated.
