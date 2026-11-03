# GOAL109 — standalone thumbnail admission closeout

2026-10-25. Baseline `1a106027dcc3fa8f20dfa393da6cff358917b63c`, clean
worktree on entry; GOAL107 is an ancestor. GOAL108/V2 and product code unchanged.

**NO-GO for restoring the eight standalone images with the evidence currently
available. This is an admission decision, NOT a finding that YouTube prohibits
all thumbnails or that a no-key solution can never exist.** No photography search,
new artwork, Cloud project, public deployment, or user database access occurred.

## What official policy actually supports

| Question | Supported finding |
|---|---|
| Are thumbnails categorically forbidden? | No. Developer Policies III.F.2 explicitly covers thumbnails and requires YouTube source branding. |
| Can discovery cards be an intended experience? | The policy guide gives a mixed-platform search engine as an independent-value example. This supports that category of UI, not every acquisition method. |
| Image integrity / click | The guide says thumbnail/title metadata should remain visible and unmodified. A custom thumbnail play button must initiate playback. Links follow the YouTube-app/system-browser rule. A card opening an idle detail player must not misleadingly claim immediate playback. |
| Minimum size | RMF: a thumbnail initiating playback is at least 120×70. The 200×200 player minimum is a different rule, not a thumbnail minimum. |
| Data API thumbnails | `snippet.thumbnails` supplies provider-returned URLs/dimensions. Available sizes vary. Use the returned variant, not an invented higher-resolution CDN URL. Public-data access still requires the documented Data API setup/credentials; it does not imply OAuth access to private accounts. |
| 16:9 vs original 480×360 | The original hqdefault response is 4:3. Preserving the complete image in a 16:9 card requires contain/letterboxing, not stretching or cropping. A 16:9 variant may be used only if actually returned through an admitted mechanism. |
| Attribution | Applicable official YouTube brand feature and clickable source attribution; plain publisher text alone must not be assumed to satisfy every branding requirement. Do not imply endorsement. |
| Storage/update | Developer Policies III.E.4 requires refresh/deletion of applicable non-authorized API data within 30 days and reasonable freshness. This is not an unlimited image download/bundling licence. Provider failure/deletion must revoke the displayed result and use the existing fallback. |

Primary sources checked:
- https://developers.google.com/youtube/terms/developer-policies
- https://developers.google.com/youtube/terms/developer-policies-guide
- https://developers.google.com/youtube/terms/required-minimum-functionality
- https://developers.google.com/youtube/data/reference/rest/v3/thumbnails
- https://developers.google.com/youtube/data/getting-started
- https://developers.google.com/youtube/terms/branding-guidelines

## No-key oEmbed: one genuine metadata request, not a display grant

One GET to YouTube's public oEmbed endpoint for registered video 0QgbtsBWZhk
returned HTTP 200, application/json, `type=video`, `version=1.0`. Title and WTT
publisher matched the catalog; HTML referred to the exact embed ID. The returned
thumbnail was the same exact-ID hqdefault URL, 480×360. No image request was made.
Response byte SHA-256:
`400e611ab70abb2e91ce1f41419dc2369e6cce630f633ef9b648f99510e92582`.

The primary oEmbed specification (https://oembed.com/ §2.3.4) defines an optional
thumbnail URL and video embed HTML; §2.3.4.2 discusses `photo` versus `video`
representations. It does not itself grant YouTube copyright/display rights or
resolve YouTube's client-specific acquisition rules. The technical response is
real; the four requested YouTube policy pages do not explicitly document this
endpoint's standalone-thumbnail use for this client. No claim that oEmbed is
necessarily forbidden is made. Evidence still lacks a supported YouTube-specific
basis to approve that acquisition-and-display combination. Third-party tutorials
were not treated as permission. Developer Policies III.D.7 also makes undocumented
API use a material question that cannot be settled by HTTP 200 alone.

Likewise, a historical constructed CDN URL is not the same provenance as an
official Data API response. Both can point at identical bytes, but the URL shape
does not establish the acquisition/display conditions. Data API credentials would
not themselves grant arbitrary editing, promotion, video download or redistribution.

## Concrete result and stopping point

- Covers restored: **0/8 YouTube**, Bilibili unchanged/separate (empty original URL).
- New product screenshot / image load / click-through acceptance: **NOT_TESTED**;
  no image was rendered after the admission decision. Do not present the older
  GOAL107 player screenshot as a restored homepage-cover screenshot.
- GOAL107 intact-player viewing remains available for its reviewed 0Q source.
  It is not an extraction mechanism for independent thumbnails.
- No frontend/runtime media, catalog permissions or resource policy were changed.
- Missing condition: either a documented/confirmed YouTube-specific no-key
  standalone-thumbnail path for this use, or an actually configured, compliant
  official Data API path. Both need precise source identity, unchanged original
  metadata, branding/click checks, freshness/revocation and real product rendering
  verification. Cloud remains paused; no account operation is requested here.
- No automatic follow-up search, photography purchase or another fallback design
  is planned. Reopen this gate only on new evidence for the missing condition.

`source-results.json` records all nine current entries without upgrading rights.
The raw response and observation remain local in ignored `build/reports/goal109`,
not a runtime/public/Git media payload; refresh/delete by 2026-11-24T04:49:28Z.
The date is a handling boundary, not a scheduled deletion task.

## Verification

From repository root:
`node products/ptti/docs/goal109-evidence/verify.mjs` — PASS: response bytes,
shape/identity, seven identity negatives, eight unchanged gates, separate Bilibili.
It needs the real local ignored response; missing evidence causes failure, not
a reconstructed response.

From frontend: official-theater, Feed, Story/favorites, YouTube-thumbnail and
media-distribution regressions all PASS this run. V2 light preflight PASS
(available 3,930,054,656 bytes; commit headroom 19,489,021,952 bytes).

No new build or browser session was necessary after NO-GO. TypeScript/Vite result
is **reused GOAL107 PASS, not rerun**: frontend Git tree at GOAL107 and baseline
HEAD is exactly `82b6c7bbba3e7deec82ae6e777fe7768ee2cec38` in both cases, including
lockfile and source. GUI, new cover rendering and Windows Native remain untested
for this task. Do not label them PASS.
