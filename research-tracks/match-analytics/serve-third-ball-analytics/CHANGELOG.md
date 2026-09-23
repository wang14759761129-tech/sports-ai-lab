# Changelog

## v0.1 — 2026-09-22

- Initial research question and point-level schema.
- Added uncertainty labels and a three-zone serve-location guide.
- Added synthetic workflow test and staged pilot plan.

Future changes to category definitions must record what changed and why.

## v0.2 — 2026-09-23

- **What changed:** Added a visual-evidence gate for point-specific tactical coding and a Mini Pilot uncertainty threshold. The schema and category definitions are unchanged.
- **Why:** The supplied local video allowed visible scoreboard transitions to be read, but the sampled inspection did not reliably support serve, receive, third-ball, or rally classifications.
- **Expected effect:** Prevent score-only observations from being misrepresented as tactical annotations; pause expanded coding when core-field uncertainty is high.
- **Old definition:** The protocol did not specify minimum visual review conditions or a stop threshold.
- **New definition:** Review complete points at normal speed and replay; use scoreboard-only evidence for outcomes; pause expansion if unknown + unclear exceeds 30% in a core field.

## 2026-09-23 — Pilot 1B attempt (no protocol version change)

- The intended full-playback/replay feasibility check could not be performed because the available visual interface refused the local video under its security policy.
- No Pilot 1B observations, field tiers, timing, or protocol changes were claimed. Version remains v0.2; the earlier Pilot 1 record remains intact.

## v0.3 — 2026-09-23 — Pilot 1C human annotation calibration

- **What changed:** Clarified how to timestamp a point already underway at clip start; defined field-level eligible denominators and conditional eligibility for third-ball side/outcome; classified tactical fields as unusable for analysis from this 480p source unless future calibration succeeds; marked serve spin optional/future specialized observation for this source.
- **Evidence:** External dense frame-by-frame review supplied 10 rows. Core match-state fields were populated across all 10 points; serve/receive/third-ball/rally tactical fields remained unknown or unclear in every applicable row. `third_ball_side` and `third_ball_outcome` had zero confirmed eligible attacks. Total time and replay count were not recorded.
- **Why:** Avoid false uncertainty denominators and avoid treating unresolved tactical labels as usable evidence; preserve an honest clip-start timestamp for the partial first point.
- **Impact:** Core match-state description can be retained for this 10-point calibration sample. The current serve/third-ball association question does not pass its measurement gate for this source. No sample expansion is authorized by this result.
- **Schema:** Field list and 21-column structure unchanged; only the timestamp definition was clarified.
