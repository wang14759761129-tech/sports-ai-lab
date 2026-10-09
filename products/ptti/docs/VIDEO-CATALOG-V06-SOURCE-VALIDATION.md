# v0.6 first-stage source validation

Status: VIDEO_CATALOG_SUPPLY_PARTIAL. This is first-stage validation, not a thousand-match delivery.

## Actual result, 2026-10-09
Five existing official World Table Tennis samples were opened, without downloading media, extracting streams, signing in, buying services or bypassing access controls.

| Source ID | Match | Actual result | Surface |
| --- | --- | --- | --- |
| H77vNFk3neg | Wang Chuqin / Ma Long, Macao 2023 | Initial sign-in prompt; one later repeat played after session state changed | Codex in-app browser |
| ekfCZiIEYi0 | Wang Chuqin / Fan Zhendong, Ljubljana 2023 | Initial sign-in prompt; one later repeat played after session state changed | Codex in-app browser |
| JTUWXpB-NVo | Ma Long / Fan Zhendong, 2019 Finals | Initial sign-in prompt; one later repeat played after session state changed | Codex in-app browser |
| DTPNEl3-2b0 | Sun Yingsha / Kim Nayeong, Macao 2024 | Actual play; 0 to 10.487318 seconds; middle 577.417544 and late 1057.385284 samples played | Codex in-app browser |
| iQhVLkcGCFE | Lin/Cheng vs Wang/Sun, 2021 Worlds | Actual play; 49.76546 to 85.431804 seconds | Codex in-app browser |

The browser session state differed during these checks. No account identity is recorded. Failure records remain dated observations, not permanent unavailability. Success is session-specific. Official advertising remained intact. The first successful sample exposed duration 1145.021 seconds, the second 1950.381 seconds. Moving match pictures were observed. Neither was watched end-to-end: publisher full-match claims remain TITLE_CLAIM_ONLY and is_full_match stays null. External playback is not Windows PTTI embedded playback.

Before: 1 locally playable research video, 0 verified professional embedded videos, 0 verified external playbacks. After: local remains 1; professional embedded remains 0; external actual playback samples 5. Existing official source records remain 8, independently verified complete matches 0. There are no new verified score-indexed complete points. One local research asset has non-commercial research permission, not public redistribution permission; official references have no analysis licence.

## Product / source contract
MatchVideoSource separates match identity, shared stream identity and nullable reviewed match intervals. The same stream can supply several match associations. Start/end ordering and source duration constraints are validated; no stream boundary has been invented. Completeness, availability, embedding and analysis permission are independent. Legacy EMBED_VERIFIED alone cannot upgrade a source; actual recorded evidence is required. Official-source API responses now include canonical projections and separate totals. Verified external entries are ordered ahead of untested sources. The existing feed exposes counts and an explicit completeness warning without a UI rebuild. No new database schema or bulk synchronization was introduced.

## TT Archive cooperation boundary
Reviewed https://ttarchive.ovh/, /terms, /about and /contact. The site displays 22,067 indexed matches and uses timed links into official long streams. Its public terms describe an informational archive and warn third-party content can change. They do not provide affirmative permission for PTTI to copy the full index. No public bulk API or export grant was found in those reviewed pages; this is not proof that a private API does not exist. No match database was scraped or mirrored.

A cooperation request should use the published contact page and ask for: a small licensed evaluation export first; match/source IDs, player IDs and reviewed start/end timestamps; permission for commercial/non-commercial catalogue display and search; attribution requirements; scope and term; export/API rate limits; correction/deletion feeds; permitted caching; and evidence rights. Index authorization does not grant audiovisual rights. No request has been sent.

## Official rights routes
WTT Media Archive https://media.archive.worldtabletennis.com/terms_of_use requires prior written permission for copying/use and third-party applications. Licensing scope and fees depend on the intended use, territory and distribution. Its public professional contact is media.archive@worldtabletennis.com. This is an authorization route, not a free public stream or a price quote. No registration, purchase or content capture was performed there.

YouTube https://developers.google.com/youtube/terms/developer-policies limits aggregation, requires refresh/deletion of applicable stored API metadata within 30 days, prohibits unauthorized audiovisual storage and restricts substitute browse experiences. Large cross-owner synchronization remains disabled pending approved use and rights review. No API credential was requested, read or stored. Existing small metadata references are not a commercial aggregation approval.

## Deferred stages / resources
No 100/1,000/10,000 synthetic catalogue was seeded, and no capacity benchmark is claimed: stage 1 remains incomplete relative to fully reviewed complete matches and the Windows-internal goal. No cloud storage/CDN was provisioned or video uploaded. Future cloud estimates must use licensed GB stored and GB delivered, then provider prices; there is no credible quote without scope and region. Prefer authorized producer feeds or owner-supplied small evaluation clips with explicit playback/analysis scope over more unverified URLs.

Native source-QA uses an isolated temporary TEST database and is not a packaged v0.6 EXE. Existing Preview is preserved. Full regression and packaging remain subject to the unchanged RAM guard. No GPU inference or large media download is part of this sprint. Production DB, official TEST, GAME_5 and frozen algorithms remain outside scope.

## Executed validation
- Python source-contract + library regression: 24 passed, 1 pre-existing Starlette/httpx deprecation warning.
- Frontend regression: 34 passed (8 feed, 9 review, 5 score, 12 observation); final TypeScript/Vite build passed.
- pip check, source compile and git diff check passed. Full Python regression was not rerun in low RAM. No Ruff installation or full formatting was undertaken.
- Native pywebview source-QA was restarted normally against the same isolated TEST database; the source-status row displayed external=2/internal=0/complete=0/analysis=0 and ordered the two passing references first. This is native UI evidence of the registry display, not native embedded-media success or a new EXE.
- Available RAM measured 1.663 GiB at start and 1.075 GiB at the later check. Peak RAM/VRAM, 1,000/10,000-row capacity and sustained throughput were not measured. The temporary official test tab was closed after use. No new Preview build was started below the 2 GiB guard; the old Preview remains intact.
- Frozen Hit config SHA256 rechecked: fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3.

## Final bounded recheck superseding interim counts
The browser began showing an existing authenticated session during checks. No login, credential read or access bypass was performed by the agent. Exactly one repeat of each of the three earlier login-blocked samples subsequently succeeded; both observations remain in source records. Their advancing times were H77vNFk3neg 0.512458 -> 15.636063 (duration 1704.721), ekfCZiIEYi0 0.220873 -> 31.969694 (3166.301), JTUWXpB-NVo 0.214410 -> 49.016291 (2517.841), all readyState=4 and paused=false. Actual matching footage was observed. Final external-playback success count is 5, not the interim 2. This establishes five small current-session playback samples, not five end-to-end viewing acceptances. Official full-match completeness and Windows internal playback stay unverified. No larger source set or bulk sync was started.

Final source-QA refresh displayed external=5/internal=0/complete=0/analysis=0; the same isolated database contains 0 ScoreMoment records. Final source-contract/catalog checks: 12 passed (overlap with the 24 earlier tests). Local screenshots remain outside Git. Native-source QA does not validate the user's system browser or a packaged v0.6 player. No automatic sync grant or long-term availability is claimed.

