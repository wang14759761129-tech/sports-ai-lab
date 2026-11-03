# P0-C3 gate result

HEAD: 5cc753886b112305736fcc14ea77b37662726c9f (uncommitted changes retained).
17 tests executed: 14 PASS, 0 FAIL, 3 SKIP_PRIVILEGE.
Physical symlinks: outside target, missing target, symlink parent all returned
Windows 1314 at fixture creation. No elevation or security setting change attempted.
No separately authorized disposable Windows executor was established this run.

Evidence boundaries:
- media: generated synthetic MP4 registered through real ASGI; returned bytes hash
  matched; nonapproved paths and changed content rejected.
- database: actual temporary SQLite write/read and PRAGMA path checked.
- junction/hardlink: actual filesystem fixtures rejected; temporary canary unchanged.
- LOCALAPPDATA/cache/config/log/WebView: configuration containment checks passed;
  these are path-configuration evidence, not complete physical runtime write traces.
- Vision: QA router excluded and nonallowlisted requests refused through real ASGI.
- WebView2 actual physical storage: NOT_TESTED.
- Full application/native child-process write audit: NOT_TESTED.

No candidate, commit, GUI, push or deployment. Mandatory physical symlink gate
remains incomplete, so packaging and GUI were not attempted. No production data
or formal launcher was used. tests.log contains current execution evidence.
