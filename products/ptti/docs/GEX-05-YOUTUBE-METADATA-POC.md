# GEX-05 YouTube metadata POC

Status: isolated implementation only. No API key, Cloud project, live request, live metadata, approved display grant, or release integration is present.

## Data path

`apps/youtube_data_api.py` exposes a server-only batch `videos.list` transport. It accepts 1–50 unique 11-character IDs, requests `snippet,contentDetails,status`, and fails closed unless the caller supplies a reviewed, YouTube-Data-API-v3-scoped, server-restricted client configuration. It does not log, persist, retry, or rewrite thumbnail URLs. The browser does not receive the API key.

`frontend/src/youtubeVideoMetadata.mjs` maps response items only to registered catalog rows with an exact video ID and exact existing HTTPS watch URL. It does not infer a match ID, channel identity, or watch URL. Existing `match_id` is copied unchanged; absent values remain `null`. An absent, duplicate, or mismatched API item does not borrow another row's metadata.

Thumbnail variants are selected from the API response by requested width; the selected URL and reported dimensions are preserved. Aspect ratio is reported and never cropped or rewritten. Freshness metadata has a 30-day refresh/delete deadline. After refresh failure, a still-fresh response can be retained in memory; stale/invalid data falls back. This POC intentionally adds no durable API cache.

## Three cover states

- `YOUTUBE_API_THUMBNAIL`: future conditional display state. Requires exact source/video/URL identity, a fresh live record, internal review mode, and the existing reviewed Cinema runtime sidecar. GEX-05R removed the separate PoC grant checks; checks delegate to `resolveYoutubeThumbnail`. This POC has no such approved record and does not connect it to Cinema.
- `AUTHORIZED_MEDIA`: requires `resolveEditorialMatchPhoto` approval plus a matching asset entry in the existing `public-match-cover-manifest.v0.2.json`. That manifest currently has zero distributable assets; the withheld WTT photo remains withheld.
- `NO_IMAGE_FALLBACK`: the current state for all eight MOCK records and the fail-closed result for missing, stale, mismatched, or unreviewed data.

The mock fixture uses `.invalid` image hosts and is explicitly marked `MOCK` / `SIMULATED_ONLY`; it cannot be mistaken for official API evidence or successfully load a thumbnail.

## Pre-release checks (not completed)

- Decide and document API-client ownership, purpose, hosting, key restrictions, user disclosure, privacy policy, terms acceptance, and support/deletion contact.
- Display YouTube as the source, retain returned title/thumbnail unmodified, preserve normal YouTube player behavior and YouTube/system-browser click routing.
- Confirm the exact product surfaces and Windows WebView identity/referrer behavior with current official requirements. Do not treat API response success as embedding permission or as a media redistribution grant.
- Implement and verify refresh/delete of API data by the applicable deadline, with no effect on match identity, favorites, Story, Moment Cards, or Pro Lab notes.
- Complete required policy/compliance review before switching any presentation state or shipping an API client.
- Keep release/distribution gate closed until those checks and an actual approved client are complete.

## Current separation

The server transport requires `PTTI_YOUTUBE_DATA_API_KEY` plus explicit client review configuration, but no real credential is configured here. Tests inject an in-memory opener. No call to Google is made. This branch does not alter the Founder QA thumbnail mode, the formal media gate, or Cinema UI.

## Official references consulted 2026-10-27

- [YouTube Data API `videos.list`](https://developers.google.com/youtube/v3/docs/videos/list)
- [YouTube Data API thumbnail resources](https://developers.google.com/youtube/v3/docs/thumbnails)
- [YouTube API Services Developer Policies](https://developers.google.com/youtube/terms/developer-policies)
- [Developer Policies Guide](https://developers.google.com/youtube/terms/developer-policies-guide)
- [Required Minimum Functionality](https://developers.google.com/youtube/terms/required-minimum-functionality)
- [API Services Terms of Service](https://developers.google.com/youtube/terms/api-services-terms-of-service)

GEX-05R reconciliation, field sources, test commands and live prerequisites: [GEX-05R-BRANCH-RECONCILIATION.md](GEX-05R-BRANCH-RECONCILIATION.md).
