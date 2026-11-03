# Project Roadmap — Next 12 Months

**Status:** PLANNED / LEARNING — measurement feasibility gate active

## Current gate — Pilot 2: Video Source Validation

Before collecting more points, test up to three candidate video-source classes with 10 points per source under Protocol v0.3. The purpose is to identify view conditions that support reliable tactical annotation, not to compare players. Pilot 1C is evidence about the tested 480p source only; the primary research question remains on hold pending this source validation.

Required release checks: rally length ≥90% reliably observable; point winner/score state ≥95%; and at least two of serve length, serve location, receive type, and third-ball attack at ≤30% unknown + unclear (preferred ≤20%). If none meets the tactical minimum, do not build a tactical dataset from the tested sources; reconsider collection conditions and only then revisit the research question.

| Period | Focus | Evidence to build |
|---|---|---|
| Months 1–2 | Descriptive analysis | Clean CSVs, definitions, one-match summaries |
| Months 3–4 | Comparison | Compare games or matches with explicit groups |
| Months 5–6 | Statistics | Variation, uncertainty, and careful interpretation |
| Months 7–8 | Research question | Narrow one question from observed patterns |
| Months 9–10 | Small study | A documented design, analysis, limitations, and reflection |
| Months 11–12 | ML / computer vision gate | Only a small baseline if foundations and data quality are ready |

The last phase is a gate, not a promise. The immediate project step is video-source measurement validation; stronger Python, data handling, and research literacy continue alongside it.
