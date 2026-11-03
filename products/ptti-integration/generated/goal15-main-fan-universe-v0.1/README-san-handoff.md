# GOAL15 Main → San handoff

Snapshot reviewed: 2026-10-18. This is an additive, strict-public content snapshot; it does not replace the existing Goal14 package or any app/database data.

## Files and generation

- San-consumable package: `match-library-strict-public.json`
- Non-public review ledger: `candidate-review-internal.json`
- Admissions fixture: `products/ptti-integration/fixtures/goal15-main-fan-universe-v0.1/admissions.json`
- Builder: `products/ptti-integration/scripts/build_goal15_main_fan_universe.py`

From the repository root, regenerate reproducibly with:

```powershell
python products/ptti-integration/scripts/build_goal15_main_fan_universe.py --generated-at 2026-10-18T10:56:58Z
python -m unittest products.ptti-integration.tests.test_goal15_main_fan_universe products.ptti-integration.tests.test_goal14_main_content_expansion products.ptti-integration.tests.test_goal14_main_public_admission -v
```

The package keeps `ptti.match-library-index/0.1` and `view=STRICT_PUBLIC`. Existing `matches`, `video_sources`, `stars`, `evidence_sources`, `analysis_compatibility`, and rights fields are unchanged in meaning. New optional display fields include `display_title_zh`, `event_display_zh`, `round_zh`, `event_id`, and `published_at`; consumers may ignore them. `source_manifest` includes upstream manifest entries plus exact SHA-256 values for the Goal14 base package, GOAL15 admissions fixture, and builder.

## Newly admitted exact chains

| Match ID | Match / result | Video source ID | Official link |
|---|---|---|---|
| `pro:wtt:china-smash-2025:sun-yingsha-wang-manyu-ws-final` | China Smash 2025 WS Final; Sun Yingsha 2–4 Wang Manyu | `video-source:youtube:ttUevnAZSEY` | https://www.youtube.com/watch?v=ttUevnAZSEY |
| `pro:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final` | Singapore Smash 2026 MS Final; Wang Chuqin 4–0 Lin Yun-Ju | `video-source:youtube:cDccQqVlMnc` | https://www.youtube.com/watch?v=cDccQqVlMnc |

The match ↔ source edges are `HUMAN_VERIFIED` using the WTT result/report and exact video title/publisher metadata. These are PTTI match IDs; `provider_match_id` remains null. The Singapore provider event ID is intentionally null. Dates not independently confirmed remain null.

The exact title says `FULL MATCH`, so `content_type_claim=FULL_MATCH`; this is a publisher title claim only. `completeness_status=UNVERIFIED`, current external playback, territory, login/paywall, embedding, desktop playback, and Vision remain untested/unknown. The safe user action is `OPEN_OFFICIAL_PLATFORM_URL`; do not iframe/embed, render thumbnails, download, analyze, or redistribute based on this package.

## Current public counts

- 5 match records, 15 distinct official video-source records, 8 minimal star records.
- 5 exact match ↔ source edges. Ten inherited WTT videos remain event-level highlights with no match or player edge.
- Official title/source claims: 3 `FULL_MATCH`, 10 `HIGHLIGHTS`, 2 `UNKNOWN`. `SHORTS=0` admitted. No source has verified-complete status.
- External video playback passes: 0; desktop native playback passes: 0; Vision analysis passes: 0; embedding grants: 0; thumbnail grants: 0.
- 35 internal source records remain internal and are not included as a public fallback.

The 8 athlete IDs are the existing Wang Chuqin, Felix Lebrun, and Tomokazu Harimoto records plus official-profile-backed Sun Yingsha (`athlete:131163`), Wang Manyu (`athlete:121411`), Lin Shidong (`athlete:137237`), Liang Jingkun (`athlete:119588`), and Kuai Man (`athlete:135049`). Chinese display labels are user-provided UI labels and are never join keys. No portrait is included. Official personal social accounts, gear models, endorsement/sponsorship claims, interviews, and coach observations remain unverified or uncollected.

## Why other items remain excluded

- The existing internal Singapore 2026 women's-doubles candidate `O241nV8y4Dc` was not promoted: this pass did not complete a matching official result/report plus exact source-evidence package.
- No exact official WTT Shorts ID was verified in this pass; no placeholder link is emitted.
- WTT event news and result URLs can be linked as official news, but do not grant media reuse. YouTube's sharing help documents copying an official video link; it does not grant PTTI embedding, thumbnail, download, analysis, or redistribution rights.
- No YouTube Data API credentials or bulk API aggregation were used. Only a small, preselected set of exact public video IDs was cross-checked; no thumbnail or media bytes were retrieved. Any future Data API integration must separately review the then-current API terms, policy, retention, and rights-holder scope before collecting or storing metadata.
- Liang Jingkun's official ITTF result search identifies `#119588`; direct profile fetch returned HTTP 403 in this review session, so the ID is sourced but direct profile-page availability is unverified.

## Evidence links

- WTT China Smash 2025 event/result: https://www.worldtabletennis.com/eventInfo?eventId=3098
- WTT Singapore Smash 2026 men's final report: https://www.worldtabletennis.com/description?artId=5957
- ITTF profile IDs: https://results.ittf.link/index.php/player-profile/details/59/29264 (Sun), `.../19634` (Wang Manyu), `.../35272` (Lin Shidong), `.../18077` (Liang Jingkun; retrieval returned 403), `.../33096` (Kuai Man).
- YouTube link-sharing help: https://support.google.com/youtube/answer/57741?hl=en

All upstream metadata was reviewed only for this selected set; this was not a bulk API aggregation, video download, thumbnail fetch, or playback test.
