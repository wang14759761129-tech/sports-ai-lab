# PTTI v0.1.2 — Chinese Desktop Experience

PTTI v0.1.2 is a Chinese-first Windows desktop release for local table-tennis match analysis. It adds a coherent product shell, first-run onboarding, clearer CSV import and validation, evidence-aware dashboard states, Chinese point exploration, match-library controls, settings/about pages, and clearly labelled future-module placeholders.

Download `PTTI-v0.1.2-Windows-x64.zip`, extract the whole folder, read `START-HERE.txt`, and open `PTTI/PTTI.exe`. The portable package includes a per-user `INSTALL.cmd` fallback that creates a Start Menu entry and optional desktop shortcut when an installer compiler is unavailable. Windows 10/11 x64 and Edge WebView2 Runtime are required; Python, Node, Git and developer tools are not.

Changes: recovered canonical Protocol v0.3; documented all 21 field mappings; added historical CSV detection and an adapter retaining original values and provenance; exposed uncertainty-aware denominators, exclusions and evidence states; improved Chinese import, validation and dashboard copy; delivered both native and historical-format synthetic examples. Native schema `1.0.0-new` remains supported. Unresolved tactical evidence produces an explicit unavailable/insufficient state, never a guessed zero.

Validation: 50 automated tests passed, zero failed. The frontend production build and PyInstaller Windows build passed. The packaged application was exercised through onboarding, sample loading, Chinese navigation, Protocol v0.3 preview/save, validation errors and warnings, dashboard sections, point filters, evidence details, library reopen/delete confirmation, settings/theme, JSON Save As and HTML Save As. JSON was parsed and the HTML report was inspected as Chinese output. Printing/PDF remains explicitly experimental and independently unverified.

Research conclusions are unchanged: Pilot 1C remains REVISE / HOLD, the primary question remains ON HOLD PENDING MEASUREMENT FEASIBILITY, and Pilot 2 has not started. No video inspection or new tactical research result is claimed.

Known limits: one match per CSV; complete game prefixes only; insufficient tactical evidence suppresses metrics; the fallback installer is a PowerShell installer rather than a signed Setup EXE; independent clean-machine use and KAIKAI TEST 01 remain pending.

Only next external milestone: **KAIKAI TEST 01 — PENDING**. Independently unzip, launch, load sample, import CSV, inspect dashboard/points, restart, confirm persistence and export. Report every failed step.
