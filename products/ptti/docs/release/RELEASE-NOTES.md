# PTTI v0.1.1 — Research Integration Release

PTTI now lives in `sports-ai-lab/products/ptti`, with both research history and the original v0.1.0 release commit preserved through a non-squashed Git subtree import.

Download `PTTI-v0.1.1-Windows-x64.zip`, extract the whole folder, read `START-HERE.txt`, and open `PTTI/PTTI.exe`. Keep `_internal` beside the executable. Requires Windows 10/11 x64 and Edge WebView2 Runtime; Python, Node, Git and developer tools are not needed. Check the accompanying SHA256 file.

Changes: recovered canonical Protocol v0.3; documented all 21 field mappings; added historical CSV detection and an adapter retaining original values and provenance; exposed uncertainty-aware denominators, exclusions and evidence states; improved Chinese import, validation and dashboard copy; delivered both native and historical-format synthetic examples. Native schema `1.0.0-new` remains supported. Unresolved tactical evidence produces an explicit unavailable/insufficient state, never a guessed zero.

Validation: 34 automated tests passed, zero failed, including all original 16 tests and the real 10-row Pilot fixture. TypeScript/Vite production build and PyInstaller Windows build passed. Native sample dashboard, point explorer, restart persistence and Protocol v0.3 uncertainty display were verified on the development computer. Packaged-server CSV import and JSON/HTML export responses were checked. The final handoff copy also passed native GUI file selection, historical-format import/save, point inspection and JSON Save As; the saved JSON was parsed and verified. Independent clean-machine use and printing remain Kaikai test items.

Research conclusions are unchanged: Pilot 1C remains REVISE / HOLD, the primary question remains ON HOLD PENDING MEASUREMENT FEASIBILITY, and Pilot 2 has not started. No video inspection or new tactical research result is claimed.

Limits: one match per CSV; complete game prefixes only; incomplete tactical evidence suppresses metrics; product evidence thresholds are conservative display rules, not validated scientific confidence thresholds. No video, LLM, cloud, CSV editing or broad v0.2 feature development. Existing saved 0.1.0 analyses retain their original version and must be reimported to receive the new evidence calculations.

Only next external milestone: **KAIKAI TEST 01 — PENDING**. Independently unzip, launch, load sample, import CSV, inspect dashboard/points, restart, confirm persistence and export. Report every failed step.
