# GOAL 12 · Cinema featured source review v0.1

This is a small, internal-only view over three existing `VideoSource` IDs. It is
not a public catalog, rights grant, complete-match validation, or media player.
The generated list is suitable for an authenticated review surface that clearly
labels external viewing as untested and keeps the official URL as a user action.

## Generate

From the repository root:

```powershell
python products/ptti-integration/scripts/build_match_library_index.py --generated-at 2026-10-15T00:00:00+00:00
python products/ptti-integration/scripts/build_cinema_curated_sources.py --generated-at 2026-10-15T15:00:00+00:00
```

Output:

`products/ptti-integration/generated/goal12-cinema-featured/featured-sources-internal-review.json`

The source allowlist and one-off observations live in
`fixtures/goal12-cinema-curation-observations.json`. The generator accepts only
`ptti.match-library-index/0.1` with `view=INTERNAL_REVIEW`, joins by exact
`source_id`, and rejects unknown/duplicate IDs or attempts to supply rights,
thumbnail, or Match-link overrides. It has no strict-public fallback.

## Reviewed entries

| Video source | Category / title claim | Current official page request | External video playback | Match link | Rights |
| --- | --- | --- | --- | --- | --- |
| `video-source:youtube:0QgbtsBWZhk` | MS final, China Smash 2025 | HTTP 200; publisher metadata matches the recorded channel metadata | NOT_TESTED; a historical embed attempt was technically blocked | UNKNOWN; event/pair record does not bind this video ID | public listing / viewing / embed / thumbnail UNKNOWN; local analysis / redistribution NOT_GRANTED |
| `video-source:youtube:KCGdLksBH7s` | WS final, ITTF Worlds 2025 | HTTP 200; publisher metadata matches recorded channel metadata | NOT_TESTED | UNKNOWN; ITTF confirms event and pair, not this video ID | same conservative status |
| `video-source:youtube:O241nV8y4Dc` | WD semifinal, WTT Singapore 2026 | HTTP 200; publisher metadata matches recorded channel metadata | NOT_TESTED | UNKNOWN; available evidence is the publisher title claim only | same conservative status |

For all three, the current page probe and one-off official YouTube oEmbed
metadata check are not a watch-session test. The recorded publisher name/URL
matched the existing snapshot; the publisher's rights-holder affiliation was
not independently verified. “FULL MATCH” remains a title claim and all three
remain `UNVERIFIED` for completeness. No thumbnail URL is emitted.

The 2025 ITTF report independently describes Sun Yingsha vs Wang Manyu as the
women's singles final, but it does not identify the YouTube video ID. That is
event corroboration, not a Match–VideoSource link. The other title/event claims
likewise stay unlinked unless an exact source-to-match reference is found.

## Release boundary

All entries are `INTERNAL_REFERENCE_ONLY`; every `public_listing` remains
`UNKNOWN`. The existing strict-public projection remains empty and must be read
from its own generated file. A reachable URL is not proof of playability or
permission to embed, display thumbnails, analyze locally, or redistribute.
Opening the official platform page must remain an explicit user action; don't
autoplay or substitute a cached player.

The selection deliberately keeps `ptti.match-library-index/0.1`, Review Targets
v0.1, and Evidence Pack v0.1 unchanged. The new additive sidecar is
`ptti.cinema-curated-sources/0.1`.
