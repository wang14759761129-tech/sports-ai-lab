# PTTI database forensic report — 2026-10-05

## Scope and handling

Direct database inspection used SQLite read-only mode and `PRAGMA query_only=ON`; no application write endpoint was called, and no manual migration, cleanup, or restore was performed. Two developer EXE processes were nevertheless running, their database paths could not be confirmed through GUI automation, and later whole-file observations differed. Consequently, this report cannot certify that no external process wrote or replaced the production-path file during the full session. A byte-for-byte copy was made of the latest observed snapshot after confirming no `matches.db-wal` or `matches.db-shm` existed and SQLite reported DELETE journal mode.

## First recorded snapshot and backup

| Item | Value |
|---|---|
| Original path | `%LOCALAPPDATA%\PTTI\matches.db` |
| Size | 40,960 bytes |
| Modified | 2026-10-05 18:16:08.7149139 +08:00 |
| Observed SHA256 at that check | `710FE918632896B02B6B0EFAF68126C217B41848433035F809E128785666362A` |
| Byte-copy path reported at that check | `%LOCALAPPDATA%\PTTI\matches.db.forensic-backup-20261005-185959` |
| Byte-copy SHA256 reported at that check | `710FE918632896B02B6B0EFAF68126C217B41848433035F809E128785666362A` |
| Copy verification | Source hash unchanged; backup hash equals source hash |
| SQLite integrity check | `ok` |
| Journal mode | `delete`; no WAL or SHM files present |

That byte-copy was described as a safety copy of the post-incident state, not a pre-incident recovery source. On a later inspection on 2026-10-05, the named copy was not present; do not rely on that earlier path as available recovery evidence.

## Later observation during v0.2 continuation

Two `PTTI-Vision-Dev.exe` processes were running from different product build folders (PIDs 10100 and 43860). The native-app automation inventory returned no applications, so neither window could be inspected or controlled through the UI. Read-only `GET /api/matches` checks against their separate localhost ports returned one synthetic example from one process and zero matches from the other. No API write request was sent.

During the same inspection, the production path was observed at different whole-file states. One hash check returned `710FE918632896B02B6B0EFAF68126C217B41848433035F809E128785666362A`; subsequent read-only inspection found a 262,144-byte file with SHA256 `276e7e527e28f07adf0a41d9196665a8383d22ae3b793018e78a33acea6566ec`. The latter passed SQLite `integrity_check`, used DELETE journal mode, and contained four synthetic-example rows of 52 points each. A new byte-for-byte copy of that latter observed file is at `%LOCALAPPDATA%\PTTI\matches.db.forensic-backup-20261005-resume`, with the same 262,144-byte size and SHA256. The production file and this copy matched when checked.

The reason for the differing observations is unknown. The API endpoints queried were read-only, but the two running applications' resolved database paths could not be confirmed from the inaccessible UI, and no process-level write audit was available. Do not infer that either app caused the change. Further application interaction has been stopped to avoid adding uncertainty. The later four-row snapshot supersedes the one-row description below as the latest observed state; the historical comparison still cannot determine whether any authentic match was lost.

## Schema and related records

SQLite reports `application_id=0` and `user_version=0`; there is no migration/version table.

| Table | Rows | Schema / keys | Relationships |
|---|---:|---|---|
| `matches` | 1 | `id TEXT PRIMARY KEY, payload TEXT NOT NULL`; SQLite primary-key auto-index | No foreign keys |
| `preferences` | 1 | `id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL` | No foreign keys |

There are no separate `points`, `players`, `events`, `analysis`, or `reports` tables, and no declared foreign keys. The single `matches` payload contains the match metadata, 52 point objects, validation, and analysis as embedded JSON. The one preferences payload contains language, theme, start-page, and onboarding state. The report is generated from the match payload and has no persisted report row.

## Synthetic record

- Match ID: `58b371ff-8231-4ae0-8547-f52b967867f9`
- Title: `Training lab · synthetic demo`
- Synthetic flag: `true`
- Embedded point objects: 52
- Created/updated timestamps: absent
- Source-type field: absent
- Separate linked analysis/report/point rows: none

At the first recorded snapshot the database had one synthetic match row. At the later snapshot it had four synthetic match rows, all with 52 points. No authentic match row was present in either observed snapshot. These observations cannot establish whether other records existed before the accidental application write or explain the intervening file-state difference.

## History and overwrite evidence

The bounded search found no historical `.bak`, `.backup`, `.old`, `.sqlite`, `db-copy`, autosave, or migration backup in `%LOCALAPPDATA%\PTTI` or the product tree’s searched backup locations. The normal File History location yielded no available history files. `vssadmin list shadows` could not enumerate shadow copies because this process lacks administrator permission; shadow-copy availability is therefore **unknown**, not confirmed absent.

A prior session recorded a pre-incident database SHA256 of `9B949BE38ACD2FAE177A4DFD794600D677A77AFB5D24BD9666FA3746C72CF48F`. The current hash differs, proving the file bytes changed between those observations. No pre-incident byte copy or row-level audit is available, so this is not enough to establish whether prior match rows were overwritten or whether the database was empty before the synthetic row was saved.

## Root cause and protection

Before the isolation change, the packaged experimental `PTTI-Vision-Dev` startup did not set a database path. It imported `backend.main.app`; module-level `app=create_app()` constructed a `Repository` using the fallback `%LOCALAPPDATA%\PTTI\matches.db`. Loading the synthetic sample in that UI therefore saved into the production library. Separately, importing `backend.main` in pytest also constructed that default app as an import side effect, even though the existing API tests passed explicit `tmp_path` paths to their own apps.

The current development change removes that implicit production fallback: production desktop startup selects the production path explicitly, source/developer mode defaults to a separate `PTTI-Dev` database, pytest bootstrap uses a temporary database, and test/development paths resolving to the production database raise `PRODUCTION_DATABASE_WRITE_GUARD`. Automated regressions cover missing test configuration, changed working directory, development defaults, explicit production paths, and temporary test databases.

## Conclusion

**`STATE_UNCERTAIN_DO_NOT_MODIFY`**

The later observed snapshot and matching byte-copy are preserved. Neither can recover unknown pre-incident contents. The two whole-file states and the unavailable earlier copy add uncertainty; do not delete rows, replace, restore, migrate, or otherwise write the production database until an independently verified historical source or a user-approved recovery plan is available.
