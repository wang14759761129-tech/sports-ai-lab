# GOAL105 — concrete photo candidates, no new distribution grant

Base: `4d39b4257e69938c4674a0ec9fc37c3ae13c3a57` on the original R4 enhancement line.
The eight remaining registered sources were investigated. Seven specific official
photo pages and their publisher-provided 1024×683 rendition metadata were obtained.
No new JPEG was downloaded, packaged or displayed.

## Per-source outcome

| Registered video | Specific photo page | Identity finding | Rights for PTTI distribution |
|---|---|---|---|
| `0QgbtsBWZhk` | https://www.flickr.com/photos/wttglobal/54834351810/ | WANG Chuqin, China Smash 2025 Day 8; taken 2025-10-05. Exact opponent/round/image still pending. | NEEDS_PERMISSION_FOR_DISTRIBUTION |
| `vYsJLPTEIaI` | https://www.flickr.com/photos/wttglobal/55122621851/ | SUN Yingsha, Singapore Smash 2026 Day 8; taken 2026-03-01. Exact final image still pending. | NEEDS_PERMISSION_FOR_DISTRIBUTION |
| `aFs7HJ0NX18` | https://www.flickr.com/photos/ittfworld/50631735883/ | MA Long, taken 2020-11-22. Photo title does not identify the event; membership in the Finals Day 4 album was not established. | NEEDS_PERMISSION_FOR_DISTRIBUTION |
| `JTUWXpB-NVo` | https://www.flickr.com/photos/ittfworld/49222410018/ | Publisher caption explicitly names Zhengzhou 2019 Grand Finals, Fan vs Ma, MS final, 2019-12-15. Photo pixels not reviewed this run. | NEEDS_PERMISSION_FOR_DISTRIBUTION |
| `H77vNFk3neg` | https://www.flickr.com/photos/wttglobal/52838846732/ | WANG Chuqin, Macao 2023 Day 7; taken 2023-04-23. Exact opponent/round/image still pending. | NEEDS_PERMISSION_FOR_DISTRIBUTION |
| `DTPNEl3-2b0` | https://www.flickr.com/photos/wttglobal/53986897282/ | SUN Yingsha, Macao 2024 Day 3; taken 2024-09-11. Official event report corroborates the Sun/Kim R16 fixture that day, but not the pixels of this image. | NEEDS_PERMISSION_FOR_DISTRIBUTION |
| `iQhVLkcGCFE` | https://www.flickr.com/photos/wttglobal/51712851879/ | Publisher title names Lin/Cheng, WTTC2021; taken 2021-11-28. Semifinal context is corroborated, exact photo/opponent verification pending. | NEEDS_PERMISSION_FOR_DISTRIBUTION |
| `BV1nb421H7jB` | No admissible photo association | Spectator-video match, date and round remain unverified. Four player names cannot establish a photo binding. | UNKNOWN; no asset |

These are **seven concrete candidates**, not seven confirmed match photographs.
One new photo has an exact-match publisher caption; six need further identity work.
All seven selected photo pages report Flickr licence ID 0 (All Rights Reserved).
Individual photographers remain UNKNOWN. The WTT pages' editorial-use wording is
retained without upgrading it to Web publication or downloadable-software permission.

The prior Ljubljana photograph `53034902256` remains preserved under the GOAL104-R2
distribution hold. Its historical browser decode PASS is not a new GOAL105 display.
No registry match IDs were invented for sources without an existing exact ID.

## Other licence paths and rejected matches

- Commons public metadata search for the named editions did not establish a matching
  reusable file. Seven Flickr searches filtered for CC BY/BY-SA/CC0/PD similarly
  established no suitable match. This bounded search does not prove global absence.
- A CC0 search hit for “Ginger Smash” is a beverage, not a tennis match. It was rejected.
- ITTF photo `50605794726` explicitly depicts the Weihai **2020 Men's World Cup**
  final (2020-11-15), not the Zhengzhou **2020 ITTF Finals**. Same players/year must
  not create an association. Earlier-round Ma/Franziska and Ma/Falck photos likewise
  did not establish the final.
- Reuse rules: https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia
  and https://www.flickrhelp.com/hc/en-us/articles/10710266545556-Using-Flickr-images-shared-by-other-members

No licence, attribution, crop or likeness approval is inferred from search filters,
watermarks, download URLs, account ownership or an editorial notice. An actual open
licence could be reviewed on its own terms; no private letter is mechanically
required for every Commons file. No matching eligible open-licence file was found here.

## Runnable delivery

Internal data: `data/professional/cover_review/goal105-cover-review.v0.1.json`.
This reuses `ptti.match-cover-review/0.1`; it is not an additional runtime media system.
Observed search/page metadata is preserved in adjacent `goal105-*-observations.json`.
Image-byte hashes remain null because new image bytes were not acquired; response
hashes are explicitly page-metadata evidence, not media hashes or copyright proof.

From `products/ptti/frontend`:

```text
node scripts/review-goal105-photo-coverage.mjs
node scripts/test-goal105-photo-coverage.mjs
npm run test:media-distribution
```

The reader validates exact existing source/video/match references, reports real
counts and refuses identity, duplicate, permission or hash-state corruption. It
does not activate candidates. The existing runtime resolver rejects every candidate.
The active public media manifest remains v0.2 with zero assets. Standard Windows
staging excludes this internal cover-review folder and retains only that manifest.

## Shortest next dependency

The founder reports the WTT email was sent. No duplicate was sent and the mailbox
was not accessed this run; no claim is made about whether a reply has arrived.
Review any reply against the exact photo IDs, target platforms, distribution mode,
commercial use, credit, links, crops, territories, dates, fees and withdrawal terms.
It must not automatically cover ITTFWorld archive photos or additional WTT photos.

In parallel, close the six remaining exact-image identity gaps. Only after identity
and the actual intended-use licence both pass should Main populate the existing
runtime sidecar and active manifest. Until then HOST keeps the photo-free build.
