# Web MVP migration record

Migration date: 2026-10-12

## Source

- Repository: `wang14759761129-tech/PTTI.git` (local checkout; remote access was unavailable during the migration).
- Branch: `codex/ptti-web-mvp-v0-1`.
- Source commit: `e5cca2cfd9de0efdf83680739d4bd5f39e506d3a` (`feat: add independent PTTI web MVP v0.1`).
- Parent: `4585439ea11dc8250cc15031a991aa71084fea3f`.
- The source commit changes only `products/ptti-web/**` (17 files). The source worktree and commit remain intact.

## Destination

- Repository: `wang14759761129-tech/sports-ai-lab`.
- Worktree: `C:\PTTI-Worktrees\web-mvp-v0-1`.
- Branch: `codex/ptti-web-mvp-v0-1`.
- Base: `2c87a6433437f39bf85a9439cccf99709cce887e`.
- Migration commit: `8bd041271fd05f100c6ffe1b702136044a6b8490`.
- Source-managed files were copied with matching SHA-256 values. Generated `node_modules`, `dist`, and `tsconfig.tsbuildinfo` were excluded; a local `.gitignore` keeps them out of future commits.

The source QA record is retained in `docs/QA.md`. Its checks describe the source-session run; current destination-worktree verification is recorded separately below.

## Destination verification

- `npm ci --offline --no-audit --no-fund` — passed.
- `npm run build` — passed (TypeScript and Vite production build).
- `npm run check:sources` — passed, 79 checks across four match records.
- Vite served this worktree on `http://127.0.0.1:4174/`; the home page, application module, and curated JSON returned HTTP 200.
- Browser navigation rendered Cinema, Pulse, Stars, search empty state, and the local-only feedback flow. The 390×844 mobile capture showed no horizontal overflow. Desktop and mobile captures were displayed during the verification session; they are not exported as files.
- Cinema's official WTT event link opened a new tab at its configured `worldtabletennis.com/eventInfo` URL. The official page contained the WTT Finals Doha 2023 listing and the named players. No video URL exists for the sample, and `playbackTested` remains `false`.

The public sample stays separate from the desktop app and does not access its database, player, Vision API, or Launcher.

## Sprint 0.2 continuation

- Confirmed the destination is the sports-ai-lab remote and the requested codex/ptti-web-mvp-v0-1 branch at HEAD d3d1c50aeab2693a96b9731892c8812e9605c3f8 before changes.
- Continued only in C:\PTTI-Worktrees\web-mvp-v0-1; no repository migration, reset, or change to another development worktree was performed.
- The independent Web app now starts on strict loopback port 4174 and does not import desktop, playback, Vision, backend, or Launcher modules.
- Sprint 0.2 verification is recorded in docs/QA.md.
