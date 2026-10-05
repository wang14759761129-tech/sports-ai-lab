# Product and research are distinct evidence layers

PTTI is software for the owner and Kaikai; [Serve & Third-Ball Analytics](../../../research-tracks/match-analytics/serve-third-ball-analytics/) defines research observation/evidence standards. Software percentages are not scientific results; hypotheses are not product facts.

Inspected at revision `1b30e8ea0f8a90a745fb6c30105599f0334fdf7c`: README, DATA_SCHEMA, PROTOCOL, ANNOTATION_GUIDE, ANALYSIS_PLAN, OBSERVABILITY_MATRIX, PILOT_1_REPORT, PILOT_1B_REPORT, PILOT_1C_REPORT, PILOT_2_PLAN, PILOT_2_REPORT, VIDEO_SOURCE_SCORECARD, LIMITATIONS, research CHANGELOG and root RESEARCH_LOG. Also inspected real match_001 CSV/metadata, synthetic example, validate_data.py and summarize_points.py. These are existing records, not new video observations.

Protocol v0.3 retains 21 fields. Pilot 1C's 10 points from one 480p source support match-state description only. Tactical fields are unknown/unclear. Conditional third-ball fields have **zero confirmed eligible attacks and ten unresolved eligibility cases**. Timing and replay count were unrecorded. No tactical superiority, causal inference or broader reliability claim is supported.

Pilot 1C decision remains REVISE / HOLD expansion; primary question remains ON HOLD PENDING MEASUREMENT FEASIBILITY. D/F tracks remain ACTIVE. Pilot 2 is planned and NOT STARTED. No video was inspected, no new measurements/source scores/verdicts were created in this integration. Historical research files and changelog stay unchanged.

Original PTTI commit `4585439ea11dc8250cc15031a991aa71084fea3f` is imported as an ancestor using non-squashed Git subtree into products/ptti. Research history also remains an ancestor. Original local annotated v0.1.0 is untouched in its original checkout. Monorepo release tag is ptti-v0.1.1. The inaccessible standalone PTTI remote is not used as the canonical destination.
