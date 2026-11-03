# GEX-05R: branch reconciliation and live readiness

Date: 2026-10-27. This work stays on `codex/gex05-youtube-metadata-poc`; no merge, cherry-pick, live query or release activation.

## Git findings

- Main: `54d75007eb7dc63e33dd8ac419afc20cf7e2615c`, clean at inspection.
- Original PoC: `70526f1f14ddc028670eb2eb548e70b1710a0042`, clean at inspection.
- Merge base is exactly Main. Left/right commit counts: `0 / 1`. PoC is a child extension, not a divergent competing implementation.
- The original PoC changed 10 files: `apps/youtube_data_api.py`, `frontend/package.json`, `tests/test_youtube_data_api.py`; added the output schema, PoC document, MOCK fixture, Node test, metadata module/declaration, and stdlib unittest module.

## Duplicates found and disposition

| Area | At original PoC | GEX-05R decision |
|---|---|---|
| Python requests | Single/snippet and batch/full metadata functions repeated request, decoding and error handling | Keep both public profiles; share one `_request_videos_list` implementation |
| Frontend adapter | Cinema runtime is used by `feedCatalog.ts`; PoC batch normalization is unconnected | Retain separate layers: batch data normalization, then existing Cinema runtime; no new adapter |
| Thumbnail selection | Two URL/dimension validators and selectors | Existing runtime exports the shared selector; PoC adds only aspect-ratio reporting |
| Freshness | Two implementations of the 30-day rule | Existing runtime owns the shared deadline/parser/classifier; PoC delegates |
| Cache | No actual persistent API cache in either branch | Keep in-memory freshness/failure handling only; no second cache store |
| Media permission | PoC had a second permissive grant/manifest check | Remove it; delegate to `resolveYoutubeThumbnail` and `resolveEditorialMatchPhoto` with existing manifest consistency checks |
| Types | Two response item definitions, with different field coverage | Runtime declaration owns common fields and types; PoC re-exports strict batch profile. Legacy optional snippet response remains compatible |
| Schema validation | Output test checked keys, not instances | Add raw-response schema and actual Python transport → Node normalizer → JSON Schema instance tests |

The formal gate, Founder QA mode, source catalog, existing image manifest and UI files are unchanged. No Mock record is eligible for API display. The existing manifest has zero approved distributable photos.

## Unique intended chain

Registered exact video IDs → reviewed server client configuration → shared `videos.list` transport → unchanged provider JSON → raw response contract validation → batch metadata records → shared freshness rule → existing per-source runtime with independently verified publisher identity → existing image permission resolver → `feedCatalog.ts` sidecar → Cinema card → existing official HTTPS watch link.

Implemented and tested in isolation: transport, raw field validation, normalized schema validation, freshness, runtime delegation, error handling and contract tests. Not connected yet: live API invocation, durable API cache, backend sidecar delivery into Cinema. These are explicit future integration steps, not current runtime capabilities.

## Request profiles and field origins

| Request / field | Origin and interpretation |
|---|---|
| `fetch_videos_list(id)` | Backward-compatible `part=snippet`; no status/duration claim |
| `fetch_videos_list_batch(ids)` | `part=snippet,contentDetails,status`, 1–50 exact unique IDs; pilot plan uses the eight registered IDs |
| `id`, title, channel ID/name, published date, thumbnails | `items[].id` and `items[].snippet`; original strings/URLs retained |
| duration | `items[].contentDetails.duration`, ISO duration string; absent is unknown |
| privacy status, embeddable | `items[].status`; absent is unknown. `embeddable` never becomes `embed_permission` |
| source ID, watch URL, match ID | Existing catalog identity only. Seven match IDs remain unknown |
| fetched time and deadline | Local response receipt time; shared 30-day maximum. Future/invalid timestamps fail closed |

Raw schema: `data/schemas/youtube-videos-list-response-0.1.schema.json`. Normalized schema remains `ptti.youtube-video-metadata-poc/0.1`. The only changes to the original single-source runtime are shared helper exports and stricter invalid timestamp rejection; its sidecar schema stays `YoutubeThumbnailRuntime/0.1`.

## Safe preflight and live status

Checked only configuration presence, never secret contents: the API key is absent from the current process and Windows User/Machine environment. No `.env`, `.env.local`, `products/ptti/.env`, or frontend `.env.local` exists at the inspected roots. Other private directories/credential stores were not searched. No reviewed executable client configuration was found. Only `PTTI_YOUTUBE_DATA_API_KEY` is supported as a credential environment input; client-review/scope/restriction fields are explicitly supplied by a reviewed server configuration, not inferred from environment variable names.

Run from `products/ptti`:

```powershell
python -m apps.youtube_data_api --check-config
python -m unittest tests.test_youtube_data_api_batch_unittest -v
```

The preflight sends no request and reports booleans and non-secret configuration status. A ready-shaped configuration is not proof of key validity, Cloud restrictions, account authority or permission.

Run from `products/ptti/frontend`:

```powershell
node scripts/test-youtube-video-metadata.mjs
node scripts/test-youtube-thumbnail-runtime.mjs
node scripts/test-video-feed.mjs
```

Contract tests require Node and the test-only dependency pinned in `tests/requirements-youtube-metadata.txt` (`jsonschema==4.26.0`, already present during this run); Feed/TypeScript require the existing locked frontend dependencies. No dependency installation was performed. No backend application import or database is needed by these API tests.

## Actual validation

- PASS: 11 Python unittest cases, including real Python transport code with an in-memory opener, Node normalization and actual JSON Schema instance validation. Wrong field types and malformed dates were rejected; no request reached Google.
- PASS: Node metadata mapping/contract/gate tests; existing single-source thumbnail runtime; Feed render/contracts; Story/favorites; six frontend favorite failure/reconciliation scenarios; media distribution gate; full TypeScript project check; `git diff --check`.
- PASS: protected visual, source catalog, manifest, favorite repository, Moment Cards, Pro Lab and Arena source files are unchanged from Main. The test verifies those files exist before comparing them.
- NOT_TESTED: browser visibility, real API identity/playback, Native and real SQLite restart. The frontend favorite tests are not a substitute for SQLite persistence. `pytest` is absent; no backend/database was imported to work around that limitation.
- NOT_RUN: Vite/Native builds; available RAM was 1.22 GiB during final checks. No new GUI capability was wired in this task.

## GEX-05R file ownership

| File | Change |
|---|---|
| `apps/youtube_data_api.py` | Shared transport, returned-ID rejection, secret-safe local preflight |
| `frontend/src/youtubeThumbnailRuntime.mjs` / `.d.mts` | Shared thumbnail/freshness/URL helpers and common response types; retain legacy snippet response typing |
| `frontend/src/youtubeVideoMetadata.mjs` / `.d.mts` | Raw-field validation; delegate selection, freshness and media permission; re-export shared batch types |
| `data/schemas/youtube-videos-list-response-0.1.schema.json` | Raw provider response contract; optional status/contentDetails fields stay optional |
| `frontend/scripts/test-youtube-video-metadata.mjs` | Gate bypass negatives, schema field types, expiry boundaries and invalid catalog identity |
| `tests/test_youtube_data_api_batch_unittest.py` | Python/Node/JSON Schema contract and exceptional response tests, legacy single-call compatibility, source integrity |
| `tests/requirements-youtube-metadata.txt` | Test-only schema-validator version |
| This document and `GEX-05-YOUTUBE-METADATA-POC.md` | Audit findings, corrected gate description, pending integration plan |

## Pending live proof and minimal approval

1. Founder must explicitly resume the paused API-client setup. Prefer a reviewed existing project if available; a new project is conditional, not assumed necessary. No billing/payment/trial enrollment.
2. Provide the key to the server process through an approved secret mechanism, restrict service scope to YouTube Data API v3 and application use to the real server egress. Do not paste a key into chat, put it in a browser/EXE, or use an unrestricted key to proceed.
3. Approve the public query scope: first `0QgbtsBWZhk`, then one batch containing `JTUWXpB-NVo`, `H77vNFk3neg`, `ekfCZiIEYi0`, `DTPNEl3-2b0`, `iQhVLkcGCFE`, `0QgbtsBWZhk`, `vYsJLPTEIaI`, `aFs7HJ0NX18`.
4. Validate raw response and exact IDs. Missing items remain `NOT_RETURNED`; duplicates/unexpected IDs fail closed. Independently confirm each channel identity and match relationship; do not derive those approvals from the API result itself or fill missing match IDs.
5. Complete the existing client disclosure/display review, then deliver an approved sidecar to the existing Cinema consumer in an isolated browser QA session. Preserve returned title, URLs and dimensions, YouTube attribution and the existing official external watch path.

Current real API identity proofs: `0/8`; real API thumbnail displays: `0/8`. Founder QA historical remote images are a different path. API thumbnails can become visible only after steps 1–5; a working key or a single successful query alone does not satisfy display readiness.

## Minimal merge plan (not executed)

Review Main → final PoC diff as one dependency-ordered change set: shared Python transport; shared runtime helpers/types; batch mapper/raw schema; contract tests and docs. Keep all UI, storage and catalog changes outside this change set. Reconfirm Main has not advanced, run targeted tests/TypeScript and a resource-permitted production build, then request explicit integration approval before any fast-forward/merge. Do not cherry-pick the original uncorrected PoC alone. If Main advances, re-evaluate the actual diff; do not overwrite it.

Rollback: Main is untouched and can continue at its existing SHA. This local branch can remain unintegrated; if later integrated, revert the reviewed change set without resetting user state. No data migration, image download, Native candidate or desktop activation was made. `scripts/dev_sync.py` is deliberately not run: it builds/activates desktop software outside this task's authorization.
