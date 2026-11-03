# GOAL16 Desktop version check, data backup and rollback

This describes the manual release path. No downloader, updater endpoint, active version pointer or automatic activation is implemented.

## User data that must survive an upgrade

Saved matches, followed athletes, and training/match/coach/Fan notes are stored under the WebView2 local origin in `ptti-fan-universe-local-v1`. They are local to the PTTI desktop profile and are not synchronized to system browsers.

Before upgrading, the user exports the Fan JSON backup from “My Corner”. The new version must keep the production WebView2 user-data folder at `%LOCALAPPDATA%\PTTI\DesktopFan\WebView2` and keep the same loopback origin and port. Staging a new executable must never replace or clear that folder. QA runs use a separate profile below `%TEMP%\PTTI-GOAL16-DesktopFan-QA\Port-<port>\WebView2`. The GOAL17.3 candidate defaults to QA mode and port 4202 even when its EXE is opened directly. It cannot select the production profile through its CLI.

For a release that changes origin, WebView2 storage behavior or the backup contract, stop activation until a migration is reviewed. Do not silently import, reset or transform user data.

## Manual version check and stage

1. A future “Check version” action contacts only the authenticated release endpoint after the user selects it. It reports installed and offered versions without downloading.
2. The user selects “Prepare update”. Download into a new immutable version folder; never overwrite a running folder.
3. Verify the release-manifest signature against the pinned publisher key, then verify every file SHA-256, WebView2 runtime requirement and source/catalog/media identities. An unsigned manifest plus its adjacent hash is not publisher authentication.
4. Before activation, confirm that the current Fan backup JSON parses under its declared contract and every saved/followed reference still exists in the offered catalog. Preserve the original export unchanged.
5. Show the version, source commit, media identities, package hash, data handling and rollback target. Require a separate user confirmation and the supported release-approval action.
6. Only then may a future installer atomically switch a version pointer. Ask the user to close the current PTTI window normally; never terminate it to force an update.

## Backup and rollback validation

The Fan JSON backup is the portable recovery copy. Before changing versions, retain the exported file and record its SHA-256 locally. Validate it with the same parser and reference checks used by “My Corner”. After the upgrade, export again and compare the canonical local-data JSON or verify the saved-match, followed-athlete and note IDs and counts. Do not include the backup contents in diagnostic logs.

If the new version loses data or fails to load, close it normally, atomically restore the prior version pointer, and reopen the retained release with the same WebView2 profile. Confirm the prior data IDs/counts. If any data is still missing, import the untouched pre-upgrade JSON only after the app shows the expected destination and the user confirms replacement.

The WebView2 profile remains in place across app rollback; only version folders and the version pointer change. Keep the prior package and its signed manifest until rollback validation passes. A profile-folder copy is an additional recovery measure only while the app is fully closed; it is not a substitute for the portable Fan JSON backup.

## Signing, integrity and approval

- Authenticode-sign the desktop host with the approved publisher certificate and timestamp it; verify the signer identity and signature status before staging.
- Sign a canonical release manifest with the release key. The signature must cover version, source commits, catalog/media hashes, runtime requirements and all package file hashes. Keep private keys outside the worktree and build machine.
- Verify signature first, then file hashes. Store the detached manifest hash as a quick corruption check, not as a replacement for a signature.
- Submit the exact selector/pointer change, candidate and rollback hashes through the platform's supported approval mechanism. Present those same values for explicit user confirmation immediately before activation.
- Retain current and prior immutable packages. Rollback is an atomic pointer restore plus a normal restart; never rewrite the prior package or profile.

Current state: package `0.1.6-fan-bb0a0c2` is unsigned and unactivated. It defaults to QA-only port 4202 and preserves that QA profile across normal restarts; this is not a production-data migration. JSON export uses the native WebView2 save dialog. The GOAL16.7 selector approval package remains unchanged. No automatic update mechanism or approval channel is available in this session, and formal activation remains blocked by the earlier policy rejection of the selector replacement.
