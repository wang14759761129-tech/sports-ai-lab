# PTTI — Chinese Desktop + experimental v0.2 visual perception

Stable athlete delivery remains **ptti-v0.1.2**. This development branch adds a separate optional vision worker; it is not a consumer v0.2 release.

## Computer Vision (experimental)

Chinese local-video / licensed-local-WTT ingestion, input quality classification, pinned RacketVision BallTrack inference, sparse-GT benchmarking, ball-position JSON/CSV, HTML and trajectory overlay. [Vision architecture/setup/limits](docs/VISION.md) · [legal video sources](docs/VIDEO_SOURCES.md). RacketPose and TrajPred remain gated and **not implemented**; ball positions never become invented tactical fields. Heavy CUDA dependencies live in vision_worker/.venv, never the normal desktop environment. Build the independent PTTI-Vision-Dev EXE using scripts/build_vision_windows.bat; stable installed shortcuts are unchanged.

## Professional athlete and match foundation

This development branch adds a sourced 16-athlete registry, editable player groups, immutable weekly ranking snapshots, six professional match metadata records, and Chinese-first athlete/profile and professional-match pages. Professional identities use stable IDs; local CSV match records remain compatible and are not silently linked by name. External event pages are references only. The WTT inbox supports an explicitly selected licensed file, SHA/media preflight, duplicate checks, and rights/source metadata. A separate development-only full-match pipeline has chunk checkpoints/resume, global frame/time mapping, frozen RAW BallTrack, and a human-edited game/point/rally/scene timeline. No complete authorized professional match was available for an end-to-end real-video run; automatic segmentation and tactics are not claimed. See [architecture audit](docs/CURRENT_PLAYER_ARCHITECTURE.md), [verified registry](docs/PROFESSIONAL-PLAYER-REGISTRY.md), [next-step design](docs/PROFESSIONAL-MATCH-ROADMAP.md), and [full-match pipeline limits](docs/VISION.md#professional-full-match-foundation-development-only).

## Stable 0.1.2 delivery

Personal Table Tennis Intelligence / 个人乒乓球比赛智能分析系统。Local-first Windows match workbench for the owner and Kaikai. Chinese-first interface; no account, telemetry, silent upload, AI API or cloud analysis. **KAIKAI TEST 01 PENDING.**

## Install or unzip

[Release](https://github.com/wang14759761129-tech/sports-ai-lab/releases/tag/ptti-v0.1.2): extract the whole `PTTI-v0.1.2-Windows-x64.zip`, read START-HERE.txt, and run INSTALL.cmd for a per-user copy with desktop / Start Menu shortcuts. Default desktop shortcut is checked by design (omit using INSTALL.ps1 -NoDesktop). No administrator rights. Inno Setup was unavailable; this release uses an explicit PowerShell/batch installer fallback, **not a setup EXE**. Windows may enforce local script policies; portable direct launch remains available.

Portable mode: open PTTI/PTTI.exe, keep _internal alongside it. Windows 10/11 x64 and Edge WebView2 Runtime required. Python, Node, Git, Codex and VS Code are unnecessary for users. The executable is unsigned; no security-setting bypass is part of this release.

Installation: %LOCALAPPDATA%\Programs\PTTI\versions\0.1.2. Normal uninstall via Start Menu Uninstall PTTI asks confirmation and retains %LOCALAPPDATA%\PTTI\matches.db. Existing same-version differing binaries are never overwritten; existing shortcut files are backed up before replacement.

## Chinese UX

Three-step first-run introduction; match information → file/template selection → automatic preview checks → explicit save. Chinese issue severity and suggestions. Dashboard tabs: overview, service/receive, third ball, rallies, points, evidence. Chinese column labels, filters and expandable original research fields. Searchable/date-filtered library with confirmed deletion. Persistent Chinese language, light/dark/system theme, onboarding and home/recent startup preference. Settings opens the local data folder in the desktop edition. One export menu for JSON, Chinese HTML, and experimental current-section printing/PDF.

Future player, training and AI-coach modules are **planning-only shells**, visibly unopened. Match Intelligence is active; the optional video module is explicitly experimental.

## Evidence and research

[Research](../../research-tracks/match-analytics/serve-third-ball-analytics/) → Protocol/schema → adapter → analytics → FastAPI/SQLite → React → pywebview/PyInstaller. Native `1.0.0-new` and historical Protocol v0.3 CSVs remain supported; player=A/opponent=B, native scores after point, research scores before point. Templates are synthetic. See [schema comparison](docs/SCHEMA-COMPATIBILITY.md), [evidence definitions](docs/EVIDENCE-METRICS.md) and [research basis](docs/RESEARCH-BASIS.md).

Analytics/adapter remain 0.1.1: calculations and thresholds did not change in this UX release. Unknown, unclear and N/A retain semantics and original values. Unavailable evidence produces a state, not fake zero. Pilot 1C remains REVISE / HOLD, primary research question ON HOLD PENDING MEASUREMENT FEASIBILITY; Pilot 2 NOT STARTED. No new research result.

## Development / tests / build

From products/ptti in the full monorepo, Python 3.12 and supported Node:

```bat
setup_windows.bat
run_dev.bat
.venv\Scripts\python -m pytest -q
build_windows.bat
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/package_release.ps1
```

Icon is original programmatic geometry, reproducible with Python standard library in scripts/make_icon.py. Shared CSS tokens / reusable UI primitives; score chart loaded on demand. Internal code/API/research field names stay English. Packaged app serves the built frontend. Git tracks source/tests/assets/scripts/docs only; binaries and hashes belong in Release assets.

SQLite matches table and old payloads remain unchanged. Additive preferences table has no destructive migration. Old saved analyses are retained and labeled, not silently recalculated. Back up with the app closed. PTTI_DB and PTTI_WINDOW_SIZE are developer smoke-test overrides.

## Limits and quality gates

Single match and complete game prefixes only; no doubles/cross-game service enforcement or annotation-consistency certification; receive subtypes can coarsen with warnings/raw retention. No data editing/JSON reimport/video/LLM/cloud. Printing/PDF experimental; clean-machine athlete use, large-match performance, additional monitor/scaling combinations require independent validation. No broad v0.2 work.

[0.1.2 verification](docs/desktop-verification-v0.1.2.md) · [Kaikai checklist](docs/USER-FEEDBACK.md). Only next external milestone: **KAIKAI TEST 01**.

## Development database isolation

The stable packaged `PTTI.exe` explicitly selects `%LOCALAPPDATA%\PTTI\matches.db`. Source and `PTTI-Vision-Dev.exe` use a separate development database; pytest bootstraps only from a temporary database and per-test repositories use `tmp_path`. Test/development startup raises `PRODUCTION_DATABASE_WRITE_GUARD` if the selected path resolves to production. Run the suite with `.venv/Scripts/python.exe -m pytest -q`.

The 2026-10-05 incident investigation is recorded in [database_forensic_report.md](docs/database_forensic_report.md). Its conclusion is `STATE_UNCERTAIN_DO_NOT_MODIFY`; the synthetic demonstration remains preserved.
