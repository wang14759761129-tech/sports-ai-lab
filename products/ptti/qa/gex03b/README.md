# GEX-03B isolated Native QA

This candidate is internal QA only. It does not replace the installed R4, its
launcher, database, or WebView2 profile.

## Build after the existing 2.5 GiB gate allows it

From `products/ptti`, use a clean committed worktree and the existing guarded
builder:

```powershell
$env:PTTI_PREVIEW_PROFILE = 'video-first-r4'
$env:PTTI_PREVIEW_BUILD_ROOT = Join-Path $env:LOCALAPPDATA 'PTTI-Builds'
.venv\Scripts\python.exe scripts\build_dual_source_v061_preview.py
```

The output reports `output_folder`. Pass its
`dist\PTTI-Video-First-R4-Preview` directory to
`qa\gex03b\Start-GEX03B-Native-QA.ps1`. The launcher verifies the candidate
identity and executable SHA-256, then uses Resource Policy V2's existing heavy
2.5 GiB launch gate and a non-terminating runtime monitor.

## Isolated state

- Origin is always `http://127.0.0.1:48761`; an occupied port is a hard error.
- QA SQLite is under `%LOCALAPPDATA%\PTTI-Dev\NativeQA\GEX03\<commit>\qa-data\matches.db`.
- WebView2 cookies and local storage use the dedicated durable
  `%LOCALAPPDATA%\PTTI-Dev\NativeQA\GEX03\<commit>\webview2-user-data`
  directory. pywebview receives `private_mode=False` and this exact
  `storage_path`.
- Native QA research data uses the matching dedicated `research-data` folder.
- Existing profile identities, database files, or path mismatches are preserved
  and refused. Earlier `%TEMP%\PTTI-GEX03B-Native-QA` data is not searched,
  moved, imported, overwritten, or cleaned. Different commits have independent
  QA profiles and SQLite databases; this is intentional isolation, not a data-
  loss signal. Cross-commit transfer requires an explicit, verified backup and
  restore operation; no automatic migration runs.
- After the app has initialized its SQLite database, a commit/instance-bound
  readiness marker is written. If that database or the existing WebView2
  profile later disappears or becomes corrupt, startup refuses to create an
  empty replacement under the same QA identity.

## Manual restart acceptance

1. In Cinema, create a Moment Card; in Pro Lab, select a video the user owns,
   add a note, and save; in Fan Arena, record and settle a prediction; create a
   QA-only favorite.
2. Close the Native QA window normally and confirm that its process exited.
3. Start the same candidate again with the same launcher. Confirm that Moment
   Cards, notes after reselecting the local file, Arena history, and the QA
   favorite are still present.
4. Pro Lab's local file handle/object URL is not expected to persist. The user
   must reselect the file; video bytes are neither copied nor exported.
5. Confirm session-only search/scroll behavior separately: it may reset after a
   full process restart, while in-app return should restore it.

The current checkout still needs a freshly built, hash-verified isolated
candidate before these Native restart steps can count as acceptance. Browser
tests do not count as WebView2 restart acceptance.

## Explicit cross-commit QA backup

In a running Native QA candidate, open **更多 → 设置 → Native QA 数据保全**.
Export a SHA-256 checked JSON bundle before changing commits. The bundle only
contains the three application-owned localStorage records and the favorite keys
returned by this QA catalog; it does not contain video bytes, file handles,
cookies, the WebView2 profile, or unrelated SQLite tables. Keep the file in a
location you control because Pro Lab note text and local file names are private.

On a different candidate commit, restore is a separate, explicit action and is
accepted only when that commit's QA localStorage keys and favorite list are
empty. Schema, record, source commit and SHA-256 checks run before writes. If a
favorite cannot be matched in the destination catalog or a write/readback fails,
the importer removes only entries attempted by that import and verifies the
destination is empty again. No data is migrated at launch. If rollback cannot
be confirmed, stop using that QA environment and inspect it before retrying.
