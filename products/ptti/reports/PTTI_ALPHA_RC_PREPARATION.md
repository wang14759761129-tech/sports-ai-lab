# Playback Windows Alpha RC preparation — GOAL 05

Product baseline: f725556f6fac02b9b5286753f715e014edd1f3a6.
Worktree: C:\PTTI-Worktrees\playback-recovery-sprint-0-3.
Branch: codex/ptti-playback-recovery-sprint-0-3. Candidate target is the final clean local HEAD of this preparation commit, not the baseline or old EXE.

## Verified code chain and visible delta from archived d6d62c1 EXE

1. Library primary action → existing DesktopAPI.select_evidence_video dialog → selected absolute local file. Folder/manual-path input remains secondary.
2. POST /api/video-evidence/library/files → rights/read confirmation → LocalMediaIndexer.start(single_file=True). Unsupported/network/link/holdout input is rejected. Only the selected file is processed; no parent enumeration.
3. Media metadata and SHA → REVIEW_REQUIRED preview. Pending work does not show a completed zero count; failure/interruption have separate messages. Metadata preview is not playback or full-frame decoding evidence.
4. GET /folders → pending older preview can be restored and selected. Optional match fields collapse; required source/rights declaration remains visible. Rights/source edits reset acknowledgement.
5. POST /folders/{id}/confirm → repeat link/containment checks and SHA → registration. Individual confirmation opens the existing player; already registered entries offer playback.
6. QA session resume checks controlled OS Temp location, candidate identity, DB integrity and process ownership. It does not rescan. This is an explicit QA launcher feature, not production DB migration.

The old EXE has none of the GOAL04 single-file/registration UI improvements or scan-status source changes. User acceptance of the old synthetic player does not establish revised UI acceptance.

## Evidence handoff

See playback-qa-handoff.sample.json. It is an internal engineering evidence sample, NOT the public match/media contract and NOT a real-match record. Paths, process IDs, DB location and user identity are omitted. MainDex may reference its artifact/source/media SHA and provenance; no message was sent to another thread.

Old archive ZIP, EXE, manifest and build-info hashes were rechecked read-only. Actual synthetic bytes match their registered SHA. Native operations are creator-confirmed; no new GUI operation or screenshot was made this round. Vision recognition and Chrome final target verification remain NOT_TESTED in this handoff.

## Build checklist (not executed)

- Approve an exact clean source SHA. Before push, check remote ancestry, diff/sensitive files and same-branch active runs live. A normal push to this branch auto-triggers CI; push and that one run must be authorized together. No manual second run.
- Existing isolated workflow: standard windows-2022, Python 3.12.10, Node 22.14.0, pip 25.0.1; npm lock; pinned FFmpeg archive SHA; contents:read; no persisted checkout credentials; 45-minute job limit.
- Full pytest, pip check, all frontend gates (now includes import/status/recovery tests), frontend build, frozen config check, package/source audit and PyInstaller. Failure blocks candidate upload; diagnostic reports retain their existing upload path.
- Real health result + matching source + isolated RUNNER_TEMP DB + zero exit, with the existing independent 120-second timeout. A health success is not GUI acceptance.
- Record ZIP/EXE/manifest/build-info/SHA256SUMS, dependency freeze, logs and source-bound frontend hashes. New candidate hashes do not exist until a successful build. RC_PREBUILD_SHA256SUMS.txt covers selected critical text inputs with CRLF normalized to LF, not a complete package manifest. These are normalized text hashes, not raw Get-FileHash/package hashes.
- Preserve the archived old candidate and original R4. Archive new output under a separate Run/source identity. The legacy internal EXE/profile/version name does not identify the RC; exact SHA/build-id/manifest do. No official release flag or activation.

## Isolation and remaining blockers

- Current candidate_qa_launcher.py pins d6d62c1 and its exact artifact hashes. It intentionally rejects the new RC. After CI, a separately reviewed RC pin/launcher copy is required; do not replace the existing shortcut or old archived launcher and do not accept package-supplied identity as trust.
- New RC must start in a fresh controlled OS Temp QA session. The old candidate may resume its old session. Cross-version reuse of old launch.json/DB is currently rejected; do not rewrite identity metadata to bypass it. If reuse is later required, a separately tested, source-bound copy transition is needed. Fresh RC single-file import avoids folder path/scanning work without migration.
- Before native launch: real RAM >=2.5 GiB, disk/package checks, no other candidate, matching reviewed pins and isolated DB environment. Launch needs explicit authorization. Run native picker, preview, rights rejection, registration/playback, re-entry and normal exit; distinguish creator observations from automation.
- No production DB access; no installation into existing desktop roots; R4/Launcher/shortcut/rollback remain intact. Future desktop update is a separate authorization and requires full release gates.
- Real Vision input still missing: local owned/authorized table-tennis MP4 + explicit analysis permission note. Source SHA/availability, actual sparse-frame decode and matched trusted result evidence must precede analysis. No recognition claim from synthetic playback.

## Local test evidence

PASS: 49 candidate/health/session/database tests; 11 single-file/path-negative regressions; 20 frontend import/rights/recovery assertions; Vision source/gate regression; TypeScript compilation; handoff JSON/redaction assertions. One existing Starlette/httpx deprecation warning remains. No Windows RC build or native revised-UI acceptance is claimed. dev_sync is not invoked because this round forbids build/install/activation.

State: RC build preparation ready subject to authorization/live preflight; RC artifact and RC launcher binding pending; DESKTOP_UPDATE_PENDING.
