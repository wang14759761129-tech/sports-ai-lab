# P0-C2 isolated QA profile

Baseline: 5cc753886b112305736fcc14ea77b37662726c9f. No Playback patch included.

The dedicated qa_desktop entry forces QA mode. Explicit existing OS-temp
PTTI-QA-* root and all seven path variables are mandatory. Native profile storage
uses pywebview 6.2.1 storage_path with private_mode=False (EdgeChromium assigns
UserDataFolder and IsInPrivateModeEnabled). Actual native disk activity is NOT_TESTED.

Allowed: manifest-hash-verified synthetic file registration, relink, media streaming,
local library, favorites, evidence/points/collections. Database guard runs on every
repository connection. File identity is rechecked before streaming and hashing.
Denied: directory crawling, external evidence packages, Vision/preview routers,
non-allowlisted API routes, downloads/exports, native external links and third-party
network resources (CSP). Denial is explicit; these are QA restrictions, not new
production functionality. Original frontend and CSS unchanged.

Path checks reject relative/UNC/device paths, different drives, ancestor reparse
points, symlinks, junctions and hard-linked files. Physical junction and SQLite tests
use temporary fixtures/canaries only; no formal user directory is touched. This is
application isolation, not an OS security sandbox against another process changing
paths after validation. Hash-to-use races cannot be completely eliminated here.

Build: use existing build_dual_source_v061_preview.py with PTTI_ISOLATED_BUILD=1,
PTTI_PREVIEW_PROFILE=video-first-r4 and an independent PTTI_PREVIEW_BUILD_ROOT.
Existing high-load guard remains. No launcher/desktop shortcut is replaced.
Rollback: keep using unchanged installed R4; this branch and output are independent.
