# Original R4 thumbnail mechanism — bounded verification

Source baseline: `5cc753886b112305736fcc14ea77b37662726c9f`.

## Reproduce the offline identity audit

From `products/ptti/frontend`:

```powershell
node scripts/audit-original-thumbnail-mechanism.mjs
```

This reads Git and the existing catalog only: no backend, database, image fetch,
API key, Cloud project, or permission mutation. The adjacent JSON is an internal
source-audit result, not a public media manifest. Recorded publisher/embedding
claims are not fresh provider verification.

## What actually produced the original wall

`feedCatalog.ts` copied `v.thumbnail_url` to `FeedVideo.thumbnail` without a
display-permission check. `VideoFeed.tsx` used an ordinary lazy `<img src>` with
an error fallback. All eight YouTube entries used their exact video ID in an
`i.ytimg.com/vi/VIDEO_ID/hqdefault.jpg` URL. Thus the browser displayed remote
provider images; the code did not extract frames or download JPEGs into the app
package. Browser-managed network caching is separate from application-managed
storage; remote display is not a promise that no browser cache exists.

Bilibili had no thumbnail URL, explaining the first blank card in the founder's
reference. It is not a ninth YouTube thumbnail.

## Three distinct delivery methods

1. Remote `<img>`: exposes an image separately from the official player. A
   reachable CDN URL and historical successful display do not establish the
   applicable display permission. No standalone hotlink grant was established
   in the official documents reviewed here; existing image gates remain closed.
2. Official embedded player: documented iframe/IFrame API route with no Data API
   key or Cloud setup required for basic embedding. YouTube supplies its own
   player presentation, potentially including its preview. This is not an API
   that grants a standalone JPEG. Keep branding/controls intact, no blocking
   overlays, normal Referer/client identity, no autoplay, and obey disabled
   embedding, login, geography, and errors. Minimum viewport is 200×200; a 16:9
   player consequently needs at least about 356px width. A narrow four-column
   card cannot simply become a compliant player by shrinking it. A selected
   detail player can reuse `OfficialVideoPlayer` after exact source eligibility
   is established. Do not treat a failed/disabled embed as a valid cover preview.
3. App-managed JPEG download/bundling: creates a distributed asset and requires
   its own rights evidence. It is not authorized by either of the above methods.

Official sources checked:
- https://www.youtube.com/static?template=terms (Permissions and Restrictions)
- https://developers.google.com/youtube/player_parameters (iframe route, sizes)
- https://support.google.com/youtube/answer/171780?hl=en (embedding control,
  Referer/error 153, application/WebView distinction)
- https://developers.google.com/youtube/terms/developer-policies (embedded API
  obligations; user authorization is not required for IFrame viewing)

These support investigation of a no-Cloud official-player route, not blanket
approval of eight images, or a conclusion that all client compliance is done.
Existing `allowedEmbed` conditions and thumbnail runtime are unchanged.

## This run's actual boundary

RAM measured 4.26 GiB before the single browser attempt. Opening the registered
`0QgbtsBWZhk` watch page failed during CUA initialization: kernel-assets write,
Windows os error 3. No page opened. No alternative tool or repeated launch was
used to work around this failure. Cover rendering, attribution visibility,
watch-click behavior, actual playback and Windows native display are all
BLOCKED/NOT_TESTED this run. Zero new covers are admitted or restored.

Once the supported browser works, use one isolated HTTP preview and the existing
registered source: inspect the official watch page's Share/Embed availability;
if allowed, test the intact official player in an adequately sized detail view,
including preview, attribution, Watch on YouTube and disabled/error fallback.
Only then review per-source eligibility for the other seven. Bilibili requires
its own provider evidence. Keep the four-column product and existing image gates
unchanged until those tests and display conditions succeed.
