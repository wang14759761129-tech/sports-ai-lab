# GOAL 11-M · Match Library Index v0.1

## What this index contains

The ptti.match-library-index/0.1 adapter reads only the committed professional data snapshots under products/ptti/data/professional/. It does not read SQLite, private video files, Web/Playback worktrees, or runtime user data, and it does not download media.

The source snapshots contain 36 video-source rows: 9 in official_video_sources.json, 9 in catalog_expansion_r1.json, 16 in catalog_expansion_r51_closeout.json, and 2 in catalog_expansion_20261011.json. Deduplication by (platform, video_id) removes one repeated nXwsn2IN9tI row. The result is **35 source records**, not 35 independently verified canonical matches.

The index separately contains the 6 registered professional match records, 16 athlete profiles, and 26 source-provenance records from registry.json. The 35 video sources have no explicit match_id in the source snapshots. They remain canonical_match_id: null / match_link_status: UNKNOWN; the six registered matches have no video source IDs. Do not join by event title, round, player name, or similar-looking score.

## Current inventory snapshot

The generated internal index reports 34 YouTube and 1 Bilibili source. Video-source category counts are MS 12, WS 9, MD 6, WD 6, XD 2. All retain reference-only rights and none is public-listing eligible.

Latest recorded playback-status values across the 35 deduplicated sources are:

| Recorded status | Count | Meaning |
| --- | ---: | --- |
| NOT_TESTED | 23 | No playback result in the selected latest source snapshot |
| RESTRICTED | 3 | Restriction recorded; not a statement about all regions or current access |
| EMBED_BLOCKED | 2 | Historical platform embed attempt was blocked |
| EMBED_NOT_TESTED | 6 | Embed was not tested |
| SOURCE_LINK_ONLY | 1 | External source link retained |

Six records preserve historical external-platform observations in a browser session, including one Bilibili view that showed moving match video with a login/trial limitation and five YouTube views with session-specific limitations. Those observations are timestamped historical evidence only: they do not establish present availability, complete-match viewing, embed permission, Windows native playback, Vision analysis, or media rights. Current-session playback eligibility remains NOT_EVALUATED_CURRENT_SESSION; Desktop Native and Vision are NOT_TESTED for all 35.

The snapshots contain 8 thumbnail URLs, but none has scoped display permission. The adapter omits the URLs and instructs consumers to use the PTTI placeholder. No entry is marked as completeness-verified; publisher title claims remain claims.

registry.json contains 6 source-backed match records and 16 athlete profiles, of which 14 have an official profile URL recorded. The match category remains UNKNOWN because the registry has no explicit discipline field; the adapter does not parse it from the round label. The Stars projection leaves equipment UNKNOWN and coach observations, interviews, sponsorships, and social feedback NOT_COLLECTED.

The strict public projection currently has **0 matches, 0 video sources, and 0 athlete profiles** because the snapshots contain no scoped, evidenced metadata-listing grant. A reference URL, public web page, platform publisher, local authorization, or hash is not such a grant.

## Generate and consume

From the repository root, run:

    python products/ptti-integration/scripts/build_match_library_index.py

Outputs:

- products/ptti-integration/generated/goal11-match-library/match-library-internal-review.json
- products/ptti-integration/generated/goal11-match-library/match-library-strict-public.json

For a reproducible output timestamp, run:

    python products/ptti-integration/scripts/build_match_library_index.py --generated-at 2026-10-15T00:00:00+00:00

San's authenticated/internal review adapter may read only the INTERNAL_REVIEW document and must preserve its review-only status. A public build must consume only STRICT_PUBLIC; it must never fall back to the internal file. The current public document is empty by design.

Useful VideoSource fields:

- source_id: stable video-source:<platform-lowercase>:<platform-video-id> identifier.
- video_id, platform, official_url, watch_entry: source key and official platform URL; watch_entry means only “open this URL”, not that it is currently viewable.
- event, event_year, match_type, round, participants_claimed: source-recorded claims; missing year/date stays null, missing category stays UNKNOWN, names are not athlete IDs.
- source_identity_status, publisher_identity_status, provenance: recorded metadata provenance, not live re-verification.
- canonical_match_id: null, match_link_status: UNKNOWN: no exact evidence-backed Match link is present.
- rights: separate public listing, external viewing, thumbnail display, embedding, local analysis, and redistribution decisions. Current unknown permissions remain UNKNOWN; local analysis and redistribution remain NOT_GRANTED for reference-only sources.
- availability: historical external-page observations are separate from current page availability, platform embed, Desktop Native, Vision, and current-session eligibility.
- thumbnail.url is always null. Even when a source snapshot has a thumbnail URL, its display permission is unknown and consumers must not fetch or render it.

## Review-target and evidence-pack boundary

The index advertises compatibility with ptti.review-targets/0.1 and ptti.review-evidence-pack/0.1; it does not copy either payload or create links. A future association requires exact match_id and source_id plus evidence. These catalog entries are currently not linked to review data. Do not convert external page observations into playback candidates or current Web session eligibility.

Source snapshot SHA-256 values in source_manifest identify the local input bytes only. They do not prove match identity, source truth, permission, video content, or playback.

## Remaining evidence needed

Before a source can enter the strict public view, add a scoped metadata-listing authorization with an issuer, evidence reference, and verification time. External-viewing terms, territory, embedding, thumbnail display, local analysis, and redistribution each require their own evidence. To link a video source to a registered Match, record an exact human-reviewed ID mapping with evidence. To mark Windows playback or Vision, provide the exact build/package/media identity and actual native test evidence.
