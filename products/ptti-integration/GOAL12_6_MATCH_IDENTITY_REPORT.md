# GOAL12.6-M · Three-match identity and rights review

Reviewed 2026-10-16 (Asia/Shanghai). Baseline: `86e3b99aa4fe0cf474cb436738138b8cc03fbaf7`.
Internal evidence only; no public feed admission, media download, or rights upgrade.

## Result per match

| Match | Match identity | Exact publisher video identity | Direct match/video binding | Date / time | Public admission |
| --- | --- | --- | --- | --- | --- |
| Wang Chuqin–Felix Lebrun, China Smash 2025 MS final | Official China Smash result report corroborates event, pair, final and 4-0 result. Existing internal ID `pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun` remains only an unlinked review candidate. No verified provider match ID. | `0QgbtsBWZhk`; fresh single-video YouTube oEmbed returns matching title and World Table Tennis / @wttglobal. | UNKNOWN: no reviewed official match-level record explicitly references this ID. Metadata is a publisher assertion, not independent visual identification. | Exact date and local start time UNKNOWN in accepted evidence. | BLOCKED under current strict-public policy. |
| Sun Yingsha–Wang Manyu, Doha Worlds 2025 WS final | Dated ITTF report corroborates final, pair and 4-3 result. No verified provider match ID or existing canonical match join. | `KCGdLksBH7s`; fresh oEmbed matches title and publisher. | UNKNOWN: official final report does not reference the exact video ID. | 2025-05-25 from official dated final report; local start time UNKNOWN. | BLOCKED under current strict-public policy. |
| Nagasaki/Shin–Diaconu/Xiao, Singapore Smash 2026 WD semifinal | Exact pair/round claim supported by publisher metadata and meWATCH catalog; official announcement confirms event window only. Full athlete identities/IDs and result remain unbound/UNKNOWN. | `O241nV8y4Dc`; fresh oEmbed matches title and publisher. | UNKNOWN: forum exact-ID mention is secondary, not an official match result or rights grant. | 2026-02-26 is SECONDARY_CATALOG_ONLY; exact start time UNKNOWN. | BLOCKED under current strict-public policy. |

## New evidence and correction

Three oEmbed responses returned HTTP 200 on 2026-10-16 03:26:06–08 UTC
(11:26 Beijing time), and each supplied embed HTML. This verifies current
single-video metadata retrieval only. It does not prove frame playback,
region/login availability, per-video embed usability, or copyright permission.
No video was played in this task. All visual/native/Vision checks remain
NOT_TESTED; all three completeness states remain UNVERIFIED. The historical
error-150 embed block for the MS source is retained, not retested.

The WTT URL `https://www.worldtabletennis.com/eventInfo?eventId=3108` currently
has an indexed result describing **China Smash 2026**, conflicting with its
previous use as a Doha 2025 citation. This is a search-index observation, not
a live rendered-page finding; dynamic content/caching may contribute. Its
underlying cause is UNKNOWN. The new projection excludes this citation from
Doha identity evidence and preserves the historical GOAL12.3 files unchanged.
An ITTF tournament number must never be assumed to share the WTT event or
match namespace. No new provider match ID is invented from an event ID.

## Fact sources

- MS result: https://china-smash.com/description?artId=5479
- MS event reference (event scope only): https://www.worldtabletennis.com/eventInfo?eventId=3098
- WS dated result: https://www.ittf.com/2025/05/25/japan-ends-64-year-mens-doubles-drought-as-wang-chuqin-becomes-the-new-world-champion-in-doha/
- ITTF event dates: https://www.ittf.com/tournament/3108/ittf-world-/page/4/
- WD official event window: https://singaporesmash.com/description?artId=5602
- WD secondary match/date listing: https://www.mewatch.sg/list/WTT-Singapore-Smash-2026-Full-Matches-762560
- WD exact video-ID mention (secondary only): https://forum.tt-news.de/showthread.php?p=3858771
- Original watch pages: https://www.youtube.com/watch?v=0QgbtsBWZhk , https://www.youtube.com/watch?v=KCGdLksBH7s , https://www.youtube.com/watch?v=O241nV8y4Dc

## Permissions, separately

YouTube's terms describe personal non-commercial viewing and the official
embeddable player subject to their conditions. They do not license independent
use of the media outside the service. Policy reference checked this round:
https://www.youtube.com/static?template=terms (document dated 2023-12-15).

The PTTI records retain public listing, external viewing, thumbnail reuse and
embedding as UNKNOWN. This means scoped evidence is missing in this project;
it is not a finding that an ordinary platform user is categorically forbidden
to watch. Download permission is UNKNOWN/no scoped license evidence; no
download is attempted. Local analysis and redistribution remain NOT_GRANTED.
No thumbnail is emitted. Link action remains an explicit official-platform
external entry for internal review. Platform policy and a returned iframe do
not automatically grant all of these distinct uses.

## Cinema compatibility and San handoff

Run from the repository root:

```powershell
python products/ptti-integration/scripts/build_goal12_6_identity_report.py
python -m unittest products.ptti-integration.tests.test_goal12_6_match_identity -v
```

Outputs under `products/ptti-integration/generated/goal12-6/`:

- `cinema-source-review-internal.json`: existing `ptti.cinema-source-review/0.1`
  shape, validated against the unchanged Schema. Source IDs/watch URLs remain
  exact; canonical Match IDs stay null. The historical HTTP_HEAD probe times
  are retained; the newly checked publisher metadata has its own current time.
- `match-identity-evidence.json`: audit report keyed by the same `source_id`,
  containing provider ID gaps, confidence categories, policy scope, supporting
  and excluded references, playback limits and next evidence needed.

San may consume the first file only on the existing internal-review surface.
Do not join `registered_match_review_candidate` to a real Match automatically.
Do not substitute this list into strict public: that projection remains zero.
Review Targets, Evidence Pack, statistics and simulated Golden inputs are not
modified or joined to these real sources.

## Minimum remaining evidence

1. Obtain official match-level result identifiers and exact match-to-video
   references; for WD also verify full athlete identities and date/result.
2. Record actual watch sessions with visual content, time advancement,
   tested region/login context; verify completeness separately.
3. Resolve each intended public/thumbnail/embed/download/analysis/redistribution
   use against its own policy or rightsholder evidence. Missing scope stays
   UNKNOWN/NOT_GRANTED; do not mirror or rehost media while collecting it.
