# GOAL11.1 — persistent desktop launcher

## Final location

Windows Known Folder Desktop: `<LOCAL_USER_ROOT>\OneDrive\Desktop\PTTI Cinema.lnk`.
The entry invokes Windows PowerShell with:
`-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "<LOCAL_USER_ROOT>\PTTI\Web-Pro\Start-PTTI-Web-Pro.ps1"`.
Working directory: `<LOCAL_USER_ROOT>\PTTI\Web-Pro`.
Icon: `<LOCAL_USER_ROOT>\PTTI\Web-Pro\ptti-cinema.ico`.

The dedicated user-root directory was chosen because ordinary AppData writes inside Codex were previously observed under the client's LocalCache namespace. The launcher, worker, configuration, icon and recovery script now live outside AppData, Codex and OneDrive. No runtime launcher path or icon depends on Codex cache. The old cache installation remains untouched for recovery.

The source installer is scripts/desktop/Install-PTTI-Web-Pro.ps1. It refuses an existing candidate directory, verifies the existing shortcut/configuration, preserves the exact configuration bytes, prepares a candidate without modifying the desktop, checks the service, and (only with -Activate) confirms a guarded candidate Shell URL invocation before changing the single desktop shortcut. It rechecks the old shortcut hash before activation. No application or EXE wrapper was created.

## Version verification

Starting clean San HEAD was `9d1ec1572b29ce7f2b4fb62e900bfd8fd75b73d7`.
`git merge-base --is-ancestor d4b8ea0abe94b31c73cec9baa9cfef13fa298901 9d1ec1572b29ce7f2b4fb62e900bfd8fd75b73d7` returned 0: d4b8ea0 is the earlier direct ancestor; 9d1ec15 adds the isolated Main source library.
Current product source, health workspace identity and served Vite module path were checked independently of old browser-log timestamps. Playback Core remains `304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe` at the configured sibling worktree. This change adds installation/recovery documentation and does not rewrite the app or statistics engine.

## Evidence and limits

- Actual Windows PowerShell 5 parser and installer execution PASS, candidate activation completed at 2026-10-15T17:31:13+08:00.
- Candidate stable-path service identity validation and actual Shell browser URL invocation PASS before replacing the desktop entry. Browser use remained above the existing 2.5 GiB guard.
- Reuse twice PASS: 4174 listener PID remained 31792; no duplicate service was created.
- Wrong Core identity configuration rejected with exit 1 and explicit occupied-unverified-service error; the original listener PID remained 31792. No process was stopped.
- Original service configuration SHA remained `cae9c22e19252f29254c75ebe32daa3a27218a655c14128e1cad2d854c152b07`.
- Browser product flow PASS: 6 groups in 5816 ms, real synthetic test file selection, 19-point Main demo, correct target IDs, only p002/p004 confirmed, p006 disabled, stable session between Cinema/Insight/Review, hidden-player cancellation, six sourced player cards, bilingual/mobile UI and deep-link return to search. This closes the earlier callback-only RAM-blocked check.
- Existing Main library validation PASS: 35 unique unlinked sources / 6 registered matches / public0 with 15 rejection cases. Existing playback adapter: 53 assertions PASS.
- Product/browser artifacts: `.alpha-qa/goal11-cinema/`. Launcher logs and installation receipt: `<LOCAL_USER_ROOT>\PTTI\Web-Pro`.

Cold start from the NEW stable directory is NOT_TESTED: the current 4174 service was preserved as required. The identical detached-worker logic had a real cold-start PASS at its old location in GOAL11. It was copied byte-for-byte, and its new path/configuration/parser checks passed, but that is not a new-location cold-start result. The active service may still have its earlier worker as parent; subsequent cold launches will use the stable worker. No user process was terminated to force this test.

Shell shortcut invocation and automated browser rendering are separate from an observed physical mouse double-click. Human double-click, logout/reboot persistence and real-athlete/private-match acceptance remain NOT_TESTED.

## Recovery

Stable backup directory: `<LOCAL_USER_ROOT>\PTTI\Web-Pro\backups\20261015-173109`.

- To restore the previous working Web entry, copy `PTTI Cinema.lnk` from that backup to the Windows Desktop, overwriting only the shortcut. The backup hash is recorded in installation-receipt.json; old cache launcher/config/worker are preserved both in their original location and as snapshot files.
- Original R4 shortcut, launcher copies, version pointer and metadata are additionally retained in its `r4-origin` subdirectory. R4 EXE and launcher hashes were checked unchanged.
- To restore R4 without launching it:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<LOCAL_USER_ROOT>\PTTI\Web-Pro\Restore-PTTI-Cinema.ps1" -BackupDirectory "<LOCAL_USER_ROOT>\PTTI\Web-Pro\backups\20261015-173109\r4-origin"
```

The recovery script checks the original launcher hash and desktop location, saves the current Web shortcut before replacing it, and does not edit or run the R4 EXE.

## Remaining backlog

Portable packaging still requires removing the live sibling Playback Core source dependency. The current Web and Core source directories and Node runtime must remain in place. The Vite chunk-size warning and launcher error-dialog localization are nonblocking backlog items. Current-source cold boot/logoff checks require a separate safe window. Internal35 remains opt-in/local only; strict public remains 0; user videos and annotations are not uploaded or persistently saved by default. No push, CI, public deployment or R4 update.
