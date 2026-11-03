# PTTI Web · Alpha Bridge v0.2

The active match catalog now consumes the producer’s **Alpha Bridge JSON**, not `MatchRecord[]` legacy fixtures.

## Two explicit modes

- **Internal review:** `npm run dev:review` → http://127.0.0.1:4174/ . Reads `.alpha-qa/bridge/web-internal-review.json` through a loopback-only dev endpoint. The page is labelled internal testing. Current imported snapshot: **4 matches / 4 sources**; rights stay UNKNOWN.
- **Strict public:** `npm run dev:public` → http://127.0.0.1:4175/ . Reads only `public/data/web-strict-public.json`. Current producer file: **0 matches**. No fallback to review or legacy data; URL parameters cannot change mode.
- **Production:** `npm run build` always uses strict public data. `vite build --mode internal-review` is refused. `npm run preview` serves the strict build on 4175; it is local, not a public deployment.

## Match Center · Fan / Pro

- Open a review match directly, for example http://127.0.0.1:4174/?match=web-match%3Adoha-2023-ms-sf-fan-lin, then switch **球迷视角 / 专业分析**. Fan details, official source state, deep link and PNG share card remain available.
- Pro shows **尚无该场逐分标注数据** for a real Bridge match. Its separate practice record loads the MainDex fixture as `ptti.match-intelligence/0.1`, with `SIMULATED_ONLY:goal07-match-001`, 24 generated rows and no real athlete, source or timeline association.
- Pro edits existing demo rows only. Statistics update from the rows, and saved/exported changes use the shared contract's `SIMULATED_INTERACTIVE_EDIT` lineage; source binding remains null. No Web-only envelope or native PTTI field transformation is used. See [GOAL_07_PRO_JSON_HANDOFF.md](docs/GOAL_07_PRO_JSON_HANDOFF.md).
- Save writes only to this browser's localStorage; export is a user-triggered JSON download. Neither path sends data to a server. A strict-public build still contains 0 real matches; the clearly labeled synthetic practice fixture is separate from the Bridge catalog.

Targeted checks:

```powershell
npm run check:pro
$env:PTTI_PLAYWRIGHT_MODULE = '<installed Playwright index.mjs absolute path>'
npm run check:pro-browser
npm run build
npm run check:preview
```

## Import the real producer files (read-only at source)

```powershell
cd C:\PTTI-Worktrees\web-mvp-v0-1\products\ptti-web
npm run bridge:import -- --source-dir C:\PTTI-Worktrees\integration-preview-sprint-0-1\products\ptti-integration
npm run dev:review
# In a separate local terminal, if both modes are needed:
npm run dev:public
```

The importer validates version/IDs/references and public permissions before copying. Review JSON and the source bridge document remain in ignored `.alpha-qa/bridge`; only the producer’s strict-public bytes enter `public/`. SHA-256 hashes are recorded locally. It never writes the producer worktree or changes rights.

Review deep link: http://127.0.0.1:4174/?match=web-match%3Adoha-2023-ms-sf-fan-lin . Stable source IDs and match IDs are consumed directly, without title-based associations. The old unnamespaced fixture IDs are not silently translated into new identities.

Details, Chinese/English preference, search, source filters, PNG cards and sharing text operate on the imported records. Source kind UNKNOWN is displayed as not reviewed, not relabelled ARTICLE or VIDEO_PAGE. Event/player IDs, publisher and association states remain unreviewed where missing. Independent external/embedded/native/audio evidence is preserved.

Legacy test records are retained only at `scripts/fixtures/cinema-legacy.json`; old sample narratives and the legacy Pulse/Stars data are not used to populate this Bridge catalog. The active navigation is matches and local feedback until authorized data for other sections is supplied.

## Targeted acceptance

```powershell
npm run build
npm run check:preview
$env:PTTI_PLAYWRIGHT_MODULE = '<installed Playwright index.mjs absolute path>'
npm run check:bridge
```

The browser check requires local 4174 review and 4175 public dev servers plus Chrome. It verifies actual Bridge bytes, joins, modes, six viewport/locale combinations, deep links/sharing and negative payload rejection; it also serves the actual production dist briefly on an ephemeral loopback port to verify public0. `check:alpha` and `check:watch-flow` point to this Bridge acceptance, replacing the prior fixture-specific browser flow.

No deployment, media download/embed, desktop API or database access is configured. Feedback stays in the browser and only creates a local JSON export. Real user participation remains zero.

[GOAL 05 connection proof and upstream gaps](docs/GOAL_05_BRIDGE_CONSUMPTION.md)
