# GOAL27 Main Match Experience Delta v0.1

This is an additive, strict-public delta for San. It contributes one exact match record and one official-platform match-highlights source without modifying the GOAL15 base catalog, GOAL17 additions, GOAL22 inspiration package, or GOAL24 report package.

## Consumer files

- `public/match-experience-delta-v0.1.json` — `ptti.main.match-experience-delta/0.1`; San-compatible `matches`, `video_sources`, and `evidence_sources` rows.
- `../../contracts/match-experience-delta-v0.1.schema.json` — closed-field JSON Schema.
- `internal/review-source.json` — source review and evidence observations. Keep outside public builds.

The delta pins GOAL15 strict-public payload SHA-256 `1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930`. Reject or regenerate the delta if that base changes.

## Record identity and evidence

- PTTI canonical match ID: `match:ittf-doha-2025:ms:wang-chuqin-wong-chun-ting`.
- `provider_match_id` is explicitly `null`; no provider match ID was found.
- Event ID `wtt-event:3108` is the WTT event identifier for ITTF World Table Tennis Championships Finals Doha 2025.
- The date and round are `null` / `UNKNOWN`. The ITTF report date is not treated as the match date.
- `athlete:121558` maps Wang Chuqin to the existing base profile. Wong Chun Ting's athlete ID is `null` because the base package has no exact mapped profile.
- The ITTF report identifies Wang's 4–0 result over Wong (12–10, 11–6, 11–5, 11–7). The official WTT YouTube title names both players and labels the item “Match Highlights”; the link is associated to the match by these two metadata sources. No in-player visual check was made.
- Source ID: `video-source:youtube:suwultS-Jcc`.

Evidence links: [ITTF Doha Day 4 report](https://www.ittf.com/2025/05/20/day-4-underway-mixed-doubles-quarterfinalists-decided-as-singles-action-intensifies/), [WTT event record](https://www.worldtabletennis.com/eventInfo?eventId=3108), and [official WTT YouTube highlights](https://www.youtube.com/watch?v=suwultS-Jcc).

## Viewing and media rights

This is an external official-platform link only. `HIGHLIGHTS` is retained as its own class; do not label it `CLIP` or `FULL_MATCH`. Page opening in a system browser, video start, complete viewing, territory and login availability remain untested/unknown. The research tool could not fetch the YouTube page (throttled) and returned 403 for the ITTF page; that tool response is not interpreted as user-browser link failure.

`thumbnail_display` is `NOT_ALLOWED`, `embedding` is `UNKNOWN`, and download, local analysis and redistribution are `NOT_GRANTED`. PTTI must not copy or transform the media. The YouTube description identifies WTT as copyright holder and states that images may not be reproduced without prior approval.

## Merge before San's existing consumer

After verifying the pinned base SHA, San can create a temporary in-memory candidate by appending the delta arrays to the base catalog's `matches`, `video_sources`, and `evidence_sources`; update only the three public count fields in `quality_summary`, then pass the candidate to `consumeFanCatalog()`. Do not change the base JSON in place. The read-only consumer smoke in this worktree confirmed that the resulting source appears in `filterFanHighlights`, stays out of `filterFanClips`, retains evidence IDs, and keeps current-session playback eligibility at `NOT_EVALUATED_CURRENT_SESSION`.

## Rebuild and validate

From the repository root:

```powershell
python products/ptti-integration/goal27_match_experience.py --build --generated-at 2026-10-22T04:57:20Z
python -m unittest products/ptti-integration/tests/test_goal27_match_experience.py -v
python products/ptti-integration/goal27_match_experience.py --validate
```

Omit `--generated-at` for a fresh UTC timestamp; the output hash will then change.
