# GEX-002-H / HOST WORK — Grand Experience packaging assessment

Status: PROPOSED / downstream. Do not run a production installation. Wait for accepted SAN candidate plus pinned Main input.

## Goal and value
Assess how the accepted Cinema candidate can be packaged and independently tested on Windows without disturbing the existing desktop experience.

## Verified starting evidence
WORK read `C:\PTTI-Worktrees\ptti-goal23-desktop-builder`; HEAD `c7137574db8f7454a18e99d5d7151a8894cf6f78`. goal23-build.json pins SAN `4d24c130cbe9dbdd66390423605c29f26a7ee792`, Main `753edfbd1b95bc85881bdc7632e6df14a09fdc24`, version 0.1.8-fan-4d24c13, host 0.1.8-goal23, QA 4208 and min free RAM 2.5 GiB; bridge disabled. Launcher file exists at `<LOCAL_USER_ROOT>\AppData\Local\PTTI-Cinema\launcher.ps1`, 2791 bytes. Active pointers, candidate build and native GUI are UNVERIFIED. Do not repeat historical Launcher-missing status as current.

## Scope
Allowed: read-only environment check, separate candidate configuration/build proposal, and isolated QA artifacts only if existing lane authorization and resource checks permit. Forbidden: Launcher/desktop shortcut/current-preview/stable changes, original DB, media edits, other-lane processes, resource-guard reduction, native R4 bridge activation or automatic release install.

## Inputs / dependencies
SAN GEX-002-S accepted build with full SHA + static file hash; Main agreed manifest; source rights summary; Playback separate runtime report. New prototype is not automatically eligible for packaging. Follow products/ptti/AGENTS.md when its scope applies; do not treat dev_sync as permission to violate Founder’s no-deployment rule.

## Steps
1. Read actual worktree status, config, resource availability, port ownership and existing build receipts. Preserve every existing change.
2. Distinguish existing GOAL23 configuration from generated candidate proof. Do not fabricate a 0.1.8 receipt from config.
3. Produce a candidate build plan with exact SHA/hash dependencies, isolated profile/data location and free QA port; protect existing ports. Do not mutate byte-pinned current config merely to fit a prototype.
4. If authorized candidate building is possible, use a new candidate output; verify package hashes and isolated startup without changing the desktop pointer. Otherwise provide exact BLOCKED prerequisites.
5. Run actual Windows media checks only in authorized QA. UI presence, Web success or a pointer simulation never establish native playback success.

## Tests / success evidence
Source pins, artifact hashes, environment thresholds, candidate manifest consistency, no production DB path in candidate, actual process/version identification, launcher untouched hash and native test scope. Distinguish CODE_COMMITTED, TESTS_PASSED, WINDOWS_BUILD_VERIFIED, DESKTOP_UPDATED, NATIVE_GUI_VERIFIED. DESKTOP_UPDATED must remain NO in this task.

## Rollback
Close only your explicitly owned QA instance if necessary; keep active pointers unchanged. Retain isolated artifacts and rollback instructions; no automatic deleting or reverting user data.

## Final receipt
PTTI WORK REPORT with actual root/HEAD/status, input/output hashes, process/port ownership, runtime evidence, candidate vs stable status, unperformed gates, recovery path and Founder approval needed for any later deployment.
