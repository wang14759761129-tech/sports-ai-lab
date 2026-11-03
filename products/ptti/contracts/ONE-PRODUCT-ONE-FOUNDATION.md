# PTTI One Product, One Foundation — integration contract 0.1

Status: **isolated MAIN integration candidate**. This contract is a typed projection between existing modules. It is not a new database, a replacement schema, or permission to merge another workspace.

## Product map

| Product space | Existing responsibilities | Boundary |
|---|---|---|
| CINEMA | R4 `VideoFeed`, match/source catalog, official watch routing, Story and Moment Cards | The 5cc wall remains the home page and the source of exact catalog identities. |
| ARENA | `fanArenaEngine.mjs`, predictions and history | Current match is a one-game `SIMULATED_ONLY` scenario. Its point sequence is not a real match timeline. |
| PRO LAB | `ProLab`, Vision, score/evidence review; future Motion Twin and Rally Coach | Local and professional video evidence remain separate. Any timed claim needs an exact asset and timestamp. |
| FOUNDATION | Shared identity, provenance, permissions, storage, and native resource contracts | Infrastructure and contract boundary; no parallel home page. |
| GROWTH | Favorites, recent-opened, trusted local progress, and curated lists | Uses exact references and transparent rules; no trained or hidden recommendation claim. |

Moment Cards is a CINEMA capability. Vision, Motion Twin, Rally Coach, score review and evidence tools belong inside PRO LAB, not as peer products.

## Version and dependency matrix

| Layer | Current contract/source of truth | Candidate integration rule |
|---|---|---|
| Public match/source data | Existing strict-public match library and `feedCatalog.ts` | Match/source/video relationships are exact IDs. Missing `match_id` stays null/UNKNOWN. No title or athlete-name joins. |
| Review analytics | `review-targets/0.1`, `review-evidence-pack/0.1`, Protocol v0.3 | Keep their versions and meanings. Foundation records only reference/project them. |
| YouTube metadata | Server-only `apps/youtube_data_api.py`; GEX-05R batch mapper `youtubeVideoMetadata.mjs`; `YoutubeThumbnailRuntime/0.1` | One `videos.list` transport/normalization line. No new provider client, cache store, UI adapter or API key. Mock fixtures stay `MOCK`. |
| YouTube display and playback | `youtubeThumbnailRuntime.mjs`, `thumbnailPermission.mjs`, `reviewedOfficialEmbed.mjs`, `officialPlayback.mjs` | Fresh metadata, `status.embeddable`, a usable iframe, thumbnail display, and playback permission remain distinct. No provider field grants rights. |
| Favorites and collections | `matchFavorites.mjs`, `favoritePersistence.mjs`, existing SQLite `media_feed_favorites` | SQLite remains canonical for favorites. A `UserCollection` is a projection over exact IDs; no new favorite table or duplicated favorite store. |
| Moments and local notes | `momentCards.mjs` (`videoKey`, seconds, isolated localStorage); `proLabNotes.mjs`; internal GEX-06R restore bridge | Preserve each current store. An adapter may represent a moment as `video_asset_id + timestamp_ms`; it must not infer a match ID. |
| Rally and point evidence | `backend/video_evidence.py`, `backend/score_navigation.py`, existing Protocol v0.3 | A media-time event requires an asset and integer milliseconds. A scoreboard observation without complete boundaries remains an observation, not a point event. |
| Arena | `fanArenaEngine.mjs` | Prediction target is an exact point-event ID inside a simulation. No official athlete, match, video or media timestamp is invented. |
| Pose and automated analysis | GEX-06R prototype `evidence.mjs`; frozen BallTrack and current evidence provenance | Any `MODEL_INFERENCE` needs model ID/version, input refs and an explicit confidence state. Uncalibrated outputs may use null confidence. GEX-06S source was not found in local worktrees/refs, so it is not integrated. |
| Native/runtime | `apps/native_qa.py`, per-commit QA identity, fixed `127.0.0.1:48761`; `RESOURCE-POLICY-V2.md` | QA storage is commit-isolated. No automatic cross-commit data migration. Heavy build retains the 2.5 GiB gate; medium WebView2 QA uses measured budget. |
| Media distribution | Existing media manifest and `test-media-distribution.mjs` | Current approved distributable real covers remain zero. Founder QA thumbnails remain an isolated mode. No JPEG or third-party video bytes added. |
| Internationalization | Existing `frontend/src/i18n.ts` | Extend existing key-based Chinese/English dictionaries; do not create parallel copy files or hard-code translated labels in adapters. |

Observed toolchain during this integration: Node 24.15.0; locked React 19.3.0, TypeScript 5.9.3, Vite 7.3.6; Python 3.13.14; project requirements pin FastAPI 0.142.2, Pydantic 2.13.5, pywebview 6.2.1 and PyInstaller 6.22.3. The GEX-05 contract test dependency is isolated in `tests/requirements-youtube-metadata.txt` (`jsonschema==4.26.0`).

## Shared record contract

`foundation-v0.1.schema.json` is the cross-line contract. Its 12 records are `MatchIdentity`, `MediaSource`, `VideoAsset`, `PlaybackState`, `Moment`, `Rally`, `PointEvent`, `Prediction`, `PoseEvidence`, `CoachAnnotation`, `UserCollection`, and `RightsEvidence`. `personal-discovery-v0.1.schema.json` separately constrains the small local profile; `personal-discovery-v0.1.synthetic-example.json` is test-only data, not a real user profile.

Every record carries `schema_version`, a unique record ID, exact optional match/source/asset references, provenance, and a timeline anchor or explicit null. The shared schema is additive: it does not change Protocol v0.3, the review-targets/evidence-pack contracts, the existing GEX-05 metadata schema, or SQLite rows.

Invariants enforced by the schema/runtime checks:

- A media-timeline Moment, Rally, PoseEvidence, CoachAnnotation, or real PointEvent names one exact `video_asset_id` and integer `timestamp_ms`; a Rally may also have an `end_ms` strictly after its start.
- A simulated PointEvent has no media anchor, match ID, or source ID and carries `SIMULATED_ONLY` / `SYNTHETIC_ONLY`. It cannot masquerade as a time-coded real match.
- A Prediction refers to an exact PointEvent record. Arena predictions stay inside the same simulation ID.
- A model-derived record carries `model_id`, `model_version`, input evidence references, and confidence or an explicit `UNAVAILABLE`/`UNCALIBRATED` state. Raw response strength is not treated as calibrated confidence.
- `provider_embeddable` and `embed_permission` are separate fields. The provider boolean never grants embedding or other usage rights.
- Remote display, web display, native display, package distribution, embed, download, edit, analysis and commercial use are separate `RightsEvidence` decisions. `ALLOWED` requires attached evidence for that exact use.
- Collections reference exact record IDs. Favorites continue to be read/written by the existing SQLite repository; this contract does not move or copy them.

`foundation-v0.1.examples.json` is explicitly synthetic contract data. It is not catalog content and must never enter Cinema or a release package.

## Growth profile and user data

`personalDiscovery.mjs` is a pure local-profile module. It stores only exact IDs and user-open-request timestamps, plus progress for a trusted, available local HTML media asset with a verified file SHA and confirmed local playback rights. It stores no search queries, local paths, video bytes, official iframe progress, or favorite copies. It exposes separate `recentlyOpened`, `continueWatching`, favorites supplied from SQLite, and curator-specified collections. Ranking is deterministic and returns the exact reasons (`RECENTLY_OPENED`, `FAVORITED_IN_SQLITE`, `CURATOR_SELECTED`); it does not claim AI training. This is a tested data seam only; no new Growth shelf is rendered into the Cinema page in this contract step.

Existing browser storage is read without writing during initialization. Unsupported/corrupt profiles fail closed and retain their raw stored bytes. Persistence is explicit. The module is not yet rendered as a new home shelf; a later Cinema UI change must place it below the original video wall and test 5cc density before shipping.

## Historical asset audit and provenance decisions

| Asset | Observed relationship | Reuse decision |
|---|---|---|
| 5cc original `5cc7538…` | Ancestor of current MAIN 54d and selected candidate | Protected visual baseline; no homepage replacement. |
| GEX-03D `c6b0a94…` + GEX-03E fix `4915980…` | Both are ancestors of MAIN 54d | Reuse exact R4 source, internal thumbnail path, Native QA identity and media gate. Historical 8/8 browser records are not fresh evidence for this candidate. |
| `ffc86c7…` GEX-06R local-moment bridge | Ancestor of the reviewed `3ec76c2…` MAIN candidate | Selectively retained in the candidate: local-only restore/preview and safe return path. The standalone prototype and media files remain untouched. |
| GEX-05R `70526f1…` → `f895441…` | Two commits after MAIN 54d, no divergence; selected with reviewed ordered cherry-picks | One shared server transport, batch normalization, one freshness helper, existing thumbnail/right gates. Live API, durable API cache and Cinema wiring remain absent. |
| GEX-06R prototype `71ff6af…` | Separate `products/ptti-web/prototypes/gex06`; not descended from 54d | Reuse only as reviewed reference. Synthetic timing/events and prototype media are not real match data. |
| `69167c9…` alternate Cinema candidate | Branch point is `c6b0a94`, before the later MAIN fixes | Not used as integration base. Its UI tweak remains a separate reviewed candidate until rebased and regression-tested. |
| GEX-06S | No matching file or commit found in inspected local worktree paths/refs | `SOURCE NOT FOUND`; do not claim review or port. Request the exact deliverable before any integration. |
| RacketVision / BallTrack | Present as research branches and current frozen research records. `BALLTRACK_V1_FROZEN_RAW`; current RacketVision tuning candidate is rejected. | Research model/checkpoint/output are not Cinema media facts. Keep metrics, source video identity, model/config version, and uncertainty together. No model was imported by this contract change. |
| Native media/resource policy | Native QA identity module and Resource Policy V2 are present in MAIN | Preserve per-commit WebView2 identity, isolated QA SQLite, 2.5 GiB heavy-work gate, existing media-distribution checks and formal-launcher boundary. |

The 2026-10-26 QA evidence under `qa/full-speed-evidence/RESULTS.json` reports 8/8 remote images decoded in an internal Founder QA build and separately marks official video playback `NOT_TESTED_THIS_RUN`. That is historical, internal-only evidence for its recorded commit—not permission, release status, or this candidate's GUI result.

## Official metadata status

GEX-05R remains the only approved technical `videos.list` chain: exact registered IDs → server-side transport → raw response schema → typed batch normalization → existing freshness helper → current per-source thumbnail and rights gates → existing `feedCatalog.ts` consumer. It can fetch `snippet`, plus reviewed batch fields `contentDetails` and `status`; absent fields remain unknown. The eight-ID fixture is `MOCK`. No live credentials were found/provided for this candidate; no API request, Cloud project, billing, key or new service endpoint was created. API expiration only expires/removes metadata; it must never delete a match, favorite, moment, Pro Lab note or Arena history.

## Controlled integration order

1. **Foundation contract (this candidate):** record shapes, exact identity/time rules, rights separation, integration tests, and local discovery-profile primitives. No database migration or visual redesign.
2. **GEX-05 live-read gate:** only after a reviewed, approved server API client and explicit Founder query approval; first one video, then the exact eight IDs. Validate publisher and event identity independently. Keep live API fields, thumbnails and permission separate.
3. **Growth shelf in original Cinema:** consume existing SQLite favorites plus local recent-open/progress by exact IDs; show “recently opened” separately from “actually played”; place below the 5cc wall and retain Founder QA/distributable separation.
4. **Moment/Rally/Point integration:** bridge only against media asset identity plus millisecond timestamps. External official iframe has no readable progress/seek and must stay external or standalone note mode.
5. **Arena:** keep simulated event sequence isolated. A real-match prediction/event integration requires a reviewed event ID and exact media timestamp source.
6. **PRO LAB Vision/Rally Coach/Motion Twin:** require input asset hash, source frames/times, model/config version, confidence status and human review. Never turn coverage into accuracy or inference into confirmed fact.
7. **Native upgrade:** explicit export/preview/confirmation/rollback only; no automatic cross-commit migration. Re-run isolated persistence and rights gates when a Native candidate is separately authorized.

## Rollback and remaining gates

All work is on `codex/ptti-one-foundation-gex05`, based on the reviewed MAIN candidate `3ec76c2…`. Roll back by checking out the prior candidate SHA or reverting the small foundation commit and the two ordered GEX-05 commits. MAIN, formal R4, Launcher, user DB, Favorites, Journal, media, and other worktrees are untouched. No merge, push, deploy, API call, Native build, or release action occurred.

Still pending: actual Founder GUI proof for this combined candidate; GEX-06S original delivery; live YouTube metadata; backend sidecar route into Cinema; Growth shelves in the rendered page; real full-match media; all formal thumbnail rights. Do not report these as passed.
