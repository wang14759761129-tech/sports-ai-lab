# PTTI v0.1.0 — First Usable Release

Local-first table tennis match analysis for the project owner and Kaikai. No API key, account, telemetry, or cloud storage.

## Run the Windows release

Open `dist/PTTI/PTTI.exe`. Keep the entire `PTTI` folder together when sharing it. Windows 10/11, x64, Microsoft Edge WebView2 Runtime required. A directory release is deliberate: it avoids extracting a large runtime on every launch. Python and Node are not needed by release users.

## Development: fresh clone → setup → run → test → build

Install Python 3.12+ and Node 22.12+ (or Node 20.19+). From the repository root:

```bat
setup_windows.bat
run_dev.bat
.venv\Scripts\python -m pytest -q
build_windows.bat
```

For frontend live reload run `run_backend.bat` and `run_frontend.bat` in separate terminals; open the Vite URL. `run_dev.bat` opens the desktop window against built frontend assets, so rebuild after frontend edits.

## First match

Click **Load sample match** for an explicitly synthetic three-game match. Or select **New / import match**, fill player names (Chinese supported), and upload UTF-8 CSV. Validation errors block saving; warnings permit saving but identify incomplete annotations. The dashboard shows denominators, progression, rally bands, patterns and evidence. Open Point explorer to inspect/filter rows. Export JSON or standalone HTML, or print from the dashboard. Reopen saved matches from the library.

Use `data/samples/synthetic.csv` as a column template, not as real match evidence. See [schema](docs/data-schema.md). Scores are after each point; `server`/`winner` use A/B independently of player names.

SQLite lives in `%LOCALAPPDATA%\PTTI\matches.db`. Close PTTI before copying this file for backup. Developer/test overrides use `PTTI_DB`. Exported JSON includes metadata, original parsed point values, validation, and versioned analysis. JSON reimport is not supported in this release; exchange CSV for reanalysis.

## Historical research status

This workspace contained only an empty Git repository, with no commits or research files. Searches of current tracked/untracked workspace files found no Student Athlete Research Lab, sports-ai-lab, RallyLab, annotation protocol, approximately 21-field schema, or Wang Chuqin/Fan Zhendong datasets. No historical files were deleted or replaced. Historical schema: **SOURCE NOT FOUND**. The documented `1.0.0-new` schema is an explicit new protocol; migrate old data through a reviewed adapter when sources are recovered.

See architecture, methodology, metrics, roadmap, and `docs/release-verification.md` for scope and verification details.

## Release freeze and Kaikai handoff

Functionality is frozen at 0.1.0. No v0.2 development before **KAIKAI TEST 01** passes, except release-blocking fixes. Product/analytics: 0.1.0; schema: 1.0.0-new, with no historical v0.3 compatibility claim.

After `build_windows.bat`, run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/package_release.ps1`. This produces `dist/PTTI-v0.1.0-Windows-x64.zip` plus a Chinese non-developer handoff folder. The script refuses to overwrite an existing handoff folder/archive; preserve or move it before preparing another package. Close PTTI before rebuilding.

Source, tests, lockfile, launch/build scripts and handoff documents belong in Git. Generated executables, runtime folders, archives, databases and development environments remain ignored; attach the ZIP to GitHub Release v0.1.0 when a verified remote is available. See [release policy](docs/release-freeze.md) and [small feedback form](docs/USER-FEEDBACK.md).
