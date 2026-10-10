# Desktop Auto Update v1

Fixed Preview entry: `%LOCALAPPDATA%/PTTI-Cinema/launcher.ps1`, invoked by the desktop `PTTI Cinema` shortcut. It verifies all files before starting the current version, or the previous verified package if current verification fails. Existing stable 0.1.2 and older shortcuts/packages are untouched. Local hashes detect corruption; they are not a publisher signature against an attacker who can rewrite the local manifest.

## Developer sync

From `products/ptti`, after a clean committed change:

```
.venv\Scripts\python.exe scripts\dev_sync.py
```

The command checks clean HEAD/frozen config/media exclusion, RAM (2.5 GiB start; 2 GiB runtime floor) and disk (3 GiB), runs Python tests/dependency checks, frontend tests/TypeScript/Vite, builds an independent onedir Preview using the existing packager, verifies frontend hashes and the complete package, performs isolated temporary-DB health startup, then atomically activates the new pointer. The old package is retained. No running PTTI is terminated; next launch uses the new target. Failures report `DESKTOP_UPDATE_PENDING` without changing current.

Stale `.deploy.lock` after a crash blocks activation rather than guessing whether another deployment is active. Diagnose the recorded PID before manually recovering it. Package failures may leave unactivated diagnostic directories; they are never launched automatically.

## Remote channels

Preview and Stable release discovery use the fixed official GitHub repository API over HTTPS, no embedded credentials. Only published `ptti-` tags in the appropriate prerelease channel are considered. Startup and 30-minute discovery are non-blocking; offline failure does not block playback. Commit notifications do not create installable releases.

**Remote download/install remains disabled.** There is no authenticated signing chain or native unsigned-Preview confirmation/installer workflow yet. Discovery is not an install approval. Stable activation is not implemented and the existing Stable installation is protected. These are explicit remaining work, not a complete production updater.

## Content refresh

Video Feed has manual refresh and a five-minute visible-page refresh. It updates directory state only, retains the selected official player object, and does not download media or rewrite playback/rights evidence. Local Watch/Vision playback is not refreshed by this feed component. Existing separate timelines and UNKNOWN states remain unchanged.

## Acceptance

Unit fixtures are simulated packages, not executable videos or native UI acceptance. A/B/C pointer changes, corruption fallback, failed health activation, data preservation and the real Windows PowerShell verify-only path are tested. Actual new-build health and native GUI acceptance must be reported separately. No databases/media/model weights enter packages or Git.

Every delivery reports CODE_COMMITTED, TESTS_PASSED (scope), WINDOWS_BUILD_VERIFIED, DESKTOP_UPDATED and NATIVE_GUI_VERIFIED separately.
