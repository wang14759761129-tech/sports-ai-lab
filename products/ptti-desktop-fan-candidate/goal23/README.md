# GOAL23 Desktop Fan 0.1.8 QA Builder

This directory is a separate build path for `0.1.8-fan-4d24c13`. It does not edit `build-goal18.2.py`, Desktop 0.1.7, the formal selector, R4, a release pointer, or a user WebView2 profile.

The checked-in `goal23-build.json` pins San `4d24c130cbe9dbdd66390423605c29f26a7ee792`, Main `753edfbd1b95bc85881bdc7632e6df14a09fdc24`, Main JSON SHA-256 `702bc12850676ae9eeda39b533ade9cc5f2da0fe8710aa8ebc82f0c2b803c5c9`, the canonical static artifact tree SHA-256, Host version, and QA port 4208. The builder independently checks those values against the live worktrees and 0.1.7 rollback package before staging anything.

## Offline checks

From this directory, run:

```powershell
python -m unittest discover -s tests -v
powershell.exe -NoProfile -File .\tests\test_process_identity.ps1
```

The process-identity helper is test-only. It requires the exact normalized executable path, matching SHA-256, a live PID resolving to the same path, and consistent creation time. A same-name executable elsewhere is ignored; an unreadable exact-name process fails closed. It is not imported by `Start-PTTI.ps1`.

## Read-only preflight

```powershell
python .\build_goal23.py preflight `
  --san-root C:\PTTI-Worktrees\web-goal14-fan-mvp `
  --main-root C:\PTTI-Worktrees\integration-preview-sprint-0-1 `
  --static-root C:\PTTI-Worktrees\web-goal14-fan-mvp\products\ptti-web\dist `
  --main-json C:\PTTI-Worktrees\integration-preview-sprint-0-1\products\ptti-integration\generated\goal22-main-inspiration-v0.1\public\fan-inspiration-v0.1.json `
  --parent-release <LOCAL_USER_ROOT>\PTTI\Candidates\GOAL18\0.1.7-fan-6d87ae3 `
  --output-root <LOCAL_USER_ROOT>\PTTI\Candidates\GOAL23
```

Preflight validates fixed commit identities, San cleanliness, Main JSON bytes, static output bytes, the complete 0.1.7 rollback inventory, and that the QA port is free. It never writes the candidate or starts a process.

## Build

Run the same arguments with `build` instead of `preflight`, and add:

```powershell
  --python '<LOCAL_USER_ROOT>\OneDrive\文档\ChatGPT\table tennis intelligent\.venv\Scripts\python.exe'
```

The builder stops before Host compilation when free RAM is below 2.5 GiB. It never reuses the 0.1.7 executable: PyInstaller compiles the separate `desktop_host.py`, with its release pins generated from the config. The new Host exposes only the Fan static site. It has no selector/R4 bridge, no SQLite code, and no path to the live matches database.

The QA WebView2 profile is scoped under `%TEMP%\PTTI-GOAL23-DesktopFan-QA\0.1.8-goal23\Port-4208\WebView2`. It is kept between candidate restarts for synthetic Journal persistence checks and is separate from the production profile. The Host refuses startup below 2.5 GiB, uses loopback only, checks port 4208 once, and does not retry or stop any process.

The package and adjacent build receipt are new versioned paths. Existing candidate paths cause a fail-closed refusal. `release.json` records each payload file SHA-256; the receipt records the release manifest SHA, Host EXE SHA, pinned inputs, port, profile policy, and disabled Native bridge state.

No candidate is activated automatically. GUI operation and WebView2 persistence remain separate manual acceptance steps after the resource gate passes.
