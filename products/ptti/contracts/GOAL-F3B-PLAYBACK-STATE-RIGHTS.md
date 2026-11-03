# GOAL-F3B — Playback State and Rights Projection

Status: isolated code candidate based on F3A. No UI, browser, Native, or real-media acceptance is claimed.

## Source-of-truth decision

| Concern | Owner | Evidence and rule |
|---|---|---|
| Saved local resume position | Playback `localPlayback.mjs` at `a9824180a87eb3a4b424ca35db136809bd7b4a73` | Key `ptti.local-video-progress/1`; schema 1 entries keyed by `sha256-chunks-v1:<64 hex>`. Pro Lab reads after exact local-file content identification and writes on `timeupdate` (throttled to 5 seconds), seek, pause/end, page hide, and leaving the active view. Read validates a positive duration, stored duration within 0.5s, and position within bounds. Resume is suppressed after user interaction and at 0/end. |
| Discovery/profile activity | Foundation `personalDiscovery.mjs` | `ptti.personal-discovery/0.1` remains unchanged. Its historical `local_progress` shape is retained and validated so existing bytes survive. F3B disables new writes through the legacy progress writer and marks preserved rows `LEGACY_STORED_NOT_RESUMABLE`; it never uses these rows to resume. The shelf consumes only eligible Playback projections. |
| Actual player observation | PlaybackState record | Foundation v0.1 has no progress-position property and is closed to extra fields. Projection emits a valid PlaybackState with `observation: NOT_TESTED`, `observed_at: null`, `provider_embeddable: null`, and `embed_permission: UNKNOWN`. Saved milliseconds live only in the read-only adapter envelope. A saved position does not mean the player is loaded, playing, or authorized to embed. |
| Use-right evidence | Existing Foundation RightsEvidence record | Never manufactured. It must validate, bind to the exact local VideoAsset record and ID, use `LOCAL_PERSONAL_PLAYBACK_CONTINUATION`, match the WEB/NATIVE display surface, have verified or user-confirmed provenance and nonempty evidence references, and be unexpired. This does not grant provider embedding, download, redistribution, or analysis rights. |

## Projection API

`projectLocalPlaybackToFoundation({recordId, videoAsset, currentAvailability, currentDurationMs, progressSnapshot, rightsEvidence, target, now})` is pure and performs no storage access. A caller must obtain the snapshot from the existing `localPlayback.readProgress()` call and pass its exact hash identity. Snapshot status is `FOUND`, `EMPTY`, or `UNVERIFIABLE`; it must name the canonical Playback storage key. The function rejects remote-provider assets, Pro Lab metadata tuples, identity mismatches, missing media, duration drift over the existing 0.5 second tolerance, invalid/out-of-range history, unknown/expired/revoked rights, and unsupported targets.

The result separates:

- `playbackState`: Foundation v0.1 record; actual observation remains `NOT_TESTED`.
- `savedProgress.position_ms`: the stored position in the adapter view only.
- `continuation`: eligible only when media is available, position is strictly inside the duration, and matching current RightsEvidence permits the exact display surface/use case.

`buildGrowthShelf({playbackProjections})` is a read-only view of only those eligible projections. Legacy profile progress remains readable/preservable but never appears as resumable. No key migration or automatic cleanup occurs.

## Verification boundaries

- Automated tests use synthetic local assets and explicitly synthetic test evidence only.
- A one-command source integration test imports the exact Playback module from the supplied absolute path and uses in-memory storage; it never opens browser storage or user data.
- No browser, Native, live user storage, or actual playback was tested in this candidate.
- No Foundation schema/example protocol file was changed.
