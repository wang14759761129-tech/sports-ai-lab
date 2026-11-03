# GOAL14 Main Content & Source Intelligence Handoff

## Delivered sidecar

Contract: `ptti.fan-content-intelligence/0.1`
Runtime type: `runtime/fan-content-intelligence-v0.1.d.ts`
Schema: `contracts/fan-content-intelligence-v0.1.schema.json`
Observation fixture: `fixtures/goal14-fan-content-observations.json`
Generator: `scripts/build_goal14_fan_content.py`
Internal review output: `generated/goal14/fan-content-internal-review.json`
Strict public output: `generated/goal14/fan-content-strict-public.json`
San-ready delivery graph: `generated/goal14/fan-content-delivery-internal-review.json`
Delivery schema: `contracts/fan-content-delivery-v0.1.schema.json`
Chinese editorial labels: `fixtures/goal14-fan-localization-v0.1.json`

Run from the repository root:

```powershell
python products/ptti-integration/scripts/build_goal14_fan_content.py
```

Omit `--generated-at` for the current UTC generation time. The generator reads only the committed professional registry, the GOAL14 observation fixture, and the existing Goal 11 internal index (the latter is SHA-recorded as upstream reference and is not merged into the GOAL14 catalog). It does not read San/Playback worktrees, user databases, private videos, thumbnails, or media bytes, and makes no network requests.

## Content inventory and source state

The internal review sample contains five WTT events, three registry-backed athlete examples, and 20 event-level highlight candidates. Ten have an exact YouTube watch URL surfaced in search metadata; ten have only an official WTT event-page related-video listing and must route to that event page. The delivery graph deduplicates these into 14 unique watch-source nodes. The platform for unresolved listings remains `UNKNOWN`. All 20 are `NOT_TESTED` for actual playback. The exact-link count is a URL-resolution count, not a playback-success count.

| Event ID | Event | Viewing route state |
| --- | --- | --- |
| `event:wtt:3094` | WTT Champions Yokohama 2025 | Official WTT event page lists related highlight titles; six candidates. Current access, region, and playback are untested. |
| `event:wtt:3083` | WTT Star Contender Doha 2025 | Official page lists 2025 qualifying, Days 2–4, and Top 10 highlights; five candidates. Its stale 2024 Day 1 entry was excluded. Dates are listed as 6–11 Jan 2025. |
| `event:wtt:3128` | Europe Smash - Sweden 2025 | Official event page lists qualifying and daily Top Points; seven candidates here. Only the qualifying item has an exact video ID. |
| `event:wtt:chongqing-champions:2025` | WTT Champions Chongqing 2025 Presented by AITO | Official article states YouTube or local-broadcaster routes; one verified-channel “Highlights Show” candidate has an exact URL. `provider_event_id` remains null because no provider event ID was verified for this article record. |
| `event:wtt:3085` | Singapore Smash 2025 | Official WTT event page lists a Top 10 Points title; its direct video URL is unresolved. |

The WTT event page itself is an official navigation route, not proof that a specific item is available in every region. A title appearing under related videos is a listing observation only. Dates remain null when the cited evidence did not expose a precise event date. Per-record `source_verified_at` / evidence `observed_at` means metadata was observed in the official-page or search-index source on 2026-10-18; it does not mean the link was opened in a user browser or the video played.

## Content and identity relationships

The three example athletes are `athlete:135977` Felix LEBRUN, `athlete:121558` WANG Chuqin, and `athlete:123980` Tomokazu HARIMOTO. Names, association, official profile URL, ITTF ID, and the registry snapshot timestamp are selected from `products/ptti/data/professional/registry.json`; rankings, birth dates, portrait URLs, biography, equipment, interviews, sponsorships, and social feedback are omitted or marked unknown/not collected. The profile snapshot was last checked on 2026-10-05; live profile access is `NOT_TESTED_CURRENT_SESSION`.

The Yokohama event-page player list supports only `LISTED_ON_EVENT_PLAYER_ROSTER`. It does not establish that a player appears in a particular highlight. Candidate-to-event relationships are scoped to either an official page's related-video listing or a title/hashtag event association. No candidate is associated with a canonical Match, a player-specific clip, scorecard, or match ID: `match_id=null`, `match_link_status=UNKNOWN`, and `quality_summary.match_video_links=0` throughout.

## Rights, playback, and public projection

Rights are separate dimensions: `public_listing`, `external_viewing`, `embedding`, and `thumbnail_display` remain `UNKNOWN`; `local_analysis`, `download`, and `redistribution` remain `NOT_GRANTED`. No thumbnails are fetched or emitted. No video is downloaded, cached, mirrored, embedded, analyzed, or packaged. Direct watch URLs are exposed only as official external destinations in the **internal review** dataset; the actual playback status remains `NOT_TESTED` and territory/login remain `UNKNOWN` / `NOT_TESTED`.

The captured WTT YouTube metadata includes a publisher copyright notice and an image-reuse approval statement for the Chongqing highlight. This is evidence against assuming image reuse rights, not a grant. YouTube's own guidance separately describes owner-controlled embedding restrictions and states that video availability or an embed feature does not grant a third party copyright rights. Therefore `generated/goal14/fan-content-strict-public.json` intentionally contains zero events, stars, candidates, evidence, and relationships. A public build must consume only this strict view and never fall back to `INTERNAL_REVIEW`.

## San consumption boundary

San may use `INTERNAL_REVIEW` only in an authenticated/internal demo. For an exact URL, render an “official platform” external-link action with a visible `NOT_TESTED` status; do not show an in-app play claim. When `video_id` and `official_video_url` are null, link to the official event page and label it “video listing on official event page”; do not invent a YouTube URL. Do not use event-roster membership as a star-to-video relation. Only a future authorized, evidence-backed `STRICT_PUBLIC` record can enter public Cinema/Stars/Clips; this generator emits none.

San-facing stable fields:

- `events[].event_id`, `provider_event_id`, `name`, `event_year`, `official_event_page_url`, `official_viewing_route`, `rights`, and `public_status`.
- `stars[].athlete_id`, names, `association`, `ittf_id`, `official_profile_url`, `profile_snapshot_verified_at`, and `display_permissions`.
- `content_candidates[].candidate_id`, `event_id`, `title`, `content_type`, `video_id`, `official_video_url`, `watch_route`, `source_evidence_ids`, `source_verified_at`, `published_at`, `playback_status`, `territory`, `login_or_paywall`, `embed_status`, `thumbnail_url`, `match_id`, `match_link_status`, `rights`, and `public_status`.
- `relationships[]` carries a typed event relation plus evidence ID and a scope label that explicitly does not assert clip appearance or match identity.
- `evidence_sources[]` carries the evidence URL, observed date, claims, optional listed titles/athletes, and limitations.

The delivery projection preserves the v0.1 core and adds a typed graph for direct Fan UI consumption:

- `stars[]`, `events[]`, `clips[]`, `matches[]`, and `watch_sources[]` are separate node collections. `matches[]` is intentionally empty because none of the candidates is verified to a specific match.
- `relationships[]` contains evidenced roster/listing edges and `CLIP_CANDIDATE -> WATCH_SOURCE` routes. `relationship_gaps[]` explicitly marks `STAR_TO_MATCH` and `MATCH_TO_CLIP` as `NOT_ESTABLISHED`.
- Event and candidate `title_zh` values are PTTI editorial translations. The English source title remains intact; `official_translation_status` stays `UNKNOWN`.
- `source_index[]` is the evidence registry. Candidate-to-event-page fallback reuses the exact event evidence URL; direct YouTube routes require the exact video ID/URL pair.
- The delivery projection is `INTERNAL_REVIEW` only, bound to the base dataset and localization source hashes. It carries no local media paths, thumbnails, or media bytes. San must never use it as a strict-public fallback.

The same build command writes the delivery graph.

## Verification

Targeted tests: `python -m unittest products.ptti-integration.tests.test_goal14_fan_content_intelligence products.ptti-integration.tests.test_goal14_fan_content_delivery -v`
Expected negative cases include duplicate candidate IDs, rights escalation, guessed match IDs, wrong YouTube ID/evidence pairing, title mismatch, unknown event reference, and unknown protocol version. JSON Schema checks validate both views. The output also asserts the existing Goal 11 internal catalog remains 35 reference sources and has no catalog-to-review-data links; those sources are not imported here.

Not performed: San browser integration, current-region external playback, YouTube embed checks, native Windows playback, public release, and publisher/rightsholder permission review.
