# Video Feed v0.5.1 delivery record

## BEFORE / AFTER
The v0.5 native home showed one complete cover in the first viewport; athlete and event screens prioritized metadata. The v0.5.1 native source QA shows three complete 16:9 covers per row at a captured 1354x762 viewport, with the following row visible below. Wider layouts use four columns. Full 1920x1080 native capture was not obtained; a requested larger window was clipped by the available capture surface.

Home, athlete filtering, event filtering, search, favorites and local history share a source-backed feed. Analysis tools remain accessible through a secondary menu. Local playback reuses VideoEvidencePlayer; the five fixed score links use existing confirmed ScoreMoment guards. Missing indexes show an explicit empty state; Vision is disabled when no aligned trajectory exists.

## EVIDENCE / USER VALUE
Native pywebview SOURCE QA was launched against an isolated temporary TEST database, separate from the old Preview. Home and athlete filtering were clicked; Wang Chuqin returns four official-source entries. The registered licensed game_1 local video played with changing picture and advancing time, and remained registered after normal exit/restart. Screenshots stay in the local QA evidence directory and are not distributed with source.

One local research video remains playable; this sprint adds six distinct official source entries to the previous two, for eight official publisher full-match sources. This is not six additional verified playable videos. Users can browse sources directly without first navigating technical athlete/match metadata. No human time-saving measurement was performed.

## Source verification
All eight titles, channel and thumbnails were checked with official YouTube oEmbed; publisher is World Table Tennis. FULL MATCH is publisher metadata, not independent full-content verification. Duration, publishing date, API embeddability and regional permissions remain unknown. Two historical native embedding failures retain error 150. YouTube documents 150 as equivalent to 101 (embedding disallowed); it alone does not establish geography. One official watch page was opened this sprint and required sign-in to confirm the visitor was not a bot. No access control was bypassed.

Official professional playback verified inside PTTI: 0. Official watch-page playback verified this sprint: 0. One watch page LOGIN_REQUIRED, seven NOT_TESTED. External links are labeled accordingly; unverified sources do not auto-open an iframe or enter local watch history.

Reference: https://developers.google.com/youtube/iframe_api_reference

## Tests and limits
Python targeted suites: 41 passed (library, desktop preview, score navigation), plus 23 passed (database isolation, export security, overlay resources). The final library recheck passed 14 tests, overlapping the first group. Frontend: 34 passed (9 review, 5 score, 12 observation, 8 feed). TypeScript/Vite build, pip check, source compilation and diff check passed. Ruff is absent in the current venv and was not installed. Full Python regression was not rerun under low-memory conditions.

Last available RAM: 1.491 GiB, below the unchanged 2 GiB build guard. The independent v0.5.1 build entrypoint is prepared but no new EXE was built. Native SOURCE QA is not packaged Preview acceptance. Fixed-score empty states were read in the native accessibility tree; confirmed-score playback is covered by existing automated guards, not a new real-score manual acceptance.

## Safety and gate
Production DB, official TEST, GAME_5 and frozen algorithms were not accessed for this work. Frozen Hit config SHA256 remains fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3. No restricted media, model weights, local databases or machine-specific QA paths are included in this commit. No main merge, tag or Release.

Gate remains VIDEO_FIRST_V0_5_M1_PARTIAL. Source-fed UI provides visible browsing improvements; professional in-app playback and packaged v0.5.1 delivery remain incomplete.
