# Cinema Video Library Expansion R1

## Actual content

New reviewed sources: 9, publisher World Table Tennis, verified by explicit official oEmbed requests. No scraping or media download. New counts: MS 2, WS 1, MD 3, WD 3.

Isolated catalog including prior entries: MS 7, WS 3, MD 4, WD 3, XD 1; total 18. The prior MD includes a third-party Bilibili reference. Old items are not newly verified R1 evidence. The 160-entry target is NOT MET. No configured YouTube Data API key was available; bulk publisher-directory reuse permission was not established. Scraping is not a substitute for authorized API access.

## Current-session browser QA

| Category | New metadata/category verified | Official pages opened | PTTI internal playback | Region restricted | Other |
| --- | ---: | ---: | ---: | ---: | --- |
| MS | 2 | 1 | 0 | 1 | 1 page not tested |
| WS | 1 | 1 | 0 | 1 | none |
| MD | 3 | 1 | 0 | 1 | 2 pages not tested |
| WD | 3 | 1 | 0 | 0 | 1 ad only, 2 pages not tested |

Samples: WoqgXTjZNSk, X5hp7YM7BIk, X8Jx8rs20FA, gxLOCVeMCM0. First three pages displayed regional prohibition. WD displayed an advertisement only; match playback was not verified. No bypass attempted.

FULL_MATCH is a publisher title claim, never content-reviewed completeness. Dates and athlete IDs remain unknown. Abbreviated pair names are not expanded by inference. New covers are placeholders; no image redistribution permission is assumed.

## Import and isolation

Independent TEST database under OS TEMP: ptti-library-r1/catalog-qa.db. First import inserted 9; repeat inserted 0 and reported 9 duplicates. Report files are local, outside Git.

Existing media_online_sources table reused. Provider/source ID keys and independent timelines; no automatic match merge. Atomic transaction plus append-only audit. Interrupted batches roll back; retry does not duplicate. Existing human mapping and playback records are never overwritten by batch import; category conflicts are reported.

Import CLI requires localhost TEST diagnostics and refuses report overwrite. API blocks production mode. Source metadata older than 30 days is hidden pending refresh. This is not a completed compliance audit for a large YouTube Data API client; bulk collection remains disabled.

## Product

Cinema navigation preserved. MS/WS/MD/WD/XD category controls; player/pair/title query; year/event/platform/content filters and existing favorites. Four real category card clicks reached the exact official watch link, with zero unlicensed player iframes. Page access is separate from content playback.

Current UI acceptance is BROWSER_HOST_QA_ONLY. Existing EXEs retain packaged assets; no new Windows build. MANUAL_GUI_CHECK_REQUIRED.

## Tests and boundaries

Python catalog and source contract: 21 passed; production-import rejection separately: 1 passed. Frontend review 9, score 5, observations 12, feed 19: 45 passed. Cinema layout: 17 checks passed. TypeScript, Vite, pip check, compile and diff checks passed. Full Python suite was not rerun.

SQL interruption test verifies rollback and retry. Synthetic tests are engineering QA only. No GPU task. RAM dropped to approximately 1.97 GiB; no heavy build attempted.

CONTENT_EXPANSION_R1_PARTIAL. Existing product, completeness, Score and Vision gates unchanged. Frozen Hit SHA256 remains fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3. No Production DB, official TEST, GAME_5, main merge or Release.

## Policy references

- https://developers.google.com/youtube/terms/developer-policies
- https://www.youtube.com/static?template=terms
- https://www.tv-tokyo.co.jp/index/company/link.html
- https://www.ittf.com/2025/05/16/everything-you-need-to-know-ittf-world-table-tennis-championships-finals-doha-2025/
