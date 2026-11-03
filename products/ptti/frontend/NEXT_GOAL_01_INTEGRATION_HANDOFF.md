# NEXT-GOAL-01 — Cinema integration review

This handoff describes code at `44a782b2cf908478528cb909a734367029bdc346`, based on the isolated restoration candidate `ffc86c7ea377f9328c7f7f2d1d9e6f1c1878fa2e`. The original 5cc baseline is `5cc753886b112305736fcc14ea77b37662726c9f`. This is a review candidate, not a release or Founder visual approval. The earlier CINEMA_ORIGINAL_QA_HANDOFF.md describes the ffc86c7 restoration snapshot; its statement that the wall files are unchanged applies only to that snapshot.

## Smallest patch and integration interface

Review the exact changes with `git diff ffc86c7..44a782b -- products/ptti/frontend/src/VideoFeed.tsx products/ptti/frontend/src/LegacyMatchStory.tsx products/ptti/frontend/src/cinemaViewing.mjs products/ptti/frontend/src/cinemaViewing.d.mts products/ptti/frontend/src/video-feed.css products/ptti/frontend/scripts/test-cinema-viewing.mjs products/ptti/frontend/scripts/test-goal99-story-favorites.mjs products/ptti/frontend/scripts/test-video-feed.mjs`. The commits are `69167c9`, `d4f5368`, `81759b4`, and `44a782b` in order. MAIN should review against its own current source rather than assume patch application or merge compatibility.

The changes reuse `VideoFeed`'s existing `navigate`, match/source identities, `filterFeed`, favorites, Story, and `OfficialVideoPlayer`; `personalShelfFilters(page, filters)` only projects existing filters for favorites/history without mutating saved discovery state. Player Back clears the active player while preserving Story. Story opens a source only after `findOfficialFeedVideo` matches the exact source and `watchUrl` passes the existing URL gate. No new API, database, media distribution grant, or player is introduced.

## Wall comparison at source level

The four-column grid rule and 16:9 cover aspect ratio remain in `video-feed.css`; search, categories, actual catalog cards, favorites, Story, and official actions remain in the existing components. The addition is a compact discovery row and hover/focus treatment, not a replacement wall. Founder QA-only remote thumbnail admission and distribution-mode checks are untouched. This is source evidence, not a rendered comparison: actual first-screen image share, 2560×1600 layout, scroll position, transitions and thumbnails remain NOT_TESTED.

Available history records a local video opened timestamp, not a reliable playback position. The interface labels this as viewing history and does not claim resume from a timestamp. No official embed permission, player verification or third-party image distribution is inferred.

## Verification and next step

Prior targeted runs passed TypeScript, feed and Story/favorite checks, session filter projection, official-player contracts, thumbnail and media-distribution isolation. No new production build or candidate GUI/browser/playback test is claimed. The historical GEX03E thumbnail results concern a different candidate and internal QA only.

Host may run the candidate only with the isolated API, test database and QA profile described in the restoration handoff and all existing resource, idle and browser-control guards. Compare actual original 5cc and this candidate at the same viewport and scroll, then exercise discovery, exact Story, official opening, return and favorites. Save real screenshots only after observing the candidate. Founder approval remains outstanding. Do not merge, deploy, push, change the official launcher, or activate a release based on this handoff.

## Follow-up: unavailable favorites and current candidate

Code candidate `844c81a510a66feb2dd7c365447fc019731bcbc8` adds `unavailableFavoriteKeys` in `matchFavorites.mjs`: favorite keys missing from the currently available feed remain stored, while the favorites view explains that they cannot currently be displayed. It does not manufacture match metadata or delete the stored keys. Add `matchFavorites.mjs`, `matchFavorites.d.mts`, and the corresponding test changes when reviewing the full `ffc86c7..844c81a` range; the earlier range above intentionally describes the previous snapshot.

A fresh production-mode Vite build of `844c81a` passed the existing WEB media-tree gate in a unique temp directory, with 23 files and 0 approved packaged match photos. Main JS: 501.08 kB, gzip 155.99 kB, SHA-256 `6907fd3f4f62800b1c1fa3851625fb2272fa7902d0694b2493941b72365625dd`. This does not prove GUI, rights for externally loaded QA imagery, or Founder visual approval. The previous temp build is a different code identity.
