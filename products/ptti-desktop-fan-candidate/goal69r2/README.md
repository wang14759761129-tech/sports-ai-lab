# Direct Start isolated Host candidate

Manual startup no longer reads input idle. Available RAM below 2.5 GiB or unavailable memory status produces an explicit Yes/No advisory (default No), not unconditional rejection. This advisory level is inherited conservatism, not a measured minimum requirement. Real allocation/runtime failures remain startup errors. No processes are killed and no memory is reclaimed.

Computer automation must use --automation AND obey its external platform rules. This switch retains RAM >=2.5 GiB and real idle >=60 seconds; it is an application convention, not an authorization boundary or proof of human input. Builds retain the same resource/idle gates.

All package hashes, isolated version/port profile, loopback-only serving, busy-port refusal and disabled R4 bridge remain. Original EXE, Safe Start and shortcuts are untouched. Port 4213 and version 0.1.12-direct-ab484d6 use a fresh QA profile; no existing notes are copied.

Build once using the existing approved Python/pywebview/PyInstaller environment: python -B build_direct.py. No Web rebuild. --verify-only checks package integrity without starting GUI. A new Desktop shortcut is only appropriate after an actual build succeeds. GUI acceptance is separate.

FAST DEVELOPMENT MODE: reuse unchanged verified inputs; inspect ownership/status and only touched dependencies; targeted tests; build only changed artifacts; independent candidate delivery. Extra checks match actual data/release/interface risk. Do not push or activate releases. Do not repeat GUI or expensive scans for unchanged modules.
