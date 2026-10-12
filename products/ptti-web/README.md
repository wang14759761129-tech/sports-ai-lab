# PTTI Web MVP v0.2

An independent, browser-first PTTI pilot for finding table tennis matches, opening official source pages, and browsing a small set of source-attributed stories. It is a static Vite app; it does not call the desktop FastAPI service or access its SQLite data.

## Run locally

Requirements: Node.js 20.19+ or 22.12+ and npm.

```powershell
cd products/ptti-web
npm install
npm run dev
```

Open <http://127.0.0.1:4174>. The app binds to loopback on its own strict port. To produce the static site build, run `npm run build`; output is written to `dist/` within this product directory. No public deployment is configured.

## Language and content

- Simplified Chinese is the first-visit default. The language switch updates the current page immediately and restores the chosen language after refresh.
- Player names and official event names keep their recognizable original spelling. Interface descriptions, filters, status labels, and feedback controls use one shared dictionary in src/i18n.ts.
- Pulse is manually curated, not a live feed. Categories without a reviewed source show an empty-state explanation; no popularity ranking is claimed without evidence.
- Cinema routes are explicitly classified as an official event page, an official video page, or source information only. A route link never implies playback was tested.

## Language and content

- Simplified Chinese is the first-visit default. The language switch updates the current page immediately and restores the chosen language after refresh.
- Player names and official event names keep their recognizable original spelling. Interface descriptions, filters, status labels, and feedback controls use one shared dictionary in src/i18n.ts.
- Pulse is manually curated, not a live feed. Categories without a reviewed source show an empty-state explanation; no popularity ranking is claimed without evidence.
- Cinema routes are explicitly classified as an official event page, an official video page, or source information only. A route link never implies playback was tested.

## Pages

- **Cinema**: player search, discipline, tournament, platform and source-status filters; official source route cards; explicit playback and territory status.
- **Pulse**: a small static selection of WTT-published items with publisher attribution and original links. There is no live feed.
- **Stars**: source-backed public profiles with event and story links. Individual social accounts are shown only with a clear verification label.
- **Feedback**: a bilingual exit survey stored in the current browser only, with issue categories and JSON export. It asks for no name or email and sends nothing to a server.

## Source and status rules

`public/data/cinema.json` is the source record for Cinema. A direct official video URL is stored in `videoOriginalUrl`; `platformUrl` may instead be an official event page containing the media listing. A missing route results in a no-watch-link message and has no outbound watch button. `playbackTested` records an actual playback check and remains `false` for this pilot. `embedAllowed: null` means embedding permission is unknown, so the app does not embed any video.

All dates in `lastVerifiedAt` and `verifiedAt` refer to the source review performed for this sample on 2026-10-12. They do not mean the video played successfully or will remain available. Sources and rights status are documented in [docs/SOURCES_AND_RIGHTS.md](docs/SOURCES_AND_RIGHTS.md).

## Boundaries

- Static, manually reviewed sample records only; no automatic feed updates.
- Original content stays on publisher platforms. No video is downloaded, proxied, embedded or re-hosted.
- The app has no backend, public API, analytics, telemetry, login, upload or desktop database connection.
- Feedback remains in local browser storage unless the user exports it.
- See [docs/USER_TEST_PLAN.md](docs/USER_TEST_PLAN.md) for the real-user tasks and blank observation template.
