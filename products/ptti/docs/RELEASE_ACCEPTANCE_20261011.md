# Desktop release acceptance audit

The existing fixed launcher follows `current-preview.json`, validates the full
package, and falls back to `previous-preview.json` on integrity failure. Updating
an accepted pointer does not require another desktop shortcut. This remains a
Preview channel; an active Preview is not a formally released Stable build.

## Change

`dev_sync.py` previously activated after an isolated health check without native
playback acceptance. It now requires `PTTI_RELEASE_ACCEPTANCE` to name a local
review record before activation. The record must have schema 1, the exact package
commit and file-hash map, a reviewer and timestamp, and PASS for automated_tests,
native_cinema, native_vision, resource_guard and rollback_integrity. Activation
also rechecks 2.5 GiB available physical RAM. Missing evidence leaves the existing
pointer untouched. A review record is a local audit assertion, not a signed
remote publisher credential. Do not populate it from simulated test results.

The underlying package installer remains a low-level local primitive; callers
must enforce release acceptance. This change does not implement or claim a
remote Stable installer, launch-crash recovery, or native GUI verification.
Existing integrity fallback is distinct from detecting a crash after launch.

Archived packages already contain manifest.json. Manifest generation now excludes
that external file, consistently with verification, so re-installing a verified
archive no longer fails due to a self-referential manifest entry. A regression
test covers archive verification and installation using a simulated package.

## Results on this revision

- Desktop update and catalog tests: 28 passed, one existing deprecation warning.
- Python compilation and diff check passed.
- The real launcher passed VerifyOnly, resolving the existing active 5cc7538
  package. No actual application launch was performed.
- Available physical RAM measured 1.67 GiB; full regression, build and native QA
  were not run. Existing 9abf647 CI candidate remains untouched.
- Remote Release discovery remains non-installing. Authenticated release
  signing, package verification and installation consent are not implemented;
  arbitrary Git commits are never treated as installable releases.

## Catalog verification

Two explicit WTT URLs were checked through the existing public oEmbed method:

- https://www.youtube.com/watch?v=nXwsn2IN9tI — MD final, Foz do Iguacu 2025;
  already present, not a new unique entry.
- https://www.youtube.com/watch?v=ZmwzPe0hRII — WD final, Lagos 2025;
  one new unique reference entry.

Both returned publisher World Table Tennis, author URL @wttglobal. Only title
metadata and official reference links are recorded. Playback, regional access,
embedding rights and completeness are unverified; analysis remains denied.
The WD title does not claim FULL MATCH and content type remains UNKNOWN.

The existing catalog importer was executed against a dedicated OS-temporary
TEST database. Repeated import inserted zero entries and reported two
duplicates. The library API combines nine existing imported entries with ten
bundled sources; after deduplication and the one new WD entry it returns 19:
MS 7, WS 3, MD 4, WD 4, XD 1. This is the isolated validation library count,
not a claim that the active desktop database was updated. The old localhost
service was unavailable; no user database or favorites were overwritten.

Tokyo TV's official index and WD directory were reachable, but their retrieved
text did not expose individual match entries. No unrestricted indexing or
playback permission was inferred from those pages. No bulk scraping, video
download, embedding test or thumbnail redistribution was performed.

## Continuation

Keep the same shortcut and existing activation pointer. Complete the preserved
16-item native QA only when resources allow. Use actual review evidence before
local activation; preserve rollback. Remote automatic Stable delivery requires
a separately established trusted signing/consent policy. Import the reviewed
catalog through the existing isolated app endpoint when that service is running.
