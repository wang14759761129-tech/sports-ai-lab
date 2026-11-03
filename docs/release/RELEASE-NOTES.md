# PTTI v0.1.0 — First Usable Release

Local-first Windows match intelligence for two table-tennis teammates. CSV → validation → saved match → charts/statistics → tactical evidence → point explorer → JSON/HTML export → reopen after restart. No OpenAI API key or developer tooling required to run the packaged app.

Download `PTTI-v0.1.0-Windows-x64.zip`, extract the whole folder, read `START-HERE.txt`, and open `PTTI/PTTI.exe`. Keep all runtime files together. Requires Windows 10/11 x64 and Edge WebView2 Runtime. Verify the archive against the accompanying SHA256 file.

Product and analytics 0.1.0. Data schema 1.0.0-new; historical v0.3 source was not found and compatibility is not claimed. The included synthetic CSV is a demo/template, not real match evidence.

Release verification: 16 automated tests passing; TypeScript/Vite production build and Windows PyInstaller directory build successful. Native application, sample dashboard, point explorer and persistence verified on the development Windows computer. Kaikai/clean-machine gate is PENDING. Download Save As dialog was observed; actual user-selected saving and printer output remain real-user test items.

Known limits: English UI with Chinese names; complete game prefixes only, no mid-game start state; no doubles identity/cross-game service/match-length enforcement or annotation consistency checks; broad metric filtering; no CSV editing, JSON reimport, video, LLM or cloud; API-only deletion; large-match performance not validated.

Only next milestone: KAIKAI TEST 01. Failures become bug reports. No v0.2 feature work before that gate passes.
