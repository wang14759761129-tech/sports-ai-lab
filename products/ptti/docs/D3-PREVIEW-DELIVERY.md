# D3 desktop preview delivery

Source baseline: c91aeee319e2bb1f0e0fbfc128e68f8351a5b073 (D2).
Version: 1.0.0-D2. Runtime remains UNVERIFIED.

Stable independent directory: %USERPROFILE%/PTTI/Candidates/D2/1.0.0-D2-c91aeee319
Executable: PTTI-Next-Preview.exe
SHA256: e57503202a12faca742f6c7471e2349bd3380d57a8e7cb5408add1120492ab0d
Desktop shortcut: PTTI Next D2 预览版.lnk; direct EXE target, package directory as working directory.
Keep the whole directory including _internal. package-manifest.json records 212 payload files; the manifest itself is additional. Never copy the EXE alone.

Reproduction: from products/ptti, use the pinned Python environment and run scripts/build_ptti_next_preview.py. Existing resource, offline dependency, media and clean-source guards remain required. Output identity changes with the source commit; this delivered EXE is D2, not rebuilt from this documentation commit.
Verification: python scripts/build_ptti_next_preview.py --verify-only <package-directory>.

Startup review: identity and resource check precede configuration checks; missing frontend/catalog, invalid LOCALAPPDATA and missing registered WebView2 receive Chinese diagnostics. Mutex rejects duplicate previews. Runtime failures log traceback and release the mutex in finally. Embedded API stops and joins its owned thread and closes its reserved socket on startup failure and window exit. A five-second join is bounded, not proof of actual native teardown; a stalled thread remains a runtime verification gap. Registry checks do not prove the WebView runtime can create a window.
Data and WebView storage are under PTTI-Dev/Next-D2-Preview, separate from D1 and formal R4. No frontend business changes. No Native launch was attempted.

Backup proposal (NOT uploaded): BACKUP-R2's fixed catalog does not include D1 9c0f333283834a8cba4a61f3a474bd9ef748c49a or D2 c91aeee319e2bb1f0e0fbfc128e68f8351a5b073. Do not push their shared original history blindly. Prepare separately screened source snapshots for D1/D2 plus this delivery document, full source-to-safe SHA mapping and per-file hashes. Scan every reachable object; exclude restricted WTT photography, screenshots, env files, secrets, databases, media, model weights and caches. Review approved source scope before a new private branch push.
Binary backup is separate: package contains third-party runtime DLLs and ffmpeg/ffprobe; media gate passing and local packaging do not independently certify redistribution licenses. Review bundled licenses/THIRD_PARTY_NOTICES and all runtime assets before any external binary upload. Do not treat a private repository as permission. No executable upload is approved by this task.

Rollback: close only this preview normally, use unchanged D1/formal entry. This shortcut and candidate directory may be removed later only with explicit cleanup authorization; never delete data to roll back. No database migration, formal shortcut change, deployment or push.

NATIVE_RUNTIME=NOT_TESTED
CINEMA_VISUAL=NOT_TESTED
REAL_PLAYBACK=NOT_TESTED
