# Research Log

## 2026-09-22 — First reproducible match description

- **Current stage:** D — FIRST PROJECT IN PROGRESS; E/F infrastructure prepared
- **Question:** What happened in a small table tennis match when the game scores are described directly?
- **Hypothesis:** A short, explicit summary can show the basic shape of a match without explaining why it happened.
- **What I did:** Created a synthetic CSV, a standard-library Python script, a data dictionary, a result file, and a project README.
- **Finding:** The practice input describes 3 games won, 2 lost, 49 points won, 45 lost, a +4 point difference, and a 0.60 game win rate.
- **Limitation:** The data are synthetic practice data, not a real athlete dataset. There is one match, no uncertainty estimate, and no causal or general claim.
- **Next step:** Learn reliable CSV handling and descriptive statistics, then define a permitted multi-match comparison.

## 2026-09-22 — Flagship track opened

- **Project:** Serve & Third-Ball Analytics
- **Question:** How are serve characteristics associated with third-ball opportunities and point outcomes?
- **What was built:** A point-level schema, observation protocol, annotation guide, staged pilot plan, limitations, reliability design, analysis plan, synthetic example CSV, and standard-library validation/summary scripts.
- **Decision made:** Keep the first schema compact and make uncertainty explicit rather than forcing a guess.
- **What remains uncertain:** Whether the categories can be applied consistently to a permitted real match and how long annotation takes.
- **Next methodological problem:** Run Pilot 0, then select one permitted real match for Pilot 1.

## 2026-09-22 — Pilot 1 access checkpoint

- **Pilot:** Pilot 1 — One Real Match
- **Source:** Official WTT YouTube full-match URL supplied by the user
- **Points annotated:** 0; the fixed boundary is Games 1–3
- **Protocol version:** v0.1
- **Data quality:** Header-only 21-column CSV created; no point values entered
- **Main ambiguity:** The browser session reached an automated-access verification page, so no visual observation was possible.
- **Main methodological lesson:** A real annotation cannot begin until the source is actually viewable; an empty dataset is preferable to invented observations.
- **Next decision:** Complete the viewing-access verification, then run the 10–15 point Mini Pilot and checkpoint the protocol.

## 2026-09-23 — Pilot 1 Mini Pilot and Protocol Checkpoint

- **Pilot:** Pilot 1 — local user-supplied video; scoreboard displays Wang Chuqin and Fan Zhendong
- **Source:** Local video inspected in-session; no video, audio, or broadcast frames added to GitHub. The earlier official YouTube source access failure above is preserved.
- **Points annotated:** 10 outcome-only rows from Game 1; intended full sample boundary remains Games 1–3. Annotation paused before expanding.
- **Protocol version:** v0.2 (method update; 21-field schema unchanged)
- **Data quality:** Validator passed 10 rows, 21 columns, no blank cells, missing identifiers, duplicates, invalid categories, outcome errors, or sequence errors. Six tracked tactical fields are 100% unknown/unclear/not-applicable.
- **Main ambiguity:** Sampled inspection supports visible scoreboard transitions, but not reliable serve, receive, third-ball, or rally coding.
- **Main methodological lesson:** Outcome-only evidence must be kept distinct from tactical annotation; high uncertainty is a stop signal, not a prompt to guess.
- **Checkpoint:** KEEP existing schema and uncertainty categories; MODIFY visual-review protocol and add a >30% core-field uncertainty stop threshold; REMOVE none; ADD no columns.
- **Next decision:** Establish full-speed point-by-point review and measure annotation time; continue Games 1–3 only if the observation gate becomes workable, otherwise revise before Pilot 2.

## 2026-09-23 — Pilot 1B observation-feasibility attempt blocked

- **Pilot:** Pilot 1B — same first 10 points of Game 1; no sample expansion
- **Source:** Same user-supplied local video. File presence and technical properties were confirmed, but the visual browser refused local-file preview and prohibited alternate access workarounds.
- **Points re-reviewed under full-playback/replay protocol:** 0
- **Protocol version:** v0.2 unchanged
- **Data quality / uncertainty:** No new observations or valid Pilot 1B uncertainty rates. Prior Pilot 1 counts remain the baseline only; third-ball eligible denominators remain unestablished.
- **Annotation burden:** Not measured; scale cost not estimable.
- **Main methodological lesson:** File accessibility is not equivalent to visual review. A feasibility result requires actual complete-point inspection and timed replay, otherwise the honest outcome is unassessed.
- **Decision:** STOP / HOLD expansion of Pilot 1. This is a procedural stop, not evidence that the source itself is unsuitable.
- **Next decision:** Resume only when the same 10 points can be reviewed under the specified visual method; then calculate eligible-denominator uncertainty and timing before deciding GO / REVISE / PIVOT.

## 2026-09-23 — Pilot 1C human / visual annotation calibration

- **Pilot:** Same Match 001, Game 1 points 1–10; no sample expansion
- **Source/method:** User supplied external dense frame-by-frame visual annotation. Points 2–10 had full serve/rally review; point 1 began mid-rally. This is user-supplied observation, not a new Work video review.
- **Protocol version:** v0.3 (21-column schema retained; timestamp and conditional-denominator rules clarified)
- **Observability:** Match-state fields, scores and outcomes were populated for all ten rows. Tactical serve/receive/third-ball/rally fields remained unknown/unclear in every eligible row; no field was demonstrated to become reliably classifiable specifically through replay.
- **Data quality:** 10 rows/21 columns; validator passed all structure, category, participant, point-order, and adjacent score-progression checks. Scores and winners reconcile through 5–5.
- **Uncertainty:** Serve side/length/location 10/10; spin 10/10; receive type/location 10/10; third-ball attack 10/10; rally length 10/10. Third-ball side/outcome have 0 confirmed eligible attacks and 10 unresolved eligibility cases, so rates are not estimable. `not_applicable` count is zero.
- **Annotation burden:** 10 points checked; elapsed time and replay count not recorded; average and scale cost not estimable.
- **Main lesson:** Core match-state fields are usable in this segment, but the tactical variables needed for the primary association question do not meet the measurement gate on this 480p source.
- **Decision:** Pivot away from tactical association analysis for this source; retain the long-term flagship direction. Revise and hold sample expansion until a more suitable source or reliable tactical measurement is available.

## 2026-09-23 — Pilot 2 video-source validation opened

- **Current node:** D — Flagship Project ACTIVE; F — Measurement & Research Methods ACTIVE; Video Source Validation.
- **Purpose:** Test which video conditions support reliable tactical annotation, not compare player performance.
- **Scope:** Up to three candidate source classes; 10 points per actual source under Protocol v0.3. Do not expand the current Wang Chuqin vs Fan Zhendong sample.
- **Baseline distinction:** Pilot 1C supports “the tested 480p source was unsuitable for the current tactical annotation protocol.” It does not show tactical variables are unmeasurable from all table-tennis video and does not invalidate the long-term question.
- **Primary research question:** Retained unchanged and marked ON HOLD PENDING MEASUREMENT FEASIBILITY.
- **Status:** No Pilot 2 candidate source has been supplied or tested. No source verdict or project-level GO / CONDITIONAL GO / PIVOT is assigned yet.
- **Next:** Populate the source scorecard with actual video conditions, 10-point uncertainty rates, and measured annotation burden before making a decision.
