# P0-C2 evidence and remaining release gate

Source HEAD: 5cc753886b112305736fcc14ea77b37662726c9f
Branch: codex/ptti-p0c-isolated-r4-qa
Changes are uncommitted because the full physical negative-test gate is incomplete.

Pre-edit recovery files: outputs/P0C2-preserve in the Codex task workspace.
Contains tracked binary diff, status, exact copies of four dirty/new files and hashes.

Actual isolation execution: python -m unittest test_qa_physical test_qa_routes -v
14 tests discovered, 13 PASS, 0 FAIL, 1 SKIP.
SKIP: physical Windows symbolic-link creation returned WinError 1314. No privilege
or execution-policy changes attempted. Real junction creation/rejection PASS;
hardlink rejection PASS; external temp-canary bytes unchanged PASS. Canary stands
in for a protected directory; no actual formal user directory was touched.
Real SQLite CREATE/INSERT/SELECT and PRAGMA database_list verified QA temp path.
Real ASGI registration and media response SHA matched generated ffmpeg testsrc2 MP4.
Unapproved path rejected; unreviewed Vision/import/export routes returned HTTP 403.
This is API/byte evidence, not decoded playback or GUI evidence.

TypeScript + Vite production build PASS (Vite 7.3.6, original lock unchanged).
Feed regression: 31 PASS, 0 FAIL.
Original frontend source/CSS not modified.
pywebview 6.2.1 inspected locally: explicit storage_path/private_mode supported;
EdgeChromium sets UserDataFolder and IsInPrivateModeEnabled. Native paths NOT_TESTED.

Current gate: no commit, no QA EXE packaging and no GUI launch until remaining
physical symbolic-link test can execute through a normally authorized environment.
Do not change system policy or use another channel to bypass this restriction.
No push, merge, deployment, formal Launcher, user DB or private media changes.

Coverage map:
- apps/qa_isolation.py: canonical/reparse/hardlink path checks, media hash allowlist,
  DB dual-variable agreement, explicit layout, HTTP default-deny QA route policy.
- apps/desktop.py + qa_desktop.py: mandatory isolated entry, WebView storage,
  disabled external links/folder/package selectors/downloads, no user-log fallback.
- backend/database.py: QA DB identity guard on repository connections.
- backend/video_evidence.py: register, availability, relink, hash, stream validation;
  external package imports denied in QA.
- backend/match_library.py: folder crawling denied; synthetic thumbnails confined.
- backend/main.py: QA middleware; Vision and research-preview routers not imported.
- scripts/build_dual_source_v061_preview.py: optional dedicated QA entry and build
  identity, no external Vision path; existing normal build behavior preserved.

Limitations: application checks are not an OS security sandbox; a separate malicious
process replacing paths between check/use remains a TOCTOU risk. Native WebView and
child-process physical writes require actual runtime evidence before acceptance.
QA disables external content and exports; it is not a production feature promotion.
Playback a9eafe9 is not integrated.

Backend existing regressions: 83 PASS, 0 FAIL, 1 deprecation warning, 105.66 seconds. Command: python -m pytest tests/test_video_evidence.py tests/test_match_video_library.py tests/test_database_isolation.py tests/test_desktop_ux.py -q. Python syntax and git diff --check PASS.

Continuation: changed path validation to lstat so dangling reparse points are not silently ignored by exists(). Added actual-source reparse-metadata negative test (mocked OS metadata, not a physical symlink). Latest isolation suite: 15 total, 14 PASS, 0 FAIL, 1 physical symlink SKIP (WinError 1314). Actual junction/SQLite/ASGI tests passed again. No new EXE, commit or GUI acceptance claimed.
