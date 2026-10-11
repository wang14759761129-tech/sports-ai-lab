# PTTI AFTERNOON GOAL R5 — evidence report (IN PROGRESS)

This is a live delivery report, not a completion claim. The full objective remains active. No research or product quality gate is upgraded.

## A. Executive summary

Completed source work: Cinema search now includes trustworthy linked athlete aliases, category and year tokens; rendered-card counts are accurate; heavy motion/tracking chunks are lazy; local Vision Lab exposes existing modules and analysis results; Lab permissions, source scope and packaged-worker commit binding are checked; rejected uploads are cleaned without deleting accepted inputs. Remaining: current-code full regression, real page/screenshots, controlled DEV smoke and successful desktop deployment.

## B. Product UI

R4 black four-column layout and top navigation remain. Source player stays outside the Lab tab switch. Analysis Results reuses existing per-job overlays and exports; it never binds those overlays to the top player implicitly. API errors remain visible outside the Ball tab. No current R5 rendered screenshot or native click is available: NOT_TESTED. Intermediate JSX transpilation is syntax evidence only.

## C. Video library

Preserved baseline: MS 7 / WS 3 / MD 4 / WD 3 / XD 1 = 18 public entries. Effective additions: 0. New official-page openings, actual match playback and PTTI embedded playback: 0 verified this sprint. Current availability recheck and completeness audit are incomplete; do not infer fresh playback from old observations. Full-match verification: no new evidence. Source acquisition is blocked by missing approved API/aggregation basis; no bulk YouTube scraping or media downloading performed. TV Tokyo link conditions were inspected; public visibility alone is not catalogue authorization. Historical WD observations remain historical, not R5 playback acceptance.

## D. Vision module map

UI Accessible below means a source-level reachable route, not an actual GUI PASS. Backend Ready means the specified contracts were inspected or tested, not model inference acceptance.

| Module | UI Accessible | Backend Ready | Model Ready | Smoke this sprint | Research gate / limitation |
|---|---|---|---|---|---|
| Source Video | VisionPlayer | video-evidence media API exists | not required | NOT_TESTED | FPS frame label remains estimated; no precise PTS claim |
| Ball Tracking | Lab Ball, existing import/job UI | permission/resource/cleanup tests pass | file present in earlier live inventory; not loaded | NOT_RUN | BALLTRACK_V1_FROZEN_RAW |
| Player Tracking | Lab players, existing seed/review tool | DEV-only sample/source scope inspected and tested | SAM2 Small file/runtime present; not probed | NOT_RUN | PARTIAL; IDs/seed review unchanged |
| Player Motion | Lab pose, existing 2D motion tool | DEV job and worker source scope tested | RTMPose ONNX file/runtime present; not loaded | NOT_RUN | EXPERIMENTAL; 2D estimates only |
| Hit / Events | Lab link to existing evidence workspace | existing candidate/review API retained | frozen rule configuration | NOT_RUN | HIT_EVENT_V0_2_PARTIAL; no v0.3 retuning |
| Score & Rally | Lab link to existing score review | existing ScoreMoment/observations retained | OCR not implemented | NOT_RUN | observation is not confirmed Point |
| Scene | Lab link to videoCenter scene gallery | scene/module contract tests pass | DINO/RT-DETR files present; not loaded | NOT_RUN | SCENE_BOOTSTRAP_PARTIAL; no new calibration acceptance |
| Analysis Results | direct reuse of completed analysis list | analyses/assets APIs exist | per-job provenance required | NOT_TESTED | no cross-source binding or quality upgrade |
| Diagnostics | lightweight /lab inventory and export | opt-in and low-RAM rejection tested | presence != readiness | lightweight probe only | CUDA NOT_PROBED; explicit heavier probe guarded |
| RacketPose / TrajPred | legacy Doctor status | status only | NOT_IMPLEMENTED per models.py | NOT_RUN | no fake model installation |
| PaddleOCR / MMAction / CoTracker | legacy module status | unavailable/experimental status retained | not established | NOT_RUN | no new installation or inference |

The Scene link exposes existing scene candidates/reviews; a complete interactive perspective-calibration product is not established by this audit.

## E. Performance

Intermediate Vite main JS changed from 513.90 to 465.82 kB after consistent lazy imports. This is bundle size only, not measured startup or RAM improvement. Earlier lightweight GPU diagnostic: RTX 5060 Laptop, 8151 MiB total, 6215 MiB free, driver 616.64; CUDA not probed and this snapshot is not current free capacity. RAM caused guarded full-suite stops at 1.95 and 1.99 GiB; no crash or deployment activation is inferred from a stop. The first stop occurred during synthetic scene contract test's real Torch probe; that test is now isolated. The second stop occurred earlier with test main RSS about 207 MiB; external/system pressure is not conclusively attributed.

## F. Tests

Latest targeted run: 26 backend tests passed, one Starlette/httpx deprecation warning. Earlier current-sprint frontend checks: feed 31, studio 17, score time 5, score observation 12, review queue 9 (74 total). Two changed JSX modules passed syntax transpilation before the last backend-only changes. Intermediate TypeScript/Vite passed before subsequent changes; final current-code checks PENDING. Full-suite collection was 599 before the newly added diagnostic guard test. Neither interrupted full execution is a pass. Real Vision smoke, migration acceptance, native R5 QA and fresh screenshot audit: NOT_TESTED.

## G. Git

Start: f8a07e66666cf7129188ac15ee3389eaf8a782a0. Branch: codex/ptti-afternoon-full-optimization-r5. Source milestones and exact test context are recorded in AFTERNOON-GOAL-R5-PROGRESS.md. Latest verified remote before this report: a6853d3c1413fb8428e9e4aa91e4edeba2f6b7be. Obtain current HEAD via git rev-parse HEAD; report is unfinished and must be refreshed after final validation. No main merge or release.

## H. Windows delivery

R5 new EXE: not generated. Active previous Preview: f8a07e66666cf7129188ac15ee3389eaf8a782a0. Existing EXE SHA256: c9bb2ff8846f21929da42c1e4b4924ed700f4c3d84bec2a5d48be80f1c0b9e48. Fixed Launcher and old R4 rollback preserved. DESKTOP_UPDATE_PENDING. NATIVE_GUI_VERIFIED: NOT_TESTED for R5. Remote installation remains disabled.

## I. Research integrity

Frozen Hit config remains SHA256 fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3. No frozen inference rules, weights or quality gates changed. Lab benchmark route rejects official TEST. DEV tracking/pose jobs exclude GAME_5 before source hashing. No Production DB, official TEST or GAME_5 experiment is authorized. No real-world truth is inferred from synthetic test fixtures.

## J. Next three actions

1. With stable memory headroom, finish current-code full regression/TypeScript/Vite and existing dev-sync; retain old pointer on any failure.
2. Execute bounded authorized DEV source/player/model QA, then native human acceptance separately; capture real screenshots and job provenance.
3. Obtain approved catalogue/API or reviewed rights-holder list before content additions; update each availability count with real evidence.
