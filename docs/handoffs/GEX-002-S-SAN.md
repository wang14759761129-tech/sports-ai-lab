# GEX-002-S / SAN DEX — Grand Cinema isolated integration candidate

Status: PROPOSED. Founder visual review and Main/Playback interface agreement precede product integration. Do not merge or deploy.

## Goal and value
Apply cinematic presentation while retaining source trust, existing fan navigation and personal data. Founder should complete the browse → watch → mark → collect → return journey without losing context.

## Verified starting evidence
WORK observed `C:\PTTI-Worktrees\web-goal14-fan-mvp` HEAD `4d24c130cbe9dbdd66390423605c29f26a7ee792`. Read React/Vite package and FanCatalogPage entry, fan-navigation.mjs, fan-local-data.mjs. Existing pages: cinema/stars/clips/highlights/rivalries/corner. local-data/2 has strict keys and SELF-only athlete journal. Existing fan-gold.css, FanArtwork, FanSearchOverlay, media/source gates exist. Current runtime and working-tree cleanliness UNVERIFIED.

## Allowed / forbidden
Allowed: new isolated integration branch/worktree; scoped presentation components, candidate tokens, adapter bindings and tests. First inspect AGENTS, status and build scripts; never overwrite uncommitted changes. Forbidden: stable branch merge, shared 4174/4183 replacement, raw prototype storage copied over existing records, removal of Stars/Pulse/fan routes, rights-check relaxation, official thumbnails without permission, Host changes, release publication.

## Inputs / dependencies
GEX-001 design docs and src are reference implementation, not drop-in production code. Main GEX-002-M identity contract; Playback GEX-002-P adapter; Founder feedback on visual feel. Existing PREMIUM_DESIGN_INTEGRATION.md remains baseline.

## Steps
1. Record actual root/HEAD/status, inspect existing equivalent components and token names; document reuse vs new code.
2. Map proposed colors to a scoped theme; preserve focus, reduced motion, Chinese-first reading, source badges and current return snapshots.
3. Implement lobby and theater with legal source options. Details panel outside video. If no media qualifies, show an honest official-page route or empty state.
4. Add moments through an agreed separate namespace/contract; do not append unknown fields to fan-local-data/2. Provide export and tested recovery before migration proposals.
5. Keep Arena labelled DEMO and separate from actual data. No probability/model claims. Keep Pro Lab proposed until its implementation is accepted.
6. Preserve all current package build gates; do not remove a check to get green. Use dedicated free port determined at runtime, not occupied shared ports.

## Tests / success evidence
Actual build/type checks and existing source-rights/public-isolation gates; browser journey, back/forward and search; notes/collection persistence and duplicates; source failure; storage failure; local media teardown. Inspect 1440/768/390/320 px, keyboard focus, no overflow and reduced motion. Include truthful screenshots if available. No UI or native playback PASS without running it.

## Rollback
Candidate theme/route changes behind an isolated entry or feature flag; preserve prior store; no stable migrations executed. Revert own candidate commit only.

## Final receipt
PTTI WORK REPORT: root/branch/full HEAD/status, reuse mapping, files, build output/hash, runtime URL/port and process ownership, exact test evidence, screenshots if obtained, pending gates, storage compatibility, rollback and Host handoff. Label PROTOTYPE/CANDIDATE separately from deployed.
