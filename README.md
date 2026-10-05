# Sports AI Lab

An undergraduate research workspace for exploring table tennis, human performance, data analysis, and—later—AI. The lab starts with careful definitions and simple baselines before complex models.

**Status:** PROJECT IN PROGRESS — early flagship repository. Results are currently practice or exploratory results, not general claims about athletes.

## Current flagship project

### Serve & Third-Ball Analytics — Pilot 2: Video Source Validation

**Current position:** D — Flagship Project ACTIVE · F — Measurement & Research Methods ACTIVE
**Protocol:** v0.3 · **Decision:** REVISE / HOLD
**Project status:** Pilot 1C complete; Pilot 2 planned, not started.

The project is nested in this repository, rather than being a separate GitHub repository. [Open the project folder](research-tracks/match-analytics/serve-third-ball-analytics/) or start with its [project README](research-tracks/match-analytics/serve-third-ball-analytics/README.md).

Pilot 2 tests which video conditions support reliable tactical annotation. It does not analyze player performance or treat Pilot 1C's single 480p source limitation as evidence that the research question is invalid.

## Research

[Serve & Third-Ball Analytics](research-tracks/match-analytics/serve-third-ball-analytics/) remains the flagship: Protocol v0.3, Pilot 1C REVISE / HOLD, Pilot 2 Video Source Validation planned and not started. The research question remains ON HOLD PENDING MEASUREMENT FEASIBILITY. Product integration does not change these conclusions.

## Product

[PTTI — Personal Table Tennis Intelligence](products/ptti/) is local-first Windows software for the owner and Kaikai. Stable version 0.1.2 provides Chinese desktop UX with Protocol v0.3 compatibility and evidence states. [Schema compatibility](products/ptti/docs/SCHEMA-COMPATIBILITY.md) · [research basis](products/ptti/docs/RESEARCH-BASIS.md) · [Windows release](https://github.com/wang14759761129-tech/sports-ai-lab/releases/tag/ptti-v0.1.2). Kaikai Test 01 is pending; The development branch adds an optional experimental BallTrack perception layer; RacketPose, trajectory prediction, LLM and cloud capabilities are not implemented. See [Computer Vision](products/ptti/docs/VISION.md).

## Research tracks

### Match Analytics — ACTIVE / LEARNING

Describe game scores, points won and lost, point difference, and game win rate before comparing matches or forming stronger questions.

### Training & Human Performance — PLANNED

Explore training load, practice consistency, recovery, and performance data only when definitions, consent, and data quality are clear.

### Computer Vision — PLANNED

Later explore movement or ball-tracking questions after Python, statistics, data management, and research methods are stronger.

## Research pipeline

**Question → Data → Method → Result → Limitation → Reproducibility → Reflection**

## Public research questions

### Descriptive

- What happened in a table tennis match?
- How are points distributed across games in a match?
- How often does a player win a game after reaching a given point difference?

### Comparative

- How do first and later games differ in point difference?
- Do practice matches and competition matches show different score patterns?
- How do serve, receive, or rally categories compare when they are recorded consistently?

### Statistical

- How stable is game win rate across repeated matches?
- What uncertainty should be reported when the number of matches is small?

### Predictive

- Can early-match descriptive variables support a modest, transparent baseline for later game outcome?

### Computer vision

- Can permitted video data help describe ball placement or movement patterns with a reproducible definition?
- Which visual measurement is reliable enough to compare across sessions?

These are questions to refine, not claims that have already been answered.

## Repository map

- [Serve & Third-Ball Analytics](research-tracks/match-analytics/serve-third-ball-analytics/): flagship project; current node is Pilot 2 video source validation
- [projects/01-match-descriptive-analysis](projects/01-match-descriptive-analysis/): first reproducible, synthetic practice study
- [RESEARCH_STANDARDS.md](RESEARCH_STANDARDS.md): shared evidence standard
- [PROJECT_ROADMAP.md](PROJECT_ROADMAP.md): a 12-month learning and project path
- [RESEARCH_LOG.md](RESEARCH_LOG.md): dated lab decisions and reflections
- [data](data/README.md): data source and sharing requirements
- [reports](reports/README.md): future reports with methods and limitations
