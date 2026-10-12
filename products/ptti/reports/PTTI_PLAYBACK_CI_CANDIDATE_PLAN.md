# PTTI Playback Recovery — Windows CI Candidate Plan

Status: `PREPARED_LOCALLY_NOT_PUSHED`; no GitHub Actions run has been started.

## Why the R5.1 workflow cannot run this branch as-is

`.github/workflows/ptti-r51-candidate.yml` is a push-only workflow restricted to
`codex/ptti-r5-1-stability-playback`. The current Playback Recovery branch is
`codex/ptti-playback-recovery-sprint-0-3`, so pushing this branch does not match
the R5.1 trigger. That workflow also omits the focused official-playback, Vision
source-recovery, and QA-proxy frontend tests required for this recovery.

The existing build-only harness is otherwise a suitable base: it checks an
exact clean source commit, requires a Windows Actions runner, preserves the
2.5 GiB start guard and 2 GiB runtime floor, requires 3 GiB disk space, runs
tests and PyInstaller, validates a packaged health check, computes the EXE and
manifest hashes, and never installs or activates the candidate.

## Prepared isolated route

The new `ptti-playback-candidate.yml` runs only after a push to
`codex/ptti-playback-recovery-sprint-0-3` touching `products/ptti/**` or this
workflow. It uses `windows-2022`, read-only repository permissions, pinned
action SHAs, Python 3.12.10, Node.js 22.14.0, `npm ci`, and the existing
FFmpeg 8.1.1 archive SHA-256 check. It has no cache, deployment, release,
activation, or credential permission. The job has a 45-minute timeout; actual
runner time and account billing are unknown until a run completes.

`ci_windows_candidate.py` now records Python/pip/Node/npm versions, the npm
lockfile SHA-256, expected FFmpeg archive SHA-256, and the Actions run identity.
It adds the official playback, Vision source-recovery, and QA-proxy tests. Its
health-check database is created under `RUNNER_TEMP` and removed when the
health-check scope ends. Candidate package and reports are uploaded for seven
days only after the relevant success/failure conditions; the package upload is
success-only. The candidate report binds the artifact to the exact GitHub
source commit and records the EXE SHA-256, package manifest and Python
dependency freeze.

Python direct dependencies are pinned in `requirements.txt`; the resolved
Python environment is recorded with `pip freeze`, but transitive Python
dependencies are not hash-locked. Frontend dependencies use `npm ci` and the
committed lockfile. The FFmpeg archive and third-party Actions are hash/SHA
pinned. There is no dependency cache to invalidate or share across branches.

## Acceptance boundary

A successful run means `BUILD_VERIFIED_NATIVE_ACCEPTANCE_PENDING`. It does not prove native GUI
launch, real video decode/playback, Chrome handoff, clipboard behavior, or
compatibility on the user's computer. Those remain `NOT_TESTED` until a future
one-time local acceptance window. Keep `PTTI_PLAYBACK_DIAGNOSTICS=1` opt-in and
enable it only for that native run. The current R4 activation, Launcher, user
database, and rollback package are outside this workflow.

The workflow is intentionally not pushed or triggered as part of preparation:
pushing the prepared commit would match its branch/path trigger and consume a
Windows Actions run. Explicit user approval is required before that push.
