# PTTI Web integration handoff — Sprint 0.6

Date: 2026-10-12

Web branch: `codex/ptti-web-mvp-v0-1`

Web HEAD at handoff: `843d54928bd6820b14fae572800e2dee6e6ae634`

## Contract comparison status

The read-only comparison used `ptti.match-media/0.1` at `C:\PTTI-Worktrees\integration-preview-sprint-0-1`, branch `codex/ptti-integration-preview-sprint-0-1`, local HEAD `c18e80e5d1daf79651099664556e7e2813f25ab2` (clean at inspection). This is the current committed integration snapshot, not a released/frozen production contract. No file in that worktree was edited.

The contract is a root object with required `contract_version`, `matches`, `video_sources`, `local_video_assets`, and `timeline_mappings`. The Web projection emits one match and one source per Web record; local assets and timeline mappings remain empty. The existing shared adapter owns this conversion; Web should supply source facts and preserve unknowns, without implementing another adapter.

## Web-to-contract mapping

| Web `MatchRecord` / evidence | `ptti.match-media/0.1` field | Mapping and current gap |
| --- | --- | --- |
| `id` | `match.match_id`, `video_source.source_id` | Adapter namespaces as `web-match:<id>` and `web-source:<id>`. |
| `event`, `eventYear`, `discipline`, `round`, `players`, `result` | `match.event.name/year`, `match.discipline`, `match.round`, `participant_names_unassigned`, `match.result` | Event category has no current contract field. The Web sample does not provide explicit side/member IDs; names remain unassigned rather than being invented into participant sides. |
| `event` identity / player identity | `match.identity_status`, `match.event.event_id`, participant `player_id` | Web has no `identityStatus`, explicit `eventId`, or stable player IDs. Adapter retains the event name/year, sets status to `UNKNOWN`, and leaves event/player IDs null. |
| `routeType` | `video_source.resource_kind` | `event-page` → `OFFICIAL_EVENT_PAGE`; `video-page` → `VIDEO_PAGE`; `source-only` → `UNKNOWN` conservatively. The current Web article/source-only sample is not explicitly typed as `ARTICLE`. |
| `platformUrl`, `videoOriginalUrl`, `sourceEvidence` | `video_source.canonical_url`, `provenance.source_urls` | Event route uses the event URL; video route uses its original video URL; source-only uses an evidence URL. All source URLs remain in provenance. |
| `platform` | `video_source.platform` | Direct text mapping; the current field is a platform label, not a verified publisher identity. |
| `sourceStatus` | `video_source.match_link_status` | **No direct mapping.** The shared adapter reads a separate `matchLinkStatus`, which Web does not have. `official-listing-found` is not automatically `VERIFIED` match identity; current output safely remains `UNKNOWN`. |
| `lastVerifiedAt` | `video_source.verified_at` | Direct date mapping. `published_at` is absent in Web and remains null. |
| `playbackStatus`, `playbackTested`, `playbackEvidence` | `evidence.external_video_page` | A qualifying Web `PLAYBACK_PASS` means only visual playback on the external official video page. Contract enum: `EXTERNAL_VIDEO_PAGE_VISUAL_PASS`. It does not populate embed, Desktop-native playback, or Vision evidence. |
| `embedAllowed` | `rights.embedding` | `true/false/null` maps to `ALLOWED/DENIED/UNKNOWN`. Permission is not evidence that an embed played. |
| Missing rights fields | `rights.metadata_listing`, `thumbnail_display`, `external_viewing`, `local_analysis`, `model_training`, `redistribution` | Remain `UNKNOWN`. No cover URL is supplied; the adapter includes a thumbnail only with explicit `thumbnailDisplayPermission: ALLOWED`. |
| `regionRestriction`, playback evidence `territory` | `video_source.territory` | Preserve `UNKNOWN`, empty territory list, and the Web text as notes. No country/region is inferred from a successful test-browser playback. |
| `sourceEvidence`, `note`, `lastVerifiedAt` | `provenance` | Source URLs and verification date are available. `recordedAt`, `reviewer_ref`, and evidence artifact references are absent and remain null/empty. |
| No Web local video or timeline fields | `local_video_assets`, `timeline_mappings` | Empty arrays. No local locator, media file, hash, database, or Vision result is exported. |

Contract-required fields include match/source IDs, identity and route states, provenance, rights decisions, territory status, and four separate evidence objects (`page_access`, `external_video_page`, `embed_playback`, `desktop_native_playback`). Evidence objects require a status and checked date; the date schema permits null. Fields such as event date, result, publisher, published date, thumbnail, permission basis/review date, territory notes, evidence URLs, and evidence details are optional or nullable. The current shared adapter supplies safe defaults for absent values; defaults must remain `UNKNOWN`, `NOT_TESTED`, null, or empty rather than implying permission or success.

Required structure, as written in the current schema draft:

- Root: `contract_version`, `matches`, `video_sources`, `local_video_assets`, `timeline_mappings`.
- Each `match`: `match_id`, `identity_status`, `event`, `discipline`, `round`, `participants`, `provenance`; `event` requires nullable `event_id`, `name`, and `year`. Participant objects require `side`, `identity_status`, and `members`; member objects require nullable `name` and `player_id`. Provenance requires `method`, `source_urls`, nullable `recorded_at`, and `review_status`.
- Each `video_source`: `source_id`, `match_id`, `match_link_status`, `resource_kind`, `platform`, `canonical_url`, nullable `publisher`, nullable `published_at`, `verified_at`, `discipline`, `content_type`, `rights`, `territory`, `evidence`, and `provenance`. Rights requires all seven permission decisions. Territory requires `status` and `territories`. Evidence requires all four evidence objects; each object requires `status` and nullable `checked_at`.
- Local-asset and timeline-mapping objects have required fields in the schema, but the Web projection must emit empty arrays and no local asset records.

Optional match fields are `match_date`, `participant_names_unassigned`, and `result`. Optional provenance fields are `reviewer_ref`, `evidence_refs`, and `notes`. Rights `basis_urls` and `reviewed_at`, territory `notes`, and the detailed evidence fields (URLs, timestamps, frames, hashes, notes) are optional or nullable. The schema sets `additionalProperties: false`; Web must not attach unrecognized fields to contract objects.

## Playback and rights meaning

Web `PLAYBACK_PASS` is gated locally on an official video-page route, exact final URL match, changed frames, at least five seconds of timeline progress, official publisher title, and no observed login/region/verification prompt. It is a visual observation in the specified test browser only. Audio output was not independently confirmed; PTTI embed permission and cross-region availability remain unknown. This cannot be labelled `EMBED_PLAYBACK_PASS` or `DESKTOP_NATIVE_PLAYBACK_PASS`.

The shared adapter at `c18e80e5d1daf79651099664556e7e2813f25ab2` accepts same-host final URLs and any positive timeline advancement (`last > first`) for external visual pass, with changed frames and a checked date. Web uses an exact URL match and a five-second minimum. Align this validation in the shared adapter before treating the two gates as equivalent. The contract has no dedicated audio-output field, and the current adapter leaves `notes` empty for a visual pass; preserve the audio uncertainty in notes or a future versioned field.

## Public, minimized four-record sample set

These samples contain public match/player names and official source URLs only. The projection omits test-device identifiers, account/contact data, local filesystem/database paths, media, thumbnails, feedback, and credentials.

| Web sample ID | Match / event | Source kind | Playback evidence | Public canonical source |
| --- | --- | --- | --- | --- |
| `doha-2023-ms-final` | Fan Zhendong vs Wang Chuqin · WTT Finals Men Doha 2023 | Official event page | `NOT_TESTED` | [WTT event page](https://www.worldtabletennis.com/eventInfo?eventId=2866&selectedTab=Overview&innerselectedTab=Completed&subEvt=MSINGLES) |
| `doha-2023-ms-sf-fan-lin` | Fan Zhendong vs Lin Gaoyuan · WTT Finals Men Doha 2023 | Official single-match video page | External visual `PASS` in prior specified browser; 0:02→1:01. Audio, embed rights and territory remain unknown. | [WTT official YouTube page](https://www.youtube.com/watch?v=qIXmFTzXcs0) |
| `singapore-2021-ws-final-wang-sun` | Wang Yidi vs Sun Yingsha · WTT Cup Finals Singapore 2021 | Official single-match video page | External visual `PASS` in prior specified browser; 0:02→0:20. Audio, embed rights and territory remain unknown. | [WTT official YouTube page](https://www.youtube.com/watch?v=XHGCGiAyKkc) |
| `chongqing-2025-ws-final-sun-chen` | Sun Yingsha vs Chen Xingtong · WTT Champions Chongqing 2025 | WTT article, evidence only | `NOT_TESTED`; no match-specific video URL | [WTT report](https://www.worldtabletennis.com/description?artId=4731) |

## Filter semantics and handoff gates

“已核验官方视频” and route types describe different dimensions. “无播放证据” intentionally overlaps event-page and source-only records: those sources have no playback evidence because no direct video route is established. The UI now states this in Chinese and English, and regression coverage asserts the overlap. It does not change the two verified-video records or their priority.

Before adapter integration, confirm and freeze the shared contract commit, align the external evidence threshold/URL check, decide how the Web route/source distinction and match-link relation should be represented, and preserve audio uncertainty. Founder acceptance **0**; external users **0**; Cloudflare deployment **not authorized**; cross-region video availability **not verified**; Windows native Vision **not verified**.
