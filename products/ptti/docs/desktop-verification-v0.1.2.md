# PTTI v0.1.2 desktop verification record

- Build: `products/ptti/dist/PTTI/PTTI.exe`, rebuilt 2026-10-05.
- Window: Chinese native title `PTTI · 个人乒乓球比赛分析`; packaged pywebview window opened at 1366×768 and was readable at the observed 150% Windows DPI scale.
- Isolated smoke database: `dist/smoke12/matches.db`; the user's `%LOCALAPPDATA%\\PTTI\\matches.db` was not used or modified.
- GUI flows: first-run onboarding and sample load; home/navigation; import metadata; invalid CSV errors; Protocol v0.3 preview followed by explicit save; dashboard tabs; point filters and source fields; evidence page; library reopen, cancel-delete and delete confirmation; settings theme; About/future placeholders; JSON and HTML Save As.
- Export files: `dist/smoke12/gui-v012.json` parsed successfully and retained synthetic metadata; `dist/smoke12/gui-v012.html` contained `lang="zh-CN"`, Chinese match content and evidence text.
- The first export attempt failed only because a cached accessibility element ID was stale. A fresh state and a fresh control reference/visible Save As dialog completed both exports.
- Printing/PDF: UI is labelled experimental; no independent PDF/physical print result is claimed.
