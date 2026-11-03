> Historical v0.1.0 record. Protocol v0.3 has now been recovered; current compatibility, evidence gates and verification are documented in SCHEMA-COMPATIBILITY.md, RESEARCH-BASIS.md, EVIDENCE-METRICS.md and integration-verification.md. Earlier SOURCE NOT FOUND statements describe the original empty workspace only.

# PTTI v0.1.0 — First Usable Release

Freeze date: 2026-10-05. Product and analytics 0.1.0; data schema 1.0.0-new. Historical v0.3 source: SOURCE NOT FOUND. There is no claimed compatibility with the historical research protocol. This is the repository's legitimate first commit; no earlier history is invented.

## Version-control and binary policy

Commit source, tests, dependency lockfile, documentation and reproducible build/package scripts. Never commit .venv, node_modules, build caches, __pycache__, local databases/user data, secrets or generated release artifacts. `.gitignore` excludes those paths. Existing local ignored environments and build outputs are retained on disk, not deleted or included in Git.

Distributables belong in GitHub Release assets, not source control. Windows folder package contains PTTI.exe and bundled required runtime; use a ZIP to hand it to Kaikai. No Python, Node, Git, VS Code or Codex installation is needed to run it. Microsoft Edge WebView2 Runtime is a Windows prerequisite. Reproducibility means versioned source and repeatable build commands, not byte-identical EXEs across machines/tool versions.

## Build and archive

1. `setup_windows.bat` from a fresh clone (Python 3.12+ and supported Node required for developers only).
2. Close PTTI. Run `build_windows.bat`: TypeScript/Vite production build → pytest → PyInstaller directory distribution.
3. Run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/package_release.ps1`.
4. Preserve both the SHA256 sidecar and ZIP. The script refuses to overwrite previous handoff outputs.

The ZIP has only `PTTI-v0.1.0-Windows/`: `PTTI/` runtime folder, `START-HERE.txt`, `sample/synthetic.csv`, and quick-start/template/feedback docs. It does not contain repository source, local databases, development environments or build caches.

## Remote publishing boundary

At freeze inspection there was no remote. Do not invent an account or repository. The one missing user action is to provide the intended GitHub repository URL (or configure it as origin). After verifying that it is the correct PTTI destination, use `git push -u origin main` and `git push origin v0.1.0`. Create release v0.1.0 with the versioned release notes, ZIP and SHA256 sidecar if authenticated GitHub tooling is available. No remote publication is claimed until it happens.

## Only next milestone: KAIKAI TEST 01

Status: **PENDING — not passed**. PASS requires Kaikai to receive the archive, extract/copy the entire folder, launch on his own Windows computer without Python or Node, open the sample, successfully import one CSV, see the dashboard, restart and reopen persisted data, and successfully export. Record failures in docs/USER-FEEDBACK.md and turn each reproducible failure into a GitHub issue when the remote is connected. Do not begin v0.2 before this gate; only release-blocking fixes are allowed.
