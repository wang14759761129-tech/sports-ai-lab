# GOAL19.1 Watchability Evidence Addendum

This is an additive, read-only handoff for San. It does not replace the GOAL15 strict public match library or the GOAL17.1 official video delta, and it makes no playback, embed, thumbnail, download, analysis, or redistribution permission grants.

## Consumer files

- `watchability-evidence-v0.1.json`: versioned evidence view over all 17 official YouTube source records.
- `../../contracts/goal19-1-watchability-evidence-v0.1.schema.json`: JSON Schema for this addendum.
- Source base: `goal15-main-fan-universe-public-v0.2/match-library-strict-public.json`, SHA-256 `1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930`.
- Source delta: `goal17-1-real-content-v0.1/public/official-match-video-additions.json`, SHA-256 `6f05d1fc48fb74ffc305abe20fd9152973bd96bb009fe6a183d42c031a31198a`.

## Evidence interpretation

`publisher_identity_baseline` and `match_link_baseline` preserve the prior package's evidence; they are not fresh playback checks. `current_page_fetch` is this sprint's direct read-only fetch result. `external_system_browser_open`, `video_started`, and `complete_watch` remain distinct fields. No system browser was launched and no video was played in this sprint.

Current direct source fetches: one YouTube response surfaced the recorded Wang Chuqin vs Félix Lebrun title; four fetches were throttled by the read-only retrieval surface; twelve sources were not attempted this sprint. The WTT event pages for event IDs 3231 and 3098 returned only a page shell, so their competition facts were not independently refreshed here.

The base library has 15 sources and the GOAL17.1 delta has 2; source IDs and target URLs are each unique (17/17). Seven source records have match IDs: five retain prior `HUMAN_VERIFIED` joins and the two Doha 2026 additions remain title-metadata associations with visual match confirmation not tested. Ten Day/Qualifying/Top Points/Highlights records remain event-level and unbound to a single match. The package counts five `FULL_MATCH` title claims, ten event-highlight title claims, and two match-specific sources whose content type remains unknown. No title claim establishes complete video coverage.

All current territory restrictions remain `UNKNOWN`; login/paywall state remains unknown or untested. Embed and thumbnail permissions remain non-allowed/unknown; downloading, local analysis and redistribution remain ungranted. Use the existing official external-link route only where the source package explicitly records it.

## Rebuild and validate

From repository root:

```powershell
node products/ptti-integration/scripts/build_goal19_1_watchability_evidence.mjs --build
node products/ptti-integration/scripts/build_goal19_1_watchability_evidence.mjs --validate
node --test products/ptti-integration/tests/goal19_1_watchability_evidence.test.mjs
```

The builder locks both input SHA-256 values and rejects duplicate IDs/URLs or any attempted promotion of browser, playback, completeness, embed, thumbnail, download, analysis, or redistribution evidence.
