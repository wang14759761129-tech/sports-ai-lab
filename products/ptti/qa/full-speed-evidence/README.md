# Cinema / Moment Cards / Pro Lab — Founder QA

Open the existing loopback service: http://127.0.0.1:5173/ .
Use **时刻卡片** or **Pro Lab** above the original video wall. The page was
left open for the founder; services were reused, not restarted.

`RESULTS.json` records this run's browser observations, source identity,
resource decisions, build comparison and remaining limitations. Eight remote
YouTube covers decoded in Founder QA. This does not grant distribution rights;
the ordinary Web/Windows media gate still approves zero packaged photos.

The existing backend reports the old b53f4f5 QA build label. Its diagnostics
confirmed an isolated system-temp database. Vite served the updated frontend
source through hot reload. No EXE, launcher, user database or private video was
modified. Browser screenshot capture timed out; no screenshot PASS is claimed.

From `products/ptti/frontend`, relevant runnable checks:

```powershell
npm run test:moments
npm run test:moment-backup
npm run test:moment-view
npm run test:pro-lab
npm run test:pro-lab-view
npm run test:cinema-viewing
npm run test:feed
npm run test:goal99-story
npm run test:favorite-persistence
npm run test:official-theater
npm run test:youtube-thumbnail
npm run test:media-distribution
npm run build
node scripts/check-media-distribution.mjs dist --windows
node scripts/inspect-arena-reuse.mjs C:/PTTI-Worktrees/web-goal14-fan-mvp
```

SQLite regression was run separately with `PTTI_ENV=test`, explicit
system-temp `PTTI_DB` and isolated `LOCALAPPDATA`:
`.venv\Scripts\python.exe -m pytest -q tests/test_muse_favorite_http.py`.
Do not import backend modules before establishing those paths.

## Arena next slice

`arena-reuse.json` pins four existing, clean San files and their hashes. The
inventory command reads them without copying or changing San, and checks its
existing pure simulation reducer. No second Arena engine was created.

When a portable Muse/San component arrives, mount it as a secondary lazy
workspace through `WorkspaceFrame` and the existing `returnToWall` pattern.
Resolve its i18n and scoped styles; keep `onOpenJournal` disconnected. It must
accept `onBack`, and must not receive real match/source/video identities,
change media gates, write Journal, or replace the Cinema wall. The current
inventory is an integration preparation artifact, not an integrated Arena UI.
