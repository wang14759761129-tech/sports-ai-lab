# Pilot 2 — Video Source Validation Plan

**Status:** PLANNED — no new candidate video source has been supplied or tested.

## Purpose

Identify video conditions that can support reliable table-tennis tactical annotation. Pilot 2 tests measurement feasibility, not player performance. Pilot 1C establishes that one 854×480, 25 fps broadcast source failed the current tactical annotation gate; it does not show that the research question is invalid or that all video sources fail.

## Candidate source classes

Test no more than three actual sources, with 10 points per source:

- **A — High-quality broadcast:** 1080p or higher preferred; 50/60 fps preferred; stable full-table framing, few rally cuts, visible ball, serve contact and first bounce.
- **B — Fixed training camera:** stable camera, whole table visible, no broadcast cuts, consistent angle, high resolution.
- **C — End-line / diagonal training view:** player-end or diagonal rear view to test serve placement/length, receive action, and third-ball visibility. Serve spin is not required for a source to pass.

Record actual resolution, frame rate if known, camera angle and distance, cuts/rally continuity, slow-motion availability, ball visibility, serve-contact visibility, first-bounce visibility, and receiver-contact visibility. Do not infer missing specifications.

## Sample and procedure

1. Use Protocol v0.3 without changing definitions mid-source.
2. Select exactly 10 consecutive points from one source; record the boundary and any clipped points. Do not skip difficult points.
3. Review points visually and record normal playback, pause/slow review, and replay usage distinctly.
4. Keep `unknown`, `unclear`, and `not_applicable` separate. Report `(unknown + unclear) / eligible observations`; exclude `not_applicable` from numerator and denominator. For third-ball side/outcome, eligibility requires `third_ball_attack=yes`; unresolved attack eligibility is reported separately.
5. Preserve raw annotations and document any protocol issue before revising definitions.

## Fields and targets

Benchmark `serve_length`, `serve_location`, `receive_type`, `receive_location`, `third_ball_attack`, `third_ball_side`, and `rally_length`. Track `serve_spin` separately as an optional high-difficulty field; never infer it from player identity, stereotyped motion, outcome, or later rally pattern.

Release thresholds for a source:

- `rally_length`: ≥90% reliably observable.
- point winner / score state: ≥95% reliably observable.
- At least two of `serve_length`, `serve_location`, `receive_type`, and `third_ball_attack`: unknown + unclear ≤30% (preferred ≤20%).
- Annotation cost must have actual elapsed time and replay counts; acceptable time must be judged from the measured workflow, not guessed.

Use 10 points for feasibility only; do not claim inter-rater reliability from one observer. If repeat coding or an additional annotator is later available, document it as a separate reliability check.

## Timing record

For each source record points reviewed, actual start time, actual end time, total active minutes, replay count, and average minutes per point. If timing is missed, write `NOT RECORDED`; do not estimate or borrow another source's rate.

## Scorecard and verdict

Enter results in `VIDEO_SOURCE_SCORECARD.md`. Use only these source verdicts:

- **SUITABLE:** all required quality targets pass and annotation cost is measured and judged acceptable.
- **CONDITIONALLY SUITABLE:** some tactical fields pass, but only a narrower schema meets targets.
- **NOT SUITABLE:** no tactical minimum passes or required objective fields fail.

After up to three sources, Pilot 2's project-level decision is:

- **GO:** at least one source meets the key tactical and objective targets → restart Real Match Pilot with that source.
- **CONDITIONAL GO:** some core tactical fields pass → narrow the tactical schema before scaling.
- **PIVOT:** reasonable tested conditions still fail broadly → revise collection method and then reconsider the research question. Do not infer this outcome from Pilot 1C alone.

## Current research position

The long-term primary question remains unchanged and is **ON HOLD PENDING MEASUREMENT FEASIBILITY**. Current node: **Video Source Validation**. No Pilot 2 outcome is assigned before candidate sources are tested.
