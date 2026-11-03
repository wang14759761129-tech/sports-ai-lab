# PTTI OFFICIAL THUMBNAIL DELIVERY SPEC

**Version:** 0.1
**Prepared:** 2026-10-23
**Main worktree:** `C:\PTTI-Worktrees\integration-preview-sprint-0-1`
**Source HEAD at review:** `33bd035d318f5856178babd5596777fbb013a17a`
**Status:** `CONDITIONAL_PATH_DEFINED / API_LOOKUP_NOT_RUN / NO_PUBLIC_MEDIA_INCREMENT`

## Decision

YouTube's documented API-client terms provide a conditional route to display YouTube thumbnails and accompanying metadata inside a compliant API Client. This is a permission to display API content under the YouTube API Services Agreement; it is **not** a general image copyright license, a right to copy/rehost thumbnails, or authorization to download, embed, analyze, or redistribute the underlying video.

PTTI has not registered/configured a YouTube API Client for this use, has no API credential configured in the current environment, and has not queried any of the eight video IDs. Therefore all existing Main thumbnail states remain unchanged, zero covers are newly approved, and no public media increment is produced. The old static `thumbnail_url` behavior remains evidence of prior rendering only; it does not satisfy this delivery path.

## Official policy basis

The following primary documents were checked on 2026-10-23:

- [YouTube Data API `videos.list`](https://developers.google.com/youtube/v3/docs/videos/list) — supports requesting a video by exact ID and selecting `snippet`; the returned video resource contains snippet metadata and thumbnail URL/dimensions. `videos.list` costs one quota unit per call according to the current method documentation.
- [YouTube API Services Developer Policies](https://developers.google.com/youtube/terms/developer-policies) — API Clients may display YouTube audiovisual content and accompanying metadata subject to the Agreement; a feature displaying YouTube content, including thumbnails, must clearly attribute YouTube using the required Brand Features. Displayed API Data must remain current; limited non-authorized API Data can be temporarily stored for no more than 30 calendar days, after which it must be deleted or refreshed. YouTube audiovisual-content copies must not be downloaded, backed up, cached, or stored without prior written approval.
- [Developer Policies guide](https://developers.google.com/youtube/terms/developer-policies-guide) — thumbnail and title metadata must remain visible and unmodified; an overlaid custom play button is acceptable only when tapping it initiates playback. A YouTube link must open the YouTube app when available, otherwise the system browser. Do not interfere with player controls, ads, related links, or playback context.
- [YouTube API Services Terms](https://developers.google.com/youtube/terms/api-services-terms-of-service) — API use is governed by the Terms, Developer Policies, Guidelines and assigned credentials; YouTube grants no rights beyond those expressly stated in the Agreement.
- [YouTube Branding Guidelines](https://developers.google.com/youtube/terms/branding-guidelines) — use the appropriate YouTube brand feature beside the API-backed feature; any YouTube logo in the app must link to YouTube content or a YouTube component and must not be altered or obscured.
- [YouTube IFrame Player API](https://developers.google.com/youtube/iframe_api_reference) and [YouTube Help: embedding videos](https://support.google.com/youtube/answer/171780?hl=en) — the official player is the embed route; uploader settings can disable embedding. Embedded requests need a valid HTTP referrer; missing referrer can produce error 153. The documented player minimum viewport is 200 × 200 px; 16:9 players are recommended to be at least 480 × 270 px.
- [YouTube Data API setup](https://developers.google.com/youtube/data/getting-started) — register a Google Cloud project, enable YouTube Data API v3 and create credentials. Public video reads do not inherently require user OAuth; private/user-specific operations do.

These rules support a **conditional API-client display path** for a Cinema discovery page; they do not themselves clear PTTI's particular commercial presentation. PTTI should request a YouTube API Compliance Audit if its mixed-source/paid presentation or the boundary between Web and Windows API Clients remains uncertain. This is a policy/compliance gate, not a reason to infer permission from a thumbnail URL.

## API Client and credential prerequisites

1. The responsible PTTI account owner must accept the applicable YouTube API Services Agreement on behalf of the actual product owner.
2. Register the actual API Client in Google Cloud, enable YouTube Data API v3, and create only the credential needed for public `videos.list` reads. Do not request OAuth scopes for this read-only use.
3. Use credentials assigned to that client only. The policies require exactly one API Project per API Client when credentials are needed; PTTI Web and an independently distributed Windows application may be distinct API Clients if each accesses/uses the API. Confirm the intended boundary before creating projects. Do not reuse a credential across clients.
4. Keep credentials out of source, public JSON, the installer, and a distributed native binary. For a Web/API service, store the key in a restricted server secret and restrict it to YouTube Data API v3 and the serving environment. If a browser key is considered, restrict it to exact HTTPS referrers and get a security review first. Do not put the key in a URL or chat.
5. The API Client must publish and enforce its own Terms and privacy policy, disclose YouTube API use and data handling, link YouTube Terms and Google's Privacy Policy, and obtain the required user agreement before the applicable features are used.
6. Non-website clients such as installed software must be remotely updateable to current YouTube API versions. API quota defaults and policy requirements can change; monitor the Google Cloud quota page and do not circumvent limits.

## Smallest validation for the existing video

Target: `0QgbtsBWZhk` (`video-source:youtube:0QgbtsBWZhk`). No request was made because there is no configured YouTube/Google API credential in the current environment.

After the above prerequisites are approved and configured, make one documented request using the official endpoint, for example:

```text
GET https://www.googleapis.com/youtube/v3/videos?part=snippet&id=0QgbtsBWZhk&fields=items(id,snippet(title,channelId,channelTitle,publishedAt,thumbnails))
```

Provide the credential through the approved secret/header mechanism, not a committed URL or source file. Accept the response as a technical identity check only if exactly one returned `items[].id` equals `0QgbtsBWZhk`. Record the returned `channelId`, `channelTitle`, `publishedAt`, and available thumbnail keys/dimensions with a retrieval time and expiry. Compare the channel ID against an independently verified official-publisher record; a channel title string alone is insufficient. The API response does not prove that this video depicts the associated match: preserve the existing Main match↔source evidence separately. It also does not establish playback success, region availability, embed permission, or complete-match status.

Expected audit record shape (a template, **not** a fabricated API response):

```json
{
  "source_id": "video-source:youtube:0QgbtsBWZhk",
  "provider_video_id": "0QgbtsBWZhk",
  "api_method": "youtube.videos.list",
  "requested_parts": ["snippet"],
  "returned_item_id": null,
  "returned_channel_id": null,
  "returned_channel_title": null,
  "thumbnail_keys_returned": [],
  "retrieved_at": null,
  "refresh_or_delete_by": null,
  "result": "NOT_RUN_NO_CREDENTIALS"
}
```

## Permitted card and click behavior after client approval

1. Fetch the exact known video ID through the official API. Do not scrape YouTube pages, call undocumented endpoints, or construct `i.ytimg.com` URLs by pattern.
2. Display a thumbnail URL only when it is present in the current API response for that exact ID. Select only an actually returned resolution; do not assume `maxres` exists. Scale responsively while preserving aspect ratio. Do not crop, retouch, recolor, combine with player photographs, bake a PTTI logo into the image, or package the thumbnail as a local asset.
3. Keep YouTube's returned title visible and unchanged. If PTTI adds its own match title or translation, label that as PTTI catalog text and visually distinguish it from YouTube metadata.
4. Identify YouTube as the source next to each YouTube card in a mixed-source feed, using the appropriate unmodified YouTube Brand Feature and required sizing/placement. Do not rely on a single page-level attribution when multiple sources are intermingled.
5. A click must be a clearly user-initiated YouTube action. For external watch, open the YouTube app if the platform offers it; otherwise open the system browser at `https://www.youtube.com/watch?v=<video_id>`. For Windows desktop, the safe fallback is the user's system browser. Copy-link remains a recovery option but does not replace the primary watch action.
6. If using an in-app player, use the official YouTube embed/IFrame Player API. Use only when the video owner permits embedding and the platform allows the viewer to watch. Keep standard controls, ads, attribution, related links and player behavior intact; no autoplay. Provide valid origin/referrer context. If embed fails or is restricted, show the actual reason when available and offer the official external watch link.
7. The thumbnail itself is not a PTTI promotion poster. PTTI may use its own neutral branded placeholder when the API route is unavailable; it must not imply a real match image or YouTube origin.

## API Data freshness and fallback

- Treat API-returned title, channel fields, thumbnail URL and image selection as API Data, not durable Main facts. Keep only the limited data required for the client; attach `retrieved_at` and `delete_or_refresh_by` no later than 30 calendar days after retrieval. Refresh sooner when the user-facing UI needs current data. Delete expired records if refresh fails.
- Do not commit API responses, thumbnail URLs, thumbnail bytes, or derivative image files into a long-lived public catalog or installer. Do not proxy/cache image bytes. The API policy expressly prohibits copies of YouTube audiovisual content absent prior written approval; for thumbnail-byte caching beyond the temporary API Data path, obtain explicit written clarification rather than assuming it is allowed.
- A stale or unavailable API record must not fall back to a hard-coded CDN URL. Hide the thumbnail and render an original PTTI placeholder while preserving the verified official watch URL, if that URL remains part of the independently admitted catalog.
- If the API returns no item, a mismatched ID, a publisher mismatch, a missing thumbnail, or a policy/configuration error: do not display the returned image; report `UNAVAILABLE` or `REVIEW_REQUIRED`, preserve the official external-link status independently, and retry only under normal quota/backoff rules.
- Page ads/sponsorships are a separate policy review. YouTube policies restrict ads/sponsorships on a screen containing YouTube API Data unless independently valuable non-YouTube material on that screen provides sufficient value if the API Data were removed. Do not sell access to watch an embedded YouTube video.

## Current eight-match feasibility snapshot

This is a read of existing Main package states, not a re-review of match facts. Existing `rights.thumbnail_display` values remain unchanged. `API lookup` is `NOT_RUN` for every row; no actual thumbnail is approved by this document.

| match_id | source_id / video ID | Existing thumbnail state | API-route feasibility | Current decision |
|---|---|---|---|---|
| `pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun` | `video-source:youtube:0QgbtsBWZhk` / `0QgbtsBWZhk` | `NOT_ALLOWED`; URL suppressed in strict package; prior source metadata indicated a thumbnail URL | Candidate for exact-ID API lookup; not queried | `REFERENCE ONLY`; no cover approval |
| `pro:wtt:doha-star-contender-2025:harimoto-jonathan-groth` | `video-source:youtube:jv_XQ6oKaDU` / `jv_XQ6oKaDU` | `NOT_ALLOWED`; URL suppressed | Candidate for exact-ID API lookup; not queried | `REFERENCE ONLY`; no cover approval |
| `pro:wtt:wtt-finals-fukuoka-2024:chen-xingtong-wang-manyu-ws-final` | `video-source:youtube:lb4UMbE8Pfs` / `lb4UMbE8Pfs` | `NOT_ALLOWED`; URL suppressed | Candidate for exact-ID API lookup; not queried | `REFERENCE ONLY`; no cover approval |
| `pro:wtt:china-smash-2025:sun-yingsha-wang-manyu-ws-final` | `video-source:youtube:ttUevnAZSEY` / `ttUevnAZSEY` | `NOT_ALLOWED`; URL suppressed | Candidate for exact-ID API lookup; not queried | `REFERENCE ONLY`; no cover approval |
| `pro:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final` | `video-source:youtube:cDccQqVlMnc` / `cDccQqVlMnc` | `NOT_ALLOWED`; URL suppressed | Candidate for exact-ID API lookup; not queried | `REFERENCE ONLY`; no cover approval |
| `match:ptti:wtt-doha-2026:ms-r16:lin-shidong-benedikt-duda` | `youtube:ywX9mUJ8NtI` / `ywX9mUJ8NtI` | `NOT_GRANTED_PENDING_WRITTEN_APPROVAL` | Candidate for exact-ID API lookup; not queried | `NEEDS PERMISSION`; no cover approval |
| `match:ptti:wtt-doha-2026:ms-sf:lin-shidong-jang-woojin` | `youtube:Kbhf47vb3eE` / `Kbhf47vb3eE` | `NOT_GRANTED_PENDING_WRITTEN_APPROVAL` | Candidate for exact-ID API lookup; not queried | `NEEDS PERMISSION`; no cover approval |
| `match:ittf-doha-2025:ms:wang-chuqin-wong-chun-ting` | `video-source:youtube:suwultS-Jcc` / `suwultS-Jcc` | `NOT_ALLOWED`; no thumbnail URL recorded in current Main delta | API may return a thumbnail if the exact video remains available; not queried | `UNAVAILABLE` in current thumbnail package; no cover approval |

**Counts:** 0 approved display assets; 5 `REFERENCE ONLY`; 2 `NEEDS PERMISSION`; 1 `UNAVAILABLE` in the current recorded cover path. All eight API queries, thumbnail loadability, and visual match checks are `NOT_TESTED`.

## San runtime handoff contract

Do not alter the stable `ptti.match-media/0.2` permission field or publish a static thumbnail URL. If the API route is approved, consume an ephemeral runtime view model separate from the strict Main catalog:

```ts
type YoutubeThumbnailRuntime = {
  provider: "YOUTUBE_DATA_API";
  source_id: string;
  provider_video_id: string;
  status: "NOT_CONFIGURED" | "CURRENT" | "STALE" | "UNAVAILABLE" | "ID_MISMATCH" | "PUBLISHER_MISMATCH";
  api_client_review: "NOT_STARTED" | "CONDITIONAL_APPROVAL" | "APPROVED";
  api_data_retrieved_at: string | null;
  delete_or_refresh_by: string | null; // <= 30 days after retrieval
  youtube_title: string | null; // display unmodified
  channel_id: string | null;
  channel_title: string | null;
  thumbnail: { url: string; key: string; width: number; height: number } | null; // live API result; never static public catalog data
  attribution_required: true;
  click_target: "YOUTUBE_APP_OR_SYSTEM_BROWSER" | "OFFICIAL_IFRAME_PLAYER";
  embed_permission: "UNKNOWN" | "ALLOWED" | "NOT_ALLOWED";
};
```

The consumer must fail closed: only `status=CURRENT`, `api_client_review=APPROVED`, exact video-ID match, verified channel identity, and a returned thumbnail permit the YouTube thumbnail component to render. Otherwise render the PTTI placeholder. This runtime gate does not change Main's independent `thumbnail_display` status until Main records a reviewed API-client basis. Playback, embed, regional access, download, local caching, analysis and redistribution remain separate permissions/evidence.

## Required gates before a public increment

1. Founder authorizes creation/use of the product's API Client and project; responsible legal/account owner accepts the terms.
2. API Client registration, least-privilege credential restrictions, terms/privacy disclosures and branding implementation are in place.
3. If the commercial/mixed-source client design is uncertain, complete the YouTube API Compliance Audit or obtain written policy clarification.
4. Run the single-ID `videos.list` verification and retain only the allowed temporary API Data with a <=30-day refresh/delete job.
5. Verify exact returned video ID and publisher channel ID. Do not infer match association from the thumbnail, title similarity, or API response alone.
6. San demonstrates unmodified thumbnail and title, per-item YouTube attribution, click-through to YouTube app/system browser, a first-party placeholder fallback, and no persisted thumbnail URL/bytes in the public build.
7. Test `item missing`, exact-ID mismatch, publisher mismatch, no thumbnail, expired API Data, network/quota error, embed disabled, and region/login restriction. Keep actual playback and complete-watch status independent.
8. Only then prepare a versioned API-runtime handoff. Do not promote legacy thumbnail permissions or create a Main public media increment until the Main gate explicitly accepts this distinct API-client display basis.

## Review result

- Eight existing match/source identities were found in the current Main public package/deltas; no new match or source was added.
- API capability and policy route: `CONDITIONAL`; one-ID API verification: `BLOCKED_NO_CONFIGURED_CREDENTIAL`; actual thumbnail display permission: `0 APPROVED`.
- Existing rights, source classifications, and the strict public package were not changed.
- No San, Host, Playback, live database, Desktop, credential, or API-service state was modified.
- Worktree had a pre-existing untracked `generated/goal17-media-clearance-v0.1/` directory; it was left untouched.
