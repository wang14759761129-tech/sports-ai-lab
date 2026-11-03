# GOAL14 Playback watch-routing handoff

Contract: `ptti.watch-routing/0.1`, in `adapters/watchRoutingContract.ts`. It is a small routing/status adapter; the pinned browser Playback Core remains `304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe` and its `src/index.ts` is unchanged. The adapter never opens a link, extracts a stream, uploads local media, or automatically chooses a fallback.

## Route states

| Route | Required evidence before showing it as eligible | What eligibility means |
| --- | --- | --- |
| `OFFICIAL_EMBED` | Reviewed source reference, public-page or authorized viewing permission, `playbackType=OFFICIAL_EMBED`, `embedPermission=ALLOWED` | The official embed may be attempted. This does not prove it will play. |
| `OFFICIAL_PAGE` | Reviewed reference, `PUBLIC_PLATFORM_PAGE` or `AUTHORIZED`, `playbackType=OFFICIAL_PAGE` | The registered official page may be opened. Actual playback remains separately `NOT_TESTED` until observed. |
| `AUTHORIZED_SOURCE` | Reviewed reference, `AUTHORIZED`, `AUTHORIZED_STREAM`, verified rights evidence | A source represented as an authorized stream may be offered. Its provider still controls access. |
| `REPLAY` | Either a verified authorized on-demand source with rights evidence, or an available local file explicitly selected by the user with viewing confirmation | The authorized replay may be opened, or the selected local file may be played. Local media stays on the device. |
| `LIVE_SCORE` | Reviewed public/authorized score source and `LIVE_VERIFIED` state | Show score-only fallback; this is not video playback. |

`evaluateWatchRoute()` returns `ELIGIBLE`, `SCORE_ONLY`, or `BLOCKED`, plus `playbackEvidence` (`VERIFIED`, `NOT_TESTED`, or `FAILED`) and a stable reason code. Eligible routes should be shown as separate user choices; the adapter does not auto-redirect. Unknown or denied permission never qualifies. Page/viewing permission does not imply embed, download, analysis, or redistribution permission.

## Failure states

Use `classifyWatchFailure()` with structured evidence, not message-text guessing:

| Evidence | Stable code | User action |
| --- | --- | --- |
| HTTP 403 / 401 / 404 | `HTTP_FORBIDDEN` / `HTTP_UNAUTHORIZED` / `HTTP_NOT_FOUND` | Offer only independently eligible alternatives; reverify a missing source. These codes do not assert region restriction, login requirement, or link expiry. |
| Provider explicitly reports region/login/expired/embed-disabled/unavailable | `REGION_RESTRICTED` / `LOGIN_REQUIRED` / `LINK_EXPIRED` / `EMBED_DISABLED` / `SOURCE_UNAVAILABLE` | Respect platform restrictions. For embed-disabled, offer the official page only if that route independently qualifies. |
| Transport, local file, decoder, or user cancel | `NETWORK_ERROR` / `LOCAL_MEDIA_MISSING` / `MEDIA_DECODE_FAILED` / `USER_CANCELLED` | Retry or choose an eligible source, reselect the file, or stop. Decoder failure alone does not identify a codec or prove corruption. |

Cross-origin official pages often do not expose their HTTP response to the app. In that case use `UNKNOWN` until the provider reports a condition or the user observes it. Do not probe around login, region, 403, or platform controls.

## Ownership and San integration

San maps Main's verified source/permission fields to `WatchRouteCandidate`, evaluates each route, and renders only the eligible choices. San owns data freshness, user-facing navigation, external browser handoff, and retry UI. Playback Core owns local media, seek, queues, and resource release. Native R4 is a separate engine and is not covered by this adapter.

The adapter output intentionally omits URLs, filenames, paths, video hashes, session IDs, and notes. Runtime diagnostics should use the existing opt-in, bounded privacy-safe card. Add this module to San's isolated candidate and run an actual browser flow there before calling the experience accepted; this Playback worktree does not alter San or accepted 4174.

Focused check: from `products/ptti/frontend`, run `node scripts/test-watch-routing-contract.mjs`. The existing Core/browser/official-link tests remain separate evidence and must not be described as San GOAL14 browser acceptance.
