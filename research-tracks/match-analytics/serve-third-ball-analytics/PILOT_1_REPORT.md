# Pilot 1 — Real Match Annotation Test

## Purpose

This pilot tests whether the current research protocol can be applied to one real table tennis match. This Mini Pilot is a method test only; it is not a final study and supports no causal or population-level claim.

## Match

The user-supplied local video has WTT-style graphics and a visible scoreboard naming Wang Chuqin and Fan Zhendong. Event, date, title, best-of format, and final score are unverified and recorded as unknown in metadata. The intended sample boundary remains Games 1–3; the Mini Pilot covers the first 10 points of Game 1 only.

## Data

The Mini Pilot contains 10 rows and preserves the existing 21-variable schema. Visible scoreboard transitions show the game reaching 5–5: Wang/player won 5 of the 10 observed points and Fan/opponent won 5. The timestamp values are five-second inspection intervals, not exact point times. Serve, receive, third-ball, and rally fields remain unknown or unclear because they could not be verified reliably during the sampled inspection. This is a score-only observation set, not a tactical dataset.

## Annotation experience

The scoreboard and point outcomes were readable in sampled frames. Tactical event details were not reliably classifiable from that inspection. Annotation elapsed time was not measured, so minutes per point are not reported.

## Data quality and descriptive results

The validator passed all structural checks for 10 rows and 21 columns. The six tracked tactical fields have 100% unknown/unclear/not-applicable values; third-ball attack rate, rally length summary, and server point-win rate are not estimable. See `analysis/data_quality_report.md`.

## Method problems and protocol changes

### Protocol Checkpoint (after 10 points)

- **KEEP:** The 21-variable schema and explicit `unknown` / `unclear` categories.
- **MODIFY:** Require full-point normal-speed inspection plus replay before tactical coding; scoreboard changes support outcomes only. Pause expanded annotation when a core field has more than 30% unknown + unclear values.
- **REMOVE:** None.
- **ADD:** No schema columns. Added an observation-evidence gate to the protocol.
- **Version:** Method-only update from v0.1 to v0.2; the schema itself is unchanged.
- **Decision:** Stop after the Mini Pilot. The current inspection did not validate reliable tactical annotation, so Games 1–3 will not be fully coded from score-only observations.

## Limitations

Only 10 scoreboard outcomes were recorded from one supplied video, by one annotator. Competition and date are unknown; timestamps are broad sampling intervals; no double-coding or reliability test was done. Tactical variables and annotation burden remain unvalidated. No strategy comparison or general conclusion is supported.

## Next step

Use a reliable full-speed, point-by-point viewing workflow and measure annotation time. If it supports reliable coding under v0.2, continue Games 1–3 without skipping difficult points; otherwise revise the protocol before Pilot 2.
