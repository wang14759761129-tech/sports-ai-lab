# PTTI Desktop Fan candidates

## GOAL17.3 current candidate

`0.1.6-fan-bb0a0c2` packages San commit `bb0a0c2a5558ff9424e4d89f0eb0724cd77d5284`: 7 matches, 17 sources, 8 athletes and 12 approved photo derivatives for six athlete detail pages. Its static Web build is byte-identical to San's production dist and has no Vite runtime dependency.

Open `<LOCAL_USER_ROOT>\PTTI\Candidates\GOAL17\0.1.6-fan-bb0a0c2\host\PTTI-Desktop-Fan.exe` directly. This candidate always defaults to isolated QA mode on port 4202; its profile is `%TEMP%\PTTI-GOAL16-DesktopFan-QA\Port-4202\WebView2`. It does not migrate production favorites or notes. Do not open a second instance while 4202 is occupied.

Real GUI acceptance covered the six profile photographs and attribution in 0.1.5. Version 0.1.6 preserves exactly the same Web bytes and fixes a desktop-only JSON export defect: pywebview disabled downloads by default. The fix enables its native save dialog. Version 0.1.6 passed direct startup, seven-card catalog scrolling, actual JSON file export and normal close/reopen persistence for one saved match, one followed athlete and one synthetic note. See `releases/0.1.6-fan-bb0a0c2/GOAL17.3-ACCEPTANCE.md` for evidence boundaries and hashes.

The R4 entry remains visible and stops at `BLOCKED_PENDING_SELECTOR_APPROVAL` before invoking the selector or accessing a database. Formal activation remains blocked by the earlier policy decision. All GOAL16 packages and the intermediate 0.1.5 package are retained; 0.1.5 has the documented JSON-export defect and is not the recommended new candidate.

## Historical GOAL16 candidate

Each desktop package is a fixed snapshot of a committed Fan build. It does not depend on the Vite development server on port 4183 and does not synchronize with later Web releases.

## Candidate identities

- Rollback package `0.1.1-fan-5678d96` remains intact and verifies against its original release manifest.
- Parent package `0.1.3-fan-072c57a` remains intact. It is the currently running isolated QA instance on port 4200.
- New package `0.1.4-fan-072c57a` is built from San commit `072c57a4d16c4e7fead452a22eb378f2a7a9f633`, with the five-match Main catalog, six approved WebP derivatives and fixed hashes for the catalog, media index, R4 launcher and R4 executable. Its QA instance uses port 4201 and a separate WebView2 profile.
- The signed-off desktop selector was not changed. The new candidate is not active by default.

## GUI and media acceptance

The 0.1.4 QA GUI was opened and the Fan home, Stars page and profiles for Wang Manyu, Liang Jingkun and Tomokazu Harimoto were viewed. The three photographs and their XIAOYU TANG / CC BY-SA 2.0 attribution appeared on the corresponding profiles. The home and Stars cards use PTTI artwork. The static media check rejects portrait use outside approved athlete profiles; all six image routes served bytes matching the package manifest.

## Native QA isolation

The Native button is enabled only with `--qa-profile`. Before a normal QA launch it verifies the pinned selector, launcher and R4 executable; checks the existing 2.5 GiB memory guard; opens the preview database read-only; copies it with SQLite's backup API to `%TEMP%\PTTI-GOAL16-R4-QA\<session>\Profile\PTTI-Dev\VideoFirst-R4-Preview\matches.db`; checks the copy; and routes R4 to that QA profile.

The current integration attempt stopped before copying the database or starting R4. The selector's check-only receipt lists every process named `PTTI*.exe`; that includes the running `PTTI-Desktop-Fan.exe`. The candidate interprets that nonempty list as an already-running R4, and the normal selector uses the same broad process filter. R4 is therefore `BLOCKED` until the selector can be changed through its supported approval path to check the exact R4 executable. The candidate invokes the selector without setting an execution-policy override. The unchanged selector itself uses `-ExecutionPolicy Bypass` for its pinned child launcher; no system policy or blocked selector update was bypassed. No R4 process was launched, and the live database was not opened or modified by this integration attempt.

## WebView2 data

Favorites, follows and notes use the Fan local-storage key `ptti-fan-universe-local-v1`. The production profile remains `%LOCALAPPDATA%\PTTI\DesktopFan\WebView2`; keeping the same profile and loopback origin/port preserves the existing desktop store. The QA candidates use isolated profiles and do not read or migrate production WebView2 data.

The My Corner backup supports JSON export/import for saved matches, followed athletes and note collections. The Fan data checks pass round-trip, legacy v1 migration, and invalid-file rejection. A production-profile close/reopen test has not been run; no production user data was touched.

## Release state

The 0.1.4 manifest pins the San commit, public match catalog, public media index, Main media manifest and every packaged file hash. The host EXE is unsigned. The package is a frozen snapshot, not real-time Web synchronization. It can be opened directly from its EXE path, but its integrated Native button remains QA-only and blocked by the current selector guard. No automatic download, activation, or selector replacement is enabled.
