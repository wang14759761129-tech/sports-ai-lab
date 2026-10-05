# PTTI database forensic report — 2026-10-05

## Scope and handling

The production database was not opened for writing, migrated, cleaned, or restored during this investigation. Inspection used SQLite read-only mode and `PRAGMA query_only=ON`. The present file was copied byte-for-byte after confirming no `matches.db-wal` or `matches.db-shm` existed and SQLite reported DELETE journal mode. Source size, mtime, and SHA256 were checked before and after the copy; the source hash remained unchanged.

## Current file and backup

| Item | Value |
|---|---|
| Original path | `%LOCALAPPDATA%\PTTI\matches.db` |
| Size | 40,960 bytes |
| Modified | 2026-10-05 18:16:08.7149139 +08:00 |
| Current SHA256 | `710FE918632896B02B6B0EFAF68126C217B41848433035F809E128785666362A` |
| Byte-copy path | `%LOCALAPPDATA%\PTTI\matches.db.forensic-backup-20261005-185959` |
| Byte-copy SHA256 | `710FE918632896B02B6B0EFAF68126C217B41848433035F809E128785666362A` |
| Copy verification | Source hash unchanged; backup hash equals source hash |
| SQLite integrity check | `ok` |
| Journal mode | `delete`; no WAL or SHM files present |

The byte-copy is a safety copy of the **current post-incident state**. It is not a pre-incident recovery source.

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

The current database has one match row, which is this synthetic demonstration. No other match records are present now. The current state cannot establish whether other records existed before the accidental application write.

## History and overwrite evidence

The bounded search found no historical `.bak`, `.backup`, `.old`, `.sqlite`, `db-copy`, autosave, or migration backup in `%LOCALAPPDATA%\PTTI` or the product tree’s searched backup locations. The normal File History location yielded no available history files. `vssadmin list shadows` could not enumerate shadow copies because this process lacks administrator permission; shadow-copy availability is therefore **unknown**, not confirmed absent.

A prior session recorded a pre-incident database SHA256 of `9B949BE38ACD2FAE177A4DFD794600D677A77AFB5D24BD9666FA3746C72CF48F`. The current hash differs, proving the file bytes changed between those observations. No pre-incident byte copy or row-level audit is available, so this is not enough to establish whether prior match rows were overwritten or whether the database was empty before the synthetic row was saved.

## Root cause and protection

Before the isolation change, the packaged experimental `PTTI-Vision-Dev` startup did not set a database path. It imported `backend.main.app`; module-level `app=create_app()` constructed a `Repository` using the fallback `%LOCALAPPDATA%\PTTI\matches.db`. Loading the synthetic sample in that UI therefore saved into the production library. Separately, importing `backend.main` in pytest also constructed that default app as an import side effect, even though the existing API tests passed explicit `tmp_path` paths to their own apps.

The current development change removes that implicit production fallback: production desktop startup selects the production path explicitly, source/developer mode defaults to a separate `PTTI-Dev` database, pytest bootstrap uses a temporary database, and test/development paths resolving to the production database raise `PRODUCTION_DATABASE_WRITE_GUARD`. Automated regressions cover missing test configuration, changed working directory, development defaults, explicit production paths, and temporary test databases.

## Conclusion

**`STATE_UNCERTAIN_DO_NOT_MODIFY`**

The current synthetic record is preserved. The present byte-copy is verified, but it cannot recover unknown pre-incident contents. Do not delete the row or replace the production database until an independently verified historical source or a user-approved recovery plan is available.
