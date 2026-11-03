# PTTI GOAL22 Main handoff — `ptti.fan-inspiration/0.1`

Read-only additive package for San. It does not replace the GOAL15 strict match library or GOAL17.1 video-source delta.

## Consumer files

- Public package: `products/ptti-integration/generated/goal22-main-inspiration-v0.1/public/fan-inspiration-v0.1.json`
- Public package SHA-256 (fixed `generated_at` shown below): `702bc12850676ae9eeda39b533ade9cc5f2da0fe8710aa8ebc82f0c2b803c5c9`
- Schema: `products/ptti-integration/contracts/fan-inspiration-v0.1.schema.json`
- TypeScript contract: `products/ptti-integration/contracts/fan-inspiration-v0.1.d.ts`
- Internal review evidence is kept separately at `products/ptti-integration/generated/goal22-main-inspiration-v0.1/internal/review-register.json`; do not copy it into a public build.

## Consumption rules

1. Treat `clips` as event/season highlights for the Clips view. The 10 inherited event-highlight records and the one new WTT season roundup are not match-specific unless `match_id` explicitly exists; the current event/season highlights remain unbound.
2. Treat `match_watch_sources` as video-page records with match-level associations only where their `match_id` and `verification.match_link` say so. `FULL_MATCH_TITLE_CLAIM` is a source-title claim; `full_match_completeness` remains `UNVERIFIED`.
3. `published_at: null` means no exact publication date was in the source evidence. Do not infer one from a tournament date.
4. `rights.external_viewing` permits a platform link within the recorded scope only. `embed`, thumbnails, downloads, local analysis, and redistribution are not granted.
5. `verification.external_system_browser_open`, `video_started`, and `desktop_native_playback` are `NOT_TESTED`; `complete_watch` is `UNVERIFIED`. Do not render “playing” or “full replay verified” from these fields.
6. `international_reactions` contains one French newsroom article summary. Its scope is one report, not a poll or a claim about international fans generally. Only the concise PTTI summary and source link are included.
7. `gear_dossiers` are match-specific and deliberately show `UNKNOWN` for jersey, shoes, blade, and rubber. Athlete/product-level listings are not proof of use in a particular match.
8. Follow `watch_routes` as an explicit fallback model. Never silently choose a route or convert an official link into embed permission. Event highlights cannot substitute for a full-match replay.

## Rebuild and validate

From the repository root, run:

```powershell
python products/ptti-integration/scripts/build_fan_inspiration_v0_1.py --generated-at 2026-10-20T00:00:00Z
python products/ptti-integration/tests/test_goal22_main_inspiration_v0_1.py
```

The builder pins the GOAL15 base and GOAL17.1 delta file hashes. A changed source package stops generation and requires review. Output is a strict, allowlisted JSON view; internal review notes and source paths are not copied into it.

## Current snapshot facts

- Existing strict baseline remains 7 matches, 17 official video sources, and 8 athletes (5 matches/15 sources in GOAL15 plus 2 matches/2 sources in GOAL17.1).
- This additive package contains 18 official video records: 10 inherited event-highlight title claims, 1 new WTT season-roundup link, and 7 match-watch records. The new WTT item is metadata/link-only; its official page was not opened in the system browser and playback was not tested.
- It contains one international newsroom report and gear dossiers for three existing matches. No clip actually started playing in this work; complete-watch evidence remains zero.
