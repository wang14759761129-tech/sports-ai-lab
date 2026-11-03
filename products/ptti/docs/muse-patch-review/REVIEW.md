# GOAL113 Muse selective patch review

Target baseline: `02196f19980915a1ba5f10c244609a26de1564d3`.
Branch: `codex/goal99-r4-cinema-evolution`. Initial tree clean; no other active child agent was reported.
Original patch byte hashes: `PATCH-INPUTS.json`. Patches were inspected, not batch-applied.

## Decisions and source evidence

| Patch | Decision | Reason / resulting implementation |
| --- | --- | --- |
| 01 | Adjust | Keep `data-cover-state`, `data-cover-source`, and per-card fallback diagnosis in `VideoFeed.tsx`. Failure reason is a `data-cover-fallback-reason` attribute, not additional visible cover text. Preserve existing `onError` and per-card state. `FeedCoverFallback.tsx` is unchanged. |
| 02 backend | Reject | `Repository.ClosingConnection.__exit__` delegates to SQLite's transaction context and then closes. No extra `db.commit()` is needed. Committing before the verification SELECT would make a later SELECT failure return an error after an irreversible mutation. `test_favorite_select_failure_rolls_back_mutation` protects this boundary. |
| 02 frontend | Adapt | `favoritePersistence.mjs` re-reads once on a rejected, malformed, or lost mutation response. It never retries the write, keeps a visible error, and returns only server-confirmed snapshots. `VideoFeed.tsx` prevents concurrent toggles and uses a request epoch to ignore stale directory responses. Both card and Story buttons are disabled while the request is in flight. No refresh effect is triggered on failure, so it cannot erase the error. |
| 02 test | Replace | The supplied test asserts source text and favorite-key helpers. It cannot prove SQLite persistence. Added behavioral request tests and a real frontend helper -> loopback FastAPI -> isolated SQLite test, including failed DELETE and lost successful response. |
| 03 | Adapt | `source_metadata.py` uses one request time, a timezone-aware timestamp, and the original inclusive 30-day boundary. Future, malformed, naive, missing and expired timestamps are withheld separately. The API exposes counts only. A collapsed disclosure appears only when sources are withheld. No metadata timestamp, media permission, or existing source record is renewed. |

Patch-01's old blobs match the target (`VideoFeed` `8031b02`, fallback `6d677e6`).
Patch-02's backend old blob matches (`84d44c5`), but its frontend old blob `dfc68d6` requires Patch-01.
Patch-03 expects Patch-02's backend `051500e` and frontend `251f747`; it is not an independent patch.
No Muse temporary commit identity was imported.

## Scope and observed results

- No CSS, grid breakpoints, original fallback artwork, original source data, thumbnail admission, embedding admission or distribution manifest changed.
- `.cinema-shelf .feed-grid` remains four columns above 1150px, three at/below 1150px (then the existing tablet/mobile breakpoints).
- Before repair: four new API regressions failed; invalid/missing timestamps raised exceptions, and no withheld-reason response existed.
- Frontend favorite behavior: six scenarios passed, including one reconciliation GET, no repeated PUT, malformed response, lost response and partial multi-key cancellation.
- Final Python command: `python -m pytest tests/test_muse_patch_metadata.py tests/test_muse_favorite_http.py tests/test_match_video_library.py -k "metadata or favorite" -q --tb=short`. Result: **24 passed, 21 deselected, 78.98s**. One existing Starlette/httpx deprecation warning remains; no test was skipped to obtain this result.
- Real persistence test explicitly asserts its resolved database is under pytest's temporary directory. Backend imports occur only after temporary `PTTI_DB`, `PTTI_ENV=test` and isolated `LOCALAPPDATA` are set.
- The first HTTP test run exposed a test harness GBK/UTF-8 decoding error; its subprocess now explicitly reads UTF-8. This was not counted as a product PASS.
- Complete TypeScript (`tsc --noEmit --incremental false`) and `npm run build` passed. Vite: 662 modules, 4.72s. This is a frontend build, not a Windows EXE or deployment.
- Feed, Story/favorites, official theater, YouTube thumbnail, match-photo and media-distribution scripts passed.
- Built `dist` passed both Web and Windows-target media-tree checks, `approvedAssets=0`; no raster images were present. This does not claim a Windows package was built.
- Browser preflight at `2026-10-26T03:34:52Z`: available physical memory 1,367,199,744 bytes; measured-policy budget 1024 MiB; projected reserve 293,457,920 bytes, below the 512 MiB floor. Result `PROJECTED_PHYSICAL_RESERVE_TOO_LOW`. No browser was started or retried.
- Founder QA actual image requests, decoding, visibility, per-video LOADED/FALLBACK counts, and screenshots remain `NOT_TESTED`. All eight YouTube records remain unobserved in this run. Bilibili continues the existing fallback. No static test is labeled a browser PASS.

## Metadata follow-up

`METADATA-REVIEW-QUEUE.json` is internal review preparation, not refreshed metadata or public admission.
All eight current YouTube records reach the existing 30-day boundary on 2026-11-08, approximately 22:18-22:19 Asia/Shanghai. The Bilibili record is listed separately.

1. Open only each registered official URL in a supported browser; preserve a blocked result if platform access is denied.
2. Verify exact video ID, title, actual publisher/channel, event identity and page availability. Record observation time and evidence reference.
3. Record playback separately only if actually observed; keep region, embedding, thumbnail, download and redistribution rights independent.
4. Review a separate source-data diff before updating any `metadata_verified_at`; never renew it from title similarity, HTTP 200, or this queue alone. Google Cloud remains paused.

## Minimal Host acceptance, when resources allow

Use an independently named candidate and an explicit temporary QA database/isolated local-app-data directory before importing backend modules. Preserve installed R4 and formal entry points.

1. Card save -> verify the exact SQLite key -> Story cancel -> verify deletion -> reopen Story -> refresh -> inspect all three views. Keep an unrelated favorite throughout.
2. Repeat with legacy source key + exact match key. In a disposable QA database only, reject DELETE with the test trigger; the UI must retain an error and the server's actual state.
3. Run `npm run dev:founder-qa` against that isolated backend. For each of eight remote images, record request outcome, `naturalWidth`, successful `decode()`, visibility and the `data-cover-*` state; scroll for lazy-loaded cards and capture the actual Cinema wall. A failed card alone must fall back. Do not save image response bodies.
4. Normal production mode must still show no unapproved remote covers; 0Q remains blocked from embedding. Do not re-run robot verification or error 150.

Rollback: revert only the local selective-review commit in a clean isolated branch. No database migration or data rollback is needed; this change adds no table and rewrites no favorite records.
