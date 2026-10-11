# PTTI R5.1 Stability and Playback Report

Date: 2026-10-11
Branch: `codex/ptti-r5-1-stability-playback`
Source baseline: `0ac1ecd0149fb3ff609f9ef66968a3a228f040ec`
Active desktop build observed: PTTI Video First R4, build `5cc753886b112305736fcc14ea77b37662726c9f`

## Scope and safety

Work stayed on the R5.1 branch. The active R4 instance and launcher pointer were left untouched. No production database, official TEST, GAME_5 labels, frozen Hit v0.3 configuration, or model weights were opened. The R4 health endpoint and the local DEV video registry were read only. No model worker or inference job was started.

The frozen Hit v0.3 configuration still hashes to `fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3`.

## Resource observations

The bounded sampler records RSS, USS/private memory when available, process-tree CPU, system available RAM, and aggregate NVIDIA memory. It omits command lines and executable paths, is capped at five minutes, and does not start or stop applications.

| Scenario | Samples | PTTI process tree | RSS median / peak | USS median / peak | CPU peak | System available RAM | GPU aggregate |
|---|---:|---:|---:|---:|---:|---:|---|
| R4 idle, earlier baseline | 3 | 7 processes | 520.6 / 520.6 MiB | 191.3 / 191.3 MiB | 0.79% | 2.20 median / 2.16 GiB minimum | 8,151 MiB total; 1,485 used; 6,415 free |
| R4 idle, after this run | 3 | 7 processes: PTTI plus WebView2 | 542.0 / 542.0 MiB | 197.2 / 197.2 MiB | 0.73% | 2.75 median / 2.74 GiB minimum | 8,151 MiB total; 1,440 used; 6,460 free |
| Python full regression | periodic system samples | pytest exited normally | process RSS `NOT_MEASURED` | process USS `NOT_MEASURED` | `NOT_MEASURED` | 3.59 GiB at start; 2.73 GiB minimum; no guard stop | `NOT_MEASURED` |
| Browser media playback | E2E state checks | isolated Edge plus local Vite | process RSS `NOT_MEASURED` | process USS `NOT_MEASURED` | `NOT_MEASURED` | 3.19 GiB before Vite/E2E; minimum during E2E `NOT_MEASURED` | `NOT_MEASURED` |

The prior full-suite interruption at 1.90 GiB cannot be attributed conclusively after the fact. This run used a single `pytest -q` process without a parallel-worker option, completed in 389.82 seconds, and left no test process running. Available RAM moved from 3.59 to a 2.73 GiB minimum and recovered above 3 GiB after the test. At a later read, the largest working sets were ChatGPT (912 MiB), OneDrive (819 MiB), and Windows Defender's MsMpEng (562 MiB); these were left untouched. This shows concurrent desktop memory pressure is material, but does not prove which process caused the earlier stop. No persistent pytest worker or resource leak was demonstrated.

The Windows app tree uses about 0.53 GiB RSS and 0.19 GiB USS at idle. This is a single short idle sample session, not a before/after optimization claim. Cold launch, sustained playback, Vision playback memory peak, and post-exit memory release remain `NOT_MEASURED`. GPU figures are system-wide; app-specific WebView VRAM is `NOT_MEASURED`.

## Playback and Vision

The active packaged backend reports PTTI Video First R4, build `5cc753886b112305736fcc14ea77b37662726c9f`. Its isolated DEV registry returned `game_1` (`35d991ea-e610-487c-985a-7d5bf949ba5f`) as available, SHA-verified (`1297b3db91f2e3e160337643695dff07eabf9785ea2d88c2f7b59687ba511148`), H.264 1920×1080 at 120 FPS, with `RESEARCH_NONCOMMERCIAL` rights.

The final E2E run used the current worktree frontend served from a temporary Vite development server and proxied only its local API requests to the already-running R4 DEV backend. It used an isolated headless Edge profile and was not native GUI or packaged-EXE verification. It verified real decoded media state and `currentTime`, not just HTTP status or element presence.

| Check | Status | Evidence |
|---|---|---|
| Cinema home and backend build identity | PASS | Expected R4 health response |
| Vision source `loadedmetadata` / `canplay` | PASS | Real local game_1, media range responses 206 |
| Vision play / pause | PASS | Time advanced about 0.52 s; paused delta 0 s |
| Vision seek | PASS | 2.500 s target; 2.500 s actual; measured error 0 ms in this run |
| Vision rates | PASS | 0.25×, 0.5×, and 1× reflected by the media element |
| Vision fullscreen | PASS | Enter and exit observed in headless Edge |
| Analysis View without a verified source-bound result | PASS | Correctly disabled; no synthetic overlay |
| Vision unmount cleanup | PASS after fix | Paused, `src` attribute cleared, `networkState=0` |
| Vision re-entry | PASS | New media element reached `readyState=4` |
| Cinema source `loadedmetadata` / `canplay` | PASS | Real local game_1 decoded |
| Cinema play / pause | PASS | Time advanced about 0.51 s; paused delta 0 s |
| Cinema seek and rate | PASS | 5.250 s target; 5.250 s actual; error 0 ms; 0.5× |
| Cinema fullscreen | PASS | Enter and exit observed in headless Edge |
| Cinema unmount cleanup | PASS | Paused, `src` attribute cleared, `networkState=0` |
| Native GUI | NOT_TESTED | No native-window interaction was performed |
| Verified analysis overlay | NOT_AVAILABLE | No real result bound to this video was present |

The test first exposed an automation-harness serialization error; the harness was corrected to return a boolean rather than a DOM media object. The next run then reproduced the actual Vision cleanup defect. `VisionPlayer` now pauses the captured media element, removes its `src`, and calls `load()` when the source changes or component unmounts. The same full browser run passed the cleanup assertion for Vision and Cinema. This prevents the detached Vision video from retaining its media request after returning to Cinema; no process-level memory reduction is claimed from this change.

## Vision resource guard

No inference or model smoke test was started. The currently measured available RAM remained below the existing 3.5 GiB Vision guard after tests, despite system GPU free memory around 6.3 GiB. No weights, official TEST labels, GAME_5 labels, or frozen Hit v0.3 settings were loaded or changed.

## Changes and verification

- Added `scripts/resource_measurement.py` and `tests/test_resource_measurement.py` for bounded resource sampling and summary checks.
- Added `scripts/qa_browser_playback.mjs` for local-only playback regression using the authorized DEV video and no new dependency.
- Fixed the sampler CPU metric to use process-tree CPU-time deltas.
- Fixed Vision media cleanup on source change and unmount in `frontend/src/VisionPlayer.tsx`.
- Fixed the browser harness to avoid returning a DOM object through CDP serialization.
- No Cinema playback logic, score/rights rules, model code, or frozen research configuration changed.

Current verification on the final source changes:

- Full Python suite: **604 passed**, 0 failed, 1 existing Starlette deprecation warning; 389.82 seconds. Minimum available RAM during run: **2.73 GiB**.
- Frontend tests: **74 passed** (Feed 31, Studio 17, Review Queue 9, Score Time 5, Score Observation 12).
- TypeScript and Vite production build: **passed**; 650 modules transformed.
- `pip check`: **passed**, no broken requirements found.
- `py_compile`: **passed** for the resource sampler and its tests.
- Browser harness syntax check: **passed**.
- Real local browser playback regression: **9 checks passed** across Cinema and Vision, with the evidence detailed above.
- Resource sampler tests are part of the full Python suite; the earlier focused run also reported 4 passed.
- `git diff --check`: passed on the final report and source diff before commit.
- Windows Preview candidate: **BUILT AND VERIFIED**; details below. The active launcher pointer was not changed.
- Native GUI validation: **NOT_TESTED**.

## Windows candidate Preview

An independent R4-profile candidate was built from commit `ae802c253cb4ca10a3104b6539fd25946ed2c7f8` under `C:\PTTI-R5.1-Candidates\video-first-r4-ae802c253c-20261011T091454Z\dist\PTTI-Video-First-R4-Preview`. The EXE is 8,108,838 bytes with SHA256 `8ca6915b602043c588eac8ba8113779f537c451648369ea0da36aac4c4100a32`; the complete package is 496,902,101 bytes and contains `_internal`. All 9 frontend distribution files matched their packaged counterparts by SHA256. `build-info.json` identifies the expected commit and `source_tree_dirty=false`.

The build started with 3.50 GiB available RAM, reached a 3.32 GiB minimum in the build resource log, and used a sampled peak aggregate build-worker RSS of 0.18 GiB. The package contains no research video, model weights, or production database. An isolated `--deployment-health-check` process then exited 0 and reported the same commit, product, and version. Its 290,816-byte QA database was created under `%TEMP%` at `ptti-r51-health-44fdef1f9276490e8304402165b427c8\matches.db`; available RAM reached a 3.44 GiB minimum. An initial health-check invocation used a path outside `%TEMP%` and produced no report; the application guard prevented it from using that database, and the check passed after moving to a fresh temporary location.

The candidate EXE was not opened as a visible native window and was not activated in the fixed launcher. The existing R4 remains the active desktop version and its process was left running.

## Gate

`R5.1_STABILITY_PLAYBACK_PARTIAL`

The full Python and frontend regressions pass, browser-hosted local video paths are verified after fixing Vision media cleanup, and an isolated Windows candidate passes package identity and startup health checks. There is still no native GUI run, no repeated per-scenario memory profile, no process-level playback peak measurement, and no verified analysis overlay. The active R4 desktop, launcher pointer, databases, and user records remain unchanged.
