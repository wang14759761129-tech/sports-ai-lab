# GOAL11 Desktop Web Pro delivery — 2026-10-15

## Startup

The local Alpha uses the real Web package, not an EXE wrapper. Installed launcher:
`<LOCAL_USER_ROOT>\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI-Web-Pro\Start-PTTI-Web-Pro.ps1`.
Its `web-pro.json` explicitly identifies this Web worktree, Node executable and Playback Core source. Source launchers live in `scripts/desktop/`; scripts are UTF-8 with BOM for Windows PowerShell 5.

The launcher validates package identity and its `dev:review` command, serializes launches with a named mutex, checks the loopback-only `/__ptti/health.json`, rejects an unrelated occupied port, starts a detached hidden worker if needed, waits up to 35 seconds, then opens `http://127.0.0.1:4174/` through the system URL handler. Startup logs are in the installation directory. No persistent global environment variables or video/database changes.

`-NoBrowser` performs service startup and health verification; `-CheckOnly` never starts a service. Browser opening checks the existing 2.5 GiB RAM gate. An unavailable/moved sibling Playback worktree fails clearly instead of silently selecting another Core.

## Delivery evidence

- Starting San: `ffd75c864bfcbf5c652d9e620e3c6427d1c679ab`; source changes in this commit.
- Initial Playback: `0ca59815810d232290aab3807645de92bc77938f`. During this task NextDex advanced its own worktree to `304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe` (error classification and typed issue codes). The final repeat checks consume that actual version; no NextDex file was edited by San. Health reports the current dependency HEAD on every request.
- Real service-not-running startup PASS: detached worker PID 30464, package command `npm run dev:review`; identity health ready in approximately four seconds.
- Reuse PASS twice, same listener PID and no duplicate service.
- AppData candidate shortcut shell invocation PASS: launcher logged URL opening; Chrome process command line included `--single-argument http://127.0.0.1:4174/`. Registered URL ProgId reported MSEdgeHTM, but the actual launched process was Chrome; do not infer browser identity from the registry alone.
- Bounded headless Chrome product check PASS (6 checks, 2509 ms): Cinema search, Insight/Review controls, bilingual navigation, 1366x768 and 390px without page overflow. No private video was loaded. This is product navigation acceptance, not a new Comparison/full-game acceptance or a human test.
- Build/TypeScript, preview-package privacy check, Comparison export, 22 Playback adapter assertions, PowerShell 5 parse/runtime checks PASS. Build retains its existing >500 KiB chunk warning.
- Screenshots/log: `.alpha-qa/goal11-desktop/`; these are local QA artifacts and are not production assets.

## Desktop and recovery

Actual desktop is `<LOCAL_USER_ROOT>\OneDrive\Desktop`, resolved with Windows Known Folder API.
Original shortcut points into the Codex package LocalCache R4 install, not the similarly named standard AppData directory.
Backup: `<LOCAL_USER_ROOT>\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI-Web-Pro\backups\20261015-165114`.
It contains the exact original shortcut, both original launcher copies, version pointer and SHA metadata.
R4 EXE SHA-256: `fca3bdf09a96e3d95a1f676ea63793909057c6e8a1d95d0a9274d3c3fc6738ab`.
No R4 executable, launcher, activation pointer or user database was overwritten.

To restore only the desktop shortcut:
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<LOCAL_USER_ROOT>\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI-Web-Pro\Restore-PTTI-Cinema.ps1" -BackupDirectory "<LOCAL_USER_ROOT>\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI-Web-Pro\backups\20261015-165114"`.
The recovery script checks the recorded desktop path and old-launcher hash, preserves the Web shortcut, and copies back the original R4 shortcut. It does not launch R4.

The sole normal desktop entry `PTTI Cinema.lnk` is now activated to the physical-path Web Pro launcher. AppData candidate and final desktop shell invocations logged successful default-browser URL requests. The R4 launcher hash remained unchanged. Other previously existing QA/test shortcuts were not edited or deleted.

## Product scope and gates

Cinema retains search, four internal review records, evidence-aware official external destinations, match details/deep links/share card. No official video embedding is added where permission is UNKNOWN.
Insight and Review are two entrances to the same existing Pro workbench; switching between them keeps the workbench mounted. Existing Main Review Targets, current-session playback, manual notes, JSON exports, draft/report imports and quality review remain in that workbench.
Stars and Explore currently have zero approved entries. Their existing empty-state implementation remains; navigation is shown only when there are actual entries. No empty product shells or invented data are published.
Internal review remains 4, strict public remains 0. SIMULATED_ONLY, UNKNOWN and LOCAL_SESSION_ONLY are preserved. No real-person/video acceptance is claimed.

The local Vite build directly consumes Playback Core in another worktree. This installation works on this machine; it is not a portable cross-computer release. Pin/package that dependency before portable delivery. Physical mouse double-click and real athlete usability remain separate from shell invocation and automated rendering evidence.

The desktop link uses the physical LocalCache AppData path because Codex virtualizes ordinary Local AppData writes. This avoids relying on Explorer inheriting the Codex namespace.
