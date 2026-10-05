> Historical v0.1.0 record. Protocol v0.3 has now been recovered; current compatibility, evidence gates and verification are documented in SCHEMA-COMPATIBILITY.md, RESEARCH-BASIS.md, EVIDENCE-METRICS.md and integration-verification.md. Earlier SOURCE NOT FOUND statements describe the original empty workspace only.

# Release verification — 2026-10-05

## Release freeze rerun

`build_windows.bat` was rerun before the first release commit: **16 passed, 0 failed, 1 nonfatal TestClient deprecation warning in 0.54s**; TypeScript/Vite production build completed in 3.56s; PyInstaller directory build completed with exit code 0. No analytics or product features were added during freeze; only UI version labeling was made exact (0.1.0).

`scripts/package_release.ps1` produced `dist/PTTI-v0.1.0-Windows-x64.zip`: 19,405,044 bytes (18.51 MiB), 193 archive entries, 40,859,316 uncompressed bytes. ZIP CRC check passed; all required handoff files exist; no databases, .venv, node_modules, __pycache__, Git metadata or raw build caches were present. ZIP SHA256: `4d130e0cb17d79cad8126408ca902a63287596f55881b24babd5da482e648cdb`. Binary/archive outputs remain ignored and are intended as GitHub Release assets, not committed source. Remote absent at freeze; push and GitHub Release creation remain pending the correct repository URL. KAIKAI TEST 01 remains PENDING.

## Earlier product-loop verification

Environment: Windows 11 x64; bundled Python 3.12.14 used to create a new project virtualenv; Node 24.15.0 and npm 11.12.1. Dependencies installed successfully. No pre-existing source files or commits were present.

Executed: Python virtualenv setup and dependency installation, npm install (lockfile generated, zero vulnerabilities reported), `python -m pytest -q`, TypeScript compilation and Vite production build, actual PyInstaller Windows directory builds via `build_windows.bat`. Final automated result: **16 passed**. Includes UTF-8/BOM, invalid/missing fields, scoring/order/service, deuce and game completion, small/empty match analytics, metric partitions and counts, API imports with Chinese names, exports, deletion and persistence through a new app instance.

Observed through native UI: development pywebview home; sample button loads and saves 52 synthetic points; dashboard statistics, Recharts progression, rally bands, tactical facts; point explorer displays annotations; development window closes cleanly (process exits 0); packaged executable starts and displays saved match in library; saved match opens in packaged dashboard; packaged application closes and another final build reopens with saved data intact. JSON export opens a native Save As dialog after enabling pywebview downloads; dialog was canceled, so actual user-selected filesystem save is not claimed as tested. JSON and HTML response contents are covered by API tests. Printer output was not tested.

Final executable: `dist/PTTI/PTTI.exe`, SHA256 `ED20DE09CC14C094471CD905CD46F88EDAC9619B39D1871DFA8CD2752EF8C694`. Keep `_internal` beside the EXE. This is a directory distribution, not an installer. Windows machine without developer tooling has not been separately tested; executable was run directly without invoking Python/Node on this machine. WebView2 was already available here.

One intermediate rebuild failed because the initially launched hidden test executable held a DLL open. That test process was stopped; subsequent builds completed with exit code 0 and were launched visibly. No personal match data was deleted. A synthetic demo is left in the local library.

Nonfatal warnings: Vite JS chunk approximately 610 kB (chart library included); Starlette httpx TestClient deprecation; PyInstaller missing Android-only webview modules and optional tzdata. Final Windows UI worked despite these optional-platform warnings.

Known scope limits: historical v0.3 compatibility unverified/source absent; no mid-game partial clips, doubles server identity, cross-game initial server verification, match-length rules or annotation semantic consistency checks; no inferred missing metrics; broad server drilldown only; English UI with Chinese user names; no CSV editing, JSON reimport, video or LLM; library deletion exposed through API only; report is a concise table/evidence document rather than an exported interactive dashboard. Large CSV UI performance and clean-machine installation need further validation before wider distribution.
