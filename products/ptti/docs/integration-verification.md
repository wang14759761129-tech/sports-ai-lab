# PTTI 0.1.1 integration verification — 2026-10-05

## History and scope

Canonical repository: wang14759761129-tech/sports-ai-lab. Integration branch: codex/ptti-integration-v0.1.1. Research baseline 1b30e8ea0f8a90a745fb6c30105599f0334fdf7c and original PTTI release 4585439ea11dc8250cc15031a991aa71084fea3f are both ancestors of non-squashed subtree import 2975867cd0e526aeed0b519e2c55fe43811b88f3. Original local main and annotated v0.1.0 still resolve to the original release; no history was rewritten. The integration clone is excluded only in the original repository's local .git/info/exclude.

No files under research-tracks/ or projects/ were changed. Protocol v0.3, DATA_SCHEMA, ANNOTATION_GUIDE, ANALYSIS_PLAN, OBSERVABILITY_MATRIX, Pilot 1/1B/1C reports, Pilot 2 plan/report, VIDEO_SOURCE_SCORECARD, LIMITATIONS, CHANGELOG, RESEARCH_LOG, real/sample CSVs, metadata, validator and summary scripts were inspected. Original research validation passed for ten rows and 21 columns; tactical uncertainty remains 100%, conditional third-ball fields have zero eligible rows and ten unresolved opportunities.

## Executed checks

- Final build_windows.bat: **34 tests passed, zero failed** (all original 16 retained; 18 additional cases). One non-blocking Starlette TestClient deprecation warning.
- TypeScript/Vite production build passed; non-blocking large-chunk warning.
- PyInstaller Windows directory build passed, exit code 0.
- Native application opened, loaded the 52-point synthetic sample and rendered charts. Existing sample and real Pilot imports persisted across close/reopen.
- Real Pilot CSV imported through the actual packaged application's API: ten valid points, core point-win statistics available, unknown/unclear tactical values preserved, third-ball conversion null with INSUFFICIENT_EVIDENCE. JSON and HTML responses returned 200 and were saved/checked.
- Final handoff copy launched from dist/PTTI-v0.1.1-Windows/PTTI/PTTI.exe with isolated dist/smoke/matches.db. Native GUI selected sample/protocol-v0.3-example.csv using the Windows file picker, saved it with Chinese test metadata and synthetic flag, displayed analysis and all ten points, and completed JSON Save As to dist/smoke/gui-export.json. Saved JSON parsed successfully (55,329 bytes), preserving source/provenance and synthetic label. Closed/reopened application and confirmed this imported match remained in the library.
- Final UI shows Chinese first-screen instructions, evidence states, metric denominators and exclusions, a missing-value column, original source fields, and explicit absence of winner/error semantics. Unknown is shown as an em dash plus evidence state, not 0%.
- Developer test data/export files are outside the handoff and ignored by Git. User's normal database was not used for release smoke tests.

## Handoff artifact

ZIP: dist/PTTI-v0.1.1-Windows-x64.zip; **19,422,902 bytes** (18.52 MiB).

SHA256: 797715e28805f74770c9b180b2ddc8e12b5e0b7f95e3032488a2d5a07778d815

Archive CRC verified for all 196 entries. Required executable/runtime, START-HERE, both synthetic CSVs and four user documents are present. No database, .venv, node_modules, .git or __pycache__ entries. Runtime dependencies are bundled. Requires Windows x64 and Edge WebView2 Runtime.

## Open gates and claims

KAIKAI TEST 01 remains PENDING: no independent recipient/clean-machine PASS. Printing, large-match performance and GUI HTML Save As remain unverified; HTML response export itself passed. Existing 0.1.0 saved analyses are not silently recalculated. Product minimum-five/maximum-30-percent uncertainty rules are conservative display gates, not scientific significance or validated confidence thresholds.

Pilot 1C remains REVISE / HOLD; primary research question remains ON HOLD PENDING MEASUREMENT FEASIBILITY. Pilot 2 NOT STARTED. No new video was inspected. Notion was not updated; see NOTION-SYNC-REPORT.md. GitHub push/tag/release state must be verified live in the final delivery report rather than inferred from this local document.
