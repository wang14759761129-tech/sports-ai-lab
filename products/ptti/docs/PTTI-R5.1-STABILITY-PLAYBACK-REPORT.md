# PTTI R5.1 Stability and Playback Report

Date: 2026-10-11
Branch: `codex/ptti-r5-1-stability-playback`
Source baseline: `0ac1ecd0149fb3ff609f9ef66968a3a228f040ec`
Active desktop build observed: PTTI Video First R4, build `5cc753886b112305736fcc14ea77b37662726c9f`

## Scope and safety

Work stayed on the R5.1 branch. The active R4 instance and launcher pointer were left untouched. No production database, official TEST, GAME_5 labels, frozen Hit v0.3 configuration, or model weights were opened. The R4 health endpoint and the local DEV video registry were read only. No model worker or inference job was started.

The frozen Hit v0.3 configuration still hashes to `fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3`.

## Resource observations

`scripts/resource_measurement.py` sampled the already-running R4 process tree for 4.188 seconds at two-second intervals (three samples). It records RSS, USS/private memory when available, process-tree CPU, system available RAM, and aggregate NVIDIA memory. It omits executable paths and command lines, is capped at five minutes, and does not start or stop applications.

| Scenario | Samples | Process tree | RSS median / peak | USS median / peak | CPU median / peak | System available RAM median / minimum | GPU aggregate |
|---|---:|---:|---:|---:|---:|---:|---|
| Existing R4, idle | 3 | 7 processes: PTTI plus WebView2 | 520.6 / 520.6 MiB | 191.3 / 191.3 MiB | 0.76% / 0.79% | 2.20 / 2.16 GiB | 8,151 MiB total; 1,485 MiB used; 6,415 MiB free |

GPU memory is system-wide. The NVIDIA compute-process query did not identify per-process memory for the WebView video tree, so app-specific VRAM is `NOT_MEASURED`. The CPU metric was corrected to use cumulative process CPU-time deltas; the earlier zero-valued sample from the first implementation was discarded.

Cold start, loaded home, video open, playback, seek, Vision switch, return to Cinema, and exit scenarios were not measured. No before/after product memory reduction is claimed. The existing desktop was not closed or relaunched.

## Playback and Vision

The R4 health endpoint reports the expected product and build. The isolated DEV registry returned the registered `game_1` source as available, SHA-verified, H.264 1920×1080 at 120 FPS, with `RESEARCH_NONCOMMERCIAL` rights. This is registry and metadata evidence; it does not prove browser playback.

A headless Edge/CDP test harness was added for the real local video. One run loaded the Cinema home, but selecting Vision did not produce the expected Vision player root; no media controls were exercised. A later run was stopped by the 2 GiB runtime guard when available RAM fell below the limit. The harness now waits for startup hydration, reports navigation state, requires at least 2.75 GiB before launching its isolated Edge profile, and classifies resource stops as `BLOCKED`. It has not yet completed a playback pass.

| Check | Status |
|---|---|
| R4 home and build health | PASS |
| DEV game_1 registry rights/hash/availability | PASS (registry only) |
| Browser `loadedmetadata` / `canplay` | NOT_TESTED |
| Play and pause time progression | NOT_TESTED |
| Seek error | NOT_TESTED |
| 0.25× / 0.5× / 1× | NOT_TESTED |
| Fullscreen | NOT_TESTED |
| Vision source playback and return cleanup | NOT_TESTED |
| Source-bound analysis overlay | NOT_AVAILABLE; no verified result was loaded |
| Native GUI | NOT_TESTED |

Static review found that `VideoEvidencePlayer` explicitly pauses and clears its media element during cleanup; `VisionPlayer` does not currently have an equivalent explicit cleanup effect. The browser run did not reach the point needed to reproduce or measure a retained Vision media resource, so no product change was made on that hypothesis.

## Vision resource guard

The lightweight Vision lab endpoint previously reported approximately 3.09 GiB available RAM and 6,370 MiB free VRAM; it reported weights not loaded and controlled inference not ready. The latest idle capture later measured 2.16 GiB minimum available RAM. Since Vision inference requires at least 3.5 GiB available RAM and 3 GiB free VRAM under the current guard, no inference smoke test was started. No weights or labels were loaded.

## Changes and verification

- Added `scripts/resource_measurement.py` and `tests/test_resource_measurement.py` for bounded resource sampling and summary checks.
- Added `scripts/qa_browser_playback.mjs` for local-only browser playback checks without a new dependency, external platform requests, or model execution.
- Fixed CPU usage measurement in the sampler to use process-tree CPU-time deltas.
- No Cinema, Vision, business-rule, or frozen research algorithm code was changed.

Current-turn verification:

- Resource sampler tests: **4 passed**.
- Python `py_compile`: passed for the sampler and its tests.
- Browser harness `node --check`: passed.
- Frontend tests: **74 passed** (Feed 31, Studio 17, Review Queue 9, Score Time 5, Score Observation 12).
- TypeScript and Vite production build: passed; 650 modules transformed.
- `git diff --check`: passed.
- Full Python suite: **NOT_RUN** in this R5.1 turn. The historical 600-pass result belongs to the prior baseline and is not presented as current validation.
- `pip check`: **NOT_RUN**.
- Windows Preview build and launcher activation: **NOT_RUN**; no product source changed, RAM was low, and the active pointer was intentionally preserved.

The frontend results above were run before the final edits to the QA harness and Python sampler; those edits do not touch frontend source. The current sampler test and syntax checks were run after its CPU fix.

## Gate

`R5.1_STABILITY_PLAYBACK_PARTIAL`

The R4 idle process footprint is measured, but no repeated cold-start or active-playback comparison exists. Browser playback and Vision navigation remain incomplete, full Python regression was not rerun, and no native GUI verification was performed. The active R4 desktop and user data remain unchanged.
