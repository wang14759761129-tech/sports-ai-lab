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
