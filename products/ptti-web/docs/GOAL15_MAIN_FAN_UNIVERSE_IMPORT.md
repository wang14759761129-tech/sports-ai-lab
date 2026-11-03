# GOAL15 Main Fan Universe import

## Pinned input

- Main branch: `codex/ptti-goal14-content-intelligence`
- Main commit: `eb0a52af32eaaf26dfd39cf1ce5f321e24a1adac`
- Projection release: `GOAL15_MAIN_PUBLIC_PROJECTION/0.2`
- Contract: `ptti.match-library-index/0.1`, view `STRICT_PUBLIC`
- Input: `public/data/match-library-strict-public.json`
- Input SHA-256: `1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930`
- Schema SHA-256: `4d10c5cee7b2ac5c8bb533c71887ddf88431976ebc2d2b055b8e8b6e0ca05415`
- Exact source pin: `scripts/contracts/goal15-fan-universe-source-pin.json`

## Public-content projection

This v0.2 projection supersedes the prior v0.1 artifact SHA `ca714727ebe43fd091b7e52a2c8e31225c6deba65fde30765e9da6f360c12ee2`; the data contract remains `ptti.match-library-index/0.1`. Its `source_manifest` is empty, so internal filesystem paths are not part of the public asset. Public quality counters describe this strict-public projection only.

The Web candidate consumes only the supplied strict-public artifact. The UI is driven from its stable IDs and exact edges:

- 5 matches, 15 official-platform source records, 8 admitted athlete records.
- 5 exact match-to-video-source links.
- 10 `HIGHLIGHTS` records are event-level and unlinked to an individual match or athlete.
- 3 `FULL_MATCH`, 2 `UNKNOWN`, and 0 `CLIP` content claims.
- 0 recorded playback passes; embed, thumbnail, local-analysis and redistribution permissions are not granted or remain unknown.

Full-match and highlight claims describe source metadata only. The UI opens eligible official platform pages in a user-initiated external tab; it does not embed or mirror them. Shorts/Clips remains filtered to explicit `CLIP` claims, so it is empty for this input.

## Build and isolation

Vite checks the supplied bytes, schema hash, strict-public view, protocol version, and pinned counts before serving or building. The older GOAL14 admission fixture is retained outside `public/` so the old pin check remains stable. Production-build isolation checks confirm the new catalog is strict-public, the separate GOAL14 strict-public projection remains empty, and internal review/candidate records are not copied into `dist/`.

The supplied strict-public JSON is kept byte-identical to Main's pinned delivery. Public quality counters remain source metadata and do not imply playback success or additional rights.

## Current verification boundary

Node catalog, navigation, watch-routing, GOAL14 content compatibility, TypeScript, Vite build, and static public-isolation checks are run separately and reported with their actual results. An HTTP response from the local candidate is not browser-interaction evidence. Browser screenshots and responsive interaction remain `NOT_TESTED` unless a current guarded browser run is completed.
