# R5.1 acceptance and content closeout

## Identity and activation

The inspected source baseline is e39fe61a1b2ece168de47d3c282a3fcb6975fded.
The existing CI candidate remains built from
9abf6473b9d30b05dfa99e3f70b16c99ff701ed3; it does not include the later
e39fe61 deployment-script acceptance checks. Those checks run in the current
source-side dev_sync workflow, not in the archived candidate EXE or deployed
old backend. A candidate is not a formally accepted Stable release.

The candidate's 197 manifest files passed full verification. EXE SHA256 remains
febaba6b9844c36ba8f20c07f1bf8e45efab32efa31767f4ba56c4c40df6ae5f.
Current deployed commit remains 5cc753886b112305736fcc14ea77b37662726c9f.
Previous rollback commit f8a07e66666cf7129188ac15ee3389eaf8a782a0 also passed
full package verification. No activation pointer or deployed file was changed.

The real Shell Desktop is OneDrive-redirected and contains one PTTI Cinema.lnk.
Its target is Windows PowerShell invoking the existing fixed launcher's physical
MSIX-accessible path. Launcher VerifyOnly passed and selected the current R4
EXE offline. No mouse double-click, application window or home-page visibility
was verified this turn. Do not confuse file presence with native visibility.
The shortcut does not need recreation when an accepted pointer changes.

Available physical RAM was 2.025 GiB at preflight and 2.420 GiB at the later
check, below the 2.5 GiB guard. No GUI, rebuild or CI rerun was attempted.
Existing 16 native QA items remain MANUAL_REQUIRED. Remote installation stays
disabled; the existing integrity fallback is not a claim of launch-crash recovery.

## Content expansion actually executed

Sixteen explicit source links were manually reviewed and queried serially through
the existing public official oEmbed metadata method, with two-second spacing.
Publisher identity was checked against World Table Tennis / @wttglobal.
No video streams were requested or downloaded. External discovery pages were
used only to locate links; their inferred dates were not adopted as match facts.
A compact ITTFWorlds2025 year suffix required manual parsing correction; this
was a local metadata parsing issue, not evidence of an unavailable video.

The reviewed list is data/professional/catalog_expansion_r51_closeout.json.
Dates remain null, regional access and embedding permission remain UNKNOWN /
NOT_VERIFIED, native playback is NOT_TESTED, rights are REFERENCE_ONLY, analysis
is denied, and completeness_verified remains false. A publisher FULL MATCH
title is recorded as a claim, not as verified completeness. The China Smash
Sun Yingsha versus Wang Manyu title does not claim FULL MATCH and therefore
content_type remains UNKNOWN.

The isolated library contained 19 entries before this round's imports. The
follow-up batches added sixteen unique links total and recognized the eleven
previously imported links as duplicates. Repeating the final batch inserted
zero and reported sixteen duplicates. The resulting library API returns 35
unique references: MS 12, WS 9, MD 6, WD 6, XD 2. Since the initial 19-entry
state, the net additions are MS 5, WS 6, MD 2, WD 2 and XD 1. Each entry retains an independent source
timeline, null match mapping, unverified playback and denied analysis rights.

The last five included [Wang/Sun vs Huang/Chen, XD Final, China Smash 2025](https://www.youtube.com/watch?v=lQlw6B9uK3Y), [Sun/Wang vs Harimoto/Odo, WD Final, Europe Smash 2025](https://www.youtube.com/watch?v=gHS-9_mqE2A), [Huang/Wen vs Lin/Wang, MD semifinal, China Smash 2025](https://www.youtube.com/watch?v=LJcPKmgLijc), [Zhou/Chen vs Lin/Wang, MD Final, China Smash 2025](https://www.youtube.com/watch?v=btPhCu7kW1w), and [Kuai/Wang vs Chen/Qian, WD semifinal, China Smash 2025](https://www.youtube.com/watch?v=ThE8xkQAcuk). Official-channel metadata is corroborated by the [WTT official event directory](https://www.worldtabletennis.com/eventInfo?eventId=3085&innerselectedTab=Completed&selectedTab=Overview).
Neither link has been tested for watch-page playback, embedding, territorial
availability, license for analysis, or match completeness.

This count applies to the existing OS-temporary isolated content database.
The active desktop database remains unchanged at its previously reported 18
entries. No desktop-content synchronization is claimed. Original audit records,
favorites and source rows were not overwritten by the importer.

## Tests executed on this revision

- Catalog regression: 12 passed; one existing Starlette deprecation warning.
- Desktop updater logic: 15 passed; one actual-PowerShell test deselected.
- Real installed launcher VerifyOnly separately passed.
- Current, rollback and candidate full-file integrity checks passed.
- Exact frozen Hit configuration SHA256 unchanged:
  fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3.
- No full-suite, frontend build or native playback result is claimed this turn.

No Production DB, official TEST dataset, GAME_5, models, research parameters,
UI, updater architecture or desktop shortcut was modified.

## Short native handoff

When available physical RAM is at least 2.5 GiB, use the preserved candidate
native-qa/Launch-Candidate-QA.cmd. Open the authorized game_1 source in Cinema;
test play/pause, seek, rates, fullscreen and leave/return. Repeat in Vision and
confirm Analysis View stays disabled without matched evidence. Record the real
results in the preserved 16-row CSV, including null/UNKNOWN and technical media
release as NOT_TESTED where it cannot be measured. Close and restart the same
QA launcher to verify persistence. Only actual acceptance may authorize activation.

Deployment remains DESKTOP_UPDATE_PENDING and candidate remains CANDIDATE_READY.
