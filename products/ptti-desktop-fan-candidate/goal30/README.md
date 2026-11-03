# GOAL30 Collector's Lounge Desktop QA build profile

This profile reuses the GOAL23 builder and small WebView2 Host. It does not reuse the 0.1.8 EXE. No 0.1.9 EXE has been compiled during preparation: the observed 2.091 GiB RAM failed the 2.5 GiB gate.

Fixed identity: San 03df597c1b872c4875e684c9e4f8a1cc54e7e297; Main 8036a37ff6af5ae5c7924b5c26d3290e640bf607; version 0.1.9-fan-03df597; Host 0.1.9-goal30; QA port 4209. The config pins the full static tree, eight public JSON packages and their contract versions, the Web schema, and two Main schemas. It rejects another version/source/port, missing package pins and stale artifacts without Collector's Lounge markers.

Rollback parent is the untouched 0.1.8 package, with release SHA256 e2503642757df215fc7b2234d2af01edf8fbfb8411f5886b4d9ef8a2d86a833d and complete payload verification. The legacy 0.1.8 configuration and its version validation remain intact. Staging now records the selected config rather than the legacy default file.

From the sibling goal23 directory, read-only identity preflight:

```powershell
python -B .\build_goal23.py preflight --config ..\goal30\goal30-build.json --san-root C:\PTTI-Worktrees\web-goal14-fan-mvp --main-root C:\PTTI-Worktrees\integration-preview-sprint-0-1 --static-root C:\PTTI-Worktrees\web-goal14-fan-mvp\products\ptti-web\dist --main-json C:\PTTI-Worktrees\integration-preview-sprint-0-1\products\ptti-integration\generated\goal22-main-inspiration-v0.1\public\fan-inspiration-v0.1.json --parent-release <LOCAL_USER_ROOT>\PTTI\Candidates\GOAL23\0.1.8-fan-4d24c13 --output-root <LOCAL_USER_ROOT>\PTTI\Candidates\GOAL30
```

When a fresh guard permits a future build, use the same command with build instead of preflight and the original verified Python environment argument. The builder retains checks before staging and immediately before PyInstaller; there is no retry or fallback to an older EXE. Do not run compilation when the guard fails.

Profile path: %TEMP%/PTTI-GOAL23-DesktopFan-QA/0.1.9-goal30/Port-4209/WebView2. The common parent folder name is reused deliberately; the distinct Host version and port isolate it from 0.1.8 and production. The Host permits only its pinned port and checks RAM at startup. Native bridge remains DISABLED_NO_R4_BRIDGE; there is no database or selector bridge.

Offline tests: python -B -m unittest discover -s tests -v from goal23. Tests use temporary synthetic data, including a mocked low-RAM refusal before any tool process. They do not compile or launch the Host.

GUI acceptance remains NOT_TESTED until a new EXE and release receipt exist: focus on Lounge save/card/detail/Watch-return/remove/empty/missing-data flows, synthetic close/reopen persistence and unchanged Journal/follows/legacy import. Do not inject a missing match into a live profile; use an isolated synthetic fixture. The current Host min_size is 840x620, so phone-width desktop QA is unsupported; record that limitation rather than claim a 390px window test.

No formal activation or new shortcut is part of this profile. Rollback is to close only the task-owned QA instance normally and use the preserved 0.1.8 entry; do not copy files into the old version or migrate real profiles. Output collisions fail closed.
