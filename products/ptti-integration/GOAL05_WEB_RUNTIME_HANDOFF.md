# GOAL 05 — San's exact Web runtime handoff

Base integration: `110a53447abe85a996e6038b1a808f8498281ea0`.
Web sample pin: `46f1826d80edf19147cc492e26c5461048841608`.
Only the Integration worktree was edited. No Web or Playback workspace edits.

## Executable entry points

```powershell
node products/ptti-integration/scripts/demo_web_runtime.mjs
node --test products/ptti-integration/runtime/tests/match-media-consumer.test.mjs
```

Browser/Vite consumption uses the same dependency-free runtime module:

```ts
import { consumeMatchMedia, resolveWebIds } from './runtime/match-media-consumer.mjs';
const response = await fetch('/data/web-internal-review.json');
if (!response.ok) throw new Error(`Catalog HTTP ${response.status}`);
const catalog = consumeMatchMedia(await response.json(), { view: 'internal-review' });
// idMap is the checked-in runtime/web-id-map.json .items array.
const ids = resolveWebIds(selectedWebRecordId, idMap, catalog);
const match = catalog.matches.find(row => row.match_id === ids.match_id);
const source = catalog.video_sources.find(row => row.source_id === ids.source_id);
```

This is an integration example, not a change made in San's app. Copy the
review JSON only into an authorized local/internal preview; public builds
use `web-strict-public.json` with `view: 'strict-public'`. Preserve the package
layout: runtime `.mjs` plus adjacent `.d.mts`, and `../contracts/match-media-v0.2.schema.json`.
The JSON import uses import attributes supported by the current Node/Vite
toolchain. The Node runner tests the actual consumer module; no browser GUI
or Vite/TypeScript build was run in this worktree (no installed compiler).

JSON paths: `generated/alpha-rc/web-internal-review.json` (4 matches/4 sources)
and `generated/alpha-rc/web-strict-public.json` (0/0). Internal file SHA-256:
`99446e0c41b39fac7bda87f3c5fe8176e987aca9ff501b00cab8d2d07ae4a5c8`.
Strict-public file SHA-256:
`61ad55ef42444dab0316fe2545aacbb4aa59667f053725e933d0917ca57e1873`.

## Exact ID map

| Existing Web id | Contract Match id | Contract Source id |
|---|---|---|
| doha-2023-ms-final | web-match:doha-2023-ms-final | web-source:doha-2023-ms-final |
| doha-2023-ms-sf-fan-lin | web-match:doha-2023-ms-sf-fan-lin | web-source:doha-2023-ms-sf-fan-lin |
| singapore-2021-ws-final-wang-sun | web-match:singapore-2021-ws-final-wang-sun | web-source:singapore-2021-ws-final-wang-sun |
| chongqing-2025-ws-final-sun-chen | web-match:chongqing-2025-ws-final-sun-chen | web-source:chongqing-2025-ws-final-sun-chen |

`runtime/web-id-map.json` stores this mapping and its input snapshot hash.
`resolveWebIds()` verifies IDs and the exact source->Match relationship; no
title, filename or URL inference. More than one source per Match remains
possible; a Web record chooses a specific mapped source.

## Fixed field meanings and missing handling

| Field | Meaning and safety behavior |
|---|---|
| `match_id`, `source_id`, `source.match_id` | Stable typed IDs and explicit relation. Duplicate IDs or dangling references reject the entire payload. `source.match_id: null` is unlinked, not a guessed match. |
| `match.identity_status` | Reviewed overall Match identity; all four are UNKNOWN. An event ID does not verify all participants or a source association. |
| `event.event_id` | Original provider event ID, scoped by provenance, not a global event UUID. Doha=2866, Singapore=2536, Chongqing=null. v0.2 has no separate event-identity status; do not infer VERIFIED. |
| `participants[].members[].player_id` | Stable identity only when actually supplied/reviewed. Four samples have `participants: []`, names in `participant_names_unassigned`; no side, doubles pair or player ID can be invented. |
| `source.match_link_status` | Evidence for this source belonging to this Match. All four UNKNOWN; the record linkage is a review scaffold, not a verified relationship. |
| `resource_kind`, `content_type`, `canonical_url` | Route kind, media form, exact official page URL are separate. Chongqing is `content_type: ARTICLE`, `resource_kind: UNKNOWN`; v0.2's route enum has no ARTICLE. Keep it evidence-only; do not insert a new enum or offer video playback. |
| `source.publisher` vs `evidence.external_video_page.publisher` | Two video samples already contain `World Table Tennis (verified YouTube channel)` in both fields, as supplied by the verified upstream evidence adapter. The Doha event-page and Chongqing article samples have null in both. A platform label must not fill a missing publisher; retain the existing verified values and keep the two concepts distinct. |
| `published_at`, `verified_at`, evidence `checked_at` | Publication time, metadata check time and actual observation time are distinct. Missing nullable values remain null; absent optional fields stay absent. |
| `rights.*`, `basis_urls`, `reviewed_at` | Seven independent rights. All current permissions UNKNOWN; facts/link/image/embed/analysis/training/redistribution are not interchangeable. Public listing needs listing+external-view ALLOWED; thumbnail has its own ALLOWED gate. |
| `territory.status`, `territories` | UNKNOWN/empty does not mean globally available. Retain restrictions and tested region without inference. |
| `evidence.page_access` | Page access only, not decoded media. |
| `evidence.external_video_page` | Two historical visual-pass snapshots, not fresh checks. Requires exact URL, changed frames, >=5 seconds, publisher/title/source facts, check time, and no observed barriers. Audio remains independent. |
| `evidence.embed_playback` | Actual permitted embedded-player evidence only; all NOT_TESTED. External visual pass cannot upgrade it. |
| `evidence.desktop_native_playback` | Native evidence only with build/media/package bindings; all four source records NOT_TESTED. User's separate Cinema confirmation remains in the Alpha ledger, not reassigned to official URLs. Vision analysis is not represented as a Web playback success. |

Required fields missing or enum values invalid cause explicit rejection;
the consumer does not invent defaults. v0.1, future or missing contract
versions are rejected without fallback. Local assets, private extra fields
and synthetic records are rejected at the Web boundary.

## Encoding clarification and remaining work

Read-back of the actual UTF-8 integration JSON finds zero U+FFFD characters.
The two results contain `4\u20130` (an en dash). No score was guessed or
rewritten. San should read/fetch JSON as UTF-8; corrupted input containing
U+FFFD is rejected with `INVALID_ENCODING` for source/decoder review.

San needs to wire the module into its local runtime and run its own
TypeScript/Vite/browser acceptance. Exact interfaces are documented in
`runtime/match-media-consumer.d.mts`; the shared JSON Schema remains the
validation authority. Native/rights Gates and Desktop deployment do not
change. No automatic fallback to the older MatchRecord fixture is allowed
when the v0.2 consumer rejects data.
