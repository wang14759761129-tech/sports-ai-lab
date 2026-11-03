# GOAL104 — one real match photograph, original R4

Product baseline: `5cc753886b112305736fcc14ea77b37662726c9f`.
Development input: `b2361239eed55efe92e2bdf6802fb737a483a696`.

## Delivered asset and scope

`video-source:youtube:ekfCZiIEYi0` now has one separately reviewed WTT
Ljubljana 2023 final photograph. This is **not the original YouTube thumbnail**.
No registry match_id is invented: the source still has no registry match_id.
The photo is bound to the exact registered video, URL, event, round, discipline
and participant names. A later match_id change invalidates this review.

- Photo: https://www.flickr.com/photos/wttglobal/53034902256/
- Publisher: World Table Tennis, official Flickr account `194208068@N05`.
- Publisher caption names WANG Chuqin; the image contains the opposing
  jersey text FAN ZHENDONG and Ljubljana venue signage; date is 9 July 2023.
- Publisher grants editorial use in the photo description and account profile:
  https://www.flickr.com/people/wttglobal/
- Use: factual editorial match-card illustration with `摄影 © WTT` credit
  linked to the photo page. No sponsorship, endorsement or promotional Hero.
- Full publisher-provided 1024×683 JPEG preserved without cropping, alteration
  or watermark removal. The existing 16:9 container uses `object-fit:contain`.
- Local storage is solely the editorial display asset, not an open photo library
  or a general media cache. No raw-asset sublicensing, video download or analysis.
- Individual photographer: UNKNOWN. Do not invent a name or claim a CC licence.
- SHA-256: `faaaa29e1872b917fa3e548f1d829c7e5dbe91703152075e80be69b095bf00d5`.

The review expires after 30 days; expiry, wrong identity, missing credit, invalid
scope or image loading failure restores the existing fallback. There is no
automatic refresh, Cloud request, scraping job or global permission change.

## Nine-source provenance

The machine-readable nine-entry review includes the exact 5cc thumbnail URLs
and live metadata checks:
`data/professional/cover_review/goal104-cover-review.v0.1.json`.

| Video ID | Original 5cc thumbnail | Current result |
|---|---|---|
| BV1nb421H7jB | None | Publisher prohibited unauthorized republication; page HTTP 412; no photo admitted |
| 0QgbtsBWZhk | YouTube i.ytimg.com, exact video ID | API route paused; no photo admitted |
| vYsJLPTEIaI | YouTube i.ytimg.com, exact video ID | API route paused; no photo admitted |
| aFs7HJ0NX18 | YouTube i.ytimg.com, exact video ID | API route paused; no photo admitted |
| JTUWXpB-NVo | YouTube i.ytimg.com, exact video ID | API route paused; no photo admitted |
| H77vNFk3neg | YouTube i.ytimg.com, exact video ID | API route paused; no photo admitted |
| ekfCZiIEYi0 | YouTube i.ytimg.com, exact video ID | Original thumbnail still gated; separate exact-match WTT editorial photograph admitted |
| DTPNEl3-2b0 | YouTube i.ytimg.com, exact video ID | API route paused; no photo admitted |
| iQhVLkcGCFE | YouTube i.ytimg.com, exact video ID | API route paused; no photo admitted |

All eight YouTube oEmbed checks returned the catalog title and WTT channel.
This verifies metadata only. It grants no image use or video playback evidence.
Commons Ma Long WTTC2016 and Sun Yingsha Paris interview images were excluded
because they do not depict the registered matches, despite open licences.

## Handoff and verification

Public media manifest: `data/professional/cover_review/public-match-cover-manifest.v0.1.json`.
Asset: `frontend/public/media/editorial/wtt-53034902256.jpg`.
Runtime path: `/media/editorial/wtt-53034902256.jpg`.
Existing `thumbnailPermission` module validates the scoped sidecar;
`feedCatalog` and `VideoFeed` reuse the original image and watch-card path.
Do not replace the historical thumbnail URL or promote other records.

Tests: `npm run test:match-photo`, `npm run test:feed`,
`npm run test:goal99-story`, `npm run test:youtube-thumbnail`, `npm run build`.

Actual browser evidence: `editorial-photo-browser.png` and
`browser-verification.json`. The real VideoFeed ran with a read-only static
catalog fixture, no backend/database. At 331×637, the actual JPEG decoded at
1024×683; the matching watch URL, WTT credit and favorite star remained present.
This is component-browser acceptance only, not Windows/native acceptance.
Desktop four-column GUI comparison, external video playback and Windows candidate
remain NOT_TESTED this run. Existing grid/navigation structures were not redesigned.

HOST next: build an isolated candidate from the final commit, verify the packaged
asset SHA and the original desktop wall, then confirm this one photograph and
credit. Keep the installed R4, launcher, databases and desktop entry unchanged.
