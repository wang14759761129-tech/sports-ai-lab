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
