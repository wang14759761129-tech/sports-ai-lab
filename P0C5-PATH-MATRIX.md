# WIP / NOT SAFE TO LAUNCH — P0-C5 path coverage

All paths below are relative to explicit OS-temp PTTI-QA-* root.

| Surface | Actual code entry | QA destination / refusal | Evidence / remaining gap |
|---|---|---|---|
| SQLite | database.ProductionDatabaseGuard.validate; Repository.connect | data/matches.db; both DB variables must agree; no fallback | Real SQLite + PRAGMA PASS; full Native writes NOT_TESTED |
| LOCALAPPDATA | qa_isolation.configure | local; mandatory input | Config test PASS; physical runtime NOT_TESTED |
| WebView2 | qa_isolation.webview_options; desktop.main | webview; explicit storage_path/private_mode | Mapping PASS; physical writes NOT_TESTED |
| Media reads/relink/hash/stream | video_evidence register/availability/relink/digest_file/media | media; hash manifest, ancestry/reparse checks | Synthetic MP4 ASGI PASS; filesystem TOCTOU remains |
| Folder scans/imports | match_library.LocalMediaIndexer.start; evidence package import; API guard | Refused in QA | Route denial PASS; direct research paths disabled |
| Thumbnails | match_library.thumbnail | cache/thumbnails; checked output files | Path code inspected; actual ffmpeg thumbnail writes NOT_TESTED |
| Logs | desktop exception handler; database_banner | Invalid QA prints only; database banner beside QA DB | DB path test PASS; exhaustive runtime log trace NOT_TESTED |
| Config | qa_isolation.configure | config; APPDATA mapped here | Invalid directory tests PASS; all native library writes NOT_TESTED |
| Cache | configure TEMP/TMP/XDG_CACHE_HOME; thumbnail | cache | Mapping/error tests PASS; runtime cache trace NOT_TESTED |
| Downloads/exports | desktop ALLOW_DOWNLOADS; QA API allowlist | Disabled/refused | API export denial PASS; native download behavior NOT_TESTED |
| Updates | configure removes deploy root; API default deny | Disabled, no deploy target | Env test PASS; runtime NOT_TESTED |
| Vision | main.create_app excludes vision/preview routers; configure | vision-disabled; external value rejected | Config/API denial PASS; runtime import/write trace NOT_TESTED |

Symlink tests default OFF. Authorized disposable Windows executor must explicitly
set PTTI_AUTHORIZED_SYMLINK_TEST=1 and run the three test_symlink_* methods in
products/ptti/test_qa_physical.py. No permission changes are performed.

Blank probe: scripts/blank_webview_probe.py is a prepared entry only. It requires
explicit authorization, a new temp root, 3 RAM samples >=3 GiB, and monitors >=2.5
GiB for at most 30 seconds. No PTTI backend/database/media imports. Process command
lines and root file inventory are recorded. An approved OS-level write trace is
still needed to identify ALL writes and fail any formal-directory write; inventory
alone is not physical-isolation proof. PROBE=BLOCKED pending that environment.
No probe executed. No R4 GUI, runtime isolation or candidate approval is claimed.
