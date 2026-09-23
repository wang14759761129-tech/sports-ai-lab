# Pilot 1B — Observation Feasibility Test

## Purpose

Determine whether the same first 10 points of Game 1 can support reliable observation of the existing 21 fields using complete-point viewing, pause, replay, and slow inspection.

## Sample

Intended sample: the same first 10 points of Game 1 from the user-supplied Wang Chuqin vs Fan Zhendong video. No points were re-reviewed under the Pilot 1B method. Sample expansion did not occur.

## Observation Method

The local file was confirmed present and its technical properties were checked (854 × 480, 25 fps, 57:16.2). The visual browser refused the local-file preview under its security policy. The refusal explicitly prohibited reaching the same video through alternate UI/workaround access. Therefore normal playback, pause, replay, and slow inspection were **not performed**. No new point-level observation or timing was generated.

## Observability Results

- **Tier A:** None established by Pilot 1B.
- **Tier B:** None established by Pilot 1B.
- **Tier C:** None established by Pilot 1B.

The prior Pilot 1 Mini Pilot only showed that scoreboard transitions could be read during sampled inspection. That is baseline evidence, not a full-playback observability classification. See `OBSERVABILITY_MATRIX.md`.

## Field Uncertainty Rates

No Pilot 1B eligible-observation rates exist because no re-annotation occurred. Pilot 1 baseline CSV rates remain documented separately: serve location, length, receive type, third-ball attack/outcome were 10/10 `unclear`; serve spin was 10/10 `unknown`; rally length was 10/10 `unknown`. For third-ball fields, eligible opportunity was not established, so those row-based rates are not valid eligible-denominator estimates.

## Annotation Time

Not measured. See `ANNOTATION_BURDEN.md`. Costs for 50 points, 5 matches, and 20 matches are not estimable.

## Most / Least Observable Variables

Pilot 1B cannot rank fields. In the earlier Mini Pilot, point outcomes and score transitions were readable under sampled inspection, while tactical variables were not; this does not prove direct observability during full playback.

## Schema Implications

Keep the 21-column schema unchanged for now. A **PROPOSED TIERED SCHEMA** may separate:

- **Core Schema (candidate):** match/game/point identifiers, score state, server/receiver, point winner/outcome, and rally length—subject to actual observability and reliability testing.
- **Tactical Extension (candidate):** serve side/length/location/spin, receive type/location, and third-ball variables—record only when visual evidence supports them; preserve uncertainty labels.

This is a proposal, not a frozen schema or a claim that the candidate core fields are reliable.

## Research Question Implications

The primary question remains unchanged pending valid feasibility evidence. Candidate alternatives for a later decision:

| Candidate | Measurement feasibility | Scientific value | Required data | Current readiness |
|---|---|---|---|---|
| A. How are reliably observable serve-placement categories associated with point outcomes within annotated matches? | Unknown until placement is tested with full-point review | Narrow association question with clear outcome | Reliable serve placement, point winner, multiple consistently coded matches | Not ready |
| B. How does rally length vary across points and games in selected table-tennis matches? | Unknown until contact counts are tested | Descriptive match structure; lower tactical specificity | Reliable rally length, game/point IDs, point outcomes | Not ready |
| C. What proportion of points are won by each player in a defined match sample? | Scoreboard outcomes were readable in the earlier sampled pass | Valid narrow descriptive question, but limited tactical explanation | Point sequence and winner from a defined sample | Pilot-level only; repeatable method not yet tested |
| D. How are third-ball attacks associated with point outcomes? | Unknown; third-ball eligibility and classification not tested under full playback | Directly connected to the flagship topic | Eligible opportunity, attack attempt/outcome, point winner; reliable definitions | Not ready |

No candidate is selected in this report. The original question is not defended at the cost of measurement validity.

## Protocol Changes

No evidence-supported protocol change can be justified because the required observation test did not run. Keep **v0.2**. No schema definitions were changed; no CHANGELOG version bump is made.

## Limitations

Pilot 1B was not executed. No full-playback/replay observations, field tiers, eligible denominators, replay frequency, or annotation duration are available. Browser security policy blocked the only attempted visual access route. The existing Pilot 1 baseline remains a 10-point sampled scoreboard pass, not a tactical feasibility test.

## Decision

**STOP / HOLD** expansion of Pilot 1. This is a procedural stop due to missing feasibility evidence, not a finding that the video source itself is unusable. Do not proceed to 30–80 points until the same 10 points can be reviewed under the specified method and meet the uncertainty/time/reliability gate.

## Restart condition

The user must provide a permitted viewing route that the visual interface can access, or personally perform the 10-point replay review and supply point-by-point annotations/uncertainties and timing. Do not upload the copyrighted source video to GitHub.
