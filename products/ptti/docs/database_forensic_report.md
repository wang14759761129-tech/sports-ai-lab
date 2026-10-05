# PTTI database forensic report — 2026-10-05

## Preserved decision

**STATE_UNCERTAIN_DO_NOT_MODIFY** remains in force for historical recovery. No production database was restored, migrated, cleaned, or deleted. Current physical files are distinguishable and both developer instances are now stopped. The historical pre-incident contents and origin of the real user database records remain unknown.

## Corrected snapshot interpretation

The previous report incorrectly treated two reader-dependent file views as successive versions of the same physical database. This interpretation is withdrawn. Simultaneous PowerShell/product-venv and Microsoft Store Python reads showed different sizes/hashes at the same nominal LocalAppData path. NTFS file-ID queries proved that they were different physical files. Both views remained unchanged throughout this investigation and after stopping the applications.

| Physical entity | File ID | Bytes | SHA256 | Match / synthetic rows |
|---|---|---:|---|---:|
| Real `C:\Users\wang\AppData\Local\PTTI\matches.db` | `0xb00000014b6ba` | 262144 | `276e7e527e28f07adf0a41d9196665a8383d22ae3b793018e78a33acea6566ec` | 4 / 4 |
| Codex private `C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI\matches.db` | `0x2000000012c7e1` | 40960 | `710fe918632896b02b6b0efaf68126c217b41848433035f809e128785666362a` | 1 / 1 |

Both pass SQLite integrity_check and have matches/preferences tables, user_version=0, no row creation/update timestamps, and no independently audited row history. The real database has four distinct synthetic IDs; the private database has one different synthetic ID. Their mtimes, complete IDs, schema metadata and reader evidence are in [database_snapshot_inventory.md](database_snapshot_inventory.md).

This is confirmed file-view separation, not confirmed concurrent replacement. Windows MSIX AppData virtualization explains the Codex private backing path; child processes may report UNPACKAGED while still seeing the inherited view. Do not rely on package identity or a displayed path alone. See [Microsoft packaged desktop file-system documentation](https://learn.microsoft.com/en-us/windows/msix/desktop/desktop-to-uwp-behind-the-scenes).

## Process evidence and database mapping

### PID 10100

- Parent PID: 39476
- Started: 2026-10-05T18:41:10.147879+08:00
- Executable: `C:\Users\wang\OneDrive\文档\chatgpt\table tennis intelligent\research-integration\products\ptti\dist\ptti-vision-dev\ptti-vision-dev.exe`
- Command line: `"C:\Users\wang\OneDrive\文档\chatgpt\table tennis intelligent\research-integration\products\ptti\dist\ptti-vision-dev\ptti-vision-dev.exe" `
- Working directory: `C:\Program Files\WindowsApps\OpenAI.Codex_26.930.3930.0_x64__2p2nqsd0c76g0\app\`
- Package identity API: `UNPACKAGED`
- EXE SHA256: `06a880e69376323ee23869304c60bcd376fe39adb50e3d422758f962ad380da4`
- PTTI_DB in captured process environment: `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\vision-smoke.db`
- PTTI_ENV: `ABSENT`
- PTTI_VISION_HOME: `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti`
- HTTP health version: `0.2.0-dev`. Old binaries lack embedded build manifests; PID 43860 has the `51dee43` build directory and prior build record, while PID 10100 exact source commit is UNKNOWN.

### PID 43860

- Parent PID: 31088
- Started: 2026-10-05T19:48:03.207735+08:00
- Executable: `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\PTTI-Vision-Dev-51dee43\PTTI-Vision-Dev\PTTI-Vision-Dev.exe`
- Command line: `"C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\PTTI-Vision-Dev-51dee43\PTTI-Vision-Dev\PTTI-Vision-Dev.exe" `
- Working directory: `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\PTTI-Vision-Dev-51dee43\PTTI-Vision-Dev\`
- Package identity API: `UNPACKAGED`
- EXE SHA256: `ac4a4054193f30f232b9d40b4e36c3c4931e47a76a1381820e7cd84ec7391d7e`
- PTTI_DB in captured process environment: `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\dist\vision-smoke.db`
- PTTI_ENV: `development`
- PTTI_VISION_HOME: `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist`
- HTTP health version: `0.2.0-dev`. Old binaries lack embedded build manifests; PID 43860 has the `51dee43` build directory and prior build record, while PID 10100 exact source commit is UNKNOWN.

The environment was captured read-only from the Windows PEB, retaining only a configuration whitelist. Source Repository connects to the explicitly configured PTTI_DB. Read-only API row IDs matched the respective files: PID 10100 → product `dist/vision-smoke.db`, one synthetic row (`36e49cd9-2380-445e-ba53-2a0d790e6c0c`); PID 43860 → product `dist/dist/vision-smoke.db`, zero rows. Thus these two running instances were not pointing at either production snapshot. The nested build exposed a real developer launcher defect: fixed parent-depth calculation chose the dist directory as the vision workspace. The launcher now discovers the actual workspace and defaults DB to PTTI-Dev.

## Backup lineage and missing-backup investigation

- Confirmed: real four-row file → `%LOCALAPPDATA%/PTTI/matches.db.forensic-backup-20261005-resume`, identical 262144 bytes and SHA256 `276e7e...`.
- Confirmed: Codex private one-row file → Codex-private `matches.db.forensic-backup-20261005-185959`, identical 40960 bytes and SHA256 `710fe9...`.
- The earlier named backup exists in the Codex private directory. Store Python enumerating the real user directory did not see it; no deletion is established. Prior report/tool records describe a forensic byte copy, and its current bytes verify that copy; there is no independent audit identifying a creator process.
- Source search found no automatic cleanup referring to forensic backups. Build scripts do not clean user PTTI data. Installer uninstall cleanup is restricted to its install directory; pytest temp retention concerns test directories only.
- UNKNOWN: causal lineage between the real and private databases, creator of each synthetic record, whether authentic matches existed previously, and the physical reader view of the historical `9B949BE38ACD2FAE177A4DFD794600D677A77AFB5D24BD9666FA3746C72CF48F` hash. A hash alone with no file-ID/reader evidence does not prove overwrite. Earlier VSS history inspection lacked sufficient permissions; recovery history is not certified absent.

## Freeze result

Both PID 10100 and PID 43860 were stopped only after environment/CIM/API evidence and both matching backups had been captured. Before/after scans found no changes in size, mtime, SHA256 or record IDs for the two production-view entities, their backups, or the developer DBs. No database write API was called during tracing. Full process/CIM and per-reader scans are local, ignored artifacts under outputs/db-trace.

## Fail-closed isolation

ProductionDatabaseGuard rejects production paths, MSIX PTTI aliases, symlinks/hardlinks visible in the current view, and path changes on every repository connection in development/test mode. Test mode requires OS temp and cannot switch to production even explicitly. Production mode rejects an unknown or differing physical file-ID path and packaged host identities, avoiding silently opening a private substitute. The real production database is never opened for a guard regression.

Production defaults to LocalAppData/PTTI; development defaults to LocalAppData/PTTI-Dev; pytest bootstrap uses OS temp/pytest tmp_path. Each startup prints and persists environment, displayed DB, physical path, file ID, PID, READ_WRITE mode, runtime and source/build provenance beside the selected isolated DB. Local development exposes /api/diagnostics/database; production returns 404. SQLite transaction contexts now explicitly close their handles after commit/rollback.

## Stop condition

**DATABASE_RECOVERY_REQUIRED** remains the gate because historical contents cannot be independently reconstructed and the user has explicitly retained STATE_UNCERTAIN_DO_NOT_MODIFY. Do not delete synthetic rows or substitute the private snapshot for the real user file. Path/view tracing is resolved; historical recovery is not.

The real host regression additionally showed that Path.resolve() can erase the original request by returning a private backing path. Protection now preserves the original lexical absolute request before comparing file-ID evidence. A read-only check against the live Codex view produced the expected FATAL virtualized-production-path error without opening SQLite for writing. All 100 automated tests pass, including this erasure regression.

## Packaged isolated-write smoke verification

The windowed developer EXE built from clean commit 593d5bc was launched with explicit PTTI_DB at OS-temp/PTTI-isolation-qa-593d5bc/matches.db. /api/diagnostics/database and the persistent startup-database.jsonl both recorded DEVELOPMENT, READ_WRITE, exact physical path, file ID 0x40000001664ae and embedded build commit. One explicit sample POST saved one synthetic record; read-only SQLite readback confirmed 52 points. PowerShell did not provide object fields for that nested sample response, so SQLite readback—not empty PowerShell properties—is the accepted record evidence.

The launcher now resolved PTTI_VISION_HOME to the real product workspace instead of dist. With normal window visibility, the native title was PTTI · 个人乒乓球比赛分析, MainWindowHandle was nonzero and Responding was true. A preceding hidden-window launch supplied API evidence only; its absent visible title was not classified as a product failure. No native controls were clicked because automation still enumerated apps=[]. All investigator-launched QA instances were stopped. Final real-production and Codex-private DBs and their backups retained their pre-investigation sizes, mtimes and hashes. No development instance remains running.

Final developer EXE: dist/PTTI-Vision-Dev-hardened-final/PTTI-Vision-Dev/PTTI-Vision-Dev.exe; 7,603,907 bytes; SHA256 e88068ba3986762e46dcc54df3e90cedbec221680418e32eb0e80380aacef77f. Build succeeded with optional Android and hidden-import pycparser/tzdata warnings. This local engineering artifact is not a release or desktop acceptance result.
