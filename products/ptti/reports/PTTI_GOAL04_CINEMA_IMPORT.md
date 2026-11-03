# GOAL 04 — Cinema import and Vision preparation

Baseline: `7523b9652e97da880132f5799d435bdb06e40d39`.
Scope: Playback worktree only; source, isolated tests and local commit.

## Read-only native QA closure

- PID32524 absent; no remaining PTTI-named process found.
- Resumed QA clone `PTTI-Candidate-QA-20261012-223956-d4f613f5`: SQLite `quick_check=ok`.
- One scan remains COMPLETED, candidate REGISTERED; `synthetic-review` remains AVAILABLE / PERSONAL_VIEW_ONLY.
- Creator reports actual 12-second playback, pause, forward/backward and Seek PASS, and normal window closure. These are user-observed native results for source `d6d62c103adafb2a12a996c8d6e73fffb3d41c63`, not acceptance of this new source.
- Existing QA database was opened read-only. Tests write only their own OS Temp databases. No production database, candidate, shortcut or Launcher changed.

## Product changes

- Primary library action selects one local video using the existing desktop file picker. Folder selection remains a secondary batch option; manual path entry is under advanced settings.
- New POST `/api/video-evidence/library/files` reuses the existing preview/confirmation pipeline and SHA validation. It processes only the selected file, without enumerating siblings or subdirectories; it does not register automatically.
- Pending/failed/interrupted previews are distinguished from completed zero-file results. Completed older pending reviews are recoverable through a visible selection; no new scan is necessary.
- Required source/rights confirmation precedes registration. Pending rights, blank/placeholder source notes and unchecked acknowledgement disable the action. Changing source or rights clears acknowledgement.
- Optional match metadata is collapsed. Single-item registration opens playback; already registered items offer playback directly. Preview duration is shown in seconds for short clips.
- Network paths, unsupported files, linked paths, research holdouts and unconfirmed input are rejected. Existing concurrency, hash, availability and database protections remain.

## Confirmed defect

Confirmation previously did not recheck links/path containment after preview. A deterministic test simulating a path becoming a link returned HTTP 200 before the fix. Confirmation now rejects it before reading/registering. This is a code-level regression scenario, not a claim that the creator's import failure was caused by a link. No new format/import failure was observed in the real QA session.

## Final checks

- `test_match_video_library.py`: 36 PASS (25 existing, 11 new).
- `test_database_isolation.py`: 18 PASS.
- Frontend import/status/recovery/rights assertions: 20 PASS.
- Vision source recovery and existing analysis gate assertions: PASS.
- TypeScript + Vite production frontend build: PASS. Windows packaging: NOT_TESTED.
- Pytest reports one existing Starlette/httpx deprecation warning; no dependencies installed or upgraded.
- Revised Windows picker/UI/native playback: NOT_TESTED. No GUI controlled this round.

## Minimum next Vision input and evidence chain

One local, decodable real table-tennis MP4 and a source note explicitly permitting local analysis are sufficient to begin source preparation; a short continuous rally (about 15–30 seconds) is a practical first sample. No athlete/event identity is required merely to view it.

Import and confirm rights → verify source SHA/availability → probe video metadata → decode actual sparse frames → apply analysis/resource gates → bind outputs to source SHA, frame indices/timestamps, model/config identity and review status. Existing `KeyframeSampler` plans start/end and 10-second intervals; frame planning alone is not evidence of successful decoding. Current Vision source eligibility requires LICENSED_FOR_ANALYSIS or RESEARCH_NONCOMMERCIAL; PERSONAL_VIEW_ONLY and a bare self-captured flag do not unlock analysis. Creator-owned footage still needs explicit analysis permission.

There is no suitable real authorized footage in this task. Actual frame decoding, model execution and algorithm accuracy remain NOT_TESTED; unmatched analysis evidence stays disabled. Controlled model experiments retain the existing 3.5 GiB RAM / applicable GPU guards.

## Candidate boundary

The archived d6d62c1 Windows EXE does not contain these changes. A future candidate requires separately authorized build/push/CI, a new source-bound manifest/hash, package/security checks and native file-picker/import/recovery acceptance with the existing 2.5 GiB native QA guard. R4 and all rollback/data boundaries remain unchanged. `dev_sync.py` was not run because it builds/installs/activates, which this round explicitly prohibits.

CODE_COMMITTED after local commit; TESTS_PASSED scoped above; WINDOWS_BUILD_VERIFIED / DESKTOP_UPDATED / revised NATIVE_GUI_VERIFIED: NOT_TESTED. DESKTOP_UPDATE_PENDING.
