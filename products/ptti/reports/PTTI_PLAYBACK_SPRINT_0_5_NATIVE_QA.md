# PTTI Playback Sprint 0.5 Native QA

## Prepared instrumentation

Native diagnostics are disabled by default. Set `PTTI_PLAYBACK_DIAGNOSTICS=1` in the candidate process to write a bounded JSONL trace under the operating system temporary directory. The filename uses the process ID and a timestamp; no stable user-data directory is used.

The trace records the dynamic loopback port, the normalized URL template and route, loopback Host/Origin labels and ports, client locality, HTTP status and safe rejection class, response type/field names/counts, authorized-source count, and a `game_1_present` boolean. UI events record loading/ready/error, source selection, media readiness, play/pause/seek, selected playback-rate property, and unmount. It does not record raw headers, client IPs, query strings, video IDs, titles, source hashes, media paths, file contents, or free-form error text. The trace is capped at 256 events.

The Preview QA database must be a fresh path under `%TEMP%`, supplied through `PTTI_PREVIEW_QA_DB`. The application records only the database location class, never the path. A database outside `%TEMP%` is rejected before the local server starts.

## Current gate

- Current source branch began at `c5fb8c0a82ee0266654c857e8e93bef44ed4f413`.
- Current available physical RAM at preparation: about 1.05 GiB; the unchanged package start guard is 2.5 GiB, with a 2 GiB hard runtime floor. Required free disk for the package workflow is 3 GiB.
- No package, native process, QA database, or user-data migration was started in this preparation pass.
- The existing R4 pointer and rollback remain untouched. Release state remains `DESKTOP_UPDATE_PENDING`.
- An older `startup-error.log` reported `Preview QA database must be inside OS temp` on 2026-10-11. That launch stopped before HTTP startup and is not evidence of the Sprint 0.5 native Vision request.

## One-window acceptance sequence

1. Wait until available physical RAM is at least 2.5 GiB and the build volume has at least 3 GiB free. Do not lower either guard.
2. From this clean worktree, run the existing source tests and production frontend build, then package with `PTTI_PREVIEW_PROFILE=video-first-r4` and a unique `PTTI_PREVIEW_BUILD_ROOT` under `C:\PTTI-Cinema-Builds`. Do not run the activation workflow.
3. Verify the candidate manifest commit and every package hash. Create a fresh QA directory under `%TEMP%`; launch only that candidate with `PTTI_PREVIEW_QA_DB=<fresh-temp-directory>\matches.db` and `PTTI_PLAYBACK_DIAGNOSTICS=1`.
4. In the visible native window, enter Vision and verify source-list GET status, same-origin Host/Origin, response array shape, game_1 eligibility/selection, then play, pause, seek, select each supported rate, leave, and re-enter. Confirm Analysis View stays disabled without matching trusted evidence. Return to Cinema and recheck game_1 playback.
5. Read the newest `ptti-playback-diagnostics-*.jsonl` from `%TEMP%` and compare its HTTP and UI events. Test the official event page and official match-video page separately. If Chrome cannot be reliably inspected, stop automation and have the user verify the final address bar and copied URL once.

## Preparation verification

- `npm run test:vision-source-recovery`: PASS.
- Python syntax compilation for the diagnostic, request, application, and desktop modules: PASS.
- Lightweight diagnostic smoke harness: PASS for opt-in behavior, fixed-field validation, redaction, normalized loopback URL/Origin, response structure, and `game_1` status. The bundled Python runtime has no `pytest` module and this worktree has no project `.venv`, so the pytest suite was not run.
- Full project tests, frontend production build, candidate package, native GUI, media decode/playback, Chrome URL, and clipboard: NOT_TESTED; available RAM remained below the existing start guard.
