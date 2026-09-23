# Serve & Third-Ball Analytics

**Status:** LONG-TERM FLAGSHIP PROJECT · PROJECT IN PROGRESS

## Primary research question

How are serve characteristics associated with third-ball opportunities and point outcomes in competitive table tennis?

This project uses **associated with**, not **causes**. It is a developing observational workflow, not a completed study or published result.

## Why this project exists

- **Table tennis expertise:** My training and match experience helps me understand the tactical context behind the variables.
- **Data science:** The question requires structured point-level data, cleaning, descriptive statistics, comparison, and later visualisation.
- **Research:** A defined question can grow through explicit methods, limitations, and reproducible records.
- **Computer vision:** Later, permitted video may support semi-automated annotation; manual definitions come first.
- **Long-term academic value:** A careful multi-year project can become material for undergraduate research conversations, a CV, and an SOP without claiming a formal research result today.

## Current stage

**Pilot 2 — Video Source Validation.** Pilot 1C used human visual annotations on 10 points from one 854×480, 25 fps broadcast source. Match-state fields were populated; tactical labels did not meet the reliability threshold. The primary question is **ON HOLD PENDING MEASUREMENT FEASIBILITY** while up to three video source classes are assessed with 10 points each.

See the [Pilot 2 plan](PILOT_2_PLAN.md), [source scorecard](VIDEO_SOURCE_SCORECARD.md), and [current report](PILOT_2_REPORT.md). No new source has been assessed yet.

## Research design

One point is one row. The first pilot will test whether serve, receive, third-ball, rally, and outcome variables can be annotated consistently. See [RESEARCH_QUESTION.md](RESEARCH_QUESTION.md), [PROTOCOL.md](PROTOCOL.md), and [ANNOTATION_GUIDE.md](ANNOTATION_GUIDE.md).

## Data and analysis

The repository contains 10 independently created structured point annotations for Pilot 1C; the original video and broadcast frames are not included. [`data/sample/example_points.csv`](data/sample/example_points.csv) remains synthetic workflow-testing data. Tactical values from the Pilot 1C source remain uncertain and are not used for association analysis. Future statistical and predictive work is planned, not implemented.

## Limitations

The project currently has no real sample, no inter-rater reliability evidence, manual-annotation uncertainty, and no basis for causal inference. See [LIMITATIONS.md](LIMITATIONS.md).

## Roadmap

Synthetic workflow test → Pilot 1 real-match calibration → Pilot 2 video-source validation → restart a bounded real-match pilot only after the source passes measurement gates → descriptive dataset → comparison → statistical association → carefully scoped study → possible computer-vision baseline.

## Reproducibility

Use the documented schema, never guess uncertain labels, record the source and permissions, and run the scripts from their README. Every change to definitions is recorded in [CHANGELOG.md](CHANGELOG.md).

## Learning connection

This project drives Python CSV processing, descriptive statistics, research methods, annotation practice, scientific writing, and—later—computer vision.
