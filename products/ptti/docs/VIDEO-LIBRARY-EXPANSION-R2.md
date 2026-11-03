# PTTI Cinema Video Library Expansion R2

Status: `CONTENT_EXPANSION_R2_PARTIAL` · 2026-10-10

## Starting point and isolation

- R1 commit `46b90b7d575166dccfd6c281db69b9f0dad37511` was pushed to `codex/ptti-cinema-library-expansion-r1`; GitHub returned the same SHA.
- R2 branch: `codex/ptti-cinema-library-expansion-r2`.
- Independent QA DB: `%TEMP%/ptti-library-r1/catalog-qa.db` contains the 9 R1 imported rows. A pre-R2 SQLite backup was created before appending four current page observations and four `R2_OFFICIAL_PAGE_REVIEW` audit records. Existing R1 import evidence and source metadata were retained; no source import or ID/category overwrite was performed. The 9 curated baseline entries plus those rows produce 18 visible online sources.
- No YouTube/Google API credential variable was present. YouTube's current Developer Policies say API Data aggregation is limited to channels under one recognized content owner and viewable by that owner, and prohibit storing audiovisual copies without prior written approval. PTTI has no verified owner authorization for a catalog API client, so R2 did not use Data API or page scraping to expand counts. [YouTube Developer Policies](https://developers.google.com/youtube/terms/developer-policies)
- No source is approved for download, offline storage, local analysis, or PTTI playback by the catalog reference alone.

## Reconciliation of all 18 current records

All 17 YouTube records identify World Table Tennis as publisher in the curated metadata/title evidence. Their `FULL MATCH` titles are publisher claims only; no uninterrupted full-match review was completed. The remaining record is a Bilibili user upload by “乒乓球珍藏馆”; its page says “未经作者授权，禁止转载”, and the content remains a reference only. A page response, title, ad, or loaded player is not counted as footage playback.

| ID | Class | Entry / event evidence | Publisher | R2 official page | Footage playback / restriction |
|---|---|---|---|---|---|
| BV1nb421H7jB | MD | Ma Long/Wang Chuqin vs Fan Zhendong/Lin Gaoyuan; 2023 Asian Championships audience view | 乒乓球珍藏馆 (user publisher) | Opened; title, page and collection visible | Classified `CLIP` from the source's “观众视角片段” title; R2 playback not verified. R1 recorded moving footage in a prior session with login/trial notice; the page's playlist and 10:33 item do not prove a complete match. |
| 0QgbtsBWZhk | MS | Wang Chuqin vs Felix Lebrun; China Smash 2025 final | World Table Tennis | Not reopened in R2 | Prior native embed failed with error 150 and a region restriction; external playback remains unverified in R2. |
| vYsJLPTEIaI | WS | Sun Yingsha vs Wang Manyu; Singapore 2026 final | World Table Tennis | Not reopened in R2 | Prior embed status blocked; current external footage not verified. |
| aFs7HJ0NX18 | MS | Ma Long vs Fan Zhendong; ITTF Finals 2020 final | World Table Tennis | Not reopened in R2 | Prior unauthenticated-session page did not play; current status not retested. |
| JTUWXpB-NVo | MS | Ma Long vs Fan Zhendong; ITTF Grand Finals 2019 final | World Table Tennis | Not reopened in R2 | R1 observed external playback advancing 0.214→49.016s in one session; no end-to-end/full-match check; not retested in R2. |
| H77vNFk3neg | MS | Wang Chuqin vs Ma Long; WTT Macao 2023 final | World Table Tennis | Not reopened in R2 | R1 observed external playback advancing 0.512→15.636s in one session; later session evidence had an unauthenticated restriction; not retested in R2. |
| ekfCZiIEYi0 | MS | Wang Chuqin vs Fan Zhendong; WTT Ljubljana 2023 final | World Table Tennis | Not reopened in R2 | R1 observed external playback advancing 0.220→31.970s in one session; later session evidence had an unauthenticated restriction; not retested in R2. |
| DTPNEl3-2b0 | WS | Sun Yingsha vs Kim Nayeong; WTT Macao 2024 R16 | World Table Tennis | Not reopened in R2 | R1 observed external playback advancing 0→10.487s in one session; no full-match check; not retested in R2. |
| iQhVLkcGCFE | XD | Lin Yun-Ju/Cheng I-Ching vs Wang Chuqin/Sun Yingsha; Worlds 2021 semifinal | World Table Tennis | Not reopened in R2 | R1 observed external playback advancing 49.765→85.432s in one session; no full-match check; not retested in R2. |
| WoqgXTjZNSk | MS | Tomokazu Harimoto vs Wang Chuqin; Yokohama 2025 final | World Table Tennis | Opened in R2 | YouTube displayed “uploader has prohibited playback in your country/region”; no match footage. |
| X5hp7YM7BIk | WS | Sun Yingsha vs Honoka Hashimoto; Yokohama 2025 R16 | World Table Tennis | Opened in R2 | YouTube displayed the same region restriction; no match footage. |
| GfaSz4TKlpc | MS | Hugo Calderano vs Wang Chuqin; Worlds 2025 final | World Table Tennis | Not reopened in R2 | Page/playback not retested this round. |
| VwzuMoxqTQE | MD | Lin/Huang vs Wen/Yuan; US Smash 2026 final | World Table Tennis | Not reopened in R2 | Page/playback not retested this round. |
| X8Jx8rs20FA | MD | Lebrun/Lebrun vs Lin/Huang; Singapore 2026 final | World Table Tennis | Opened in R2 | YouTube displayed the current-region restriction; no match footage. |
| O241nV8y4Dc | WD | Nagasaki/Shin vs Diaconu/Xiao; Singapore 2026 semifinal | World Table Tennis | Not reopened in R2 | Page/playback not retested this round. |
| ekvDMPZDF4o | WD | Sato/Hashimoto vs Qian/Chen; Fukuoka 2024 semifinal | World Table Tennis | Not reopened in R2 | Page/playback not retested this round. |
| nXwsn2IN9tI | MD | Shah/Thakkar vs Duda/Qiu; Foz do Iguaçu 2025 final | World Table Tennis | Not reopened in R2 | Page/playback not retested this round. |
| gxLOCVeMCM0 | WD | Choi/Shin vs Harimoto/Odo; Ljubljana 2025 final | World Table Tennis | Opened in R2 | Page and player shell loaded, but the visible 1:40 item was an ad; target match footage was not verified. |

Publisher and event fields above come from the existing R1/curated metadata snapshot; the 13 pages marked “not reopened” were not reverified live in this round. For those rows, the R1 status/history remains time-bound evidence, not a claim about current availability.

## Counts and product evidence

| Category | Existing | Newly added in R2 | Current total | Independently verified full matches |
|---|---:|---:|---:|---:|
| MS | 7 | 0 | 7 | 0 |
| WS | 3 | 0 | 3 | 0 |
| MD | 4 | 0 | 4 | 0 |
| WD | 3 | 0 | 3 | 0 |
| XD | 1 | 0 | 1 | 0 |

R2 direct page checks: 5 of 5 pages opened (four YouTube plus the Bilibili record); actual R2 match-footage playback 0/5; PTTI embedded playback 0; three current-region restrictions and one ad-only player among the four YouTube checks; the Bilibili item loaded but R2 did not verify moving footage. The other 13 URLs were not reopened in R2. Earlier R1 records contain short, session-specific external playback observations for five World Table Tennis videos and one Bilibili user upload; they do not demonstrate present availability or full-match completeness.

There are 18 unique platform/video IDs (no duplicates). R2 added 0 records. Same-match identity joins, verified complete-match count, confirmed score locations, and usable Vision tracks remain 0.

## Product changes

- Unverified/non-embeddable source cards now identify “在官方平台观看 ↗” and use an external-link glyph; local playback retains a play glyph.
- The desktop bridge opens only canonical HTTPS YouTube/Bilibili watch URLs in the operating system's browser, and rejects arbitrary hosts, query redirects, credentials and malformed IDs.
- Older source rows with a `full_match` title claim can be filtered under the clearly labelled title-claim option; only independently verified `video_source.is_full_match` entries enter the verified category.
- Cards reveal in batches of 12. Thumbnails continue lazy-loading.

This was source-level and browser-host work. No Windows EXE was built; native system-browser handoff remains `MANUAL_GUI_CHECK_REQUIRED`.

## Verification and limitations

- Isolated R1 database was read-only and remained unchanged; the R1 first/repeat/restart import report continues to show idempotent import (9 inserted once, then 9 duplicates).
- The current system had 1.03 GiB available RAM at the preflight snapshot, below the existing 2 GiB build gate. Full-suite execution and Windows packaging were skipped.
- PTTI web-host directory showed 18 entries and existing category/filter controls. The R2 public-page observations were made by opening official pages in the in-app browser, not by claiming PTTI embedded playback.
- Full Python regression and native Windows acceptance were not completed.
- Hit v0.3 frozen configuration was not changed. Production DB, official TEST and GAME_5 were not accessed.

Gate: `CONTENT_EXPANSION_R2_PARTIAL` (new records 0; public-page playback is region/advertising limited; native Preview not rebuilt or accepted).
