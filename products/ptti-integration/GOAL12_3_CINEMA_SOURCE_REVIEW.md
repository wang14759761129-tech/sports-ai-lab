# GOAL 12.3 · Evidence-backed Cinema shortlist

This is an internal review of three source records selected from the current
35-source internal index. It does not publish the records and does not change
the strict-public index, match-library v0.1, Review Targets v0.1, or Evidence
Pack v0.1. The generated sidecar is `ptti.cinema-source-review/0.1`.

## Rebuild

From the repository root:

```powershell
python products/ptti-integration/scripts/build_cinema_source_review.py --generated-at 2026-10-15T15:20:00Z
python -m unittest products.ptti-integration.tests.test_goal12_3_cinema_source_review -v
```

The first command derives a fresh internal index in memory and writes
`products/ptti-integration/generated/goal12-3/cinema-source-review-internal.json`.
It refuses a non-empty strict-public projection. The input fixture is an
explicit source-ID allowlist and accepts no rights, canonical-link, thumbnail,
playback, or Vision overrides.

## Selected sources and evidence

| Source | Event / match claim | Date evidence | Page / viewing state | Rights and link state |
| --- | --- | --- | --- | --- |
| `video-source:youtube:0QgbtsBWZhk` | China Smash 2025, MS Final, Wang Chuqin–Felix Lebrun. WTT single-item oEmbed title/author matches the source snapshot. Official WTT event record and China Smash final report corroborate event, pair and result, but do not reference this YouTube ID. | Exact match date unknown; event window/date claim not asserted here. | Official YouTube watch URL responded HTTP HEAD 200 at 2026-10-15T15:12:03Z. Visual playback not tested. A historical embed attempt was blocked with technical error 150; current embed permission remains unknown. | Canonical match link UNKNOWN; an internal registered-match ID is shown only as an unlinked review candidate. Listing, external viewing, thumbnail and embedding UNKNOWN; local analysis and redistribution NOT_GRANTED. |
| `video-source:youtube:KCGdLksBH7s` | Doha 2025 World Championships, WS Final, Sun Yingsha–Wang Manyu. WTT single-item oEmbed title/author matches snapshot; ITTF final report and WTT event record corroborate the final, not this YouTube ID. | 2025-05-25 from the dated official ITTF final report; event dates 2025-05-17–25 from ITTF tournament information. Exact start time unknown. | Official YouTube watch URL HTTP HEAD 200 at 2026-10-15T15:12:06Z. Visual playback, login and territory not tested. | No canonical registered match association. All public display/embedding/viewing rights UNKNOWN; local analysis and redistribution NOT_GRANTED. |
| `video-source:youtube:O241nV8y4Dc` | Singapore Smash 2026, WD semifinal, Nagasaki/Shin–Diaconu/Xiao. WTT single-item oEmbed title/author matches snapshot; meWATCH catalog identifies this pairing and a 26 Feb 2026 listing. Official Singapore Smash page corroborates the event window, not the exact video ID. | 2026-02-26 is secondary-catalog-only; official event window 2026-02-19–2026-03-01. Exact match start time unknown. | Official YouTube watch URL HTTP HEAD 200 at 2026-10-15T15:12:09Z. Visual playback, login and territory not tested. | No canonical registered match association. All public display/embedding/viewing rights UNKNOWN; local analysis and redistribution NOT_GRANTED. |

In all three records, `FULL MATCH` is a publisher-title claim only; completeness
remains UNVERIFIED. An HTTP response and oEmbed metadata verify neither visible
match footage nor rightsholder identity, viewing permission, thumbnail use,
embedding, local analysis, or redistribution. The entries expose only an
explicit external official-platform action; no thumbnail URL or media bytes
are included. Strict-public source count remains zero.

## San consumer fields

Consume the generated JSON only in an authenticated internal-review surface.
Use `source_id` as the stable source-record key, `original_source_url` as the
explicit user-triggered external action, and `match_claim.evidence_sources`
with each claim's role as provenance. `match_link.canonical_match_id` is null
and `status` is UNKNOWN for all three. The first entry's
`unlinked_review_candidate_match_id` is a human-review lead, not a join key.
Keep `watch_status.external_visual_video_playback`, territory/login checks,
embedding permission, all rights, and completeness at their stated values.
The accompanying `.d.ts` and JSON Schema define the exact v0.1 output.

## Minimum next evidence steps

1. Locate an official match result or video catalog entry that explicitly
   names the exact platform video ID/URL; otherwise keep the source unlinked.
2. Have a reviewer open each official page and confirm visible competition
   footage, observed playback, region/login behavior, and date; store that as
   a separate dated observation rather than upgrading this HTTP-only probe.
3. Obtain scope-specific written evidence for public listing, external viewing,
   thumbnails, embedding, local analysis, and redistribution separately.
   Do not use a reachable page or publisher title as a substitute for it.

No batch scraping, media download, or rehosting was performed.
