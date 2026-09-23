# Observation protocol

**Status:** PRACTICING — protocol design, not completed data collection.

## Unit of analysis

One point is one row. Rally length counts ball contacts with the serve as contact 1, consistently across all observations.

## Match selection

The pilot may use my own training or competition video, or video that is publicly available and legally permitted for research. The sample will not be presented as representative of competitive table tennis.

## Observation procedure

1. Locate the point start and record the video timestamp. If the clip starts after a point has begun, record the first visible timestamp and flag the row as a partial point in `notes`; do not present the clip offset as an exact point start.
2. Record the score before the point when visible.
3. Identify server and receiver.
4. Classify serve side, length, location, and spin only when supported by the view.
5. Classify the first receive action and location.
6. Identify whether the server attempts a third-ball attack using the guide.
7. Record rally length and point winner.
8. Add a short note whenever visibility or classification is uncertain.

For point-specific serve, receive, third-ball, and rally fields, inspect the complete point at normal playback speed and use replay when needed. A scoreboard transition may support point winner and score progression only; it does not support tactical coding. If a field cannot be verified from the video, use the uncertainty labels below. If `unknown` + `unclear` exceeds 30% for a core field in the Mini Pilot, pause expanded annotation and review the observation method before continuing.

## Missing and uncertain data

**NEVER GUESS.** Use `unknown` when a variable should exist but cannot be observed, `unclear` when the video is ambiguous, and `not_applicable` when the event does not apply. Keep the row and preserve the uncertainty.

For uncertainty reporting, define the eligible denominator for each field before calculating: `unknown + unclear / eligible observations`. Exclude `not_applicable` from both numerator and denominator and report its count separately. `third_ball_side` and `third_ball_outcome` are eligible only when `third_ball_attack=yes`; when third-ball eligibility itself is unknown or unclear, report unresolved eligibility separately and do not substitute all point rows as the denominator.

For this 480p source, dense frame-by-frame review still produced no stable tactical labels in the first 10 points. Keep tactical variables in the schema for auditability, but do not use them in an association analysis from this source unless a future calibration pass yields reliable labels. Treat `serve_spin` as optional/future specialized observation for this source; only code it when visual spin evidence is clear, never from outcome or gesture alone.

## Real data collection plan

Pilot 1 targets one permitted match and approximately 30–80 points. The purpose is to test feasibility, not to produce a conclusion. Start with 10–15 points as a Mini Pilot and document a Protocol Checkpoint before expanding. If visual evidence is insufficient for the core tactical fields, stop after the Mini Pilot; do not fill the remaining rows by inference.
